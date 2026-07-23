"""Assembles the Q&A `StateGraph` (SPEC §5.19.2).

Only one action exists ("ask a question"), so unlike `learning_api.graph.build` there's
no `entry_action` dispatch - every turn enters at `resolve_role`. Three intents now pause
via `interrupt()` (`admin_escalation`/`calendar_action`, S14; `branch_locator_consent`,
S15) - resumed the same way learning-api's graph is, via `Command(resume=...)` on the
same thread id.
"""

from intellichoice_observability.tracing import traced_node
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from . import nodes
from .state import QAState


class AskInput(BaseModel):
    """`ainvoke` input for every turn - deliberately narrower than `QAState` so a
    repeat message on the same thread doesn't reset the role/branch resolved on a
    prior turn back to its schema default (same reasoning as `learning_api.graph.
    build.EntryInput`, D-019).
    """

    session_id: str
    query: str


QAGraph = CompiledStateGraph[QAState, nodes.TurnContext, AskInput, QAState]


def _route_after_scope_guard(state: QAState) -> str:
    if state.scope != "in_scope":
        return "refuse"
    if state.intent == "document_qa":
        return "answer_document_qa"
    if state.intent == "admin_contact":
        return "prepare_admin_escalation"
    if state.intent == "calendar":
        return "calendar_extract"
    if state.intent == "branch_locator":
        return "branch_locator_consent"
    return "unavailable_intent"


def _route_after_answer_document_qa(state: QAState) -> str:
    """SPEC §18-C3: an empty role-filtered retrieval routes to `explain_access` (the
    metadata-only access probe) instead of paying for an LLM synthesis call that has no
    chunks to work with anyway.
    """
    return "explain_access" if not state.retrieved_chunk_ids else "synthesize_answer"


def _route_after_prepare_admin_escalation(state: QAState) -> str:
    return "admin_escalation_blocked" if state.rate_limited else "admin_escalation"


def _route_after_calendar_extract(state: QAState) -> str:
    if state.calendar_event is not None:
        return "calendar_action"
    if state.event_listing:
        return "calendar_event_listing"
    return "calendar_no_event"


def build_graph(checkpointer: BaseCheckpointSaver) -> QAGraph:
    """Each node is wrapped in `traced_node` (SPEC §5.32.2's "LangGraph span") only at
    registration here, never by editing `nodes.py`'s bodies - mirrors `learning_api.
    graph.build.build_graph`'s same reasoning (D-021's replay-safety concerns apply to
    node bodies, not to a decorator that changes nothing about them).
    """
    graph = StateGraph(QAState, context_schema=nodes.TurnContext, input_schema=AskInput)
    graph.add_node("resolve_role", traced_node("langgraph.resolve_role")(nodes.resolve_role))
    graph.add_node("scope_guard", traced_node("langgraph.scope_guard")(nodes.scope_guard))
    graph.add_node("refuse", traced_node("langgraph.refuse")(nodes.refuse))
    graph.add_node(
        "unavailable_intent", traced_node("langgraph.unavailable_intent")(nodes.unavailable_intent)
    )
    graph.add_node(
        "answer_document_qa",
        traced_node("langgraph.answer_document_qa")(nodes.answer_document_qa),
    )
    graph.add_node(
        "synthesize_answer", traced_node("langgraph.synthesize_answer")(nodes.synthesize_answer)
    )
    graph.add_node("explain_access", traced_node("langgraph.explain_access")(nodes.explain_access))
    graph.add_node(
        "prepare_admin_escalation",
        traced_node("langgraph.prepare_admin_escalation")(nodes.prepare_admin_escalation),
    )
    graph.add_node(
        "admin_escalation_blocked",
        traced_node("langgraph.admin_escalation_blocked")(nodes.admin_escalation_blocked),
    )
    graph.add_node(
        "admin_escalation", traced_node("langgraph.admin_escalation")(nodes.admin_escalation)
    )
    graph.add_node(
        "calendar_extract", traced_node("langgraph.calendar_extract")(nodes.calendar_extract)
    )
    graph.add_node(
        "calendar_no_event", traced_node("langgraph.calendar_no_event")(nodes.calendar_no_event)
    )
    graph.add_node(
        "calendar_event_listing",
        traced_node("langgraph.calendar_event_listing")(nodes.calendar_event_listing),
    )
    graph.add_node(
        "calendar_action", traced_node("langgraph.calendar_action")(nodes.calendar_action)
    )
    graph.add_node(
        "branch_locator_consent",
        traced_node("langgraph.branch_locator_consent")(nodes.branch_locator_consent),
    )

    graph.add_edge(START, "resolve_role")
    graph.add_edge("resolve_role", "scope_guard")
    graph.add_conditional_edges(
        "scope_guard",
        _route_after_scope_guard,
        {
            "refuse": "refuse",
            "unavailable_intent": "unavailable_intent",
            "answer_document_qa": "answer_document_qa",
            "prepare_admin_escalation": "prepare_admin_escalation",
            "calendar_extract": "calendar_extract",
            "branch_locator_consent": "branch_locator_consent",
        },
    )
    graph.add_conditional_edges(
        "answer_document_qa",
        _route_after_answer_document_qa,
        {
            "synthesize_answer": "synthesize_answer",
            "explain_access": "explain_access",
        },
    )
    graph.add_conditional_edges(
        "prepare_admin_escalation",
        _route_after_prepare_admin_escalation,
        {
            "admin_escalation_blocked": "admin_escalation_blocked",
            "admin_escalation": "admin_escalation",
        },
    )
    graph.add_conditional_edges(
        "calendar_extract",
        _route_after_calendar_extract,
        {
            "calendar_action": "calendar_action",
            "calendar_event_listing": "calendar_event_listing",
            "calendar_no_event": "calendar_no_event",
        },
    )
    graph.add_edge("refuse", END)
    graph.add_edge("unavailable_intent", END)
    graph.add_edge("synthesize_answer", END)
    graph.add_edge("explain_access", END)
    graph.add_edge("admin_escalation_blocked", END)
    graph.add_edge("admin_escalation", END)
    graph.add_edge("calendar_no_event", END)
    graph.add_edge("calendar_event_listing", END)
    graph.add_edge("calendar_action", END)
    graph.add_edge("branch_locator_consent", END)

    return graph.compile(checkpointer=checkpointer)
