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
from typing import Annotated, ClassVar, Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


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
    # D-205: its own task so the stage that *designs* the mathematics can run on a
    # different model from the one that writes the item up. Measured reason: the two jobs
    # want opposite things. Design is a six-field schema and wants a model that can call a
    # calculator; authoring is a fifteen-field forced schema and wants a model that emits
    # it reliably, and on this account no single model is good at both.
    EQUATION_DESIGN = "equation_design"
    QUESTION_JUDGE = "question_judge"
    # D-251: its own task rather than another field on QUESTION_JUDGE, because that judge
    # already does seven jobs in one call and the one measured consequence of that was
    # `hint_quality_score` (D-249). Separate task also means separate model choice - a
    # reviewer reading pedagogy is not obviously the same model as one rating difficulty.
    HINT_SOLUTION_REVIEW = "hint_solution_review"
    # D-260: separate from the reviewer for the reason D-205 split design from authoring -
    # reading an item and rewriting it are different jobs wanting different models, and
    # D-255 requires the repairer to be Model A while the reviewers are B and C. One task
    # slot each is what makes that roster expressible at all.
    HINT_SOLUTION_REPAIR = "hint_solution_repair"
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
        "question_help",
        "request_hint",
        "request_solution",
        "request_video",
        "why_wrong",
        "off_topic",
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


