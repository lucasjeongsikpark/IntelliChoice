"""Phase-transition orchestration for the deterministic learning flow (SPEC §5.5.1).

Node bodies operate on any object exposing `student_external_id`/`topic_id`/`phase`/
`pre_assessment_session_id`/`study_session_id`/`post_assessment_session_id`/
`blocked_session_id` - S6's `LearningState` (`learning_api.graph.state`) satisfies this,
so the S5 logic below was liftable into LangGraph nodes without a rewrite. State
persistence is the caller's job (LangGraph's `PostgresSaver` checkpoints the returned
object, SPEC §5.16); this module has no repository of its own for the session object.

S10 turns the study phase from S5's fixed 5-question batch into a per-skill retry ladder
(SPEC §5.11.7): questions are served one at a time, an unresolved skill escalates through
same-skill retries and an easier prerequisite problem, and each attempt is labeled with one
of the §5.11.7 outcomes. `advance_study` is the single place that labels the last attempt,
recomputes mastery, and decides what to serve next (retry / prerequisite / next base skill /
post-exam) - called on both the immediate-correct path and, after the hint/solution/video
`interrupt()` resumes, the graph's `intervention_choice` node.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol

from intellichoice_curriculum.content import load_curriculum
from intellichoice_db.models.assessment import AssessmentAttempt, AssessmentSession
from intellichoice_db.models.mastery import LearningGain, Mastery, StudyAttempt
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_db.repositories.study import StudyRepository
from intellichoice_observability.metrics import RETRIES, TUTOR_REVIEW_FLAGGED

from learning_api.services import mastery_bootstrap, study_outcomes
from learning_api.services.assessment_builder import build_post_exam
from learning_api.services.grading import (
    ItemAlreadyAnsweredError,
    grade,
    record_assessment_attempt_idempotent,
)
from learning_api.services.learning_gain import LearningGainResult, compute_learning_gain
from learning_api.services.study_plan import build_study_plan, create_study_item


class InvalidPhaseError(Exception):
    """The requested action doesn't apply to the session's current phase."""


class UnknownQuestionVariantError(Exception):
    """AUD-L-11: the submitted `question_variant_id` cannot be answered in this session.

    `reason` separates the two client situations, because the router answers them with
    different status codes and a caller can only act on one of them:

    - `"unknown"` - no such variant exists in the bank. A malformed request: **400**.
    - `"not_served"` - a real variant that is not an item of the session's *current*
      assessment or study session. The session's state is what's wrong, not the id, so this
      is **409**, the same answer `ItemAlreadyAnsweredError` gets. This is the case a stale
      tab and a retry landing after the phase advanced actually produce.

    Required rather than defaulted, on `record_assessment_attempt_idempotent`'s reasoning: a
    new raise site should fail typecheck rather than silently pick one of the two.
    """

    def __init__(
        self, question_variant_id: str, reason: Literal["unknown", "not_served"]
    ) -> None:
        self.question_variant_id = question_variant_id
        self.reason = reason
        super().__init__(
            f"unknown question variant {question_variant_id}"
            if reason == "unknown"
            else f"question variant {question_variant_id} is not an item of this session"
        )


class UnknownExamItemError(Exception):
    """The submitted assessment_item_id doesn't exist (or isn't this session's item)."""


class TopicAlreadySelectedError(Exception):
    """AUD-X-03: this session already built a pre-exam, and the request is not a replay of the
    selection that built it - so serving it would abandon a real exam.
    """

    def __init__(self, selected_topic_id: str | None, phase: str) -> None:
        self.selected_topic_id = selected_topic_id
        self.phase = phase
        super().__init__(
            f"this session already built a pre-exam for topic {selected_topic_id} "
            f"(phase {phase}); use /resume to return to it"
        )


class ExamNotReadyToFinalizeError(Exception):
    """S22 (SPEC §5.9/§5.13): `finalize_exam` was called with unanswered items and no
    `confirm_unanswered=True` - the caller must confirm before they're graded incorrect.
    """

    def __init__(self, unanswered_item_ids: list[str]) -> None:
        self.unanswered_item_ids = unanswered_item_ids
        super().__init__(f"{len(unanswered_item_ids)} unanswered item(s), confirmation required")


class SessionLike(Protocol):
    student_external_id: str | None
    topic_id: str | None
    phase: str
    week_id: str | None
    pre_assessment_session_id: str | None
    study_session_id: str | None
    post_assessment_session_id: str | None
    blocked_session_id: str | None


@dataclass(frozen=True)
class QuestionItemView:
    question_variant_id: str
    display_order: int
    rendered_question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str


@dataclass(frozen=True)
class AnswerResult:
    is_correct: bool
    phase: str
    items: list[QuestionItemView] | None
    learning_gain: LearningGainResult | None
    # Growth-oriented message for a served remediation question (SPEC §5.11.7's "recommend
    # more explicit support" / "easier prerequisite problem"); None otherwise.
    message: str | None = None
    # Only set for a study-phase submission - bridges into the graph's
    # `intervention_choice` node (SPEC §5.11.3), which needs to update this same row
    # with the user's hint/solution/video choice after its own `interrupt()` resumes.
    study_attempt_id: str | None = None
    # S25 (plan §9's episodic emission): set only when `advance_study` labeled a study
    # attempt this call (immediate-correct path here, or the graph's
    # `intervention_choice` node calling `advance_study` itself after a pause) - lets
    # the caller emit a `study_outcome` learning event without a second DB read.
    outcome_label: str | None = None
    target_skill_id: str | None = None
    # S26 (plan §18-L7): set only by `_serve_next_base_or_complete` when it genuinely
    # starts a new target-skill line (never on a same-skill retry/remediation item, and
    # never alongside a `phase="post_exam"` completion) - lets the caller fire a
    # `study_step` stage narrative without a second `study_repo` read to detect the
    # transition itself.
    new_target_skill_id: str | None = None


