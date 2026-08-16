"""LangGraph node bodies for the Q&A workflow (SPEC §5.19.2).

Each node reads its runtime dependencies (repositories, the profile adapter, the
caller's claims, this turn's query) from `runtime.context` (a `TurnContext` built fresh
for every `ainvoke` call), rather than the checkpointed `QAState`, mirroring
`learning_api.graph.nodes`'s existing split - state holds ids and results, not live
connections (SPEC §5.19.3/§5.5.3).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

from intellichoice_adapters.ics import generate_ics
from intellichoice_db.models.interrupts import InterruptApproval
from intellichoice_db.repositories.interrupts import InterruptApprovalRepository
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.org import OrgEventRepository
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_knowledge import retrieval
from intellichoice_knowledge.retrieval import MIN_RERANK_RELEVANCE_SCORE, retrieve
from intellichoice_observability.metrics import (
    QA_ANSWERS,
    QA_CALENDAR_CALLS,
    QA_CITATIONS_PER_ANSWER,
    QA_CONVERSATION_COST_CENTS,
    QA_EMAIL_ESCALATIONS,
    QA_OUT_OF_SCOPE,
    QA_SERVICE_DEGRADED,
)
from intellichoice_observability.tracing import traced_span
from intellichoice_shared.access_probe_policy import ACCESS_PROBE_MAX_DISTANCE
from intellichoice_shared.auth import TokenClaims
from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    ScopeAndIntentPayload,
    ScopeAndIntentResponse,
)
from intellichoice_shared.calendar import CalendarEvent
from intellichoice_shared.email import EmailMessage
from intellichoice_shared.maps import GeocodeQuery
from intellichoice_shared.mcp import McpToolError, McpToolRegistry
from intellichoice_shared.profiles import ProfileAdapter
from intellichoice_shared.rate_limit import RateLimiter
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import ValidationError

from chat_api.services import admin_escalation as admin_escalation_service
from chat_api.services import branch_locator as branch_locator_service
from chat_api.services import calendar as calendar_service
from chat_api.services import calendar_events as calendar_events_service
from chat_api.services import outcomes, qa, role_access
from chat_api.services.branch_locator import BranchLocatorResult, BranchLocatorStatus
from chat_api.services.outcomes import ACCESS_REQUIRED_MESSAGE, TurnReason

from .state import QAState

logger = logging.getLogger(__name__)

# SPEC §5.19.4, and D-351 changed both the SPEC text and this one together rather than letting
# them drift - see `outcomes.OUT_OF_SCOPE_MESSAGE` for the measured case that prompted it.
OUT_OF_SCOPE_MESSAGE = outcomes.OUT_OF_SCOPE_MESSAGE

# SPEC §5.29's "user-safe error message", re-exported from `services.qa` - it moved down
# a layer in D-156 when AUD-C-19 needed it at the synthesis call site, and this module
# already imports `services.qa` (the dependency runs graph -> services, never back).
# `main.py`'s 503 handler still imports it from here.
SERVICE_UNAVAILABLE_MESSAGE = qa.SERVICE_UNAVAILABLE_MESSAGE

UNAVAILABLE_INTENT_MESSAGES = {
    "clarification": (
        "Could you rephrase your question? I can help with questions about the "
        "IntelliChoice organization, its programs, branches, schedules, volunteering, "
        "student participation and learning, parent information and tutor or branch "
        "procedures."
    ),
}

# Must cover every SPEC §5.19.4 supported topic. Questions about the organization
# itself ("What is IntelliChoice?") and student participation were classified against
# a list that omitted them (AUD-C-02); the mock provider can't catch that omission
# because "intellichoice" is in its own keyword list, so a static coverage test
# (test_scope_prompt_covers_spec_topics) guards this string instead.
#
# AUD-F-19 + AUD-C-02's verification leg: naming the intents was not enough - the
# definitions and examples below each pin a misroute measured live on real Bedrock
# (2026-07-28, post-C-16, fresh session per call):
#   "What are the Saturday hours?"                 -> branch_locator/location-consent
#                                                     modal or clarification, 0/6
#                                                     answered across S42+today
#   "What is IntelliChoice?"                       -> refused or clarification, 0/3
#                                                     answered WITH D-111's topic fix
#   "Tell me about the people who run IntelliChoice" -> admin_contact email flow, 3/3
# SPEC §5.19.2's diagram scopes Branch Locator to the Maps/proximity path, so a
# branch's hours/address without the user's location is document_qa. The mock cannot
# see any of this (it routes on its own keyword gate); the static guard is
# test_scope_prompt_defines_intents, behaviour is CHAT_EVAL_REAL_BEDROCK's paraphrase
# cases.
#
# D-221: the three paragraphs after the topic list, and the last three examples, each
# pin a failure measured by `scripts/measure_scope_guard.py` (2026-08-08, 76 cases x 2
# repeats, real Haiku 4.5). The model's own `reasoning` said why each time, and none of
# the three causes is a topic this prompt had *omitted* - which is what AUD-C-02 was:
#
#   1. It required the question to NAME IntelliChoice. "What do I need to put in my
#      monthly report for my manager?" -> "the user's personal workplace reporting to
#      their own manager"; "What happens if my kid is absent for a whole week?" ->
#      "asking about a child's regular school". Every example below named the
#      organization explicitly, so an unqualified first-person question read as being
#      about somewhere else entirely.
#   2. It did not know where branches meet. "Carrollton Public Library Keller Springs
#      Road Saturday hours" -> "a public library facility and not related to
#      IntelliChoice". Every non-online branch in `knowledge-content/documents/public/
#      branch-directory` is hosted inside a library, church or community center, and
#      nothing here said so. Three `grounded` cases - the class this prompt was tuned
#      against - were being refused on that gap alone.
#   3. `admin_contact` and `branch_locator` each swallowed a document_qa question the
#      definitions already excluded, and the model said so while doing it ("While it's
#      framed as a 'how do I' question... this is best handled as admin_contact"). A
#      definition the model argues itself past needs the counter-example, not more
#      emphasis.
#
# All three fixes are TOPICAL on purpose. Nothing here tells the model who is asking or
# what they may read - that is D-219's rule and CLAUDE.md #3, guarded by
# `test_the_scope_prompt_says_nothing_about_roles_or_access`. "Read 'my students' as
# IntelliChoice's" is a statement about the subject of the question, not about the
# asker's permissions, and the gated corpus is still filtered pre-retrieval by
# `role_access_filter` exactly as before.
SCOPE_AND_INTENT_SYSTEM_PROMPT = (
    "Classify whether this question is in scope for IntelliChoice's "
    "organizational Q&A assistant (the IntelliChoice organization itself, "
    "branches, schedules, volunteering, student participation and learning, "
    "parent information, tutor/branch procedures, the academic calendar, and "
    "learning-app support). Any question about what IntelliChoice is, who runs "
    "it, what it offers, or how to take part is in scope.\n"
    "Questions come from people already taking part in IntelliChoice, so a "
    "question does not have to name the organization to be about it: read 'my "
    "child', 'my students', 'my manager', 'my report', 'a session' and 'the "
    "program' as IntelliChoice's unless the question names a different "
    "organization. What to do about a missed session, a student asking for "
    "help, or a report that is due is in scope.\n"
    "IntelliChoice branches meet inside public libraries, churches and "
    "community centers, so a question naming a library, an address or a city "
    "alongside hours, a schedule or a location is asking about a branch. A "
    "bare keyword phrase is still a question.\n"
    "If in scope, also classify which workflow intent it needs:\n"
    "- document_qa: answerable from organizational documents - the organization "
    "itself, its programs, enrollment and participation, branch hours, "
    "schedules, addresses, fees, policies, and the people who lead or run it.\n"
    "- branch_locator: ONLY finding or comparing branches by distance from the "
    "user's own location ('nearest branch', 'branches near me'). A question "
    "about a branch's hours, schedule, address, or programs that does not need "
    "the user's location is document_qa, and a city or area named in the "
    "question is not the user's location.\n"
    "- calendar: adding an organizational event to the user's calendar, or "
    "listing upcoming scheduled events.\n"
    "- admin_contact: ONLY an explicit request to send a message to, or be put "
    "in contact with, a person or administrator. Questions about people, or "
    "how-do-I questions, are document_qa - including how to fix, correct or "
    "resolve something, even when the answer may end in contacting someone.\n"
    "- clarification: in scope but too vague to route. Use it only when the "
    "topic itself is unclear, never because a question is casual, "
    "first-person, or written as keywords.\n"
    "Examples: 'What is IntelliChoice?' -> in_scope, document_qa. 'Tell me "
    "about the people who run IntelliChoice' -> in_scope, document_qa. 'What "
    "are the Saturday hours?' -> in_scope, document_qa. 'Which branch is "
    "closest to me?' -> in_scope, branch_locator. 'Please send a message to an "
    "administrator' -> in_scope, admin_contact. 'What should I tell a student "
    "to do first when they ask me for help?' -> in_scope, document_qa. "
    "'Carrollton Public Library Saturday hours' -> in_scope, document_qa. 'My "
    "kid got marked absent by mistake - how do I fix that?' -> in_scope, "
    "document_qa."
)

# AUD-C-27: "from this session" was wrong, and the probe that found the cap's real ceiling
# is what showed it - every attempt used a *fresh* session and the block still arrived,
# because the key is the caller (external id, else client IP), never the session. A message
# that misdescribes its own scope tells a blocked caller that opening a new chat will help.
RATE_LIMITED_MESSAGE = (
    "Too many escalation requests recently - please try again later, or contact your "
    "branch manager directly."
)
EMAIL_SENT_MESSAGE = "Your message has been sent to an administrator."
EMAIL_DECLINED_MESSAGE = "Okay, the message was not sent."
# SPEC §5.29 "Gmail MCP failure -> Preserve draft".
EMAIL_FAILED_MESSAGE = (
    "The message could not be sent right now. Please try again in a few minutes, or "
    "contact your branch manager directly."
)
NO_EVENT_FOUND_MESSAGE = (
    "I couldn't find a specific dated event to add - try asking about it directly "
    "first, then ask me to add it to your calendar."
)
NO_UPCOMING_EVENTS_MESSAGE = "There are no upcoming events currently scheduled."
UPCOMING_EVENTS_HEADER = "Here's what's coming up:"
CALENDAR_CANCELLED_MESSAGE = "Okay, nothing was added to your calendar."
CALENDAR_ICS_MESSAGE = "Here's a downloadable calendar file for this event."
CALENDAR_GOOGLE_MESSAGE = "Added to your Google Calendar."
# SPEC §5.29 "Google Calendar failure -> Generate .ics".
CALENDAR_GOOGLE_FAILED_FALLBACK_MESSAGE = (
    "Google Calendar wasn't available right now, so here's a downloadable calendar "
    "file for this event instead."
)
# SPEC §5.1.3 verbatim.
LOCATION_CONSENT_NOTICE = (
    "Your location will be used only to calculate nearby IntelliChoice branches.\n"
    "IntelliChoice will not permanently store your precise location."
)
LOCATION_DECLINED_MESSAGE = (
    "Okay, your location was not used. You can also ask about a specific branch by name."
)
# SPEC §5.22 "Location denied: ZIP or city input" - also covers "approved but no location
# came through" (e.g. the browser's own geolocation prompt was denied at the OS level).
LOCATION_MISSING_MESSAGE = (
    "I didn't receive a location. Please share a ZIP code, city, or address so I can "
    "find your nearest branch."
)


@dataclass(frozen=True)
class TurnContext:
    claims: TokenClaims | None
    profile_adapter: ProfileAdapter
    rag_repo: RagRepository
    bedrock_gateway: BedrockGateway
    interrupt_repo: InterruptApprovalRepository
    mcp_registry: McpToolRegistry
    mcp_call_repo: McpToolCallRepository
    org_event_repo: OrgEventRepository
    rate_limiter: RateLimiter
    admin_escalation_email: str
    query: str | None = None
    candidate_limit: int = 30
    top_k: int = 8
    confidence_threshold: float = 0.4
    # AUD-C-20/D-165, raised by AUD-C-21/D-166: cosine-distance ceiling for the §18-C3 access
    # probe's semantic arm. Defined once in `intellichoice_shared.access_probe_policy`, which
    # carries the measurement - including why 0.50 is not taken.
    access_probe_max_distance: float = ACCESS_PROBE_MAX_DISTANCE
    # AUD-C-12/D-172: SPEC §5.21.8's retrieval-score do-not-answer trigger, applied by
    # `retrieve`. Defined once in `intellichoice_knowledge.retrieval`, which carries the sweep.
    min_relevance_score: float = MIN_RERANK_RELEVANCE_SCORE
    client_ip: str | None = None


def _degraded(stage: str, exc: BedrockGatewayError, state: QAState) -> dict:
    """The state update every AUD-C-07/AUD-C-08 fallback returns: mark the turn degraded
    so its router sends it to `service_unavailable`, count it under its own metric, and
    still settle whatever the failed call cost (a call that failed after being billed is
    exactly the kind of spend a budget must not lose track of).

    One helper rather than three copies, because the failure is the same event at three
    call sites and an operator correlating a spike wants one log name to grep for.
    """
    QA_SERVICE_DEGRADED.labels(stage=stage).inc()
    logger.warning(
        "qa_service_degraded",
        extra={
            "stage": stage,
            "reason": type(exc).__name__,
            "detail": str(exc),
            "cost_cents": exc.cost_cents,
        },
    )
    return {
        "service_degraded": True,
        "bedrock_spend_cents": state.bedrock_spend_cents + exc.cost_cents,
    }


def _ctx(runtime: Runtime[TurnContext]) -> TurnContext:
    assert isinstance(runtime.context, TurnContext)
    return runtime.context


async def resolve_role(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §5.19.2 "Detect authentication -> Resolve role". Anonymous is a valid,
    first-class case here (unlike `learning_api`) - `ctx.claims` may be `None`.
    """
    ctx = _ctx(runtime)
    assert ctx.query is not None
    user_role, branch_external_id = await role_access.resolve_role_context(
        ctx.claims, ctx.profile_adapter
    )
    # AUD-C-01's second half (S40, D-107). This wrote `None` for an anonymous turn, so an
    # anonymous message on an owned thread did not merely go unchecked - it *erased the
    # owner*, permanently disabling the checks `/respond` and `/stream` do perform against
    # this exact field. One unauthenticated request downgraded a tutor's session to
    # ownerless for good. The route now refuses that request, and the state never drops an
    # owner it already has, so neither half depends on the other being correct.
    owner = ctx.claims.sub if ctx.claims is not None else state.user_external_id
    cleared: dict = {
        "user_external_id": owner,
        "authenticated": ctx.claims is not None,
        "user_role": user_role,
        "branch_external_id": branch_external_id,
        "query": ctx.query,
        "standalone_query": ctx.query,
        # AUD-C-04 (S40, D-107): clear last turn's result here, at the one node every
        # turn passes through first.
        #
        # A node that pauses on `interrupt()` never returns, so it never writes these
        # fields - and `/messages` builds its response by reading them straight off the
        # result. A paused turn therefore answered with the *previous* turn's answer,
        # citations and access hint, which is what made AUD-C-01 a disclosure rather than
        # just a missing check: the anonymous caller was handed the tutor's answer because
        # it was still sitting in state. `ics_content` was worse - nothing anywhere
        # cleared it, so a calendar download stuck to every later turn in the session.
        #
        # Resetting on entry rather than in each pausing node is the point: there are
        # several pausing nodes and the next one added would have to remember.
        "answer": None,
        # D-351: the reason code is a per-turn result like everything else here, and would
        # otherwise outlive the turn that produced it - the same AUD-C-04 class this block
        # exists for.
        "reason": None,
        "citations": None,
        "confidence": None,
        "missing_information": None,
        "escalation_recommended": False,
        "access_hint": None,
        "ics_content": None,
        "retrieved_chunk_ids": None,
        "event_listing": None,
        # AUD-C-07/AUD-C-08: same reasoning, one turn later. A `service_degraded` left
        # set by a failed turn would answer "temporarily unavailable" on this thread
        # forever, long after Bedrock recovered.
        "service_degraded": False,
        # AUD-C-06/D-164: and again for the access-probe flag. Left set, it would send
        # every later turn on this thread through the probe after synthesis, including
        # turns that answered perfectly well.
        "no_source_refusal": False,
    }
    if state.escalate:
        # D-164. `scope_guard` is the only node that writes `scope`/`intent`, and the
        # escalate path skips it - so without these two lines the response would carry the
        # *previous* turn's classification, which is exactly the stale-state-in-a-response
        # shape AUD-C-04 was. `intent` is the truth (the caller declared it and the server
        # acted on it); `scope` stays None because no classification happened, matching
        # `scope_guard`'s own degraded branch rather than asserting "in_scope" on no
        # evidence.
        cleared["scope"] = None
        cleared["intent"] = "admin_contact"
    return cleared


