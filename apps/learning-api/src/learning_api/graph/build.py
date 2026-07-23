"""Assembles the Adaptive Learning `StateGraph` (SPEC §5.5.1).

One request maps to one `ainvoke` call: the caller sets `entry_action` on the input delta
to pick a single top-level entry node, that node (and any node it conditionally routes
to within the same turn) runs to `END` or to a paused `interrupt()`, and the checkpointer
persists the result either way. The next user action resumes the same thread - either a
fresh top-level entry, or (if the previous turn paused) a `Command(resume=...)` that
LangGraph routes directly to the paused task, bypassing `_route_entry` entirely. There is
no long-running execution to keep alive, mirroring the HTTP API's one-request-per-user-
action shape.
"""

from intellichoice_observability.tracing import traced_node
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from . import nodes
from .state import LearningState

ENTRY_NODES = (
    "select_student",
    "select_topic",
    "resolve_attendance",
    "submit_answer",
    "finalize_exam",
    "resume",
)


class EntryInput(BaseModel):
    """`ainvoke` input for every turn: just enough to pick this thread and its entry
    node. Deliberately narrower than `LearningState` - passing a full `LearningState`
    instance here would reset every other field to its schema default on each call
    instead of leaving the checkpointed values alone (only the keys present in the
    input update the corresponding state channels).
    """

    session_id: str
    entry_action: str


LearningGraph = CompiledStateGraph[LearningState, nodes.TurnContext, EntryInput, LearningState]


def _route_entry(state: LearningState) -> str:
    if state.entry_action not in ENTRY_NODES:
        raise ValueError(f"unknown or missing entry_action: {state.entry_action!r}")
    return state.entry_action


def _route_after_submit_answer(state: LearningState) -> str:
    """SPEC §5.11.3: an incorrect *study* answer pauses for the hint/solution/video choice
    before the turn ends; every other outcome (pre/post-exam, or a correct study answer,
    which `flow.advance_study` already ran inline) goes straight to `END`.

    The guard keys on `last_study_attempt_id`, not just `phase == "study"`: an incorrect
    *final pre-exam* answer transitions the phase to "study" (the study plan is built inline)
    while `last_is_correct` is still False, but it recorded no study attempt - so
    `last_study_attempt_id` is None and it must not be routed into `intervention_choice`
    (which asserts a study attempt exists). `submit_answer` sets `last_study_attempt_id`
    only for a study-phase submission.
    """
    if (
        state.phase == "study"
        and state.last_is_correct is False
        and state.last_study_attempt_id is not None
    ):
        return "intervention_choice"
    return "END"


def _route_after_intervention_choice(state: LearningState) -> str:
    """S21: a `"hint"` choice below the ladder's final level loops back to a fresh
    `intervention_choice` superstep instead of ending the turn - see that node's own
    docstring for why this is a graph-level self-loop rather than a node-internal
    `while` loop (D-021 gotcha #1's replay-duplication risk).
    """
    if state.hint_ladder_awaiting_choice:
        return "intervention_choice"
    return "END"


def _route_after_select_student(state: LearningState) -> str:
    """SPEC §5.6.1: a parent with 2+ linked children pauses for the actual selection in
    a dedicated node (see `resolve_student`'s docstring for why identity must commit
    first); every other role/case resolved fully within `resolve_student` itself.
    """
    if state.phase == "awaiting_child_selection":
        return "await_child_selection"
    return "END"


def build_graph(checkpointer: BaseCheckpointSaver) -> LearningGraph:
    """Each node is wrapped in `traced_node` (SPEC §5.32.2's "LangGraph span") only at
    registration here, never by editing the node function bodies in `nodes.py` - those
    bodies are exactly where D-021 documents two real interrupt/resume replay bugs, and
    a decorator that changes nothing about arguments, control flow, or return value
    carries none of that risk.
    """
    graph = StateGraph(LearningState, context_schema=nodes.TurnContext, input_schema=EntryInput)
    graph.add_node("select_student", traced_node("langgraph.select_student")(nodes.resolve_student))
    graph.add_node(
        "await_child_selection",
        traced_node("langgraph.await_child_selection")(nodes.await_child_selection),
    )
    graph.add_node("select_topic", traced_node("langgraph.select_topic")(nodes.select_topic))
    graph.add_node(
        "resolve_attendance", traced_node("langgraph.resolve_attendance")(nodes.resolve_attendance)
    )
    graph.add_node("submit_answer", traced_node("langgraph.submit_answer")(nodes.submit_answer))
    graph.add_node(
        "intervention_choice",
        traced_node("langgraph.intervention_choice")(nodes.intervention_choice),
    )
    graph.add_node("finalize_exam", traced_node("langgraph.finalize_exam")(nodes.finalize_exam))
    graph.add_node("resume", traced_node("langgraph.resume")(nodes.resume_view))

    graph.add_conditional_edges(START, _route_entry, {name: name for name in ENTRY_NODES})
    for name in ENTRY_NODES:
        if name not in ("submit_answer", "select_student"):
            graph.add_edge(name, END)
    graph.add_conditional_edges(
        "select_student",
        _route_after_select_student,
        {"await_child_selection": "await_child_selection", "END": END},
    )
    graph.add_edge("await_child_selection", END)
    graph.add_conditional_edges(
        "submit_answer",
        _route_after_submit_answer,
        {"intervention_choice": "intervention_choice", "END": END},
    )
    graph.add_conditional_edges(
        "intervention_choice",
        _route_after_intervention_choice,
        {"intervention_choice": "intervention_choice", "END": END},
    )

    return graph.compile(checkpointer=checkpointer)