@dataclass(frozen=True)
class FinalizeResult:
    phase: str
    items: list[QuestionItemView] | None
    learning_gain: LearningGainResult | None
    message: str | None = None
    # S25: which assessment session type this finalize completed, and its raw score -
    # lets the caller emit an `exam_finalized` learning event without recomputing.
    session_type: str = "pre_exam"
    raw_score: float | None = None
    # S26 (plan §18-L7): the freshly built study plan's own weakest-first ranked target
    # skills (§5.11.2 rule 1) - set only on a pre-exam completion, lets the caller build
    # a `pre_outro` narrative's evidence without a second `study_repo` read.
    target_skill_ids: list[str] | None = None


def is_exam_expired(session_row: AssessmentSession, now: datetime) -> bool:
    """SPEC §5.9/§5.13 `AssessmentPolicy.time_limit_seconds` (D-064: timed by default).
    Enforcement is lazy - checked on the next request, not pushed the instant the clock
    hits zero (no background scheduler exists anywhere in this codebase yet).
    """
    if session_row.time_limit_seconds is None:
        return False
    deadline = session_row.started_at + timedelta(seconds=session_row.time_limit_seconds)
    return now >= deadline


async def items_view(question_repo: QuestionRepository, items: list) -> list[QuestionItemView]:
    """One read for every item's variant instead of one per item (AUD-F-31) - this was 10
    of the 47 statements the `select_topic` path issued. `items` order is preserved.
    """
    variants = await question_repo.get_variants([item.question_variant_id for item in items])
    views = []
    for item in items:
        variant = variants.get(item.question_variant_id)
        assert variant is not None
        views.append(
            QuestionItemView(
                question_variant_id=variant.question_variant_id,
                display_order=item.display_order,
                rendered_question=variant.rendered_question,
                option_a=variant.option_a,
                option_b=variant.option_b,
                option_c=variant.option_c,
                option_d=variant.option_d,
            )
        )
    return views


async def _used_template_ids(question_repo: QuestionRepository, items: list) -> set[str]:
    variants = await question_repo.get_variants([item.question_variant_id for item in items])
    assert len(variants) == len({item.question_variant_id for item in items})
    return {variant.question_template_id for variant in variants.values()}


def is_topic_selection_replay(
    *,
    requested_topic_id: str,
    selected_topic_id: str | None,
    pre_assessment_session_id: str | None,
    phase: str,
) -> bool:
    """AUD-X-03: decide what a second `POST /topics` means, from session state alone.

    Returns True for a replay to be served from the exam that already exists, False for a
    first selection to build, and raises `TopicAlreadySelectedError` when it is neither.

    Pure and I/O-free, which is what lets both callers share it: the route pre-flights it off
    the checkpointed state so a refused request never runs a graph turn (the same reason
    AUD-L-10's duplicate-answer check is pre-flighted - a rejected turn still leaves checkpoint
    rows behind), and `graph.nodes.select_topic` calls it again inside the turn, so the
    invariant does not depend on the route remembering to ask.

    The guard is "a pre-exam exists", not "the phase is still pre_exam", deliberately: the
    damage is worse *after* the phase advances, because the rebuild would repoint
    `pre_assessment_session_id` while a study session is already live off the old exam and the
    learning-gain comparison reads both.

    A **blocked** attendance gate builds nothing, so it leaves `pre_assessment_session_id`
    None and a replay re-runs the gate in full. That is load-bearing rather than incidental:
    `AttendanceStatus.UNKNOWN` -> blocked is a routine production state (D-152 §2), and
    re-selecting the topic after a manager marks attendance is how a student recovers (D-154).
    """
    if pre_assessment_session_id is None:
        return False
    if selected_topic_id != requested_topic_id or phase != "pre_exam":
        raise TopicAlreadySelectedError(selected_topic_id, phase)
    return True


# `flow.select_topic` used to live here, with `TopicSelectionResult`, and both were **deleted
# while fixing AUD-X-03** (D-159): they had no callers. `graph/nodes.py:select_topic`
# reimplements the same gate-then-build sequence against `LearningState` and returns a plain
# dict, and that node is the only path `POST /topics` takes. The first draft of this fix
# guarded the dead copy, and the test still measured a second exam being built - which is the
# argument for deleting it rather than leaving a second definition of the phase rules for the
# next reader to fix by mistake. Three imports (`ProfileAdapter`, `build_pre_exam`,
# `check_attendance_gate`) fell unused with it; nothing else in this module used them.
# `is_topic_selection_replay` above stays here, shared by the node and the route.


async def _upsert_skill_mastery(
    *,
    mastery_repo: MasteryRepository,
    student_external_id: str,
    skill_id: str,
    attempts: list[mastery_bootstrap.GradedAttempt],
) -> None:
    await mastery_repo.upsert_mastery(
        Mastery(
            student_external_id=student_external_id,
            skill_id=skill_id,
            raw_accuracy=mastery_bootstrap.raw_accuracy(attempts),
            weighted_score=mastery_bootstrap.weighted_score(attempts),
            accuracy_by_difficulty=mastery_bootstrap.accuracy_by_difficulty(attempts),
            highest_consistent_difficulty=mastery_bootstrap.highest_consistent_difficulty(
                attempts
            ),
            recommended_difficulty=mastery_bootstrap.recommended_difficulty(attempts),
        )
    )


