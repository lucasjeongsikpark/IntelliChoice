"""Bedrock Gateway (SPEC §5.25.1) and structured-output schemas (§5.11.4-5.11.5, §5.25.3,
§5.8.3).

`generate_structured` and `create_embedding` are defined on `BedrockGateway` - SPEC's
interface also lists `generate_stream`/`classify`/`analyze_image`, but none has a real
caller yet (S18/S29 respectively; S29 was deferred, D-078). Each is added when its first
caller lands, matching this project's existing "don't stub ahead of time" convention
(see `learning_api.graph.state.LearningState`'s own docstring). See D-022.
`create_embedding` was added in S12 for RAG ingestion - see D-035. SPEC's separate
`judge` method never got its own Protocol method either - `BedrockTask.LLM_JUDGE`
(reserved since S8, unused until S30) is dispatched through the same `generate_structured`
call every other task uses, the same "classify"-shaped tasks (`SCOPE_AND_INTENT`,
`LEARNING_CHAT_INTENT`) already do instead of a dedicated `classify()` method.

`generate_structured`'s `payload` parameter is typed as the general `BaseModel`, not a
single hardcoded request type - S8 originally hardcoded `BedrockTutorPayload` since it
was the only caller, but S9's question-generation pipeline needs several more
task-specific payload types below. Each one is still its own `extra="forbid"` model with
an exact field list, matching D-023's PII/scope-floor pattern - the generalization only
loosens *which* strict model a given call uses, not the "no ad-hoc dict payloads" rule.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict


class BedrockTask(StrEnum):
    """SPEC §5.25.2 task table. Only `TUTOR` has a configured model this session - the
    others are named now so the model registry's keys are stable as later sessions add
    callers, not because logic exists for them yet.
    """

    SCOPE_AND_INTENT = "scope_and_intent"
    TOPIC_MAPPING = "topic_mapping"
    TUTOR = "tutor"
    HINT_PERSONALIZATION = "hint_personalization"
    LEARNING_CHAT_INTENT = "learning_chat_intent"
    TUTOR_CHAT = "tutor_chat"
    QUESTION_GENERATION = "question_generation"
    QUESTION_REVIEW = "question_review"
    AUTHORED_QUESTION_GENERATION = "authored_question_generation"
    QUESTION_JUDGE = "question_judge"
    PARENT_REPORT = "parent_report"
    RAG_ANSWER = "rag_answer"
    RERANK = "rerank"
    VLM = "vlm"
    LLM_JUDGE = "llm_judge"
    EMBEDDING = "embedding"
    CALENDAR_EXTRACTION = "calendar_extraction"
    VIDEO_CLASSIFICATION = "video_classification"
    MEMORY_CONSOLIDATION = "memory_consolidation"
    STAGE_NARRATIVE = "stage_narrative"


class TutorContext(BaseModel):
    """SPEC §5.11.4 TutorContext - the full domain context assembled for a hint/solution
    generation, built by `learning_api.services.topic_resolver`. Not the wire payload
    sent to Bedrock - see `BedrockTutorPayload` for the PII-floor-restricted subset that
    actually crosses the gateway (D-023).
    """

    grade: str
    estimated_level: str
    topic: str
    skill: str
    question: str
    selected_wrong_answer: str
    common_error_tag: str | None = None
    previous_hints: list[str] = []


class BedrockTutorPayload(BaseModel):
    """SPEC §5.30.1 minimum-necessary-data list, verbatim - the only fields ever allowed
    to cross the Bedrock gateway for a tutor-task call. `extra="forbid"` plus the exact
    field set makes this independently testable the same way D-011's PII schema-purity
    test works for Postgres columns. `TutorContext.common_error_tag`/`previous_hints` are
    deliberately NOT included - SPEC §5.30.1 doesn't list them, so they stay local to
    fallback-content selection rather than being sent to the model (D-023).
    """

    model_config = ConfigDict(extra="forbid")

    grade: str
    current_topic: str
    skill: str
    estimated_level: str
    question: str
    selected_answer: str
    relevant_learning_fact: str | None = None


class HintResponse(BaseModel):
    """SPEC §5.11.4 HintResponse."""

    hint_text: str
    concept_reminder: str
    next_step_prompt: str
    answer_revealed: bool = False
    difficulty: int


class SolutionStep(BaseModel):
    """One step of SPEC §5.11.5 SolutionResponse."""

    step_number: int
    explanation: str
    expression: str
    common_mistake: str | None = None


class SolutionResponse(BaseModel):
    """SPEC §5.11.5 SolutionResponse, as an ordered list of steps plus the overall final
    answer (SPEC gives one step's field list; a full solution is a sequence of these -
    see D-023's note on this schema's shape).
    """

    steps: list[SolutionStep]
    final_answer: str


# --- SPEC §5.11.4/§5.30.1 personalized hint ladder (S21, plan §18-L2) --------------
#
# A second, narrower Bedrock task alongside TUTOR: rewrites one canonical hint-ladder
# level (hand-authored for shape templates, S20's stored `hint_ladder` for authored
# ones - never invented) using context TUTOR's payload doesn't carry. This is a *new*
# payload model, not a widened `BedrockTutorPayload`, per D-023's narrowest-field-
# list-per-task rule - TUTOR's single-shot hint/solution calls still don't get this
# context. The widened allowlist (attempt count, hint level, misconception tag,
# prior-hint summaries, plus the canonical text itself so there is something to
# rewrite) is a deliberate, explicitly-approved SPEC §5.30.1 extension for this task
# only - see DECISIONS.md. No free text and no identifying fields cross this payload
# either; `relevant_learning_fact` (S25, plan §9) is the student's top-confidence
# `active` semantic-memory fact for the current skill, resolved by `graph/nodes.py` via
# `MemoryRepository.top_fact_for_skill` - never a raw DB row, same "code resolves,
# model only receives text" split as everywhere else.


class HintPersonalizationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grade: str
    skill: str
    question: str
    selected_answer: str
    canonical_hint_text: str
    misconception_tag: str | None = None
    attempt_count: int
    hint_level: int
    previous_hint_summaries: list[str] = []
    relevant_learning_fact: str | None = None


class HintPersonalizationResponse(BaseModel):
    """Sibling of `HintResponse`, not a subclass - subclassing would change
    `HintResponse`'s own `json_schema["title"]` and break `MockBedrockProvider`'s
    title-based dispatch; a distinct type also gives the mock provider its own
    misconception/level-aware canned branch (see `mock_provider.py`) instead of the
    plain `HintResponse` one, so ladder-escalation tests see genuinely different text
    per level without needing a bespoke scripted gateway for every case. `hint_level`/
    `is_final_level` are deliberately NOT response fields - the caller already knows
    which level it requested and whether it's the ladder's last one before making this
    call, so trusting the model to echo them back would duplicate code-owned state
    (same "model proposes content, code decides facts" split as `LlmCitation`/
    `RerankResponse` elsewhere in this file).
    """

    hint_text: str
    concept_reminder: str
    next_step_prompt: str
    answer_revealed: bool = False
    difficulty: int


# --- SPEC §5.12/§5.30.1 contextual learning chat (S24, plan §18-L5, D-072) --------
#
# Chat is the first surface where a student's own free text crosses the Bedrock wire -
# every payload above sends only code-selected fields. D-072 approves a narrow, explicit
# §5.30.1 extension for exactly this task family: `redacted_message`, the student's
# message after `intellichoice_shared.pii_redaction.redact_free_text` has already run
# (deterministic email/phone/URL stripping) - never the raw message. Two Bedrock calls:
# `LEARNING_CHAT_INTENT` classifies which of six branches the message is (three of them -
# request_hint/request_solution/request_video - dispatch deterministically to the
# existing hint-ladder/solution/video services below and never reach `TUTOR_CHAT` at
# all); `TUTOR_CHAT` is the free grounded reply for `question_help`/`why_wrong` only.
# `off_topic` short-circuits to a fixed redirect, no LLM call, matching `_scope_and_
# intent_json`'s "in_scope=False" precedent in chat-api.


class LearningChatIntentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    redacted_message: str


class LearningChatIntentResponse(BaseModel):
    intent: Literal[
        "question_help", "request_hint", "request_solution", "request_video",
        "why_wrong", "off_topic",
    ]
    reasoning: str = ""


class TutorChatPayload(BaseModel):
    """Narrowest-necessary payload for a free `TUTOR_CHAT` reply - same base fields as
    `BedrockTutorPayload` (D-023) plus the one D-072 extension. Both `TUTOR_CHAT`
    branches (`question_help`/`why_wrong`) are only reachable once `nodes.py::tutor_chat`
    has confirmed a real wrong `StudyAttempt` exists for the current question - the same
    precondition the button-panel `intervention_choice` flow already enforces - so
    `selected_answer` is always a real value, never invented.
    """

    model_config = ConfigDict(extra="forbid")

    grade: str
    current_topic: str
    skill: str
    question: str
    selected_answer: str
    relevant_learning_fact: str | None = None
    redacted_message: str


class TutorChatResponse(BaseModel):
    reply_text: str
    answer_revealed: bool = False


# --- SPEC §5.8.3 AI question-generation pipeline (S9) -----------------------------
#
# Generator + Solver A + Solver B share BedrockTask.QUESTION_GENERATION ("mathematics
# and structured output" per §5.25.2's task table); the three reviewers share
# BedrockTask.QUESTION_REVIEW ("independent from generator") - six LLM calls, two model
# slots, distinct prompts per role. Every payload is `extra="forbid"`, matching
# `BedrockTutorPayload`'s pattern - the allowlist fields (`allowed_shape_keys` etc.) are
# how D-015's "never let the model invent solve code" boundary is enforced: the model
# picks from an explicit menu, and the pipeline re-validates the choice against the same
# registry before using it, never trusting the string blindly.


class GeneratorPayload(BaseModel):
    """Input to the Generator Agent - proposes which registered shape/metadata suits a
    topic+skill+difficulty. Numeric parameter bounds are deliberately NOT requested from
    the model - see `ai_pipeline.SHAPE_PARAMETER_BOUNDS` - so magnitude stays a
    deterministic, code-owned property rather than an LLM-chosen number.
    """

    model_config = ConfigDict(extra="forbid")

    topic_name: str
    skill_name: str
    grade_band: str
    difficulty_label: int
    allowed_shape_keys: list[str]
    allowed_correct_option_generators: list[str]
    allowed_distractor_generator_keys: list[str]


class GeneratedTemplateResponse(BaseModel):
    shape_key: str
    correct_option_generator: str
    distractor_generator_keys: list[str]
    common_error_tags: list[str]
    estimated_time_seconds: int
    reasoning: str = ""


class SolverPayload(BaseModel):
    """Given to each of the two independent Solver Agents - the rendered question and
    its four options, in the order actually shown to a student. Never tells the model
    which option is correct - that's exactly what's being checked (§5.8.4 "independent
    solver agreement").
    """

    model_config = ConfigDict(extra="forbid")

    rendered_question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str


class SolverResponse(BaseModel):
    selected_option: Literal["a", "b", "c", "d"]
    reasoning: str = ""


class DifficultyReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rendered_question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    skill_name: str
    proposed_difficulty: int


class DifficultyReviewResponse(BaseModel):
    difficulty_label: int
    reasoning: str = ""


class AmbiguityReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rendered_question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str


class AmbiguityReviewResponse(BaseModel):
    is_ambiguous: bool
    reasoning: str = ""


class AlignmentReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rendered_question: str
    topic_name: str
    skill_name: str


class AlignmentReviewResponse(BaseModel):
    is_aligned: bool
    reasoning: str = ""


# --- SPEC §5.8.2-5.8.5 authored question bank (S20, plan §7) ----------------------
#
# A second generation mode alongside the "shape" pipeline above: real hand-quality
# stems/hint ladders/solutions instead of parameterized templates. Solver A and Solver B
# reuse the existing `SolverPayload`/`SolverResponse` shape unchanged (still just the
# rendered question + four options, never which one is correct) but are routed through
# two already-distinct task/model slots (`QUESTION_GENERATION` for A, `QUESTION_REVIEW`
# for B) rather than a new task, so they resolve to different models (§5.25.2) without
# adding a third enum value. The three separate S9 reviewers (difficulty/ambiguity/
# alignment) are collapsed into one `QUESTION_JUDGE` call here - a deliberate
# simplification for this mode, not a schema this session reuses from S9.


class AuthoredGeneratorPayload(BaseModel):
    """Input to the Authored Generator Agent. `exemplars` are a small, fixed set of
    hand-written few-shot examples (stem/hint-ladder/solution style) baked into the
    pipeline itself, not pulled from any data file - this project has no pre-authored
    hint content yet (hints are only ever LLM-generated at request time, §5.11.4).
    """

    model_config = ConfigDict(extra="forbid")

    topic_name: str
    skill_name: str
    grade_band: str
    difficulty_label: int
    exemplars: list[str]


class AuthoredGeneratedItemResponse(BaseModel):
    stem: str
    context_block: str | None = None
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: Literal["a", "b", "c", "d"]
    answer_expression: str | None = None
    hint_ladder: list[str] = []
    canonical_solution: SolutionResponse
    misconception_tags: list[str] = []
    estimated_time_seconds: int
    reasoning: str = ""


class QuestionJudgePayload(BaseModel):
    """A single combined judge call replacing S9's three separate reviewers for this
    mode (difficulty fit + ambiguity + curriculum alignment + age-appropriateness +
    hint-ladder quality, all from one independent model call).
    """

    model_config = ConfigDict(extra="forbid")

    rendered_question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    hint_ladder: list[str]
    canonical_solution: str
    topic_name: str
    skill_name: str
    grade_band: str
    proposed_difficulty: int


class QuestionJudgeResponse(BaseModel):
    difficulty_label: int
    is_ambiguous: bool
    is_aligned: bool
    is_age_appropriate: bool
    hint_quality_score: int
    reasoning: str = ""


# --- SPEC §5.19 Q&A graph, §5.21.7-5.21.8 (S13) ------------------------------------
#
# Scope Guard + Intent Router share one BedrockTask.SCOPE_AND_INTENT call - the task
# name already implies a single combined classification rather than two round-trips.
# Reranking and answer synthesis are each their own task/payload pair, same
# `extra="forbid"` pattern as every other Bedrock call in this file.


class ScopeAndIntentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    standalone_query: str
    user_role: str  # "public" for anonymous, else Role.value (§5.19.1)


class ScopeAndIntentResponse(BaseModel):
    """§5.19.2's Scope Guard + Intent Router combined. `intent` values mirror the
    workflow diagram's branches; `document_qa` is the only one with a built retriever
    this session (S14/S15 build the others) - `in_scope=False` short-circuits to the
    §5.19.4 refusal before `intent` is even consulted.
    """

    in_scope: bool
    intent: Literal[
        "document_qa", "branch_locator", "calendar", "admin_contact", "clarification"
    ]
    reasoning: str = ""


class RerankCandidate(BaseModel):
    """Candidates are identified to the model by their *position* in the request, not by
    their `chunk_id` (D-115). A chunk id is a 36-character UUID that costs ~20 output
    tokens to echo back; at 30 candidates that alone is most of a rerank response, and
    the measured effect was real: with UUID keys the response needed 1361 output tokens
    and 15.7 s, against 613 tokens and 3.2 s for these indices. The caller maps indices
    back to chunks deterministically, so the model never handles an identifier at all.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_index: int
    chunk_text: str


class RerankPayload(BaseModel):
    """§5.21.7: top-30 hybrid candidates in for scoring; the model never reorders or
    drops candidates itself - it only scores, and the caller sorts/truncates
    deterministically from `RerankResponse.scores`, same "model proposes, code decides"
    split as D-015's shape registry.
    """

    model_config = ConfigDict(extra="forbid")

    query: str
    candidates: list[RerankCandidate]


class RerankedScore(BaseModel):
    candidate_index: int
    relevance_score: float


class RerankResponse(BaseModel):
    scores: list[RerankedScore]

    @staticmethod
    def max_output_tokens_for(candidate_count: int) -> int:
        """The output budget this response needs for `candidate_count` candidates.

        Sized from the count rather than fixed, because a fixed cap is what broke: 1024
        tokens silently truncated every 30-candidate rerank on staging for as long as
        the corpus was real (D-115). Measured need for the index-keyed shape is ~613
        tokens at 30 candidates (~20/candidate); 48 per candidate plus 128 of framing is
        ~2.3x that measurement, which leaves room for a chattier model without leaving
        room for the cap to be the thing that fails.
        """
        return 128 + 48 * max(candidate_count, 0)


class RagContextChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    chunk_text: str


class RagAnswerPayload(BaseModel):
    """§5.30.1-style minimum-necessary payload for answer synthesis: the reranked top
    5-8 chunks only (never the full candidate pool), plus the query and role (for
    tone/scope, not for any additional filtering - filtering already happened before
    retrieval per §5.21.3).
    """

    model_config = ConfigDict(extra="forbid")

    query: str
    user_role: str
    context_chunks: list[RagContextChunk]


class LlmCitation(BaseModel):
    """A citation as the model proposes it - just which chunk and which quote. The
    model is never trusted to assert the quote actually supports the answer or to fill
    in document metadata itself; `chat_api.services.qa` re-derives `document_title`/
    `document_version`/`section_title`/`page_number` from the real `RagChunk` row and
    verifies `quote` is a real substring of that chunk's text before promoting this into
    a SPEC §5.21.8 `Citation` (below). A quote that fails verification means that claim
    isn't grounded - see the Response Verifier's no-answer policy.
    """

    chunk_id: str
    quote: str


class RagAnswerResponse(BaseModel):
    """Raw Bedrock output for `BedrockTask.RAG_ANSWER`, pre-verification.
    `sources_conflict` is the model's own signal for §5.21.8's "Sources conflict ->
    do not answer" / §5.29's "Conflicting RAG sources -> surface conflict and offer
    escalation" - `chat_api.services.qa` treats it as a hard no-answer trigger
    regardless of `confidence`.
    """

    answer: str
    citations: list[LlmCitation]
    confidence: float
    missing_information: str | None = None
    escalation_recommended: bool = False
    sources_conflict: bool = False


class CalendarContextChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    chunk_text: str


class CalendarExtractionPayload(BaseModel):
    """SPEC §5.23.2 "Add it to my calendar" - the model is given the already-retrieved,
    role-filtered chunks (same `retrieve()` call `chat_api`'s document_qa path already
    makes) and asked to propose a single event. `as_of_date` anchors relative language
    ("next parent meeting") to a fixed reference date.
    """

    model_config = ConfigDict(extra="forbid")

    query: str
    as_of_date: str
    context_chunks: list[CalendarContextChunk]


class CalendarExtractionResponse(BaseModel):
    """Raw, pre-verification model output. `source_chunk_id` is only ever used to look
    up the *real* `RagChunk`/`RagDocument` row - `chat_api.services.calendar` re-derives
    `CalendarEvent.source_document_id`/`source_page` from that row, never from anything
    else the model claims (same D-038 "model proposes a chunk_id, code re-derives
    provenance" split as `RagAnswerResponse`/`LlmCitation`). `found=False` (or a
    `source_chunk_id` that doesn't resolve to a real retrieved chunk) means "do not
    guess" - no event is fabricated.
    """

    found: bool
    title: str | None = None
    start_datetime: str | None = None
    end_datetime: str | None = None
    timezone: str | None = None
    location: str | None = None
    description: str | None = None
    source_chunk_id: str | None = None
    confidence: float = 0.0


# --- SPEC §5.18 Weekly YouTube Synchronization (S15) -------------------------------
#
# The sync worker classifies each fetched video's topic/skill/difficulty coverage from
# its title+description. Same "model proposes, code re-derives" discipline as
# `CalendarExtractionResponse`/D-038: the model picks from an explicit menu of real
# curriculum topic/skill *names* (never invents new ones or returns internal ids it
# was never given), and `packages/youtube/classify.py` re-validates every proposed name
# against the real curriculum registry before storing anything - an unmatched name is
# silently dropped, never trusted outright.


class VideoClassificationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    known_topic_names: list[str]
    known_skill_names: list[str]


class VideoClassificationResponse(BaseModel):
    """Raw, pre-verification model output. `topic_names`/`skill_names` must be
    re-validated against the real curriculum registry before use - see this section's
    module docstring above.
    """

    topic_names: list[str] = []
    skill_names: list[str] = []
    grade_band: str
    difficulty_min: int
    difficulty_max: int
    reasoning: str = ""


class Citation(BaseModel):
    """SPEC §5.21.8 Citation schema - backend-constructed only (see `LlmCitation`),
    never round-tripped directly from the model.
    """

    document_title: str
    document_version: int
    page_number: int | None = None
    section_title: str | None = None
    source_reference: str
    supporting_quote_hash: str


class GroundedAnswer(BaseModel):
    """SPEC §5.21.8 GroundedAnswer schema - what `chat_api` actually returns to a
    caller. `citations` only ever contains backend-verified `Citation` entries; an
    unverifiable `LlmCitation` is dropped, and if that drops every citation the answer
    fails the no-answer policy instead of being returned uncited.
    """

    answer: str
    citations: list[Citation]
    confidence: float
    missing_information: str | None = None
    escalation_recommended: bool = False


# --- SPEC §5.15.4 Sunday memory consolidation (S25, plan §9) ----------------------
#
# Deterministic pre-aggregation happens in `packages/memory` before this call - each
# `MemoryEventSummary` is a code-rendered one-line summary of a real `learning_events`
# row (never a raw JSON dump), so the model has something readable to cite, and its
# `event_id` is the *only* thing `facts_to_add[i].supporting_event_ids`/
# `facts_to_update[i].supporting_event_ids` may reference - the caller verifies every
# cited id resolves to a real event belonging to this student inside the consolidation
# window before trusting anything (same "model proposes, code verifies" split as
# `LlmCitation`/D-038). A `chat_turn` event's summary may include the student's own
# PII-redacted chat text (D-072's `redact_free_text` already applied) - approved
# specifically for this task, D-074; it never crosses any other Bedrock payload.
# `polarity` is a deliberately coarse, code-checkable signal (not buried in
# `structured_value`) so the deterministic validator can detect "this contradicts an
# existing live fact for the same (fact_type, skill_id)" without parsing free text.


class MemoryEventSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    topic_id: str | None = None
    skill_id: str | None = None
    summary: str


class MemoryExistingFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semantic_memory_id: str
    fact_type: str
    skill_id: str | None = None
    fact_text: str
    status: str
    confidence: float


class MemoryConsolidationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[MemoryEventSummary]
    existing_facts: list[MemoryExistingFact]
    allowed_fact_types: list[str]


class MemoryFactCandidate(BaseModel):
    """One proposed new fact. `fact_type` is intentionally `str`, not a `Literal` of the
    closed enum - an out-of-enum value should drop just that one candidate (matching
    D-026's "a hallucinated key rejects the candidate" pattern), not fail Pydantic
    validation for the whole `MemoryUpdate` response.
    """

    fact_type: str
    skill_id: str | None = None
    topic_id: str | None = None
    fact_text: str
    structured_value: dict = {}
    polarity: Literal["positive", "negative"] = "positive"
    confidence: float
    supporting_event_ids: list[str]


class MemoryFactUpdate(BaseModel):
    """Reconfirms (or revises the text/confidence of) an existing fact the model was
    given in `existing_facts` - `semantic_memory_id` must match one of those ids or the
    caller drops the update.
    """

    semantic_memory_id: str
    fact_text: str
    confidence: float
    supporting_event_ids: list[str]


class MemoryUpdateResponse(BaseModel):
    facts_to_add: list[MemoryFactCandidate] = []
    facts_to_update: list[MemoryFactUpdate] = []
    facts_to_expire: list[str] = []


# --- SPEC §5.10.3/§5.13.3 personalized stage narratives (S26, plan §18-L7) --------
#
# One call site, five moments (`stage`): `pre_intro` (first SSE connect to a session),
# `pre_outro` (after pre-exam finalize), `study_step` (the study plan moves to a new
# target skill), `study_outro` (study phase completion), `post_outro` (after post-exam
# finalize). `StageNarrativePayload` is deliberately a superset with every evidence
# field optional - same "one wire shape, mostly-null per call" precedent
# `SessionSnapshotEvent` already established - rather than five near-duplicate payload
# classes, since every field here is already the narrowest-necessary resolved form
# (skill *names*, never ids; numbers already computed, never raw DB rows) regardless of
# which stage supplies it. The caller (`learning_api.services.stage_narrative`) builds
# the same dict as this payload into a `stage_transitions.evidence` JSON column *before*
# the Bedrock call, and `intellichoice_shared.numeric_grounding` re-checks every number
# in `narrative_text` against that evidence after the call returns - the model is never
# trusted to invent a number, same "model proposes, code verifies" split as D-038.


class StageNarrativePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal["pre_intro", "pre_outro", "study_step", "study_outro", "post_outro"]
    grade: str
    attendance_status: str | None = None
    weak_skill_names: list[str] = []
    target_skill_name: str | None = None
    completed_skill_name: str | None = None
    pre_raw_score: float | None = None
    post_raw_score: float | None = None
    raw_gain: float | None = None
    normalized_gain: float | None = None
    hint_count: int | None = None
    solution_count: int | None = None
    video_count: int | None = None
    independent_correct_rate: float | None = None
    relevant_learning_facts: list[str] = []


class StageNarrativeResponse(BaseModel):
    narrative_text: str
    reasoning: str = ""


# --- SPEC §5.14.2-§5.14.4 progress dashboard / student report (S28, plan §18-L9) --
#
# One task (`BedrockTask.PARENT_REPORT` - the SPEC §5.25.2 task table's own name,
# reused for every audience rather than inventing a second task key), four audiences.
# `ReportInterpretationPayload` is deliberately a superset with every field optional -
# same "one wire shape, audience-filtered per call" precedent `StageNarrativePayload`
# already established. `learning_api.services.report` builds this same payload as the
# `student_reports.verified_facts` JSON column *before* the call, audience-gated
# server-side from the caller's role (never a client-supplied value) - only the fields
# SPEC §5.14.2/§5.14.3/§5.14.4 actually authorize for that audience are populated;
# `intellichoice_shared.numeric_grounding` re-checks every number in both output texts
# against that same payload after the call returns, same "model proposes, code
# verifies" split as `StageNarrativePayload`/D-038.


class ReportInterpretationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audience: Literal["student", "parent", "tutor", "branch_manager"]
    grade: str
    date_range_label: str
    pre_raw_score: float | None = None
    post_raw_score: float | None = None
    raw_gain: float | None = None
    overall_accuracy: float | None = None
    mastery_by_skill: dict[str, float] = {}
    weak_skill_names: list[str] = []
    hint_count: int | None = None
    solution_count: int | None = None
    video_count: int | None = None
    independent_correct_rate: float | None = None
    attempts_count: int | None = None
    time_spent_minutes: float | None = None
    tutor_review_flagged: bool | None = None
    relevant_learning_facts: list[str] = []


class ReportInterpretationResponse(BaseModel):
    interpretation_text: str
    recommendations_text: str
    reasoning: str = ""


# --- SPEC §5.31.3 LLM-as-a-Judge (S30, plan §13) -----------------------------------
#
# `BedrockTask.LLM_JUDGE` was reserved (unused) since S8 (D-022) - this is its first
# real caller, `packages/evals`. One payload/response pair covers both SPEC domains
# (Adaptive Learning's 6 dimensions, Q&A's 5) via a `domain` discriminator and an
# explicit `dimensions` list, rather than two near-duplicate schemas - the rubric shape
# (score + reasoning per named dimension) is identical across domains; only which
# dimensions apply differs, and that's data, not a distinct model shape. `content_to_
# judge`/`context` hold already-generated text (a hint, solution, chat reply, or RAG
# answer plus its grounding context) - text that already passed the PII floor when it
# was first generated (D-023) - not raw student fields, so this isn't governed by
# `test_bedrock_payload_pii_floor.py`'s allowlist (same reasoning as the S9 generation
# payloads in `test_generation_payload_schemas.py`).


class LlmJudgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: Literal["learning", "qa"]
    dimensions: list[str]
    content_to_judge: str
    context: str


class RubricDimensionScore(BaseModel):
    dimension: str
    score: int
    reasoning: str = ""


class LlmJudgeResponse(BaseModel):
    scores: list[RubricDimensionScore]
    overall_pass: bool


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class BedrockGenerationResult[T: BaseModel]:
    value: T
    input_tokens: int
    output_tokens: int
    cost_cents: float
    model_id: str
    repaired: bool


@dataclass(frozen=True)
class EmbeddingResult:
    """Result of `BedrockGateway.create_embedding` - one vector per input text, in the
    same order (SPEC §5.21.1's "Embedding" ingestion step). `dimensions` is carried
    alongside the vectors themselves so callers can assert it matches the Postgres
    `vector(N)` column without importing a model-specific constant.
    """

    vectors: list[list[float]]
    model_id: str
    dimensions: int
    cost_cents: float


class BedrockGatewayError(Exception):
    """Base for every gateway failure that a caller should treat as "safe fallback
    territory" (SPEC §5.25.3's "Invalid -> Limited retry -> Deterministic fallback").
    `cost_cents` carries any real spend already incurred before the failure (e.g. a
    structured-output repair attempt that still failed validation) so callers can add it
    to their running session total even though no usable content came back.
    """

    def __init__(self, message: str, *, cost_cents: float = 0.0) -> None:
        super().__init__(message)
        self.cost_cents = cost_cents


class BedrockTimeoutError(BedrockGatewayError):
    pass


class StructuredOutputError(BedrockGatewayError):
    """Raised after the provider's raw output failed Pydantic validation and the single
    repair retry (SPEC §5.25.3) also failed.
    """


class CostBudgetExceededError(BedrockGatewayError):
    """Raised before any provider call when the session's cumulative spend plus this
    call's worst-case cost would exceed the configured per-session budget.
    """


class CircuitOpenError(BedrockGatewayError):
    """Raised before any provider call while the circuit breaker is open."""


class BedrockGateway(Protocol):
    # Deliberately *not* including `worst_case_cost_cents` (AUD-X-08's reservation
    # estimate), which `ResilientBedrockGateway` does expose. It is a pricing question,
    # not a generation one, and putting it here would oblige every scripted test fake to
    # implement a method it never calls. The per-surface estimates are constants instead,
    # kept honest by `test_cost_reservation_estimates.py`, which asserts each one still
    # bounds the real gateway's own worst case.
    async def generate_structured(
        self,
        *,
        task: BedrockTask,
        system_prompt: str,
        payload: BaseModel,
        response_model: type[T],
        max_output_tokens: int,
        session_spend_cents: float,
    ) -> BedrockGenerationResult[T]: ...

    async def create_embedding(
        self,
        *,
        texts: list[str],
        session_spend_cents: float,
    ) -> EmbeddingResult: ...