async def scope_guard(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §5.19.2 Scope Guard + Intent Router, one combined `BedrockTask.
    SCOPE_AND_INTENT` call (see `intellichoice_shared.bedrock.ScopeAndIntentResponse`'s
    docstring for why they're one call, not two).
    """
    ctx = _ctx(runtime)
    assert state.standalone_query is not None
    try:
        result = await ctx.bedrock_gateway.generate_structured(
            task=BedrockTask.SCOPE_AND_INTENT,
            system_prompt=SCOPE_AND_INTENT_SYSTEM_PROMPT,
            # D-219: `user_role` deliberately not passed - see `ScopeAndIntentPayload`.
            payload=ScopeAndIntentPayload(standalone_query=state.standalone_query),
            response_model=ScopeAndIntentResponse,
            max_output_tokens=512,
            session_spend_cents=state.bedrock_spend_cents,
        )
    except BedrockGatewayError as exc:
        # No SPEC §5.29-named fallback for this call, so the turn still fails closed
        # (CLAUDE.md #5): nothing is answered, and no intent runs. What changed in
        # Phase 0B is only what the user is told. This used to return
        # `scope="out_of_scope"`, which routed to `refuse` and told a user asking a
        # perfectly in-scope question that it was an unrelated general-purpose one
        # (AUD-C-08) - and did so identically to a genuine refusal, so neither the user
        # nor an operator could tell an outage from a policy decision.
        #
        # `scope` stays `None` on purpose: no classification happened, so claiming one
        # would be the same false statement moved into a different field.
        return {"scope": None, "intent": None, **_degraded("scope_guard", exc, state)}

    return {
        "scope": "in_scope" if result.value.in_scope else "out_of_scope",
        "intent": result.value.intent,
        "bedrock_spend_cents": state.bedrock_spend_cents + result.cost_cents,
    }


async def refuse(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    del state, runtime
    QA_OUT_OF_SCOPE.inc()
    return {
        "answer": OUT_OF_SCOPE_MESSAGE,
        "reason": TurnReason.OUT_OF_SCOPE,
        "citations": [],
        "confidence": None,
        "missing_information": None,
        "escalation_recommended": False,
        "access_hint": None,
    }


async def service_unavailable(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """AUD-C-07/AUD-C-08: the turn could not be completed for a reason that has nothing
    to do with what was asked. Reached only when an upstream node set `service_degraded`
    after a `BedrockGatewayError` it could not fall back from.

    This is still fail-closed - no answer, no citations, no intent side effects - so it
    is a sibling of `refuse`, not an escape from it. The difference is honesty: `refuse`
    makes a claim about the user's *question*, and nothing is known about the question
    here.
    """
    del state, runtime
    return {
        "answer": SERVICE_UNAVAILABLE_MESSAGE,
        "reason": TurnReason.SYSTEM_ERROR,
        "citations": [],
        "confidence": None,
        "missing_information": None,
        # Escalating to a human is the *right* advice when we cannot answer, but the
        # escalation path is itself a Bedrock-and-MCP path, so recommending it during an
        # outage sends the user into a second failure. The message says what to do.
        "escalation_recommended": False,
        "access_hint": None,
    }


async def unavailable_intent(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """Any in-scope intent not handled by a real node below (currently just
    `clarification`, an otherwise-unclassified in-scope query) gets a clear message
    instead of guessing or silently misrouting it into document QA. `admin_contact`/
    `calendar` are handled by `admin_escalation`/`calendar_action` (S14);
    `branch_locator` by `branch_locator_consent` (S15).
    """
    del runtime
    message = UNAVAILABLE_INTENT_MESSAGES.get(
        state.intent or "clarification", UNAVAILABLE_INTENT_MESSAGES["clarification"]
    )
    return {
        "answer": message,
        # An in-scope intent with no handler is the assistant needing more from the caller,
        # not a refusal about the question - `clarification` is literally the default here.
        "reason": TurnReason.NEEDS_CLARIFICATION,
        "citations": [],
        "confidence": None,
        "missing_information": None,
        "escalation_recommended": False,
        "access_hint": None,
    }


async def answer_document_qa(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §5.21.3-§5.21.7: role-filtered hybrid search + rerank. Retrieval only - split
    from synthesis (`synthesize_answer`) so an empty result can route to `explain_access`
    (SPEC §18-C3) instead of paying for an LLM synthesis call that would just produce the
    generic no-source message anyway.
    """
    ctx = _ctx(runtime)
    assert state.standalone_query is not None
    filters = role_access.role_access_filter(state.user_role, state.branch_external_id)
    try:
        retrieval = await retrieve(
            ctx.rag_repo,
            ctx.bedrock_gateway,
            query=state.standalone_query,
            filters=filters,
            session_spend_cents=state.bedrock_spend_cents,
            candidate_limit=ctx.candidate_limit,
            top_k=ctx.top_k,
            min_relevance_score=ctx.min_relevance_score,
        )
    except BedrockGatewayError as exc:
        # AUD-C-07. `retrieve()` already degrades gracefully when the *reranker* fails
        # (it keeps the RRF order), but the query embedding has no such fallback - with
        # no query vector there is no hybrid search to run - and this was the one
        # uncaught gateway call in chat-api, so it surfaced as an unhandled 500.
        #
        # Routing to `service_unavailable` instead of to the empty-retrieval path
        # matters: an empty retrieval means "nothing in the corpus matches you", which
        # would send this to `explain_access` and answer with a no-source refusal or an
        # access hint. Both are statements about the corpus, and the corpus was never
        # searched.
        return _degraded("document_qa_retrieval", exc, state)

    return {
        "retrieved_chunk_ids": [chunk.chunk_id for chunk in retrieval.chunks],
        "bedrock_spend_cents": state.bedrock_spend_cents + retrieval.cost_cents,
    }


def _reason_for_qa_answer(answer: str) -> TurnReason:
    """Which `TurnReason` a `qa.answer_question` result represents.

    Keyed on the message `qa` returned rather than re-deriving the outcome from citations and
    confidence, because `qa` has already made that decision and a second classification here
    could disagree with it - which is precisely the AUD-C-19 shape (one message, three
    causes) inverted into three reasons for one message.
    """
    if answer == outcomes.SYSTEM_ERROR_MESSAGE:
        return TurnReason.SYSTEM_ERROR
    if answer == outcomes.SOURCES_CONFLICT_MESSAGE:
        return TurnReason.SOURCES_CONFLICT
    if answer == outcomes.NO_APPROVED_SOURCE_MESSAGE:
        return TurnReason.NO_APPROVED_SOURCE
    return TurnReason.ANSWER


async def synthesize_answer(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §5.21.8: citation-grounded synthesis + verification, over the chunks
    `answer_document_qa` already retrieved (re-loaded by id - `QAState` checkpoints ids
    only, never full chunk bodies, mirroring `retrieved_chunk_ids`'s own docstring).
    Only reached when retrieval was non-empty (see `_route_after_answer_document_qa`).
    """
    ctx = _ctx(runtime)
    assert state.standalone_query is not None
    chunk_ids = state.retrieved_chunk_ids or []
    chunks_by_id = await ctx.rag_repo.get_chunks_by_ids(chunk_ids)
    chunks = [chunks_by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in chunks_by_id]

    grounded, answer_cost = await qa.answer_question(
        ctx.rag_repo,
        ctx.bedrock_gateway,
        query=state.standalone_query,
        user_role=state.user_role,
        chunks=chunks,
        session_spend_cents=state.bedrock_spend_cents,
        confidence_threshold=ctx.confidence_threshold,
    )

    no_source_refusal = qa.is_no_source_refusal(grounded)

    # AUD-C-06/D-164: `explain_access` counts the `no_answer` outcome itself, so counting
    # it here too would double every refusal that routes onward - the one real bug this
    # widening introduces. The turn is counted exactly once, by whichever node ends it.
    # `QA_CITATIONS_PER_ANSWER` and `QA_CONVERSATION_COST_CENTS` stay unconditional: the
    # synthesis call happened and cost money whatever the router does next, and
    # `explain_access` observes neither.
    if not no_source_refusal:
        QA_ANSWERS.labels(result="grounded" if grounded.citations else "no_answer").inc()
    QA_CITATIONS_PER_ANSWER.observe(len(grounded.citations))
    total_spend_cents = state.bedrock_spend_cents + answer_cost
    QA_CONVERSATION_COST_CENTS.observe(total_spend_cents)
    return {
        "answer": grounded.answer,
        # D-351: `qa.answer_question` already decided which of the three outcomes this is;
        # the mapping is by the message it returned rather than a second classification, so
        # the reason and the words cannot disagree.
        "reason": _reason_for_qa_answer(grounded.answer),
        "citations": [citation.model_dump() for citation in grounded.citations],
        "confidence": grounded.confidence,
        "missing_information": grounded.missing_information,
        "escalation_recommended": grounded.escalation_recommended,
        "access_hint": None,
        "bedrock_spend_cents": total_spend_cents,
        "no_source_refusal": no_source_refusal,
    }


async def explain_access(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §18-C3's access-aware refusal.

    Reached whenever this turn is about to tell the user there is no approved source -
    either because role-filtered retrieval came back completely empty
    (`answer_document_qa`), or because retrieval found chunks and synthesis still refused
    on them (`synthesize_answer`, via `QAState.no_source_refusal`).

    **The second entry path is AUD-C-06's fix, and it is the one that made the feature
    reachable at all (D-164).** Zero-row retrieval was the only precondition until then,
    and real hybrid search over a non-trivial corpus essentially never returns zero rows:
    measured against a real model the feature fired **0 times in 8**, including for a
    parent asking a question the seeded parent handbook answers verbatim. Retrieval handed
    synthesis 8 chunks - all public, because the pre-retrieval filter had correctly
    withheld the gated ones - so retrieval was non-empty, routing went straight to
    `synthesize_answer`, and the parent was told "I don't have an approved source" about a
    document that exists. The precondition is now the *outcome* (a no-source refusal)
    rather than a lexical property of retrieval (an empty list).

    Only that one refusal routes here; see `qa.is_no_source_refusal` for why a conflict
    refusal and a service-unavailable result must not.

    Runs one probe (`intellichoice_knowledge.retrieval.probe_access`) with the branch
    restriction lifted and the audience allowlist inverted, so a role- or branch-gated match
    anywhere still surfaces; `role_access.build_access_hint` turns the audience it names into
    a fixed, backend-authored message. If the probe finds nothing either, this is a genuine
    no-answer, same message `qa.answer_question` would have produced for empty chunks.

    **The model's part in this, stated precisely (D-168/AUD-C-22).** The probe reranks
    candidate passages and the *code* maps the winning passage's `audience` to a fixed
    message. The model never sees a role, never proposes one, and cannot change what the user
    is allowed to read - authorization is the pre-retrieval filter above, untouched. What
    changed is that "which tier holds the answer" is now decided by relevance rather than by a
    hardcoded tier order that, live, told a parent to log in as a branch manager.
    """
    ctx = _ctx(runtime)
    assert state.standalone_query is not None
    base_filters = role_access.role_access_filter(state.user_role, state.branch_external_id)
    probe_filters = base_filters.model_copy(
        update={
            "restrict_to_branch": False,
            "branch_external_id": None,
            # `audiences` (the allowlist) is dropped and replaced by its inverse: the reranked
            # probe ranks a *pool*, so a public chunk left in the pool would take a slot from
            # the gated chunk the probe exists to find. The count-based fallback tolerated
            # public rows because `build_access_hint` discards them afterwards; a top-10
            # cannot afford them.
            "audiences": None,
            "exclude_audiences": base_filters.audiences,
        }
    )

    # AUD-C-20/D-165: the probe needs a semantic signal, because keyword matching ANDs every
    # content word of the question and a caller does not use the document's vocabulary
    # (measured: 3 of 43 vs 25 of 43). The embedding is taken here rather than threaded down
    # from `answer_document_qa` deliberately - `QAState` is checkpointed, and 1024 floats per
    # turn in every checkpoint is a real cost to avoid a call that costs a fraction of a cent.
    #
    # **It must not raise.** This node runs *because* the turn already failed to answer; a
    # gateway error here would turn a working refusal into a 500. Degrading to keyword-only
    # returns the pre-D-165 behaviour, which is worse but honest, and the spend is still
    # accounted for either way.
    probe_embedding: list[float] | None = None
    probe_cost = 0.0
    try:
        embedding_result = await ctx.bedrock_gateway.create_embedding(
            texts=[state.standalone_query], session_spend_cents=state.bedrock_spend_cents
        )
        probe_embedding = embedding_result.vectors[0]
        probe_cost = embedding_result.cost_cents
    except BedrockGatewayError as exc:
        logger.warning(
            "access_probe_embedding_unavailable",
            extra={"reason": type(exc).__name__, "detail": str(exc), "cost_cents": exc.cost_cents},
        )
        probe_cost = exc.cost_cents

    probe = await retrieval.probe_access(
        ctx.rag_repo,
        ctx.bedrock_gateway,
        query=state.standalone_query,
        probe_filters=probe_filters,
        query_embedding=probe_embedding,
        session_spend_cents=state.bedrock_spend_cents + probe_cost,
        max_distance=ctx.access_probe_max_distance,
    )
    hint = role_access.build_access_hint(state.user_role, probe.matches)
    QA_ANSWERS.labels(result="no_answer").inc()
    spend = state.bedrock_spend_cents + probe_cost + probe.cost_cents

    if hint is None:
        # Reached from `synthesize_answer` this is an idempotent rewrite of what that node
        # already wrote (AUD-C-11 leaves a no-source refusal with no citations, so the
        # empty list below overwrites an empty list) - stated explicitly because the
        # alternative reading is that the probe *erases* citations, and it must not: the
        # branch that could have had them does not route here.
        return {
            "answer": qa.NO_SOURCE_MESSAGE,
            "reason": TurnReason.NO_APPROVED_SOURCE,
            "citations": [],
            "confidence": 0.0,
            "missing_information": "No verifiable, non-conflicting source supports an answer.",
            "escalation_recommended": True,
            "access_hint": None,
            "bedrock_spend_cents": spend,
        }

    # D-351: the selected tier is **logged, not shown**. `build_access_hint` still picks a
    # specific audience - it is the number D-351's instrument measures, and throwing it away
    # would make the probe unobservable - but the caller now reads one generic sentence.
    # Two reasons, one measured and one structural, both in `outcomes.ACCESS_REQUIRED_MESSAGE`.
    logger.info(
        "access_hint_offered",
        extra={"required_role": hint.required_role, "user_role": state.user_role},
    )
    return {
        "answer": ACCESS_REQUIRED_MESSAGE,
        "reason": TurnReason.ACCESS_REQUIRED,
        "citations": [],
        "confidence": None,
        "missing_information": None,
        "escalation_recommended": False,
        # `required_role` stays in *state* and is dropped at the API boundary, rather than
        # never being written. The distinction matters: it is what
        # `qa_coverage_runner`'s `role_gated` cases score, and it is how AUD-C-22's
        # wrong-tier selection was caught at all. Removing it from state would have made
        # the probe unmeasurable in exchange for a disclosure the response model already
        # closes (`AccessHintResponse` carries `message` only).
        "access_hint": {
            "required_role": hint.required_role,
            "message": ACCESS_REQUIRED_MESSAGE,
        },
        "bedrock_spend_cents": spend,
    }


def _caller_external_id(ctx: TurnContext) -> str | None:
    return ctx.claims.sub if ctx.claims is not None else None


async def prepare_admin_escalation(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §5.24.2 rate limiting + §5.24.1 deterministic draft-building (no LLM call -
    see `admin_escalation_service.build_escalation_draft`'s own docstring) - both split
    into their own completed node, not inline before `admin_escalation`'s
    `interrupt()`, for two independent reasons that happen to point at the same fix:

    1. A resume replays `admin_escalation`'s body from the top (D-021) - rate-limiting
       there would re-consume a slot on every approve/decline, and the draft would be
       silently rebuilt each time (harmless since it's deterministic, but wasteful).
    2. More importantly: a node that pauses via `interrupt()` never actually *returns*
       until it's resumed, so nothing it computes before the pause reaches checkpointed
       state - the `/respond` pending-interrupt preview (built from `state.email_draft`,
       not the live `interrupt()` payload) would see nothing to show. Building the
       draft here, in a node that completes normally *before* the pause, is what makes
       it visible to a caller previewing the pending approval.

    Mirrors `learning_api`'s `resolve_student`/`await_child_selection` split (commit
    state before the pause, do only the pause itself in the paused node).
    """
    ctx = _ctx(runtime)
    key = _caller_external_id(ctx) or ctx.client_ip or "anonymous"
    if not await ctx.rate_limiter.allow(key):
        return {"rate_limited": True}

    assert state.standalone_query is not None
    draft = admin_escalation_service.build_escalation_draft(
        query=state.standalone_query,
        missing_information=state.missing_information,
        user_role=state.user_role,
        chat_session_id=state.session_id,
        # D-219: this node is reached both from an explicit "contact an administrator"
        # request and from a turn that could not be answered. Only the second is a failure,
        # and the draft says which.
        #
        # D-221: read off `state.escalate`, the flag the *request* carried, rather than
        # `state.intent == "admin_contact"`, which is what a model decided.
        #
        # The intent test was wrong twice over, and the second way is the one that matters.
        # It was wrong when the classifier was: "My kid got marked absent by mistake - how
        # do I fix that?" routed here on staging, and the draft told an administrator the
        # user had asked for contact. But it was *also* true on the escalate path, because
        # `resolve_role` sets `intent = "admin_contact"` there (D-164, and correctly - the
        # caller did declare that intent). So the discriminator returned the same value on
        # both branches, and D-219's "asked a question the assistant could not answer"
        # opening became unreachable through the graph the moment it was written: every
        # escalation email, including one raised from a no-source refusal, told the
        # administrator the user had asked to be put in touch. Its three unit tests all
        # passed - each one calls `build_escalation_draft` directly with the boolean it
        # wants, so none of them could see the node choosing that boolean wrongly.
        #
        # Positive-signal form on purpose: this says "a user did this" only when a user
        # action is on record, and every other route into this node - including any added
        # later - falls to `assistant_routed`, which claims nothing about the user.
        origin="user_escalated" if state.escalate else "assistant_routed",
    )
    return {"rate_limited": False, "email_draft": draft.model_dump()}


async def admin_escalation_blocked(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    del state, runtime
    return {
        "answer": RATE_LIMITED_MESSAGE,
        "reason": TurnReason.POLICY_RESTRICTED,
        "citations": [],
        "confidence": None,
        "missing_information": None,
        "escalation_recommended": False,
        "access_hint": None,
    }


async def admin_escalation(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """Only the pause + resolve - `state.email_draft` is already committed by
    `prepare_admin_escalation`, which ran to completion before this node ever started.
    """
    ctx = _ctx(runtime)
    assert state.email_draft is not None
    draft = state.email_draft

    decision = interrupt({"type": "email_approval"})
    approved = bool(decision.get("approved")) if isinstance(decision, dict) else False
    caller_external_id = _caller_external_id(ctx)

    if approved:
        try:
            with traced_span("mcp.gmail.send_email"):
                await ctx.mcp_registry.call(
                    "gmail.send_email",
                    EmailMessage(
                        recipient=ctx.admin_escalation_email,
                        subject=draft.subject,
                        body=draft.body,
                    ).model_dump(),
                    caller_external_id=caller_external_id,
                    audit_repo=ctx.mcp_call_repo,
                )
            message = EMAIL_SENT_MESSAGE
            QA_EMAIL_ESCALATIONS.inc()
        except McpToolError:
            # SPEC §5.29 "Gmail MCP failure -> Preserve draft" - the approval itself is
            # still recorded below; the failed *send* is a separate fact captured by
            # the `mcp_tool_calls` audit row's `success=False`.
            message = EMAIL_FAILED_MESSAGE
    else:
        message = EMAIL_DECLINED_MESSAGE

    await ctx.interrupt_repo.record(
        InterruptApproval(
            session_id=state.session_id,
            source_app="chat",
            interrupt_type="email_approval",
            decision="approved" if approved else "cancelled",
            decided_by_external_id=caller_external_id,
        )
    )

    return {
        "answer": message,
        # The escalation resolved: an email was sent, declined, or failed to send. All
        # three are outcomes of a *human* decision rather than of the assistant's knowledge.
        "reason": TurnReason.HUMAN_ACTION_REQUIRED,
        "citations": [],
        "confidence": None,
        "missing_information": None,
        "escalation_recommended": False,
        "access_hint": None,
    }


async def calendar_extract(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §5.23 rewired for S18 (plan §18-C2): the structured `org_events` table is
    tried first, deterministically (no LLM, no retrieval) - only when nothing there
    confidently matches does this fall back to the pre-S18 RAG+LLM chunk extraction
    (`calendar_service.extract_calendar_event`), unchanged, for calendar content not yet
    migrated into the structured table. Split into its own completed node, not inline
    before `calendar_action`'s `interrupt()`, so a resume never re-runs a real Bedrock
    call or re-does retrieval (same D-021 split rationale as `prepare_admin_escalation`
    above) - that rationale now also covers never re-running the deterministic lookup.
    """
    ctx = _ctx(runtime)
    assert state.standalone_query is not None
    filters = role_access.role_access_filter(state.user_role, state.branch_external_id)
    now = datetime.now(UTC)
    events = await ctx.org_event_repo.list_events(
        audiences=filters.audiences or [role_access.PUBLIC_AUDIENCE]
    )

    match = calendar_events_service.find_event_by_keywords(events, state.standalone_query, now=now)
    if match is not None:
        event = calendar_events_service.to_calendar_event(match)
        return {"calendar_event": event.model_dump(mode="json"), "event_listing": None}

    try:
        retrieval = await retrieve(
            ctx.rag_repo,
            ctx.bedrock_gateway,
            query=state.standalone_query,
            filters=filters,
            session_spend_cents=state.bedrock_spend_cents,
            candidate_limit=ctx.candidate_limit,
            top_k=ctx.top_k,
            min_relevance_score=ctx.min_relevance_score,
        )
    except BedrockGatewayError as exc:
        # AUD-C-07's second call site, reached only when the deterministic `org_events`
        # lookup above found nothing - the RAG fallback for calendar content not yet
        # migrated into the structured table. Guarding only `answer_document_qa` would
        # have left the same unhandled 500 one calendar question away.
        return _degraded("calendar_retrieval", exc, state)

    spend = state.bedrock_spend_cents + retrieval.cost_cents

    event, extraction_cost = await calendar_service.extract_calendar_event(
        ctx.rag_repo,
        ctx.bedrock_gateway,
        query=state.standalone_query,
        chunks=retrieval.chunks,
        as_of_date=date.today().isoformat(),
        session_spend_cents=spend,
    )
    spend += extraction_cost

    if event is not None:
        return {
            "calendar_event": event.model_dump(mode="json"),
            "event_listing": None,
            "bedrock_spend_cents": spend,
        }

    # Nothing matched a specific event either way - a generic "what's coming up" style
    # question is answered directly from the structured table (SPEC §5.23.1's
    # "information request", no LLM, no interrupt) whenever anything is upcoming.
    upcoming = calendar_events_service.list_upcoming_events(events, now=now)
    listing = (
        [
            {
                "title": c.event.title,
                "starts_at": (c.next_occurrence or c.event.starts_at).isoformat(),
                "location": c.event.location,
            }
            for c in upcoming
        ]
        if upcoming
        else None
    )

    return {
        "calendar_event": None,
        "event_listing": listing,
        "bedrock_spend_cents": spend,
    }


async def calendar_event_listing(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    del runtime
    assert state.event_listing is not None
    lines = [UPCOMING_EVENTS_HEADER, ""]
    for item in state.event_listing:
        location = f" ({item['location']})" if item.get("location") else ""
        lines.append(f"- {item['title']} - {item['starts_at']}{location}")
    return {
        "answer": "\n".join(lines),
        "reason": TurnReason.ANSWER,
        "citations": [],
        "confidence": None,
        "missing_information": None,
        "escalation_recommended": False,
        "access_hint": None,
    }


async def calendar_no_event(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """Reached when neither the structured lookup nor the RAG+LLM fallback found a
    specific event, and nothing at all is upcoming (an empty `event_listing` routes
    here too, see `_route_after_calendar_extract`) - distinguishes "there's real event
    history, just nothing upcoming right now" (S18's real data: the org's own public
    calendar is entirely historical, see DECISIONS.md) from "no event data exists at
    all," which is closer to the pre-S18 message's own meaning.
    """
    ctx = _ctx(runtime)
    filters = role_access.role_access_filter(state.user_role, state.branch_external_id)
    audiences = filters.audiences or [role_access.PUBLIC_AUDIENCE]
    has_event_history = bool(await ctx.org_event_repo.list_events(audiences=audiences))
    message = NO_UPCOMING_EVENTS_MESSAGE if has_event_history else NO_EVENT_FOUND_MESSAGE
    return {
        "answer": message,
        # Nothing scheduled is a real, correct answer from the org calendar; "I could not
        # find a dated event to add" is the assistant asking for a better question.
        "reason": (
            TurnReason.ANSWER if message == NO_UPCOMING_EVENTS_MESSAGE
            else TurnReason.NEEDS_CLARIFICATION
        ),
        "citations": [],
        "confidence": None,
        "missing_information": None,
        "escalation_recommended": False,
        "access_hint": None,
    }


async def calendar_action(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """Only the pause + resolve - `state.calendar_event` is already committed by
    `calendar_extract`, which ran to completion before this node ever started, so
    nothing expensive re-runs on a resume's replay.
    """
    ctx = _ctx(runtime)
    assert state.calendar_event is not None
    event = CalendarEvent.model_validate(state.calendar_event)

    choice = interrupt({"type": "calendar_action"})
    choice_value = choice.get("choice") if isinstance(choice, dict) else None
    if choice_value not in ("google", "ics", "cancel"):
        choice_value = "cancel"

    caller_external_id = _caller_external_id(ctx)
    ics_content: str | None = None

    if choice_value == "cancel":
        message = CALENDAR_CANCELLED_MESSAGE
    elif choice_value == "ics":
        ics_content = generate_ics(event)
        message = CALENDAR_ICS_MESSAGE
    else:  # "google"
        try:
            with traced_span("mcp.calendar.create_event"):
                await ctx.mcp_registry.call(
                    "calendar.create_event",
                    event.model_dump(mode="json"),
                    caller_external_id=caller_external_id,
                    audit_repo=ctx.mcp_call_repo,
                )
            message = CALENDAR_GOOGLE_MESSAGE
            QA_CALENDAR_CALLS.labels(result="success").inc()
        except McpToolError:
            # SPEC §5.29 "Google Calendar failure -> Generate .ics".
            ics_content = generate_ics(event)
            message = CALENDAR_GOOGLE_FAILED_FALLBACK_MESSAGE
            QA_CALENDAR_CALLS.labels(result="failure").inc()

    await ctx.interrupt_repo.record(
        InterruptApproval(
            session_id=state.session_id,
            source_app="chat",
            interrupt_type="calendar_action",
            decision=choice_value,
            decided_by_external_id=caller_external_id,
        )
    )

    return {
        "answer": message,
        # Added to Google, downloaded as .ics, or cancelled - each is the result of the
        # caller's own choice at the approval dialog.
        "reason": TurnReason.HUMAN_ACTION_REQUIRED,
        "citations": [],
        "confidence": None,
        "missing_information": None,
        "escalation_recommended": False,
        "access_hint": None,
        "ics_content": ics_content,
    }


_KM_PER_MILE = 1.609344


def _format_drive_time(minutes: float) -> str:
    """D-219: "about 918 min drive" is a true number nobody can read.

    Measured on staging 2026-08-08 against the seeded branches. Under an hour stays in
    minutes, which is the common case for a real "nearest branch" result; beyond that it
    becomes hours, because the figure is there to be judged at a glance.
    """
    rounded = round(minutes)
    if rounded < 60:
        return f"{rounded} min"
    hours, remainder = divmod(rounded, 60)
    if remainder == 0:
        return f"{hours} hr"
    return f"{hours} hr {remainder} min"


def _format_branch_locator_answer(result: BranchLocatorResult) -> str:
    if result.status == BranchLocatorStatus.MAPS_UNAVAILABLE:
        lines = ["Distance lookup isn't available right now - here are all branch addresses:"]
        lines += [f"- {b.name}: {b.address}" for b in result.branches]
        return "\n".join(lines)
    if result.status == BranchLocatorStatus.LOCATION_NOT_FOUND:
        return LOCATION_MISSING_MESSAGE

    lines = ["Branches nearest to you:"]
    for b in result.branches:
        if b.distance_km is None:
            lines.append(f"- {b.name}: {b.address}")
            continue
        estimate_note = " (estimated straight-line distance)" if b.is_estimate else ""
        duration = (
            f", about {_format_drive_time(b.duration_minutes)} drive"
            if b.duration_minutes is not None
            else ""
        )
        # D-219: miles, not kilometres. IntelliChoice is a Dallas, TX organization and its
        # audience is US families; the internal figure stays metric (`distance_km`, what the
        # Maps route and `haversine_km` both return) and only the user-facing string converts.
        miles = b.distance_km / _KM_PER_MILE
        lines.append(
            f"- {b.name}: {miles:.1f} miles away{duration}{estimate_note} - {b.address}"
        )
    return "\n".join(lines)


async def branch_locator_consent(state: QAState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §5.1.3/§5.1.4: explicit approval before using the caller's location, shown
    *before* any location is even collected (mirrors the real UX - a browser only asks
    for geolocation permission after this notice). The location itself (ZIP/city/
    address/precise coordinates) travels only in the `interrupt()` resume value the
    caller supplies on approval, never through `TurnContext`/`QAState` - a resumed node
    replays this function from the top (D-021), and `TurnContext` isn't guaranteed to
    carry this turn's original payload across that replay, so reading location off
    `ctx` here would either see stale data or None. Keeping it out of every
    checkpointed field is also what SPEC §5.1.3 asks for ("do not store precise
    coordinates in PostgreSQL, ... or application logs") - see docs/DECISIONS.md for the
    one residual caveat this can't fully eliminate (LangGraph's own checkpointer
    briefly holds the resume value for crash-safety).
    """
    ctx = _ctx(runtime)
    decision = interrupt({"type": "location_consent", "notice": LOCATION_CONSENT_NOTICE})
    caller_external_id = _caller_external_id(ctx)
    approved = isinstance(decision, dict) and bool(decision.get("approved"))

    await ctx.interrupt_repo.record(
        InterruptApproval(
            session_id=state.session_id,
            source_app="chat",
            interrupt_type="location_consent",
            decision="approved" if approved else "cancelled",
            decided_by_external_id=caller_external_id,
        )
    )

    if not approved:
        return {
            "answer": LOCATION_DECLINED_MESSAGE,
            "reason": TurnReason.POLICY_RESTRICTED,
            "citations": [],
            "confidence": None,
            "missing_information": None,
            "escalation_recommended": False,
            "access_hint": None,
        }

    assert isinstance(decision, dict)
    try:
        location = GeocodeQuery.model_validate(
            {
                k: decision.get(k)
                for k in ("zip_code", "city", "address", "latitude", "longitude")
            }
        )
    except ValidationError:
        return {
            "answer": LOCATION_MISSING_MESSAGE,
            "reason": TurnReason.NEEDS_CLARIFICATION,
            "citations": [],
            "confidence": None,
            "missing_information": None,
            "escalation_recommended": False,
            "access_hint": None,
        }

    result = await branch_locator_service.find_nearest_branches(
        profile_adapter=ctx.profile_adapter,
        mcp_registry=ctx.mcp_registry,
        mcp_call_repo=ctx.mcp_call_repo,
        location=location,
        caller_external_id=caller_external_id,
    )

    return {
        "answer": _format_branch_locator_answer(result),
        "reason": TurnReason.ANSWER,
        "citations": [],
        "confidence": None,
        "missing_information": None,
        "escalation_recommended": False,
        "access_hint": None,
    }