async def _recompute_all_skill_mastery(
    *,
    student_external_id: str,
    pre_assessment_session_id: str | None,
    study_session_id: str | None,
    post_assessment_session_id: str | None,
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
    mastery_repo: MasteryRepository,
    question_repo: QuestionRepository,
) -> None:
    """Recompute bootstrap mastery for every skill touched by the pre-exam, the study phase
    or the post-exam, combining all three (outcome-aware for study attempts - only
    `independent_correct` counts, SPEC §5.10.3/§5.11.5).

    **The post-exam was structurally excluded until D-156 (AUD-L-15).** Mastery is "what
    this student currently knows", and it was computed without the most recent and most
    comprehensive measurement of the cycle. Two things followed. A report could show a skill
    at mastery 1.000 beside "skills to strengthen: that skill", because the pre-exam had it
    right and the post-exam had it wrong and only one of them counted - S36's
    `aud-student-premax`, exactly. And `topic_resolver`, which picks the *next* cycle's
    target skills from `mastery.weighted_score`, chose them without ever seeing how the last
    cycle ended.

    Including it is not free of judgement: the post-exam is also the instrument the learning
    gain is measured with. It stays a clean instrument, because `compute_learning_gain` reads
    the raw pre and post attempts directly and never consults mastery - so nothing about the
    gain calculation becomes circular. What changes is that the number driving *future*
    routing now reflects the whole cycle.
    """
    pre_attempts: list[AssessmentAttempt] = []
    if pre_assessment_session_id is not None:
        pre_attempts = await assessment_repo.get_attempts(pre_assessment_session_id)
    post_attempts: list[AssessmentAttempt] = []
    if post_assessment_session_id is not None:
        post_attempts = await assessment_repo.get_attempts(post_assessment_session_id)
    study_attempts: list[StudyAttempt] = []
    if study_session_id is not None:
        study_attempts = await study_repo.get_attempts(study_session_id)

    pre_graded = await mastery_bootstrap.resolve_graded_attempts(question_repo, pre_attempts)
    post_graded = await mastery_bootstrap.resolve_graded_attempts(question_repo, post_attempts)
    study_graded = await mastery_bootstrap.resolve_graded_attempts(question_repo, study_attempts)
    all_graded = pre_graded + study_graded + post_graded
    for skill_id in {a.skill_id for a in all_graded}:
        await _upsert_skill_mastery(
            mastery_repo=mastery_repo,
            student_external_id=student_external_id,
            skill_id=skill_id,
            attempts=[a for a in all_graded if a.skill_id == skill_id],
        )


async def _submit_pre_exam_answer(
    *,
    learning_session: SessionLike,
    question_variant_id: str,
    selected_option: str,
    response_time_ms: int,
    idempotency_key: str,
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
    mastery_repo: MasteryRepository,
    question_repo: QuestionRepository,
    rng: random.Random,
) -> AnswerResult:
    """S22 (D-064): grades immediately, as before, but no longer auto-transitions the
    phase once every item has an attempt - pre/post exams now require an explicit
    `finalize_exam` call (see below), since with skip/flag/jump navigation "last item
    answered" no longer means "the student is done."
    """
    student_id = learning_session.student_external_id
    assert student_id is not None
    assert learning_session.pre_assessment_session_id is not None

    variant = await question_repo.get_variant(question_variant_id)
    if variant is None:
        raise UnknownQuestionVariantError(question_variant_id, "unknown")

    await ensure_item_is_served(
        assessment_repo, learning_session.pre_assessment_session_id, question_variant_id
    )
    await ensure_item_unanswered(
        assessment_repo,
        learning_session.pre_assessment_session_id,
        question_variant_id,
        idempotency_key,
    )
    attempt, _ = await record_assessment_attempt_idempotent(
        assessment_repo=assessment_repo,
        student_external_id=student_id,
        assessment_session_id=learning_session.pre_assessment_session_id,
        question_variant_id=question_variant_id,
        correct_option=variant.correct_option,
        selected_option=selected_option,
        response_time_ms=response_time_ms,
        idempotency_key=idempotency_key,
        on_duplicate_item="conflict",
    )
    await _mark_item_answered(
        assessment_repo, learning_session.pre_assessment_session_id, question_variant_id
    )

    return AnswerResult(
        is_correct=attempt.is_correct, phase="pre_exam", items=None, learning_gain=None
    )


async def ensure_item_is_served(
    assessment_repo: AssessmentRepository,
    assessment_session_id: str,
    question_variant_id: str,
) -> None:
    """AUD-L-17 (found while fixing AUD-L-11): refuse an answer to a variant that is not one
    of this exam's items.

    The exam paths checked only that the variant *exists*, so a real variant belonging to
    some other exam was graded and inserted into `assessment_attempts` for this one -
    `_mark_item_answered` then silently no-ops, since there is no item to mark. That is an
    11th attempt on a 10-item exam, moving the same attempt-counted scoring denominator
    AUD-L-10 was fixed to protect. The study path already had this check
    (`_record_study_attempt`); the exam paths did not.

    Public for the same reason as `ensure_item_unanswered`: the route pre-flights it so a
    stale client gets a clean 409 without a graph turn, and `flow` re-checks so the invariant
    does not depend on which caller reaches the service.
    """
    items = await assessment_repo.get_items(assessment_session_id)
    if not any(item.question_variant_id == question_variant_id for item in items):
        raise UnknownQuestionVariantError(question_variant_id, "not_served")