class ChatVizSpec(BaseModel):
    """D-217: an optional, bounded little diagram a tutor chat reply may attach when a
    picture helps - a number line with the answer marked, or two bars comparing the two
    sides of an equation. Deliberately one flat shape (a `kind` plus parallel `labels`/
    `values`) rather than a per-kind union, so the forced-tool JSON schema the model fills
    stays simple. Every bound lives *in the schema* (the `Field` constraints below travel
    in the tool's `inputSchema`, so the model is told the rule while it writes, the same
    discipline the generator payloads use) - the client render is then a pure function of
    already-validated numbers and short strings, with no model-chosen markup, so there is
    no injection surface.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["number_line", "bar_model"]
    caption: Annotated[str, Field(max_length=80)]
    labels: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=24)]],
        Field(min_length=2, max_length=4),
    ]
    values: Annotated[
        list[Annotated[float, Field(ge=-100, le=100)]],
        Field(min_length=2, max_length=4),
    ]

    @model_validator(mode="after")
    def _labels_and_values_align(self) -> "ChatVizSpec":
        if len(self.labels) != len(self.values):
            raise ValueError("labels and values must have the same length")
        return self


class TutorChatResponse(BaseModel):
    reply_text: str
    answer_revealed: bool = False
    # D-217: present only when the model judged a picture would help; omitted otherwise.
    # Bounded by `ChatVizSpec`; validated by the same gateway machinery as the rest of the
    # response, so a malformed viz is repaired or falls back like any other field.
    viz: ChatVizSpec | None = None


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
    """Field order is load-bearing, and so is `no_option_matches` - see D-193.

    `reasoning` comes first because the gateway sends `model_json_schema()` and a model
    emits its JSON in schema order: a `selected_option` declared first is chosen *before*
    the model has worked anything out, and the reasoning that follows can only rationalise
    it. Reasoning first makes the field what it is named after.
    """

    reasoning: str
    # A solver that has computed an answer absent from the options used to have no way to
    # say so - `selected_option` is a closed literal, so it was forced to name one of four
    # wrong answers. `narrative-linear_equations-d4-23000` is what that costs: the story's
    # answer was 4, no option offered 4, and both solvers picked the same wrong option and
    # were recorded as *agreeing*. Agreement manufactured by the schema is worse than no
    # check, because the pipeline reports it as independent confirmation.
    no_option_matches: bool = False
    # Distinct from `no_option_matches`: there the solver has one answer and cannot find
    # it, here it cannot settle on one answer at all. Fail-closed either way, but the
    # rejection reason should say which happened.
    is_unambiguous: bool = True
    ambiguity_reasons: list[str] = Field(default_factory=list)
    # Still required, still a closed literal: a solver must commit to its best option even
    # when it flags one of the above, so the disagreement arm keeps working unchanged.
    selected_option: Literal["a", "b", "c", "d"]


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


class EquationDesignPayload(BaseModel):
    """Input to the equation-design stage (D-200) - the cheap call that fixes the numbers
    before anything expensive is written around them.
    """

    model_config = ConfigDict(extra="forbid")

    topic_name: str
    skill_name: str
    grade_band: str
    target_difficulty: int
    difficulty_anchor: str
    previous_attempts: list[str] = []
    # Equations already accepted for THIS slot in this run (D-273). Distinct from
    # `previous_attempts`, which is this candidate's own failed designs: these succeeded, for
    # a sibling candidate.
    #
    # **Measured need, and it is the cause rather than a symptom.** `candidates_per_slot` is
    # 2, and the two candidates of a slot were receiving an *identical* payload - the seed
    # distinguished their template ids and nothing else. So the model had no reason to choose
    # different numbers, and did not: in C1's first wave every duplicate group was a same-slot
    # pair (seeds 6200/6201 both `6 + 7`, 6400/6401 both `9 + 9`), 27 of 55 items sharing a
    # number set. Detecting that afterwards is the second-best fix; telling the design stage
    # what its slot-mate already used is the first.
    avoid_equations: list[str] = []


class EquationDesignResponse(BaseModel):
    """The mathematical skeleton of an item, before it is written up.

    Deliberately small. It exists so the *deterministic* check that has been catching the
    commonest defect - a declared answer the item's own equation does not produce - can run
    on a ~150-token call instead of after a ~2500-token one (D-200).

    `scenario_sketch` is here, rather than the equation alone, because D-192 generated an
    equation and then had a story written to dress it, and nothing verified that the story
    encoded that equation. Asking for both together keeps them coupled from the start; the
    D-193 solver panel, which did not exist then, is what verifies the coupling later.
    """

    model_config = ConfigDict(extra="forbid")

    reasoning: str
    scenario_sketch: str
    unknown_meaning: str
    equation: str
    final_answer: str
    answer_units: str | None = None


class RepairContext(BaseModel):
    """One prior rejected attempt, handed back to the Generator so it can fix the item
    rather than re-roll a fresh one (D-198).

    `defects` is deliberately **not** the raw rejection reasons. Those contain the
    independent checks' verdicts - which option each solver picked, what tier the judge
    assigned - and handing those back turns the checks into targets: the cheapest way to
    resolve "solver A picked b, you declared c" is to change the declared answer, and the
    cheapest way to resolve a difficulty gap is to relabel. `ai_pipeline.repair_feedback`
    is the one place that decides what may cross this boundary, and it passes objective
    defects and qualitative descriptions only.

    The previous item's own content travels with it because "fix this" needs a *this*;
    without it the model writes an unrelated question and the defect list reads as
    arbitrary constraints.
    """

    model_config = ConfigDict(extra="forbid")

    attempt: int
    previous_stem: str
    previous_context_block: str | None = None
    previous_equation: str | None = None
    previous_final_answer: str
    defects: list[str]


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
    # Renamed from `difficulty_label` (D-194) to say what it is: the tier this slot is
    # *asking* for, not a fact about the item. The generator answers with its own
    # `proposed_difficulty`, which is normally this number - being told the target
    # anchors it, and that is precisely why the anchored proposal is not the check. The
    # judge never sees this field (see `QuestionJudgePayload`).
    target_difficulty: int
    exemplars: list[str]
    # Absent on a first attempt, which is why it is optional rather than a separate payload
    # type: the repair call is the same task with one more input, and a second schema would
    # mean a second prompt drifting away from this one.
    repair: RepairContext | None = None
    # A skeleton that has already passed the deterministic solver (D-200). When present the
    # author must build the item around it rather than inventing its own numbers - that is
    # what removes the commonest defect, an answer the item's own equation does not produce.
    verified_design: EquationDesignResponse | None = None


class AuthoredGeneratedItemResponse(BaseModel):
    """What the Generator returns: a complete student-facing MCQ *plus* its own claim
    about how hard the item is and why (D-194).

    `extra="forbid"` here and not on the older response models on purpose. A stray field
    in a generated question is a signal that the model has drifted from the contract, and
    the failure path is the good one - schema violation, bounded repair retry, then
    rejection (SPEC §5.25.3). The cost is that a candidate can be lost to a formatting
    slip rather than to bad math, which is the trade this project has already chosen
    everywhere else content reaches a student.
    """

    model_config = ConfigDict(extra="forbid")

    stem: str
    context_block: str | None = None
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: Literal["a", "b", "c", "d"]
    # The equation that models the question, e.g. `Eq(3 + 7*m, 4 + 4*m)` for two robots
    # collecting at different rates from different starting amounts. Named for what it is:
    # this was `answer_expression`, and the generator filled it with the answer (`'7'`),
    # which made the "independent solve" a comparison of the generator against itself
    # (D-191). `authored_validation.derive_answer` solves it, so the answer is derived
    # here rather than asserted by the model that wrote the question. Still persisted to
    # the `answer_expression` column, which is not worth a migration to rename.
    equation: str | None = None
    # Exactly three levels, enforced structurally rather than only downstream (D-195).
    # `authored_validation` has always rejected a wrong-length ladder, but that is one
    # paid Generator call too late: the first four-candidate pilot lost a candidate to a
    # 4-level ladder after the model had already been billed for the whole item. Stated in
    # the schema, the bound travels in the tool's `inputSchema`, so the model is told the
    # rule while it writes and a violation costs a bounded repair retry instead of the
    # candidate. Required, not defaulted - an item with no hints is a contract violation,
    # and a `[]` default would let one through the *model* contract silently.
    hint_ladder: list[str] = Field(min_length=3, max_length=3)
    canonical_solution: SolutionResponse
    misconception_tags: list[str] = []
    estimated_time_seconds: int
    # The Generator's own difficulty claim (D-194). Bounded to the 1-5 scale the whole
    # system uses, for the reason `hint_quality_score` is bounded: an unbounded field
    # reached the model as a free integer and it invented its own scale, which silently
    # disabled the gate reading it. The bound travels in the tool's JSON schema.
    proposed_difficulty: int = Field(ge=1, le=5)
    # Deliberately `min_length`, not just required. "This is difficulty 3" and "moderately
    # difficult" restate the label and say nothing a reviewer can check; what earns the
    # label is the reasoning the item demands - translating a scenario into an equation,
    # a variable on both sides, distribution before combining like terms. A length floor
    # does not force a *good* rationale, but it does stop the empty string, and the judge
    # is what actually tests the claim.
    difficulty_rationale: str = Field(min_length=20)
    # Curriculum concepts a student needs before this item is fair. Recorded as evidence
    # for the human reviewer rather than gated on: there is no prerequisite graph to check
    # them against yet, and inventing one from a model's free text would be worse than
    # admitting they are unvalidated.
    required_prerequisites: list[str] = []
    reasoning: str = ""


class QuestionJudgePayload(BaseModel):
    """A single combined judge call replacing S9's three separate reviewers for this
    mode (difficulty fit + ambiguity + curriculum alignment + age-appropriateness +
    hint-ladder quality, all from one independent model call).

    **It no longer carries `proposed_difficulty` (D-194), and that omission is the point.**
    The judge used to be told the tier being asked for and then asked to rate difficulty,
    so "the judge agreed" meant a model had been shown a number and returned it. The
    comparison that gates the candidate is only worth making if the second number was
    reached independently, so the judge sees what a teacher would see: the question, the
    options, the hint ladder, the answer, and the topic/skill/grade it is meant for.
    Neither the Generator's proposal nor its rationale reaches here.
    """

    model_config = ConfigDict(extra="forbid")

    rendered_question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    # Which option is keyed correct (D-273). Its absence was a live source of false
    # rejections, measured on C1's first wave: the judge was given four options and a
    # solution text but never told which letter the key names, and asked whether the item is
    # internally consistent it **assumed option_a**. On a correct item - 17 + 8 = 25, keyed
    # `b`, with `24 stickers` as an ordinary distractor at `a` - it declared an "internal
    # contradiction" because option_a was not the answer, and the item was rejected while
    # both independent solvers had picked `b` and marked it unambiguous.
    #
    # `shuffle_options` is seeded and deterministic (D-191), so roughly three items in four
    # have a non-`a` answer and were exposed to this.
    #
    # **This does not weaken the blind review.** D-194's blindness is about *difficulty*:
    # the judge must not see the requested or proposed tier, and it still does not. The
    # answer was never hidden - `canonical_solution` states it in words - so this adds the
    # letter, not the answer, and lets the consistency question actually be answerable.
    correct_option: Literal["a", "b", "c", "d"]
    hint_ladder: list[str]
    canonical_solution: str
    topic_name: str
    skill_name: str
    grade_band: str


class QuestionJudgeResponse(BaseModel):
    """`reasoning` first, for the reason given on `SolverResponse` - and here there is a
    measured failure to point at (D-193).

    On `narrative-linear_equations-d4-23000` this judge derived the story's true answer,
    wrote "the canonical solution is mathematically incorrect", and closed with "I must
    flag this as internally inconsistent" - while the `is_internally_consistent` it had
    already emitted said `true`. The judge was not wrong about the question; it was asked
    for its verdict before it was allowed to think, and nothing in a JSON response can be
    revised once written. Every boolean below is now decided after the prose.
    """

    reasoning: str
    # Renamed from `difficulty_label` (D-194): this is the judge's *own* rating, reached
    # without seeing what was proposed, and the old name read like the item's settled
    # difficulty rather than one of two opinions about it. Bounded for the same reason
    # `hint_quality_score` is.
    reviewed_difficulty: int = Field(ge=1, le=5)
    # Separate from `reasoning`, which covers the whole review. This one has to name the
    # reasoning operations the item demands - the same standard the Generator's
    # `difficulty_rationale` is held to - so the two rationales are comparable when a
    # human reads the disagreement.
    difficulty_reasoning: str = Field(min_length=20)
    is_ambiguous: bool
    is_aligned: bool
    is_age_appropriate: bool
    # Separate from `is_ambiguous` because the failure is not ambiguity: the question is
    # perfectly clear, its algebra is right, and its answer is impossible in the world it
    # describes. Overloading an existing flag would have made the rejection reason lie
    # about what was wrong (D-191).
    is_internally_consistent: bool = True
    # Bounded because an unbounded score silently disabled the gate that reads it. The
    # first real-Bedrock authoring run (2026-08-05) had the judge score every item 8 or 9
    # on its own invented 1-10 scale, while `ai_pipeline`'s thresholds reject below 2 and
    # flag at or below 3 on the documented 1-5 scale - so both arms were unreachable and
    # every item passed a hint-quality check that never ran. The constraint reaches the
    # model as `minimum`/`maximum` in the tool's JSON schema (the gateway sends
    # `model_json_schema()`), and an out-of-range score now fails validation into the
    # repair retry and then rejection, which is the fail-closed direction (SPEC §5.25.3).
    hint_quality_score: int = Field(ge=1, le=5)
    # D-202. This was a regex (`answer_text_leaked`) and a regex cannot do it: it cannot
    # tell "the answer is 4" from "he buys a 4-pack", because they are the same characters.
    # It destroyed four correct items before being replaced. A reader can tell instantly,
    # so the judge is asked instead - it already has the hints and the answer in front of
    # it, and it is the only reviewer that reads both.
    hint_reveals_answer: bool = False
    hint_reveals_answer_reason: str = ""


# --- SPEC §5.19 Q&A graph, §5.21.7-5.21.8 (S13) ------------------------------------
#
# Scope Guard + Intent Router share one BedrockTask.SCOPE_AND_INTENT call - the task
# name already implies a single combined classification rather than two round-trips.
# Reranking and answer synthesis are each their own task/payload pair, same
# `extra="forbid"` pattern as every other Bedrock call in this file.


class ScopeAndIntentPayload(BaseModel):
    """D-219: `user_role` was removed, and its absence is the point.

    The field used to be sent to a classifier whose system prompt never mentions roles or
    access - so the model was handed an attribute it had no instructions for, and used it to
    make an *authorization* judgement. Measured on staging 2026-08-08: "What does the branch
    manager manual say about monthly reporting?" came back `out_of_scope` for an anonymous
    visitor, with wording byte-identical to the refusal for "What is the capital of France?",
    and `in_scope` with a cited answer for a signed-in branch manager.

    That is CLAUDE.md #3 ("authorization in the backend/query layer, never in prompts") being
    decided in a prompt, and it also collapsed "not our topic" into "not your topic" - the
    `AccessHintBanner` that exists to say "sign in to see this" could never fire, because
    `explain_access` runs *after* retrieval and the scope guard short-circuits before it.

    Scope is now a property of the question alone. Whether the asker may read the answer stays
    where it always belonged: `role_access.role_access_filter`, applied pre-retrieval.
    """

    model_config = ConfigDict(extra="forbid")

    standalone_query: str


class ScopeAndIntentResponse(BaseModel):
    """§5.19.2's Scope Guard + Intent Router combined. `intent` values mirror the
    workflow diagram's branches; `document_qa` is the only one with a built retriever
    this session (S14/S15 build the others) - `in_scope=False` short-circuits to the
    §5.19.4 refusal before `intent` is even consulted.
    """

    in_scope: bool
    intent: Literal["document_qa", "branch_locator", "calendar", "admin_contact", "clarification"]
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
    """One context passage, identified to the model by position (`LlmCitation` cites the
    same index back). The `chunk_id` it used to carry was never needed by the model and
    cost output tokens on every citation - see `LlmCitation`'s docstring.
    """

    model_config = ConfigDict(extra="forbid")

    context_index: int
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
    """A citation as the model proposes it - just which passage and which quote. The
    model is never trusted to assert the quote actually supports the answer or to fill
    in document metadata itself; `chat_api.services.qa` re-derives `document_title`/
    `document_version`/`section_title`/`page_number` from the real `RagChunk` row and
    verifies `quote` is a real substring of that chunk's text before promoting this into
    a SPEC §5.21.8 `Citation` (below). A quote that fails verification means that claim
    isn't grounded - see the Response Verifier's no-answer policy.

    `context_index` is the passage's position in `RagAnswerPayload.context_chunks`, not
    its `chunk_id` (D-115, AUD-X-12 - same change `RerankCandidate` got, for the same two
    reasons). A UUID costs ~20 output tokens per citation, and an answer citing 8
    passages spent ~160 tokens echoing identifiers back; worse, a model that garbles one
    character of a UUID produces a citation that cannot be matched to any chunk, which
    this module correctly discards - and a discarded citation is a *refusal*. An index is
    a single token the model cannot plausibly corrupt into another valid index's meaning
    without the mistake being visible.
    """

    context_index: int
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

    @staticmethod
    def max_output_tokens_for(context_chunk_count: int) -> int:
        """The output budget an answer over `context_chunk_count` passages needs.

        Derived rather than fixed, for AUD-X-09's reason and then AUD-X-12's evidence:
        the previous fixed 1536 sat at the p95 of what real answers actually emit
        (measured on staging: p50 662, **p95 1490**, max 1530 output tokens over 70
        turns), so roughly one turn in thirty truncated - and a truncated answer is not
        a slow answer, it is a **false "no approved source" refusal**, because
        `qa.answer_question` cannot distinguish a schema failure from an ungrounded
        question.

        **The floor dominates, and that correction cost a deploy.** This started as
        `768 + 192n`, reasoning by analogy with `RerankResponse.max_output_tokens_for`,
        where the response genuinely is one scored line per candidate. An *answer* is
        not: its length is a function of the question, and only its `citations` list
        scales with the passages available to cite. So the first shape produced a
        **960-token ceiling for single-passage turns - lower than the flat 1536 it
        replaced** - and staging immediately truncated 3 of 74 turns, all of them
        `context_chunk_count=1` (D-115 §10). The prose floor is therefore generous and
        fixed, with a small per-passage allowance on top: ~2.1k at one passage (40% above
        the old flat cap), ~2.8k at the current top_k of 8, both inside the gateway's
        4000-token hard ceiling.
        """
        return 2048 + 96 * max(context_chunk_count, 0)


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

    # The largest existing-fact count this response shape can serialize inside the
    # gateway's 4000-token hard ceiling. Past it the cap saturates and the caller warns -
    # see `max_output_tokens_for`.
    MAX_SAFE_EXISTING_FACTS: ClassVar[int] = 21

    @staticmethod
    def max_output_tokens_for(existing_fact_count: int) -> int:
        """The output budget a consolidation over `existing_fact_count` live facts needs.

        S43, from D-115's carry-over (ii): this was a flat 1200 over an input that grows
        with student history, which is the shape that was AUD-X-09 (the reranker, dead in
        production for a week) and then AUD-X-12 (false refusals). Unlike an *answer* -
        whose length is a function of the question, the D-115 §10 correction - this
        response genuinely is one item per input item: the model may reconfirm every fact
        it was shown and expire any of them, so two of the three lists are sized by
        `existing_facts` directly.

        Measured against the serialized schema (scratchpad sweep, chars/3.5 calibrated
        against the reranker's known ~20 tok / ~68 chars per candidate):

            live facts   1     5     10     20     40
            response   261  1249   1733   2712   4659 tokens

        Marginal cost is ~94 tok per reconfirmed fact and ~10 per expiry, so ~104/fact;
        128 carries ~20% headroom. The base covers a full slate of *new* facts, which are
        the expensive item at ~149 tokens each and do not scale with the input.

        **The base is set by the floor, not by that measurement.** 896 would have been
        ample for the need (261 tokens at one fact) but yields 1024 at n=1 - *below* the
        flat 1200 it replaces. That is precisely the regression D-115 §10 shipped and had
        to correct on the RAG answer cap: a derived formula can be strictly worse than the
        constant it replaces at the low end, where most calls live. 1280 keeps every count
        above the old cap. `test_consolidation_output_budget_scales_with_existing_fact_
        count` asserts that floor, and caught this exact mistake here before it shipped.

        **This does not fit forever, and that is the finding under the finding.** Past
        `MAX_SAFE_EXISTING_FACTS` the derived budget exceeds the gateway's own 4000-token
        hard ceiling, so no cap can rescue the largest students - the *payload* would have
        to be bounded, which is a behaviour change (which facts get dropped?) and needs its
        own decision. Deliberately not made here; `consolidation.py` logs when it is
        reached so that decision arrives with evidence rather than a guess.
        """
        return 1280 + 128 * max(existing_fact_count, 0)


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
    # AUD-L-15 (D-156): `date_range_label` describes the *range-filtered* aggregates only
    # - attempts, usage, accuracy, gain. It never described `mastery_by_skill` (no date
    # filter at all, and the post-exam is structurally excluded) or `weak_skill_names`
    # (post-exam derived), yet all three arrived under it, which is how one report showed
    # a skill at mastery 1.000 *and* "needs work" under a single "all time" heading. The
    # two labels below carry each figure's own window. Empty when the figure they describe
    # is gated away for this audience - a window with no number is noise.
    date_range_label: str
    mastery_window_label: str = ""
    weak_skill_window_label: str = ""
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
    # Bounded for the reason `hint_quality_score` is: `run_llm_judge`'s system prompt says
    # "1 (fails) to 5 (excellent)" and the schema used to say nothing, which is the exact
    # shape that made the question judge emit 8s and 9s against thresholds of 2 and 3. It has
    # never bitten here only because this task has had no production caller since S8.
    score: int = Field(ge=1, le=5)
    reasoning: str = ""


class LlmJudgeResponse(BaseModel):
    scores: list[RubricDimensionScore]
    overall_pass: bool


# --- Hint & solution review (D-251) -----------------------------------------------------
#
# Deliberately *not* built on `LlmJudgePayload`/`LlmJudgeResponse` above, and the reason is
# the whole point of D-251. That pair's substance is a 1-5 scalar per dimension, and an
# absolute scalar is root cause #1 of why the existing `hint_quality_score` turned out to
# measure the judge rather than the item (D-249: it fired on 46% of hand-authored,
# human-approved bank content). Reusing it would have reintroduced that on the first line.
#
# What is reused is the *pattern* - a thin task-specific wrapper over
# `generate_structured` - which is this codebase's convention for every task.


class HintSolutionReviewPayload(BaseModel):
    """What a reviewer needs to judge a hint ladder and canonical solution, and nothing else.

    `rendered_question` rather than the bare stem for D-196's reason: a verdict about
    content a student never sees is a verdict about the wrong text.
    """

    model_config = ConfigDict(extra="forbid")

    rendered_question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    hint_ladder: list[str]
    solution_steps: list[str]
    solution_final_answer: str
    skill_name: str
    grade_band: str


class HintSolutionDefect(BaseModel):
    """One located, actionable defect. `suggested_fix` is what makes the verdict
    automatable: a repair attempt needs an instruction, not a complaint.
    """

    model_config = ConfigDict(extra="forbid")

    target: Literal["hint_ladder", "canonical_solution"]
    # 1-based rung or step number; `None` when the defect is about the ladder or solution as
    # a whole (e.g. "no rung addresses the actual misconception"). Bounded below only - the
    # real upper bound is the item's own length and is checked by the caller, which knows it.
    index: int | None = Field(default=None, ge=1)
    problem: str
    suggested_fix: str


class HintSolutionReviewResponse(BaseModel):
    """`PASS | REPAIR | REJECT` plus located defects - a structured decision, not a score.

    `uncertainty` is a routing signal, not a quality measure: it is what sends a borderline
    item for a second reading (HINT_SOLUTION_REVIEW.md §4), which is why it is three named
    levels rather than a number.
    """

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["pass", "repair", "reject"]
    # Bounded so a model cannot answer with an essay's worth of defects and blow the output
    # budget - the same containment `MAX_SCHEMA_ERRORS` applies to diagnosis.
    defects: list[HintSolutionDefect] = Field(default_factory=list, max_length=8)
    uncertainty: Literal["low", "medium", "high"]
    reasoning: str

    @model_validator(mode="after")
    def _blocking_verdicts_must_be_located(self) -> "HintSolutionReviewResponse":
        """A `repair` or `reject` with no defects is not a decision anything can act on -
        repair has no instruction to follow and a reviewer has nothing to read. Rejecting it
        here sends it through the gateway's repair retry, which is where a fixable
        malformed response belongs.
        """
        if self.verdict != "pass" and not self.defects:
            raise ValueError(f"verdict {self.verdict!r} requires at least one defect")
        return self


class HintSolutionRepairPayload(BaseModel):
    """The item plus what the panel found wrong with it (D-260).

    `defects` arrives already filtered by `review_panel.merge_defects` - hallucinated
    locations are gone, and duplicates are **not**, because two reviewers naming the same
    step is the signal that step matters most (D-259).
    """

    model_config = ConfigDict(extra="forbid")

    rendered_question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    hint_ladder: list[str]
    # **The same shape the response must return, and D-263 measured why.** These were
    # rendered strings ("1. Divide by 4 [n = 52/4]") while the response demanded nested
    # `SolutionStep` objects, and the repairer mirrored what it was shown: 4 of 10 real
    # repairs died on `solution_steps.N: model_type` after the gateway's retry. The reviewer
    # never hit it because a reviewer only *reads* this field; a repairer has to write it
    # back. An asymmetric in/out shape is a trap for exactly one of the two roles.
    solution_steps: list[SolutionStep]
    solution_final_answer: str
    skill_name: str
    grade_band: str
    # Rendered rather than nested so the repairer reads one flat list in the order the
    # panel produced it, and so a schema change to `HintSolutionDefect` cannot silently
    # alter what a repair prompt says.
    defects: list[str] = Field(min_length=1, max_length=16)


class HintSolutionRepairResponse(BaseModel):
    """**Only the two things a defect can target.** §4.6 requires repairs to preserve
    everything the reviewers did not object to, and this schema is how that is enforced
    rather than requested: the stem, the options, the correct option and the equation are
    not fields here, so a repair *cannot* change them however the prompt is read.

    That matters more than it looks. The alternative - returning a full
    `AuthoredGeneratedItemResponse` and trusting an instruction to leave most of it alone -
    would let a repair silently move the answer key, and the panel would then be reviewing
    a different question from the one that was measured.
    """

    model_config = ConfigDict(extra="forbid")

    reasoning: str
    # **Exactly three, because that is what the item it repairs allows** (D-267).
    # `AuthoredGeneratedItemResponse.hint_ladder` is `min_length=3, max_length=3`, and this
    # was `1..8`. The repairer was never told the real rule, so it returned four rungs on two
    # items, both reviewers passed them - they have no reason to know the constraint - and the
    # defect surfaced only when the loader refused the bank file. The bound travels to the
    # model in the tool's JSON schema, which is how D-194 fixed the same class for
    # `proposed_difficulty`.
    hint_ladder: list[str] = Field(min_length=3, max_length=3)
    solution_steps: list[SolutionStep] = Field(min_length=1, max_length=12)
    solution_final_answer: str


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class BedrockGenerationResult[T: BaseModel]:
    value: T
    input_tokens: int
    output_tokens: int
    cost_cents: float
    model_id: str
    repaired: bool
    # Converse's raw `stopReason`, carried up from the provider (D-195). Nothing on the
    # serving path reads it - it exists so that when a model new to this account fails the
    # structured-output contract, the first diagnostic question has an answer. Defaulted,
    # so every existing construction site is unaffected.
    stop_reason: str = ""
    # D-217: prompt-cache accounting (D-203 measured the saving but the gateway dropped
    # these). Carried and logged so a cache hit is *visible* rather than only inferable
    # from `input_tokens` collapsing. Defaulted, so existing construction sites are
    # unaffected. Not yet billed off separately - the cost above still rates every input
    # token the same, which slightly over-states the cost of a warm-cache call.
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


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


# A model that has lost the contract entirely emits dozens of off-schema keys, and each
# one becomes an entry in a JSON column and a log line. Small on purpose: past the first
# handful a reader has already learned which way the model drifted (D-243).
MAX_SCHEMA_ERRORS = 8

# Stands in for `loc` when the response was not JSON at all, which Pydantic never sees and
# therefore never names. Bracketed so it cannot collide with a real field.
NOT_JSON_DIGEST = "<response>: not_json"


def schema_error_digest(exc: ValidationError, *, limit: int = MAX_SCHEMA_ERRORS) -> list[str]:
    """`field.path: rule` for each violation, and deliberately nothing else (D-243).

    **The omission is the point.** `ValidationError.errors()` embeds the offending `input`
    unless told otherwise, and on the generator path that input is the item the model just
    wrote - a full stem, four options, a hint ladder. Keeping it would put model-written
    content into an exception message, a log line and a database row at once, which is
    three new places for content this project keeps out of logs on principle (SPEC §5.30).

    `loc` and `type` carry everything a reader acts on: which field, which rule. They also
    group in SQL, which is what turns twenty-eight identical rows into a distribution.

    **The bound keeps rule diversity, not the first `limit` errors, and that correction
    came from this instrument failing on its own first paid run.** The generator's real
    failure mode is to wrap the item in a key of its own invention; Pydantic reports that
    as every required field `missing` plus exactly one `extra_forbidden` naming the
    wrapper, and it emits the `missing` errors first. A first-eight bound therefore
    returned eight identical `missing` entries and dropped the single entry that said what
    the model had actually sent - six failures, six identical digests, and the answer one
    layer below what the instrument could see. Round-robin across distinct rules instead:
    every rule gets one entry before any rule gets a second, so a uniform failure can
    never crowd out the rare entry, which is the only kind worth the space.
    """
    by_rule: dict[str, list[str]] = {}
    for error in exc.errors(include_url=False, include_input=False):
        loc = ".".join(str(part) for part in error["loc"]) or "<root>"
        entry = f"{loc}: {error['type']}"
        bucket = by_rule.setdefault(error["type"], [])
        if entry not in bucket:
            bucket.append(entry)

    digest: list[str] = []
    for depth in range(max((len(b) for b in by_rule.values()), default=0)):
        for bucket in by_rule.values():
            if depth < len(bucket) and len(digest) < limit:
                digest.append(bucket[depth])
    return digest


class _CyclicSchema(Exception):
    """Raised internally by `inline_schema_refs` when a `$ref` cycle makes inlining
    impossible. Never escapes the function."""


def inline_schema_refs(schema: dict) -> dict:
    """Replace every `$ref` with its `$defs` target, so the tool schema has no indirection.

    **Measured, and the largest finding of D-243.** `AuthoredGeneratedItemResponse` is the
    only response model in this project containing another model, so it is the only schema
    Pydantic emits with a `$defs` block - and it is the schema D-240 measured failing on
    41% of candidates. On Haiku 4.5, **twelve calls** carrying the `$ref` form returned a
    tool input with exactly one key, `canonical_solution` - the one field that *is* a
    `$ref` - and every other required field simply absent. **Four calls** with the same
    schema dereferenced returned three valid items. The model reads the `$ref` target as
    the schema rather than as one field's type.

    Nothing is loosened: an inlined schema is the same schema, so this is a change of
    representation at one seam rather than a change of contract. A schema with no `$defs`
    is returned untouched, which is every other model in the project.

    The evidence is 0/12 against 3/4 on one model, one topic and one prompt. That is
    enough to act on and not enough to generalise, which is why the claim here is about
    this schema and this model rather than about `$ref` in tool schemas.
    """
    defs = schema.get("$defs")
    if not defs:
        return schema

    def walk(node: object, active: frozenset[str]) -> object:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                name = ref.rsplit("/", 1)[-1]
                if name in active or name not in defs:
                    raise _CyclicSchema(name)
                target = walk(defs[name], active | {name})
                # Sibling keys beside a `$ref` (Pydantic emits `description`, `default`)
                # override the target's, which is what JSON Schema 2020-12 specifies.
                siblings = {k: walk(v, active) for k, v in node.items() if k != "$ref"}
                return {**target, **siblings}  # type: ignore[dict-item]
            return {k: walk(v, active) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [walk(v, active) for v in node]
        return node

    try:
        return walk(schema, frozenset())  # type: ignore[return-value]
    except _CyclicSchema:
        # A schema referencing a `$defs` block we just deleted is worse than the one we
        # started with, and the original already says truthfully what shape it is.
        return schema


class StructuredOutputError(BedrockGatewayError):
    """Raised after the provider's raw output failed Pydantic validation and the single
    repair retry (SPEC §5.25.3) also failed.

    `schema_errors` is the D-243 addition: which fields broke which rules. Before it, every
    failure of this kind reached the caller as one constant sentence, so the pipeline's
    single largest loss - 41% of authored candidates, measured in D-240 - was recorded 28
    times without once recording a cause. The digest is also folded into the message, so a
    caller that only flattens the exception to a string benefits without being changed.
    """

    def __init__(
        self,
        message: str,
        *,
        cost_cents: float = 0.0,
        schema_errors: list[str] | None = None,
    ) -> None:
        detail = f"{message} [{', '.join(schema_errors)}]" if schema_errors else message
        super().__init__(detail, cost_cents=cost_cents)
        self.schema_errors: list[str] = list(schema_errors or [])


class OutputTruncatedError(StructuredOutputError):
    """The specific `StructuredOutputError` where the model ran out of output tokens
    mid-response (D-115: the gateway deliberately does not retry, because the same prompt
    under the same ceiling truncates again at full input cost).

    Split out as its own type (D-207) so a caller that *can* honestly retry - by raising
    the ceiling for one attempt, which is the fix D-115 names - can tell this apart from
    "the model produced malformed JSON", where a retry really would be waste. Callers that
    do not care still catch `BedrockGatewayError` and fall back exactly as before.
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