async def ensure_item_unanswered(
    assessment_repo: AssessmentRepository,
    assessment_session_id: str,
    question_variant_id: str,
    idempotency_key: str,
) -> None:
    """AUD-L-10: refuse a second answer to an item that already has one.

    Public because the route pre-flights it before `graph.ainvoke`, so the ordinary
    duplicate-click case gets a clean 409 without a graph turn. Called here too, so the
    invariant does not depend on which caller reaches the service.

    This is a read-then-act check and therefore *not* the enforcement - two concurrent
    submissions under different keys can both pass it. `uq_assessment_attempts_session_
    variant` is what makes the invariant true; this exists to turn the common case into a
    409 rather than an IntegrityError.
    """
    replay = await assessment_repo.get_attempt_by_idempotency_key(
        assessment_session_id, question_variant_id, idempotency_key
    )
    if replay is not None:
        # A retry of this exact submission - `record_assessment_attempt_idempotent` will
        # serve the stored result (SPEC §5.9.2). Not a second answer.
        return
    attempts = await assessment_repo.get_attempts(assessment_session_id)
    if any(a.question_variant_id == question_variant_id for a in attempts):
        raise ItemAlreadyAnsweredError(question_variant_id)


async def _mark_item_answered(
    assessment_repo: AssessmentRepository, assessment_session_id: str, question_variant_id: str
) -> None:
    items = await assessment_repo.get_items(assessment_session_id)
    item = next((i for i in items if i.question_variant_id == question_variant_id), None)
    if item is not None:
        await assessment_repo.set_item_status(item.assessment_item_id, "answered")


async def _complete_pre_exam(
    *,
    learning_session: SessionLike,
    attempts: list[AssessmentAttempt],
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
    mastery_repo: MasteryRepository,
    question_repo: QuestionRepository,
    rng: random.Random,
    memory_repo: MemoryRepository | None = None,
) -> FinalizeResult:
    """The pre-exam-complete tail (SPEC §5.10.1 mastery bootstrap + study plan build) -
    shared by `finalize_exam` (the only caller now that per-answer auto-advance is gone,
    S22/D-064).
    """
    student_id = learning_session.student_external_id
    assert student_id is not None
    assert learning_session.pre_assessment_session_id is not None
    assert learning_session.topic_id is not None

    # Bootstrap mastery from the completed pre-exam (§5.10.1), including recommended
    # difficulty, so the study plan can rank/route by it.
    graded = await mastery_bootstrap.resolve_graded_attempts(question_repo, attempts)
    for skill_id in {a.skill_id for a in graded}:
        await _upsert_skill_mastery(
            mastery_repo=mastery_repo,
            student_external_id=student_id,
            skill_id=skill_id,
            attempts=[a for a in graded if a.skill_id == skill_id],
        )

    items = await assessment_repo.get_items(learning_session.pre_assessment_session_id)
    used_template_ids = await _used_template_ids(question_repo, items)
    study_session = await build_study_plan(
        question_repo=question_repo,
        mastery_repo=mastery_repo,
        study_repo=study_repo,
        student_external_id=student_id,
        topic_id=learning_session.topic_id,
        used_template_ids=used_template_ids,
        rng=rng,
        memory_repo=memory_repo,
    )
    learning_session.study_session_id = study_session.study_session_id
    learning_session.phase = "study"

    # Serve only the first study question; the rest are served one at a time as the retry
    # ladder progresses (SPEC §5.11.7).
    study_items = await study_repo.get_items(study_session.study_session_id)
    raw_score = (sum(1 for a in attempts if a.is_correct) / len(attempts)) if attempts else None
    return FinalizeResult(
        phase="study",
        items=await items_view(question_repo, study_items),
        learning_gain=None,
        session_type="pre_exam",
        raw_score=raw_score,
        target_skill_ids=study_session.target_skill_ids,
    )


def _support_history(line_attempts: list[StudyAttempt]) -> frozenset[str]:
    """The set of supports (hint/video/solution) used across a skill line's attempts."""
    supports: set[str] = set()
    for attempt in line_attempts:
        if attempt.hint_used:
            supports.add(study_outcomes.HINT)
        if attempt.video_used:
            supports.add(study_outcomes.VIDEO)
        if attempt.solution_used:
            supports.add(study_outcomes.SOLUTION)
    return frozenset(supports)


async def _record_study_attempt(
    *,
    learning_session: SessionLike,
    question_variant_id: str,
    selected_option: str,
    study_repo: StudyRepository,
    question_repo: QuestionRepository,
) -> tuple[bool, StudyAttempt]:
    """Grades the study-phase answer and writes the raw attempt (the misconception is
    recorded even for a wrong answer, SPEC §5.11.3). Labeling and mastery are deferred to
    `advance_study`, which runs after the hint/solution/video choice is known.
    """
    student_id = learning_session.student_external_id
    assert student_id is not None
    assert learning_session.study_session_id is not None

    variant = await question_repo.get_variant(question_variant_id)
    if variant is None:
        raise UnknownQuestionVariantError(question_variant_id, "unknown")

    items = await study_repo.get_items(learning_session.study_session_id)
    item_by_variant = {item.question_variant_id: item for item in items}
    this_item = item_by_variant.get(question_variant_id)
    if this_item is None:
        raise UnknownQuestionVariantError(question_variant_id, "not_served")

    prior_attempts = await study_repo.get_attempts(learning_session.study_session_id)
    prior_line = [
        a
        for a in prior_attempts
        if item_by_variant[a.question_variant_id].target_skill_id == this_item.target_skill_id
    ]

    is_correct = grade(selected_option, variant.correct_option)
    attempt = await study_repo.record_attempt(
        StudyAttempt(
            student_external_id=student_id,
            study_session_id=learning_session.study_session_id,
            question_variant_id=question_variant_id,
            selected_option=selected_option,
            is_correct=is_correct,
            retry_count=len(prior_line),
        )
    )
    return is_correct, attempt


async def _serve_next_base_or_complete(
    *,
    learning_session: SessionLike,
    is_correct: bool,
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
    question_repo: QuestionRepository,
    mastery_repo: MasteryRepository,
    rng: random.Random,
    outcome_label: str | None = None,
    target_skill_id: str | None = None,
) -> AnswerResult:
    """Every target skill's line is resolved: serve the next not-yet-started base skill, or
    if all base skills are done, build the parallel-form post-exam (SPEC §5.13.1).

    `outcome_label`/`target_skill_id` (S25) describe the just-resolved line, not the
    question this call serves next - passed through so the caller can emit one
    `study_outcome` learning event without a second DB read.

    `mastery_repo` (AUD-L-12) is read here rather than passed in as a value, so the next
    base skill is served at the tier its *current* `recommended_difficulty` names: the sole
    caller runs `_recompute_all_skill_mastery` before this, so the row reflects every
    attempt so far including the one just graded.
    """
    assert learning_session.study_session_id is not None
    session_row = await study_repo.get_study_session(learning_session.study_session_id)
    assert session_row is not None
    items = await study_repo.get_items(learning_session.study_session_id)
    served_targets = {item.target_skill_id for item in items}

    next_target = next(
        (skill_id for skill_id in session_row.target_skill_ids if skill_id not in served_targets),
        None,
    )
    if next_target is not None:
        used = await _used_template_ids(question_repo, items)
        next_mastery = await mastery_repo.get_mastery(
            learning_session.student_external_id or "", next_target
        )
        item = await create_study_item(
            question_repo=question_repo,
            study_repo=study_repo,
            study_session_id=learning_session.study_session_id,
            target_skill_id=next_target,
            skill_id=next_target,
            display_order=len(items),
            is_remediation=False,
            used_template_ids=used,
            rng=rng,
            recommended_difficulty=(
                next_mastery.recommended_difficulty if next_mastery is not None else None
            ),
        )
        learning_session.phase = "study"
        return AnswerResult(
            is_correct=is_correct,
            phase="study",
            items=await items_view(question_repo, [item]),
            learning_gain=None,
            outcome_label=outcome_label,
            target_skill_id=target_skill_id,
            new_target_skill_id=next_target,
        )

    student_id = learning_session.student_external_id
    assert student_id is not None
    assert learning_session.pre_assessment_session_id is not None
    post_exam = await build_post_exam(
        question_repo=question_repo,
        assessment_repo=assessment_repo,
        student_external_id=student_id,
        pre_assessment_session_id=learning_session.pre_assessment_session_id,
        rng=rng,
    )
    learning_session.post_assessment_session_id = post_exam.assessment_session_id
    learning_session.phase = "post_exam"
    post_items = await assessment_repo.get_items(post_exam.assessment_session_id)
    return AnswerResult(
        is_correct=is_correct,
        phase="post_exam",
        items=await items_view(question_repo, post_items),
        learning_gain=None,
        outcome_label=outcome_label,
        target_skill_id=target_skill_id,
    )


async def advance_study(
    *,
    learning_session: SessionLike,
    last_attempt_id: str,
    is_correct: bool,
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
    mastery_repo: MasteryRepository,
    question_repo: QuestionRepository,
    rng: random.Random,
) -> AnswerResult:
    """Label the last study attempt, recompute mastery, and drive the §5.11.7 retry ladder.

    Called on both the immediate-correct path (`_submit_study_answer`) and, after the
    hint/solution/video `interrupt()` resumes, the graph's `intervention_choice` node -
    which by then has set the attempt's support flags, so `_support_history` reflects them.
    """
    assert learning_session.study_session_id is not None
    ss_id = learning_session.study_session_id

    items = await study_repo.get_items(ss_id)
    attempts = await study_repo.get_attempts(ss_id)
    item_by_variant = {item.question_variant_id: item for item in items}
    last_attempt = next(a for a in attempts if a.attempt_id == last_attempt_id)
    target_skill_id = item_by_variant[last_attempt.question_variant_id].target_skill_id
    line_attempts = [
        a
        for a in attempts
        if item_by_variant[a.question_variant_id].target_skill_id == target_skill_id
    ]
    support_history = _support_history(line_attempts)

    message: str | None = None
    step: study_outcomes.LadderStep | None = None
    if is_correct:
        outcome_label = study_outcomes.correct_label(support_history)
        await study_repo.set_outcome(last_attempt_id, outcome_label=outcome_label)
        resolved = True
    else:
        step = study_outcomes.ladder_step(len(line_attempts))
        if step.kind == "exhausted":
            outcome_label = study_outcomes.UNRESOLVED
            await study_repo.set_outcome(
                last_attempt_id,
                outcome_label=outcome_label,
                tutor_review_flagged=True,
            )
            resolved = True
            TUTOR_REVIEW_FLAGGED.inc()
        else:
            outcome_label = study_outcomes.incorrect_label(support_history, terminal=False)
            await study_repo.set_outcome(last_attempt_id, outcome_label=outcome_label)
            resolved = False
            RETRIES.inc()

    # Mastery is recomputed with the label now final, so an assisted/unresolved answer never
    # inflates independent mastery.
    await _recompute_all_skill_mastery(
        student_external_id=learning_session.student_external_id or "",
        pre_assessment_session_id=learning_session.pre_assessment_session_id,
        study_session_id=ss_id,
        # Always None here - the post-exam does not exist yet during study. Passed
        # explicitly rather than defaulted so that a future caller has to say what it
        # means, which is how the post-exam went missing in the first place.
        post_assessment_session_id=learning_session.post_assessment_session_id,
        assessment_repo=assessment_repo,
        study_repo=study_repo,
        mastery_repo=mastery_repo,
        question_repo=question_repo,
    )

    if not resolved:
        assert step is not None
        skill_for_item = target_skill_id
        message = step.support_recommendation
        if step.kind == "prerequisite":
            prereq = load_curriculum().prerequisite_for(target_skill_id)
            # Only drop to the prerequisite if it actually has approved templates;
            # otherwise there's nothing easier to serve, so retry the same skill.
            if prereq is not None and await question_repo.get_active_questions_for_skill(prereq):
                skill_for_item = prereq
        used = await _used_template_ids(question_repo, items)
        item = await create_study_item(
            question_repo=question_repo,
            study_repo=study_repo,
            study_session_id=ss_id,
            target_skill_id=target_skill_id,
            skill_id=skill_for_item,
            display_order=len(items),
            is_remediation=True,
            used_template_ids=used,
            rng=rng,
            # No difficulty routing on the remediation path (AUD-L-12). The retry ladder is
            # already an explicit difficulty policy - same skill, then the prerequisite one
            # tier down - and applying the bootstrap recommendation on top could pull a
            # deliberate step-down back up, or keep re-serving the tier the student is
            # failing right now. §5.11.2 rules 2-3 describe choosing a *starting* question.
            recommended_difficulty=None,
        )
        learning_session.phase = "study"
        return AnswerResult(
            is_correct=is_correct,
            phase="study",
            items=await items_view(question_repo, [item]),
            learning_gain=None,
            message=message,
            outcome_label=outcome_label,
            target_skill_id=target_skill_id,
        )

    return await _serve_next_base_or_complete(
        learning_session=learning_session,
        is_correct=is_correct,
        assessment_repo=assessment_repo,
        study_repo=study_repo,
        question_repo=question_repo,
        mastery_repo=mastery_repo,
        rng=rng,
        outcome_label=outcome_label,
        target_skill_id=target_skill_id,
    )


async def _submit_study_answer(
    *,
    learning_session: SessionLike,
    question_variant_id: str,
    selected_option: str,
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
    mastery_repo: MasteryRepository,
    question_repo: QuestionRepository,
    rng: random.Random,
) -> AnswerResult:
    is_correct, attempt = await _record_study_attempt(
        learning_session=learning_session,
        question_variant_id=question_variant_id,
        selected_option=selected_option,
        study_repo=study_repo,
        question_repo=question_repo,
    )

    if not is_correct:
        # SPEC §5.11.3: pause for the hint/solution/video choice before advancing - the
        # graph routes this to a dedicated `interrupt()` node (`learning_api.graph.nodes.
        # intervention_choice`), which calls `advance_study` itself once resumed.
        return AnswerResult(
            is_correct=False,
            phase="study",
            items=None,
            learning_gain=None,
            study_attempt_id=attempt.attempt_id,
        )

    return await advance_study(
        learning_session=learning_session,
        last_attempt_id=attempt.attempt_id,
        is_correct=True,
        assessment_repo=assessment_repo,
        study_repo=study_repo,
        mastery_repo=mastery_repo,
        question_repo=question_repo,
        rng=rng,
    )


async def _submit_post_exam_answer(
    *,
    learning_session: SessionLike,
    question_variant_id: str,
    selected_option: str,
    response_time_ms: int,
    idempotency_key: str,
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
    mastery_repo: MasteryRepository,
    question_repo: QuestionRepository,
) -> AnswerResult:
    """S22 (D-064): grades immediately, no longer auto-transitions on the last answer -
    see `_submit_pre_exam_answer`'s docstring for why.
    """
    student_id = learning_session.student_external_id
    assert student_id is not None
    assert learning_session.post_assessment_session_id is not None
    assert learning_session.pre_assessment_session_id is not None

    variant = await question_repo.get_variant(question_variant_id)
    if variant is None:
        raise UnknownQuestionVariantError(question_variant_id, "unknown")

    await ensure_item_is_served(
        assessment_repo, learning_session.post_assessment_session_id, question_variant_id
    )
    await ensure_item_unanswered(
        assessment_repo,
        learning_session.post_assessment_session_id,
        question_variant_id,
        idempotency_key,
    )
    attempt, _ = await record_assessment_attempt_idempotent(
        assessment_repo=assessment_repo,
        student_external_id=student_id,
        assessment_session_id=learning_session.post_assessment_session_id,
        question_variant_id=question_variant_id,
        correct_option=variant.correct_option,
        selected_option=selected_option,
        response_time_ms=response_time_ms,
        idempotency_key=idempotency_key,
        on_duplicate_item="conflict",
    )
    await _mark_item_answered(
        assessment_repo, learning_session.post_assessment_session_id, question_variant_id
    )

    return AnswerResult(
        is_correct=attempt.is_correct, phase="post_exam", items=None, learning_gain=None
    )


async def _complete_post_exam(
    *,
    learning_session: SessionLike,
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
    mastery_repo: MasteryRepository,
    question_repo: QuestionRepository,
) -> FinalizeResult:
    """The post-exam-complete tail (SPEC §5.13.3 learning-gain compute) - shared by
    `finalize_exam` (S22/D-064).
    """
    student_id = learning_session.student_external_id
    assert student_id is not None
    assert learning_session.post_assessment_session_id is not None
    assert learning_session.pre_assessment_session_id is not None

    pre_attempts = await assessment_repo.get_attempts(learning_session.pre_assessment_session_id)
    post_attempts = await assessment_repo.get_attempts(learning_session.post_assessment_session_id)
    study_attempts = await study_repo.get_attempts(learning_session.study_session_id or "")
    gain = await compute_learning_gain(
        question_repo=question_repo,
        pre_attempts=pre_attempts,
        post_attempts=post_attempts,
        study_attempts=study_attempts,
    )
    await mastery_repo.record_learning_gain(
        LearningGain(
            student_external_id=student_id,
            pre_assessment_session_id=learning_session.pre_assessment_session_id,
            post_assessment_session_id=learning_session.post_assessment_session_id,
            study_session_id=learning_session.study_session_id,
            topic_id=learning_session.topic_id,
            pre_raw_score=gain.pre_raw_score,
            post_raw_score=gain.post_raw_score,
            raw_gain=gain.raw_gain,
            weighted_gain=gain.weighted_gain,
            normalized_gain=gain.normalized_gain,
            normalized_gain_status=gain.normalized_gain_status,
            skill_level_gain=gain.skill_level_gain,
            difficulty_transition=gain.difficulty_transition,
            independent_correct_rate=gain.independent_correct_rate,
            hint_dependency=gain.hint_dependency,
            solution_dependency=gain.solution_dependency,
            unresolved_skills=gain.unresolved_skills,
            response_time_change_ms=gain.response_time_change_ms,
        )
    )

    # AUD-L-15 (D-156): fold the post-exam into mastery. Deliberately *after* the learning
    # gain is computed and recorded above - the gain reads raw attempts, not mastery, so the
    # order does not change it, but keeping mastery downstream of the gain makes it obvious
    # at a glance that the instrument was read before the thing it measures was updated.
    #
    # This is also the last write before `finalize_exam`'s memory consolidation runs, which
    # is what AUD-L-13's consistency floor needs: it screens proposed ability facts against
    # `mastery.weighted_score`, and those scores now include the cycle that just produced
    # the facts.
    await _recompute_all_skill_mastery(
        student_external_id=student_id,
        pre_assessment_session_id=learning_session.pre_assessment_session_id,
        study_session_id=learning_session.study_session_id,
        post_assessment_session_id=learning_session.post_assessment_session_id,
        assessment_repo=assessment_repo,
        study_repo=study_repo,
        mastery_repo=mastery_repo,
        question_repo=question_repo,
    )

    learning_session.phase = "completed"

    return FinalizeResult(
        phase="completed",
        items=None,
        learning_gain=gain,
        session_type="post_exam",
        raw_score=gain.post_raw_score,
    )


async def mark_item_skipped(
    assessment_repo: AssessmentRepository, assessment_session_id: str, assessment_item_id: str
) -> None:
    await _validate_item_in_session(assessment_repo, assessment_session_id, assessment_item_id)
    await assessment_repo.set_item_status(assessment_item_id, "skipped")


async def mark_item_flagged(
    assessment_repo: AssessmentRepository,
    assessment_session_id: str,
    assessment_item_id: str,
    flagged: bool,
) -> None:
    await _validate_item_in_session(assessment_repo, assessment_session_id, assessment_item_id)
    state = await assessment_repo.get_item_state(assessment_item_id)
    assert state is not None
    if state.status == "answered":
        # Answered items are locked (grade-on-submit, D-064) - flag is a no-op, not an
        # error, since a client might race a flag click with an in-flight answer.
        return
    await assessment_repo.set_item_status(assessment_item_id, "flagged" if flagged else "unseen")


async def record_item_time(
    assessment_repo: AssessmentRepository,
    assessment_session_id: str,
    assessment_item_id: str,
    elapsed_ms: int,
) -> None:
    """S23 autosave tick (plan §18-L4, PROGRESS.md S22 carry-over): accumulates time spent
    on an exam item, same "plain repository write, not a graph turn" precedent as
    skip/flag - navigation timing has no routing consequence.
    """
    await _validate_item_in_session(assessment_repo, assessment_session_id, assessment_item_id)
    await assessment_repo.add_item_time(assessment_item_id, elapsed_ms)


async def _validate_item_in_session(
    assessment_repo: AssessmentRepository, assessment_session_id: str, assessment_item_id: str
) -> None:
    items = await assessment_repo.get_items(assessment_session_id)
    if not any(item.assessment_item_id == assessment_item_id for item in items):
        raise UnknownExamItemError(assessment_item_id)


async def finalize_exam(
    *,
    learning_session: SessionLike,
    confirm_unanswered: bool,
    now: datetime,
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
    mastery_repo: MasteryRepository,
    question_repo: QuestionRepository,
    rng: random.Random,
    memory_repo: MemoryRepository | None = None,
) -> FinalizeResult | None:
    """S22/D-064: the explicit "submit exam" action. Grading already happened per-item
    (grade-on-submit was kept); this just (a) synthesizes an incorrect attempt for any
    item the student skipped through to the end, gated on `confirm_unanswered` unless the
    timer has already expired, and (b) runs the same phase-completion tail that used to
    fire automatically on the last answer.

    Returns `None` if the target assessment session was already finalized - the caller
    (the graph node) should then no-op and re-serve the existing state verbatim (same
    "re-serve idempotently from checkpoint" pattern `resume_view` uses), never recomputing
    or re-running the completion tail twice.

    A retried call can arrive *after* the phase has already visibly advanced past
    "pre_exam"/"post_exam" (a dropped response, or two near-simultaneous requests) - the
    dispatch below still resolves the right target session in that case rather than
    raising, since `phase == "study"` only ever happens after `_complete_pre_exam` already
    ran (same for `"completed"`/post-exam), so that session is always already finalized
    and this correctly falls through to the idempotent no-op below.
    """
    if learning_session.phase == "pre_exam":
        session_type = "pre_exam"
        assessment_session_id = learning_session.pre_assessment_session_id
    elif learning_session.phase == "post_exam":
        session_type = "post_exam"
        assessment_session_id = learning_session.post_assessment_session_id
    elif learning_session.phase == "study":
        session_type = "pre_exam"
        assessment_session_id = learning_session.pre_assessment_session_id
    elif learning_session.phase == "completed":
        session_type = "post_exam"
        assessment_session_id = learning_session.post_assessment_session_id
    else:
        raise InvalidPhaseError(learning_session.phase)
    assert assessment_session_id is not None

    session_row = await assessment_repo.get_session(assessment_session_id)
    assert session_row is not None
    if session_row.finalized_at is not None:
        return None

    student_id = learning_session.student_external_id
    assert student_id is not None

    items = await assessment_repo.get_items(assessment_session_id)
    attempts = await assessment_repo.get_attempts(assessment_session_id)
    answered_variant_ids = {a.question_variant_id for a in attempts}
    unanswered_items = [
        item for item in items if item.question_variant_id not in answered_variant_ids
    ]

    expired = is_exam_expired(session_row, now)
    if unanswered_items and not (confirm_unanswered or expired):
        raise ExamNotReadyToFinalizeError([item.assessment_item_id for item in unanswered_items])

    for item in unanswered_items:
        variant = await question_repo.get_variant(item.question_variant_id)
        assert variant is not None
        await record_assessment_attempt_idempotent(
            assessment_repo=assessment_repo,
            student_external_id=student_id,
            assessment_session_id=assessment_session_id,
            question_variant_id=item.question_variant_id,
            correct_option=variant.correct_option,
            selected_option=None,
            response_time_ms=0,
            idempotency_key=f"finalize-unanswered-{item.assessment_item_id}",
            # A concurrent finalize that got there first has already synthesized this
            # item's incorrect attempt; that row is the right one to keep.
            on_duplicate_item="keep_existing",
        )
        await assessment_repo.set_item_status(item.assessment_item_id, "answered")

    await assessment_repo.mark_finalized(assessment_session_id, now)
    final_attempts = await assessment_repo.get_attempts(assessment_session_id)

    if session_type == "pre_exam":
        return await _complete_pre_exam(
            learning_session=learning_session,
            attempts=final_attempts,
            assessment_repo=assessment_repo,
            study_repo=study_repo,
            mastery_repo=mastery_repo,
            question_repo=question_repo,
            rng=rng,
            memory_repo=memory_repo,
        )
    return await _complete_post_exam(
        learning_session=learning_session,
        assessment_repo=assessment_repo,
        study_repo=study_repo,
        mastery_repo=mastery_repo,
        question_repo=question_repo,
    )


async def submit_answer(
    *,
    learning_session: SessionLike,
    question_variant_id: str,
    selected_option: str,
    response_time_ms: int,
    idempotency_key: str,
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
    mastery_repo: MasteryRepository,
    question_repo: QuestionRepository,
    rng: random.Random,
) -> AnswerResult:
    if learning_session.phase == "pre_exam":
        return await _submit_pre_exam_answer(
            learning_session=learning_session,
            question_variant_id=question_variant_id,
            selected_option=selected_option,
            response_time_ms=response_time_ms,
            idempotency_key=idempotency_key,
            assessment_repo=assessment_repo,
            study_repo=study_repo,
            mastery_repo=mastery_repo,
            question_repo=question_repo,
            rng=rng,
        )

    if learning_session.phase == "study":
        return await _submit_study_answer(
            learning_session=learning_session,
            question_variant_id=question_variant_id,
            selected_option=selected_option,
            assessment_repo=assessment_repo,
            study_repo=study_repo,
            mastery_repo=mastery_repo,
            question_repo=question_repo,
            rng=rng,
        )

    if learning_session.phase == "post_exam":
        return await _submit_post_exam_answer(
            learning_session=learning_session,
            question_variant_id=question_variant_id,
            selected_option=selected_option,
            response_time_ms=response_time_ms,
            idempotency_key=idempotency_key,
            assessment_repo=assessment_repo,
            study_repo=study_repo,
            mastery_repo=mastery_repo,
            question_repo=question_repo,
        )

    raise InvalidPhaseError(learning_session.phase)
