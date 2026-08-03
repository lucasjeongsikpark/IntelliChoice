import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from intellichoice_db.models.assessment import (
    AssessmentAttempt,
    AssessmentItem,
    AssessmentItemState,
    AssessmentSession,
)
from intellichoice_db.models.assessment import BlockedSession as BlockedSessionModel
from intellichoice_db.models.chat import ChatSuggestion
from intellichoice_db.models.curriculum import Skill, Topic
from intellichoice_db.models.evaluation import EvaluationResult
from intellichoice_db.models.hints import HintEvent
from intellichoice_db.models.interrupts import InterruptApproval
from intellichoice_db.models.mastery import (
    LearningGain,
    Mastery,
    StudyAttempt,
    StudyItem,
    StudySession,
)
from intellichoice_db.models.mcp import McpToolCall
from intellichoice_db.models.memory import LearningEvent, SemanticMemory
from intellichoice_db.models.org import OrgBranch, OrgEvent, OrgTeamMember
from intellichoice_db.models.questions import (
    QuestionTemplate,
    QuestionValidationRun,
    QuestionVariant,
)
from intellichoice_db.models.rag import RagChunk, RagDocument
from intellichoice_db.models.reports import ProblemReport
from intellichoice_db.models.stage_transition import StageTransition
from intellichoice_db.models.student_report import StudentReport
from intellichoice_db.models.tutor_chat import TutorChatMessage
from intellichoice_db.models.youtube import YoutubeVideo
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.chat import ChatSuggestionRepository
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.evaluation import EvaluationRepository
from intellichoice_db.repositories.hints import HintEventRepository
from intellichoice_db.repositories.interrupts import InterruptApprovalRepository
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.org import (
    OrgBranchRepository,
    OrgEventRepository,
    OrgTeamMemberRepository,
)
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_db.repositories.rag import ChunkFilters, RagRepository
from intellichoice_db.repositories.reports import ReportRepository
from intellichoice_db.repositories.stage_transition import StageTransitionRepository
from intellichoice_db.repositories.student_report import StudentReportRepository
from intellichoice_db.repositories.study import StudyRepository
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository
from intellichoice_db.repositories.youtube import YoutubeRepository
from intellichoice_shared.mcp import ToolCallAuditEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import postgres_skip_reason, rollback_session

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)


@dataclass
class QuestionChain:
    topic_id: str
    skill_id: str
    question_template_id: str
    question_variant_id: str


async def _seed_question_chain(session: AsyncSession) -> QuestionChain:
    curriculum = CurriculumRepository(session)
    questions = QuestionRepository(session)

    topic = await curriculum.create_topic(
        Topic(curriculum_version="v1", name="Linear Equations", grade_band="6-8")
    )
    skill = await curriculum.create_skill(
        Skill(topic_id=topic.topic_id, name="linear_equation_inverse_operation")
    )
    template = await questions.create_template(
        QuestionTemplate(
            curriculum_version="v1",
            topic_id=topic.topic_id,
            skill_id=skill.skill_id,
            grade_band="6-8",
            difficulty_label=2,
            difficulty_confidence=0.9,
            parameter_schema={"a": "int"},
            solution_function="solve_linear",
            correct_option_generator="gen_correct",
            estimated_time_seconds=60,
            generator_model="mock-generator",
            validation_status="approved",
            active_status="active",
        )
    )
    variant = await questions.create_variant(
        QuestionVariant(
            question_template_id=template.question_template_id,
            random_seed=1,
            rendered_question="2x + 3 = 11",
            option_a="4",
            option_b="5",
            option_c="6",
            option_d="7",
            correct_option="a",
            parameter_values={"a": 2},
        )
    )
    return QuestionChain(
        topic_id=topic.topic_id,
        skill_id=skill.skill_id,
        question_template_id=template.question_template_id,
        question_variant_id=variant.question_variant_id,
    )


def test_curriculum_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = CurriculumRepository(session)
            topic = await repo.create_topic(
                Topic(curriculum_version="v1", name="Fractions", grade_band="4-5")
            )
            skill = await repo.create_skill(
                Skill(topic_id=topic.topic_id, name="fraction_common_denominator")
            )

            fetched_topic = await repo.get_topic(topic.topic_id)
            fetched_skill = await repo.get_skill(skill.skill_id)

            assert fetched_topic is not None
            assert fetched_topic.name == "Fractions"
            assert fetched_skill is not None
            assert fetched_skill.topic_id == topic.topic_id

    asyncio.run(run())


def test_question_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            questions = QuestionRepository(session)

            fetched_variant = await questions.get_variant(chain.question_variant_id)
            active = await questions.get_active_questions(topic_id=chain.topic_id, difficulty=2)

            assert fetched_variant is not None
            assert fetched_variant.rendered_question == "2x + 3 = 11"
            assert len(active) == 1
            assert active[0].question_template_id == chain.question_template_id

    asyncio.run(run())


def test_question_validation_run_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            questions = QuestionRepository(session)

            persisted_run = await questions.create_validation_run(
                QuestionValidationRun(
                    question_template_id=chain.question_template_id,
                    outcome="pending",
                    stage_results={"deterministic_gate": {"passed": True, "failures": []}},
                    reasons=[],
                    cost_cents=1.23,
                )
            )
            # S20 (plan §7): a candidate rejected before a template ever exists still
            # gets its own append-only audit row, with no template to attach to.
            rejected_run = await questions.create_validation_run(
                QuestionValidationRun(
                    question_template_id=None,
                    outcome="rejected",
                    stage_results={},
                    reasons=["two correct options"],
                    cost_cents=0.5,
                )
            )

            fetched = await questions.get_latest_validation_run(chain.question_template_id)
            assert fetched is not None
            assert fetched.question_validation_run_id == persisted_run.question_validation_run_id
            assert rejected_run.question_template_id is None
            assert rejected_run.reasons == ["two correct options"]

    asyncio.run(run())


def test_question_repository_authored_helpers() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            questions = QuestionRepository(session)

            embedding = [0.1] * 1024
            authored = await questions.create_template(
                QuestionTemplate(
                    curriculum_version="v1",
                    topic_id=chain.topic_id,
                    skill_id=chain.skill_id,
                    grade_band="6-8",
                    difficulty_label=2,
                    parameter_schema={},
                    solution_function="authored",
                    correct_option_generator="authored",
                    estimated_time_seconds=45,
                    generator_model="mock-authored-generator",
                    validation_status="pending",
                    active_status="active",
                    authoring_mode="authored",
                    stem="What is 2 + 2?",
                    hint_ladder=["a", "b", "c"],
                    canonical_solution={"steps": [], "final_answer": "4"},
                    stem_embedding=embedding,
                    review_priority="high",
                )
            )
            await questions.create_variant(
                QuestionVariant(
                    question_template_id=authored.question_template_id,
                    random_seed=1,
                    rendered_question="What is 2 + 2?",
                    option_a="4",
                    option_b="5",
                    option_c="6",
                    option_d="3",
                    correct_option="a",
                    parameter_values={},
                )
            )

            pending = await questions.get_pending_authored_by_priority(chain.topic_id)
            assert [t.question_template_id for t in pending] == [authored.question_template_id]

            fetched_variant = await questions.get_variant_for_template(
                authored.question_template_id
            )
            assert fetched_variant is not None
            assert fetched_variant.rendered_question == "What is 2 + 2?"

            assert await questions.stem_near_duplicate_exists(
                chain.topic_id, embedding, threshold=0.01
            )
            far_embedding = [-0.1] * 1024
            assert not await questions.stem_near_duplicate_exists(
                chain.topic_id, far_embedding, threshold=0.01
            )

    asyncio.run(run())


def test_assessment_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            assessments = AssessmentRepository(session)

            exam_session = await assessments.create_session(
                AssessmentSession(student_external_id="student-ext-1", session_type="pre_exam")
            )
            await assessments.add_item(
                AssessmentItem(
                    assessment_session_id=exam_session.assessment_session_id,
                    question_variant_id=chain.question_variant_id,
                    display_order=1,
                )
            )
            await assessments.record_attempt(
                AssessmentAttempt(
                    student_external_id="student-ext-1",
                    assessment_session_id=exam_session.assessment_session_id,
                    question_variant_id=chain.question_variant_id,
                    selected_option="a",
                    correct_option="a",
                    is_correct=True,
                    response_time_ms=4200,
                    idempotency_key="idem-1",
                )
            )
            await assessments.create_blocked_session(
                BlockedSessionModel(
                    student_external_id="student-ext-2",
                    week_id="2026-W29",
                    blocked_reason="absence_acknowledged",
                )
            )

            fetched_session = await assessments.get_session(exam_session.assessment_session_id)
            summary = await assessments.get_student_assessment_summary("student-ext-1")
            items = await assessments.get_items(exam_session.assessment_session_id)
            attempts = await assessments.get_attempts(exam_session.assessment_session_id)
            by_key = await assessments.get_attempt_by_idempotency_key(
                exam_session.assessment_session_id, chain.question_variant_id, "idem-1"
            )
            missing_key = await assessments.get_attempt_by_idempotency_key(
                exam_session.assessment_session_id, chain.question_variant_id, "idem-2"
            )

            assert fetched_session is not None
            assert len(summary) == 1
            assert len(items) == 1
            assert len(attempts) == 1
            assert by_key is not None
            assert by_key.idempotency_key == "idem-1"
            assert missing_key is None

    asyncio.run(run())


def test_assessment_item_state_round_trip() -> None:
    """S22 (SPEC §5.9/§5.13, D-064): the exam nav-bar bookkeeping table, plus the
    finalize-time "unanswered -> incorrect" path's nullable `selected_option`.
    """

    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            assessments = AssessmentRepository(session)

            exam_session = await assessments.create_session(
                AssessmentSession(
                    student_external_id="student-ext-1",
                    session_type="pre_exam",
                    topic_id=chain.topic_id,
                    policy={"session_type": "pre_exam", "time_limit_seconds": 1200},
                    time_limit_seconds=1200,
                )
            )
            item = await assessments.add_item(
                AssessmentItem(
                    assessment_session_id=exam_session.assessment_session_id,
                    question_variant_id=chain.question_variant_id,
                    display_order=1,
                )
            )
            state = await assessments.create_item_state(
                AssessmentItemState(assessment_item_id=item.assessment_item_id, status="unseen")
            )
            assert state.status == "unseen"
            assert state.first_viewed_at is None
            assert state.time_spent_ms == 0

            skipped = await assessments.set_item_status(item.assessment_item_id, "skipped")
            assert skipped.status == "skipped"
            assert skipped.first_viewed_at is not None

            fetched = await assessments.get_item_state(item.assessment_item_id)
            assert fetched is not None
            assert fetched.status == "skipped"

            states = await assessments.get_item_states(exam_session.assessment_session_id)
            assert len(states) == 1

            # D-064: finalize synthesizes an incorrect attempt for an unanswered item with
            # no real selected option.
            unanswered_attempt = await assessments.record_attempt(
                AssessmentAttempt(
                    student_external_id="student-ext-1",
                    assessment_session_id=exam_session.assessment_session_id,
                    question_variant_id=chain.question_variant_id,
                    selected_option=None,
                    correct_option="a",
                    is_correct=False,
                    response_time_ms=0,
                    idempotency_key=f"finalize-unanswered-{item.assessment_item_id}",
                )
            )
            assert unanswered_attempt.selected_option is None
            assert unanswered_attempt.is_correct is False

            finalized = await assessments.mark_finalized(
                exam_session.assessment_session_id, datetime.now()
            )
            assert finalized.finalized_at is not None
            assert finalized.status == "completed"
            assert finalized.completed_at is not None

    asyncio.run(run())


def test_study_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            study = StudyRepository(session)

            study_session = await study.create_study_session(
                StudySession(
                    student_external_id="student-ext-1",
                    topic_id=chain.topic_id,
                    target_skill_ids=[chain.skill_id],
                    starting_difficulty=2,
                    maximum_attempts_per_skill=4,
                )
            )
            await study.add_item(
                StudyItem(
                    study_session_id=study_session.study_session_id,
                    question_variant_id=chain.question_variant_id,
                    display_order=0,
                    target_skill_id=chain.skill_id,
                    skill_id=chain.skill_id,
                    difficulty=2,
                    is_remediation=False,
                )
            )
            attempt = await study.record_attempt(
                StudyAttempt(
                    student_external_id="student-ext-1",
                    study_session_id=study_session.study_session_id,
                    question_variant_id=chain.question_variant_id,
                    selected_option="a",
                    is_correct=True,
                )
            )
            # Exercise the S10 outcome-label writer (SPEC §5.11.7).
            finalized = await study.set_outcome(
                attempt.attempt_id, outcome_label="independent_correct"
            )

            fetched = await study.get_study_session(study_session.study_session_id)
            items = await study.get_items(study_session.study_session_id)
            attempts = await study.get_attempts(study_session.study_session_id)

            assert fetched is not None
            assert fetched.student_external_id == "student-ext-1"
            assert len(items) == 1
            assert items[0].is_remediation is False
            assert len(attempts) == 1
            assert finalized.outcome_label == "independent_correct"
            assert finalized.tutor_review_flagged is False

    asyncio.run(run())


def test_hint_event_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            study = StudyRepository(session)
            hints = HintEventRepository(session)

            study_session = await study.create_study_session(
                StudySession(
                    student_external_id="student-ext-1",
                    topic_id=chain.topic_id,
                    target_skill_ids=[chain.skill_id],
                    starting_difficulty=2,
                    maximum_attempts_per_skill=4,
                )
            )
            attempt = await study.record_attempt(
                StudyAttempt(
                    student_external_id="student-ext-1",
                    study_session_id=study_session.study_session_id,
                    question_variant_id=chain.question_variant_id,
                    selected_option="b",
                    is_correct=False,
                )
            )

            await hints.record(
                HintEvent(
                    student_external_id="student-ext-1",
                    study_attempt_id=attempt.attempt_id,
                    question_variant_id=chain.question_variant_id,
                    hint_level=1,
                    canonical_hint_text="Try the opposite operation.",
                    personalized_hint_text="Try the opposite operation.",
                    misconception_tag="sign_error",
                    was_personalized=False,
                )
            )
            # S20 (D-059)-style nullable-FK precedent doesn't apply here - every hint
            # event always belongs to a real, already-recorded attempt - but a
            # gateway-failure fallback row (`was_personalized=False`) is a real case
            # this repository must round-trip cleanly.
            await hints.record(
                HintEvent(
                    student_external_id="student-ext-1",
                    study_attempt_id=attempt.attempt_id,
                    question_variant_id=chain.question_variant_id,
                    hint_level=2,
                    canonical_hint_text="Subtract the number added to x from both sides.",
                    personalized_hint_text="Since you picked an option with the wrong sign, "
                    "subtract the number added to x from both sides.",
                    misconception_tag="sign_error",
                    was_personalized=True,
                )
            )

            events = await hints.get_events_for_attempt(attempt.attempt_id)

            assert [e.hint_level for e in events] == [1, 2]
            assert events[0].was_personalized is False
            assert events[1].was_personalized is True
            assert all(e.student_external_id == "student-ext-1" for e in events)

    asyncio.run(run())


def test_tutor_chat_message_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            chats = TutorChatMessageRepository(session)

            old = await chats.record(
                TutorChatMessage(
                    student_external_id="student-ext-1",
                    learning_session_id="learning-session-1",
                    question_variant_id=chain.question_variant_id,
                    intent="question_help",
                    redacted_student_message="can you help me understand this?",
                    reply_text="Let's think through it together.",
                    cost_cents=0.5,
                )
            )
            # Backdated so the cost-ceiling window and the purge cutoff both exercise a
            # real boundary, not just "everything is recent".
            old.created_at = datetime(2020, 1, 1, tzinfo=UTC)
            await session.flush()

            recent = await chats.record(
                TutorChatMessage(
                    student_external_id="student-ext-1",
                    learning_session_id="learning-session-1",
                    question_variant_id=None,
                    intent="off_topic",
                    redacted_student_message="what's your favorite movie?",
                    reply_text="Let's stay focused on this question - what part is tricky?",
                    cost_cents=0.0,
                    flagged_for_review=False,
                )
            )

            # The per-day spend window moved to `cost_reservations` in S42 (AUD-X-08);
            # `test_cost_reservation.py` covers the windowing that used to be asserted
            # here. `cost_cents` remains on the row as the per-turn audit record.
            purged = await chats.purge_older_than(datetime(2024, 1, 1, tzinfo=UTC))
            assert purged == 1
            remaining = await session.execute(
                select(TutorChatMessage).where(
                    TutorChatMessage.student_external_id == "student-ext-1"
                )
            )
            remaining_ids = {row.message_id for row in remaining.scalars().all()}
            assert remaining_ids == {recent.message_id}

    asyncio.run(run())


def test_mastery_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            assessments = AssessmentRepository(session)
            mastery_repo = MasteryRepository(session)

            pre = await assessments.create_session(
                AssessmentSession(student_external_id="student-ext-1", session_type="pre_exam")
            )
            post = await assessments.create_session(
                AssessmentSession(student_external_id="student-ext-1", session_type="post_exam")
            )

            await mastery_repo.upsert_mastery(
                Mastery(
                    student_external_id="student-ext-1",
                    skill_id=chain.skill_id,
                    raw_accuracy=0.6,
                    weighted_score=0.55,
                )
            )
            # A second upsert for the same (student, skill) updates in place rather than
            # accumulating a second row (D-017's mastery recomputation happens repeatedly
            # across pre-exam/study/post-exam).
            await mastery_repo.upsert_mastery(
                Mastery(
                    student_external_id="student-ext-1",
                    skill_id=chain.skill_id,
                    raw_accuracy=0.8,
                    weighted_score=0.75,
                )
            )
            await mastery_repo.record_learning_gain(
                LearningGain(
                    student_external_id="student-ext-1",
                    pre_assessment_session_id=pre.assessment_session_id,
                    post_assessment_session_id=post.assessment_session_id,
                    pre_raw_score=6.0,
                    post_raw_score=9.0,
                    raw_gain=3.0,
                    weighted_gain=2.6,
                    independent_correct_rate=0.8,
                    hint_dependency=0.1,
                    solution_dependency=0.0,
                    response_time_change_ms=-500,
                )
            )

            weak_skills = await mastery_repo.get_weak_skills("student-ext-1", week_id="2026-W29")
            assert len(weak_skills) == 1
            assert weak_skills[0].skill_id == chain.skill_id

            single = await mastery_repo.get_mastery("student-ext-1", chain.skill_id)
            all_for_student = await mastery_repo.list_for_student("student-ext-1")
            assert single is not None
            assert single.weighted_score == 0.75
            assert len(all_for_student) == 1

    asyncio.run(run())


def test_report_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            reports = ReportRepository(session)

            await reports.create_report(
                ProblemReport(
                    question_template_id=chain.question_template_id,
                    question_variant_id=chain.question_variant_id,
                    student_external_id="student-ext-1",
                    report_type="unclear_wording",
                )
            )

            count = await reports.count_distinct_reporters(chain.question_template_id)
            assert count == 1

    asyncio.run(run())


def test_memory_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            memory = MemoryRepository(session)

            await memory.record_event(
                LearningEvent(
                    student_external_id="student-ext-1",
                    session_id="session-1",
                    event_type="question_attempted",
                    topic_id=chain.topic_id,
                    skill_id=chain.skill_id,
                    question_variant_id=chain.question_variant_id,
                )
            )
            await memory.add_fact(
                SemanticMemory(
                    student_external_id="student-ext-1",
                    fact_type="strength",
                    skill_id=chain.skill_id,
                    fact_text="Solves one-step equations independently",
                    confidence=0.8,
                    evidence_event_ids=["evt-1"],
                    first_observed_at=datetime.now(UTC),
                    last_confirmed_at=datetime.now(UTC),
                )
            )

            facts = await memory.list_facts_for_student("student-ext-1")
            assert len(facts) == 1
            assert facts[0].fact_text == "Solves one-step equations independently"

            # S25 read path (`tutor.py`/`tutor_chat.py`'s `relevant_learning_fact`):
            # only an `active`, non-expired fact is ever returned - a lower-confidence
            # `provisional` fact for the same skill must not shadow it, and an expired
            # `active` fact must not be returned either.
            await memory.add_fact(
                SemanticMemory(
                    student_external_id="student-ext-1",
                    fact_type="weak_skill",
                    skill_id=chain.skill_id,
                    fact_text="Not yet confirmed by enough evidence",
                    confidence=0.99,
                    status="provisional",
                    evidence_event_ids=["evt-2"],
                    first_observed_at=datetime.now(UTC),
                    last_confirmed_at=datetime.now(UTC),
                )
            )
            await memory.add_fact(
                SemanticMemory(
                    student_external_id="student-ext-1",
                    fact_type="strength",
                    skill_id=chain.skill_id,
                    fact_text="Expired, should never be served",
                    confidence=0.95,
                    status="active",
                    evidence_event_ids=["evt-3"],
                    first_observed_at=datetime.now(UTC),
                    last_confirmed_at=datetime.now(UTC),
                    expires_at=datetime(2020, 1, 1, tzinfo=UTC),
                )
            )
            top = await memory.top_fact_for_skill("student-ext-1", chain.skill_id)
            assert top is not None
            assert top.fact_text == "Solves one-step equations independently"

    asyncio.run(run())


def test_promote_if_eligible_enforces_the_accumulated_evidence_bar() -> None:
    """AUD-F-35: promotion applies plan §9's bar (min_events across min_sessions) to
    the fact's accumulated evidence_event_ids - it used to promote any provisional
    fact unconditionally. Evidence that doesn't resolve to this student's own events
    counts for nothing (the write-time `_verify_evidence` posture, re-applied here).
    """

    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            memory = MemoryRepository(session)

            events = []
            for session_id in ("s1", "s1", "s2"):
                events.append(
                    await memory.record_event(
                        LearningEvent(
                            student_external_id="student-ext-1",
                            session_id=session_id,
                            event_type="question_attempted",
                            skill_id=chain.skill_id,
                        )
                    )
                )
            other_students = await memory.record_event(
                LearningEvent(
                    student_external_id="student-ext-2",
                    session_id="s9",
                    event_type="question_attempted",
                    skill_id=chain.skill_id,
                )
            )

            async def provisional_fact(evidence: list[str]):
                return await memory.add_fact(
                    SemanticMemory(
                        student_external_id="student-ext-1",
                        fact_type="strength",
                        skill_id=chain.skill_id,
                        fact_text="Consistent with one-step equations",
                        confidence=0.7,
                        status="provisional",
                        evidence_event_ids=evidence,
                        first_observed_at=datetime.now(UTC),
                        last_confirmed_at=datetime.now(UTC),
                    )
                )

            # Below the event count: 2 events / 2 sessions stays provisional.
            below_events = await provisional_fact([events[0].event_id, events[2].event_id])
            result = await memory.promote_if_eligible(
                below_events.semantic_memory_id, min_events=3, min_sessions=2
            )
            assert result is not None and result.status == "provisional"

            # Below the session diversity: 3 events all in one session stays provisional
            # (needs a third same-session event to construct).
            same_session = await memory.record_event(
                LearningEvent(
                    student_external_id="student-ext-1",
                    session_id="s1",
                    event_type="question_attempted",
                    skill_id=chain.skill_id,
                )
            )
            single_session = await provisional_fact(
                [events[0].event_id, events[1].event_id, same_session.event_id]
            )
            result = await memory.promote_if_eligible(
                single_session.semantic_memory_id, min_events=3, min_sessions=2
            )
            assert result is not None and result.status == "provisional"

            # Another student's event does not count toward the bar.
            padded = await provisional_fact(
                [events[0].event_id, events[2].event_id, other_students.event_id]
            )
            result = await memory.promote_if_eligible(
                padded.semantic_memory_id, min_events=3, min_sessions=2
            )
            assert result is not None and result.status == "provisional"

            # The bar met - 3 own events across 2 sessions - promotes.
            eligible = await provisional_fact([event.event_id for event in events])
            result = await memory.promote_if_eligible(
                eligible.semantic_memory_id, min_events=3, min_sessions=2
            )
            assert result is not None and result.status == "active"

    asyncio.run(run())


def test_promote_if_eligible_leaves_non_provisional_statuses_alone() -> None:
    """A `contested` fact meeting the bar is NOT resurrected by promotion - only
    `reconfirm_fact` returns a contested fact to active (plan §9's demotion semantics).
    """

    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            memory = MemoryRepository(session)

            events = [
                await memory.record_event(
                    LearningEvent(
                        student_external_id="student-ext-1",
                        session_id=session_id,
                        event_type="question_attempted",
                        skill_id=chain.skill_id,
                    )
                )
                for session_id in ("s1", "s2", "s3")
            ]
            contested = await memory.add_fact(
                SemanticMemory(
                    student_external_id="student-ext-1",
                    fact_type="strength",
                    skill_id=chain.skill_id,
                    fact_text="Contradicted last window",
                    confidence=0.7,
                    status="contested",
                    evidence_event_ids=[event.event_id for event in events],
                    first_observed_at=datetime.now(UTC),
                    last_confirmed_at=datetime.now(UTC),
                )
            )

            result = await memory.promote_if_eligible(
                contested.semantic_memory_id, min_events=3, min_sessions=2
            )
            assert result is not None and result.status == "contested"

    asyncio.run(run())


def test_semantic_memory_purge_keys_on_last_confirmed_not_first_observed() -> None:
    """AUD-L-04 (D-114): the 90-day boundary D-072 reasoned about, restored for the
    derived text. Keyed on `last_confirmed_at` so a fact the weekly consolidation keeps
    reconfirming survives however old its first observation is, while anything nothing
    has confirmed inside the window - including `superseded` audit rows, which nothing
    ever reconfirms - ages out.

    A distinctive student id and `purged >= n`, not `== n`, in all three purge tests:
    the purge is global and the shared dev Postgres carries rows from earlier sessions
    (D-018's pattern), so exact counts and `student-ext-1` are both hostage to
    leftovers. The per-student remaining set is the exact assertion.
    """

    async def run() -> None:
        async with rollback_session() as session:
            memory = MemoryRepository(session)

            reconfirmed = await memory.add_fact(
                SemanticMemory(
                    student_external_id="retention-probe-student",
                    fact_type="strength",
                    fact_text="Old but still confirmed every week - must survive",
                    confidence=0.8,
                    evidence_event_ids=["evt-1"],
                    first_observed_at=datetime(2020, 1, 1, tzinfo=UTC),
                    last_confirmed_at=datetime.now(UTC),
                )
            )
            stale_active = await memory.add_fact(
                SemanticMemory(
                    student_external_id="retention-probe-student",
                    fact_type="weak_skill",
                    fact_text="Active but unconfirmed for years",
                    confidence=0.7,
                    evidence_event_ids=["evt-2"],
                    first_observed_at=datetime(2020, 1, 1, tzinfo=UTC),
                    last_confirmed_at=datetime(2020, 6, 1, tzinfo=UTC),
                )
            )
            stale_superseded = await memory.add_fact(
                SemanticMemory(
                    student_external_id="retention-probe-student",
                    fact_type="weak_skill",
                    fact_text="Superseded audit row - retained for the window, not forever",
                    confidence=0.5,
                    status="superseded",
                    superseded_by_id=reconfirmed.semantic_memory_id,
                    evidence_event_ids=["evt-3"],
                    first_observed_at=datetime(2020, 1, 1, tzinfo=UTC),
                    last_confirmed_at=datetime(2020, 6, 1, tzinfo=UTC),
                )
            )

            purged = await memory.purge_facts_older_than(datetime(2024, 1, 1, tzinfo=UTC))

            assert purged >= 2
            remaining = await session.execute(
                select(SemanticMemory).where(
                    SemanticMemory.student_external_id == "retention-probe-student"
                )
            )
            remaining_ids = {f.semantic_memory_id for f in remaining.scalars().all()}
            assert remaining_ids == {reconfirmed.semantic_memory_id}
            assert stale_active.semantic_memory_id not in remaining_ids
            assert stale_superseded.semantic_memory_id not in remaining_ids

    asyncio.run(run())


def test_learning_event_purge_boundary() -> None:
    """D-153: `learning_events` was the one table with no retention promise (D-141 §5).
    Events older than the cutoff go; events inside it stay, regardless of student.
    """

    async def run() -> None:
        async with rollback_session() as session:
            chain = await _seed_question_chain(session)
            memory = MemoryRepository(session)

            stale = await memory.record_event(
                LearningEvent(
                    student_external_id="retention-probe-student",
                    session_id="s-old",
                    event_type="question_attempted",
                    skill_id=chain.skill_id,
                    occurred_at=datetime(2020, 1, 1, tzinfo=UTC),
                )
            )
            fresh = await memory.record_event(
                LearningEvent(
                    student_external_id="retention-probe-student",
                    session_id="s-new",
                    event_type="question_attempted",
                    skill_id=chain.skill_id,
                    occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )

            purged = await memory.purge_events_older_than(datetime(2024, 1, 1, tzinfo=UTC))

            assert purged >= 1
            surviving = await memory.get_events_by_ids([stale.event_id, fresh.event_id])
            surviving_ids = {event.event_id for event in surviving}
            assert stale.event_id not in surviving_ids
            assert fresh.event_id in surviving_ids

    asyncio.run(run())


def test_learning_event_retention_clears_the_semantic_memory_floor() -> None:
    """D-153's floor, made executable rather than left in a comment.

    A fact's `evidence_event_ids` point at `learning_events`, and `promote_if_eligible`
    resolves them back to real rows. So the event window must outlive the fact window plus
    one consolidation window — otherwise a live fact routinely cites rows that no longer
    exist and silently stops being promotable. Lowering either constant fails here.
    """
    from intellichoice_memory.settings import MemoryConsolidationSettings
    from learning_api.services.retention_purge_cli import (
        LEARNING_EVENT_RETENTION_DAYS,
        SEMANTIC_MEMORY_RETENTION_DAYS,
    )

    consolidation_window_days = MemoryConsolidationSettings().window_days
    floor = SEMANTIC_MEMORY_RETENTION_DAYS + consolidation_window_days

    assert LEARNING_EVENT_RETENTION_DAYS >= floor, (
        f"learning_events retention ({LEARNING_EVENT_RETENTION_DAYS}d) must be at least "
        f"semantic_memory ({SEMANTIC_MEMORY_RETENTION_DAYS}d) + the consolidation window "
        f"({consolidation_window_days}d) = {floor}d, or live facts cite purged evidence."
    )


def test_stage_transition_purge_boundary() -> None:
    """AUD-L-04 item 2 (D-114): narrative text derived from tutoring data gets the same
    90-day boundary as its source.
    """

    async def run() -> None:
        async with rollback_session() as session:
            transitions = StageTransitionRepository(session)

            old = await transitions.record(
                StageTransition(
                    student_external_id="retention-probe-student",
                    learning_session_id="learning-session-old",
                    stage="pre_intro",
                    narrative_text="An old narrative",
                )
            )
            old.created_at = datetime(2020, 1, 1, tzinfo=UTC)
            await session.flush()
            recent = await transitions.record(
                StageTransition(
                    student_external_id="retention-probe-student",
                    learning_session_id="learning-session-recent",
                    stage="pre_intro",
                    narrative_text="A recent narrative",
                )
            )

            purged = await transitions.purge_older_than(datetime(2024, 1, 1, tzinfo=UTC))

            assert purged >= 1
            remaining = await session.execute(
                select(StageTransition).where(
                    StageTransition.student_external_id == "retention-probe-student"
                )
            )
            remaining_ids = {t.stage_transition_id for t in remaining.scalars().all()}
            assert remaining_ids == {recent.stage_transition_id}

    asyncio.run(run())


def test_student_report_purge_boundary() -> None:
    """AUD-L-04 item 2 (D-114): report snapshots embed semantic-memory `fact_text` in
    `verified_facts`, so they get a retention boundary too - a year, not 90 days,
    because `list_for_student` serves them to parents as history.
    """

    async def run() -> None:
        async with rollback_session() as session:
            reports = StudentReportRepository(session)

            old = await reports.create(
                StudentReport(
                    student_external_id="retention-probe-student",
                    audience="parent",
                    interpretation_text="An old report",
                    recommendations_text="Old recommendations",
                    idempotency_key="retention-old",
                )
            )
            old.created_at = datetime(2020, 1, 1, tzinfo=UTC)
            await session.flush()
            recent = await reports.create(
                StudentReport(
                    student_external_id="retention-probe-student",
                    audience="parent",
                    interpretation_text="A recent report",
                    recommendations_text="Recent recommendations",
                    idempotency_key="retention-recent",
                )
            )

            purged = await reports.purge_older_than(datetime(2024, 1, 1, tzinfo=UTC))

            assert purged >= 1
            remaining = await session.execute(
                select(StudentReport).where(
                    StudentReport.student_external_id == "retention-probe-student"
                )
            )
            remaining_ids = {r.student_report_id for r in remaining.scalars().all()}
            assert remaining_ids == {recent.student_report_id}

    asyncio.run(run())


def test_student_report_create_if_first_refuses_a_duplicate_key() -> None:
    """AUD-X-04's enforcement layer, tested where it is deterministic. The service's replay
    lookup is read-then-act, so `uq_student_reports_student_audience_key` is what actually
    makes one key mean one report - and `create_if_first` recognises that violation by matching
    the constraint *name*, which is a string that a rename would silently break. This is the
    test that fails if it ever stops matching (the alternative would be the exception escaping
    as a 500 under concurrency, where it is hard to see).

    Also asserts the scope: the same key under a different audience is a different report, since
    a parent and a tutor view of one student are two documents.
    """

    async def run() -> None:
        async with rollback_session() as session:
            reports = StudentReportRepository(session)

            first = await reports.create_if_first(
                StudentReport(
                    student_external_id="idem-probe-student",
                    audience="parent",
                    interpretation_text="First",
                    recommendations_text="First recs",
                    idempotency_key="same-key",
                )
            )
            assert first is not None

            duplicate = await reports.create_if_first(
                StudentReport(
                    student_external_id="idem-probe-student",
                    audience="parent",
                    interpretation_text="Second",
                    recommendations_text="Second recs",
                    idempotency_key="same-key",
                )
            )
            assert duplicate is None

            # The surrounding transaction is still usable - the point of the SAVEPOINT.
            winner = await reports.get_by_idempotency_key(
                "idem-probe-student", audience="parent", idempotency_key="same-key"
            )
            assert winner is not None
            assert winner.interpretation_text == "First"

            other_audience = await reports.create_if_first(
                StudentReport(
                    student_external_id="idem-probe-student",
                    audience="tutor",
                    interpretation_text="Tutor view",
                    recommendations_text="Tutor recs",
                    idempotency_key="same-key",
                )
            )
            assert other_audience is not None

    asyncio.run(run())


def test_rag_repository_round_trip() -> None:
    """Uses a nonsense marker phrase rather than a realistic word like "attendance" -
    `make knowledge-load`'s real 22-document seed set (S12/S13) is intentionally left in
    the shared dev Postgres for later sessions' retrieval work, and a realistic query
    would also match its real `parent-attendance-policy` content, inflating this test's
    result count (D-018's throwaway-content pattern).
    """

    async def run() -> None:
        async with rollback_session() as session:
            rag = RagRepository(session)

            document = await rag.create_document(
                RagDocument(
                    title="Parent Handbook",
                    source_path="public/parent-handbook/v1.md",
                    audience="parent",
                    academic_year="2026-2027",
                    effective_from=datetime.now(UTC),
                    status="approved",
                    source_sha256="a" * 64,
                )
            )
            await rag.add_chunk(
                RagChunk(
                    document_id=document.document_id,
                    chunk_text="Zqxvantendance-marker-7742 is required for each on-site session.",
                    document_title="Parent Handbook",
                    audience="parent",
                    access_level="parent",
                    academic_year="2026-2027",
                    effective_from=datetime.now(UTC),
                    status="approved",
                    source_sha256="a" * 64,
                )
            )

            results = await rag.search_document_chunks(
                ChunkFilters(audience="parent"), query="zqxvantendance-marker-7742"
            )
            assert len(results) == 1

            no_match = await rag.search_document_chunks(
                ChunkFilters(audience="student"), query="zqxvantendance-marker-7742"
            )
            assert no_match == []

    asyncio.run(run())




def test_evaluation_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            evaluation = EvaluationRepository(session)

            await evaluation.record_result(
                EvaluationResult(suite_name="grading-golden-set", case_id="case-1", passed=True)
            )

            results = await evaluation.list_results("grading-golden-set")
            assert len(results) == 1
            assert results[0].case_id == "case-1"

    asyncio.run(run())


def test_interrupt_approval_repository_round_trip() -> None:
    """S14: `session_id`/`source_app` (renamed from `learning_session_id`, plus the new
    discriminator column) and a nullable `decided_by_external_id` (anonymous chat-api
    callers have no external id to record).
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = InterruptApprovalRepository(session)

            recorded = await repo.record(
                InterruptApproval(
                    session_id="chat-session-zqxvrepo-1",
                    source_app="chat",
                    interrupt_type="calendar_action",
                    decision="ics",
                    decided_by_external_id=None,
                )
            )
            assert recorded.approval_id is not None

            stmt = select(InterruptApproval).where(
                InterruptApproval.session_id == "chat-session-zqxvrepo-1"
            )
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
            assert len(rows) == 1
            assert rows[0].source_app == "chat"
            assert rows[0].decision == "ics"
            assert rows[0].decided_by_external_id is None

    asyncio.run(run())


def test_mcp_tool_call_repository_round_trip() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = McpToolCallRepository(session)

            # Nonsense marker tool name (D-018's pattern) - `gmail.send_email` is a
            # real tool name that other tests' `TestClient(app)` HTTP calls commit real
            # rows for outside this rollback, so asserting an exact count against it
            # would be environment-dependent.
            await repo.record(
                ToolCallAuditEvent(
                    tool_name="zqxvrepo.test_tool",
                    caller_external_id="student-ext-1",
                    success=True,
                    error_type=None,
                    duration_ms=12.5,
                )
            )

            stmt = select(McpToolCall).where(McpToolCall.tool_name == "zqxvrepo.test_tool")
            result = await session.execute(stmt)
            rows = list(result.scalars().all())
            assert len(rows) == 1
            assert rows[0].success is True
            assert rows[0].caller_external_id == "student-ext-1"

    asyncio.run(run())


def test_youtube_repository_round_trip() -> None:
    """S15: natural-key (`youtube_video_id`) upsert-in-place, inactive-marking for a
    video missing from a later fetch, and metadata-filtered + embedding-ranked search.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = YoutubeRepository(session)

            def _video(
                video_id: str, *, embedding: list[float], skill_ids: list[str]
            ) -> YoutubeVideo:
                return YoutubeVideo(
                    youtube_video_id=video_id,
                    channel_id="zqxvrepo-channel",
                    channel_title="Test Channel",
                    video_url=f"https://example.test/{video_id}",
                    title="Test Video",
                    description="A test video.",
                    playlist_ids=["p1"],
                    duration="PT5M",
                    published_at=datetime(2024, 1, 1, tzinfo=UTC),
                    thumbnail_url="https://example.test/thumb.jpg",
                    language="en",
                    topic_ids=["linear_equations"],
                    skill_ids=skill_ids,
                    grade_band="3-5",
                    difficulty_min=1,
                    difficulty_max=3,
                    embedding=embedding,
                    last_synced_at=datetime.now(UTC),
                )

            # pgvector's fixed 1024-dim column (EMBEDDING_DIM) - unit basis vectors so
            # cosine distance is trivially "close" (same direction) vs "far" (orthogonal).
            axis_a = [1.0] + [0.0] * 1023
            axis_b = [0.0, 1.0] + [0.0] * 1022

            close = _video("zqxvrepo-close", embedding=axis_a, skill_ids=["zqxvrepo_skill"])
            far = _video("zqxvrepo-far", embedding=axis_b, skill_ids=["zqxvrepo_skill"])
            await repo.upsert_video(close)
            await repo.upsert_video(far)

            results = await repo.search_catalog(
                skill_id="zqxvrepo_skill", query_embedding=axis_a, limit=5
            )
            result_ids = [v.youtube_video_id for v in results]
            assert result_ids[:2] == ["zqxvrepo-close", "zqxvrepo-far"]

            # Upserting the same natural key again updates in place, not a duplicate.
            updated_close = _video(
                "zqxvrepo-close", embedding=axis_a, skill_ids=["zqxvrepo_skill"]
            )
            updated_close.title = "Updated Title"
            await repo.upsert_video(updated_close)
            reloaded = await repo.get_video("zqxvrepo-close")
            assert reloaded is not None
            assert reloaded.title == "Updated Title"

            # A video missing from the latest fetch (only "close" seen) is marked
            # inactive and drops out of search results.
            marked = await repo.mark_inactive_except("zqxvrepo-channel", ["zqxvrepo-close"])
            assert marked == 1
            results_after = await repo.search_catalog(
                skill_id="zqxvrepo_skill", query_embedding=axis_a, limit=5
            )
            assert [v.youtube_video_id for v in results_after] == ["zqxvrepo-close"]

    asyncio.run(run())


def test_youtube_repository_apply_verification_is_reversible() -> None:
    """S27: `apply_verification` flips `active_status`/increments
    `verification_failures` on a failing check and resets on a passing one - the same
    "reappear -> active again" reversibility `mark_inactive_except` already has.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = YoutubeRepository(session)
            axis_a = [1.0] + [0.0] * 1023

            video = YoutubeVideo(
                youtube_video_id="zqxvverify-1",
                channel_id="zqxvverify-channel",
                channel_title="Test Channel",
                video_url="https://example.test/zqxvverify-1",
                title="Test Video",
                description="A test video.",
                playlist_ids=["p1"],
                duration="PT5M",
                published_at=datetime(2024, 1, 1, tzinfo=UTC),
                thumbnail_url="https://example.test/thumb.jpg",
                language="en",
                topic_ids=["linear_equations"],
                skill_ids=["zqxvverify_skill"],
                grade_band="3-5",
                difficulty_min=1,
                difficulty_max=3,
                embedding=axis_a,
                last_synced_at=datetime.now(UTC),
            )
            await repo.upsert_video(video)

            verified_at = datetime.now(UTC)
            await repo.apply_verification(
                "zqxvverify-1",
                available=False,
                license_="youtube",
                transcript_available=False,
                transcript_language=None,
                verified_at=verified_at,
            )
            failed = await repo.get_video("zqxvverify-1")
            assert failed is not None
            assert failed.active_status == "inactive"
            assert failed.verification_failures == 1
            assert failed.last_verified_at is not None

            await repo.apply_verification(
                "zqxvverify-1",
                available=True,
                license_="creativeCommon",
                transcript_available=True,
                transcript_language="en",
                verified_at=datetime.now(UTC),
            )
            recovered = await repo.get_video("zqxvverify-1")
            assert recovered is not None
            # Reappearing verified-ok resets the failure count but does not itself flip
            # `active_status` back to "active" - that's `upsert_video`'s job on the next
            # real re-sync (a verification pass alone never resurrects a video that
            # hasn't reappeared in the channel's own uploads).
            assert recovered.verification_failures == 0
            assert recovered.license == "creativeCommon"
            assert recovered.transcript_available is True
            assert recovered.transcript_language == "en"

    asyncio.run(run())


def test_youtube_search_catalog_excludes_non_approved_suitability() -> None:
    """S27: `suitability_status` is an unconditional gate on `search_catalog`, not a
    caller-supplied filter arg - a flagged video never surfaces even when every other
    metadata filter matches.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = YoutubeRepository(session)
            axis_a = [1.0] + [0.0] * 1023

            flagged = YoutubeVideo(
                youtube_video_id="zqxvsuit-flagged",
                channel_id="zqxvsuit-channel",
                channel_title="Test Channel",
                video_url="https://example.test/zqxvsuit-flagged",
                title="Test Video",
                description="A test video.",
                playlist_ids=["p1"],
                duration="PT5M",
                published_at=datetime(2024, 1, 1, tzinfo=UTC),
                thumbnail_url="https://example.test/thumb.jpg",
                language="en",
                topic_ids=["linear_equations"],
                skill_ids=["zqxvsuit_skill"],
                grade_band="3-5",
                difficulty_min=1,
                difficulty_max=3,
                embedding=axis_a,
                last_synced_at=datetime.now(UTC),
                suitability_status="flagged",
            )
            await repo.upsert_video(flagged)

            results = await repo.search_catalog(
                skill_id="zqxvsuit_skill", query_embedding=axis_a, limit=5
            )
            assert "zqxvsuit-flagged" not in [v.youtube_video_id for v in results]

    asyncio.run(run())


def test_org_branch_repository_round_trip() -> None:
    """S17: natural-key (`branch_external_id`) upsert-in-place via `content_hash`, and
    inactive-marking for a branch missing from a later sync (never deleted).
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = OrgBranchRepository(session)

            branch = OrgBranch(
                branch_external_id="zqxvrepo-austin",
                name="Austin",
                address=None,
                hours={"raw_text": "Online 10 AM Central"},
                source_url="https://www.intellichoice.org/branches/",
                content_hash="hash-v1",
            )
            await repo.upsert_branch(branch)

            # Re-syncing with an unchanged content_hash is a no-op on the fields.
            unchanged = OrgBranch(
                branch_external_id="zqxvrepo-austin",
                name="Austin (should not apply)",
                hours={"raw_text": "should not apply"},
                source_url="https://www.intellichoice.org/branches/",
                content_hash="hash-v1",
            )
            await repo.upsert_branch(unchanged)
            reloaded = await repo.get_branch("zqxvrepo-austin")
            assert reloaded is not None
            assert reloaded.name == "Austin"

            # A changed content_hash updates the row in place.
            changed = OrgBranch(
                branch_external_id="zqxvrepo-austin",
                name="Austin",
                hours={"raw_text": "Online 11 AM Central"},
                source_url="https://www.intellichoice.org/branches/",
                content_hash="hash-v2",
            )
            await repo.upsert_branch(changed)
            reloaded = await repo.get_branch("zqxvrepo-austin")
            assert reloaded is not None
            assert reloaded.hours == {"raw_text": "Online 11 AM Central"}

            # A branch missing from the latest sync is marked inactive, not deleted.
            marked = await repo.mark_inactive_except([])
            assert marked >= 1
            reloaded = await repo.get_branch("zqxvrepo-austin")
            assert reloaded is not None
            assert reloaded.status == "inactive"
            active = await repo.list_branches()
            assert "zqxvrepo-austin" not in {b.branch_external_id for b in active}

    asyncio.run(run())


def test_org_team_member_repository_round_trip() -> None:
    """S17: natural-key (`team_member_id`) upsert-in-place via `content_hash`, and
    inactive-marking for a member missing from a later sync (never deleted).
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = OrgTeamMemberRepository(session)

            member = OrgTeamMember(
                team_member_id="zqxvrepo-administration-jane-doe",
                name="Jane Doe",
                role_title="Founder & CEO",
                category="Administration",
                biography="A public bio published on the org's own website.",
                source_url="https://www.intellichoice.org/pages/our-team/",
                content_hash="hash-v1",
            )
            await repo.upsert_member(member)
            reloaded = await repo.get_member("zqxvrepo-administration-jane-doe")
            assert reloaded is not None
            assert reloaded.role_title == "Founder & CEO"

            updated = OrgTeamMember(
                team_member_id="zqxvrepo-administration-jane-doe",
                name="Jane Doe",
                role_title="Founder & CEO, Ph.D.",
                category="Administration",
                biography="An updated bio.",
                audience="public",
                source_url="https://www.intellichoice.org/pages/our-team/",
                content_hash="hash-v2",
            )
            await repo.upsert_member(updated)
            reloaded = await repo.get_member("zqxvrepo-administration-jane-doe")
            assert reloaded is not None
            assert reloaded.role_title == "Founder & CEO, Ph.D."

            marked = await repo.mark_inactive_except([])
            assert marked >= 1
            active = await repo.list_members()
            assert "zqxvrepo-administration-jane-doe" not in {
                m.team_member_id for m in active
            }

    asyncio.run(run())


def test_org_event_repository_round_trip() -> None:
    """S18: natural-key (`event_external_id`) upsert-in-place via `content_hash` - no
    inactive-marking (unlike branches/team members, see `OrgEvent`'s own docstring),
    and a content-changing update never overwrites `status` (see `upsert_event`'s own
    docstring - a human-set "canceled"/"changed" designation must survive a re-sync
    that only fixes an unrelated field).
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = OrgEventRepository(session)

            event = OrgEvent(
                event_external_id="zqxvrepo-banquet",
                title="Scholarship Banquet",
                description="",
                starts_at=datetime(2023, 12, 10, 17, 0, tzinfo=UTC),
                ends_at=datetime(2023, 12, 10, 20, 0, tzinfo=UTC),
                timezone="America/Chicago",
                source_url="https://www.intellichoice.org/event/scholarship-banquet/",
                content_hash="hash-v1",
            )
            await repo.upsert_event(event)
            reloaded = await repo.get_event("zqxvrepo-banquet")
            assert reloaded is not None
            assert reloaded.title == "Scholarship Banquet"
            assert reloaded.audience == "public"
            assert reloaded.status == "scheduled"

            # Re-syncing with an unchanged content_hash is a no-op on the fields.
            unchanged = OrgEvent(
                event_external_id="zqxvrepo-banquet",
                title="should not apply",
                description="",
                starts_at=datetime(2023, 12, 10, 17, 0, tzinfo=UTC),
                ends_at=datetime(2023, 12, 10, 20, 0, tzinfo=UTC),
                timezone="America/Chicago",
                source_url="https://www.intellichoice.org/event/scholarship-banquet/",
                content_hash="hash-v1",
            )
            await repo.upsert_event(unchanged)
            reloaded = await repo.get_event("zqxvrepo-banquet")
            assert reloaded is not None
            assert reloaded.title == "Scholarship Banquet"

            # A human marks this event canceled directly (no scrape signal exists yet).
            reloaded.status = "canceled"
            await session.flush()

            # A changed content_hash updates the row in place, but never touches status.
            changed = OrgEvent(
                event_external_id="zqxvrepo-banquet",
                title="Scholarship Banquet (corrected time)",
                description="",
                starts_at=datetime(2023, 12, 10, 17, 30, tzinfo=UTC),
                ends_at=datetime(2023, 12, 10, 20, 0, tzinfo=UTC),
                timezone="America/Chicago",
                source_url="https://www.intellichoice.org/event/scholarship-banquet/",
                content_hash="hash-v2",
            )
            await repo.upsert_event(changed)
            reloaded = await repo.get_event("zqxvrepo-banquet")
            assert reloaded is not None
            assert reloaded.title == "Scholarship Banquet (corrected time)"
            assert reloaded.status == "canceled"

            events = await repo.list_events(audiences=["public"])
            assert "zqxvrepo-banquet" in {e.event_external_id for e in events}
            assert await repo.list_events(audiences=["tutor"]) == []

    asyncio.run(run())


def test_chat_suggestion_repository_round_trip() -> None:
    """S19 (plan §18-C3): id-natural-key upsert-in-place, and `list_active` returns only
    active rows ordered by `sort_order`.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = ChatSuggestionRepository(session)

            await repo.upsert(
                ChatSuggestion(
                    id="zqxvrepo-branches-nearest",
                    role_audience="public",
                    category="branches",
                    prompt_text="Which branch is nearest to me?",
                    sort_order=2,
                    active=True,
                )
            )
            await repo.upsert(
                ChatSuggestion(
                    id="zqxvrepo-general-about",
                    role_audience="public",
                    category="general",
                    prompt_text="What is IntelliChoice?",
                    sort_order=1,
                    active=True,
                )
            )
            await repo.upsert(
                ChatSuggestion(
                    id="zqxvrepo-inactive",
                    role_audience="public",
                    category="general",
                    prompt_text="Retired prompt",
                    sort_order=0,
                    active=False,
                )
            )

            reloaded = await repo.get("zqxvrepo-branches-nearest")
            assert reloaded is not None
            assert reloaded.prompt_text == "Which branch is nearest to me?"

            # Re-upserting the same id updates fields in place rather than duplicating.
            await repo.upsert(
                ChatSuggestion(
                    id="zqxvrepo-branches-nearest",
                    role_audience="public",
                    category="branches",
                    prompt_text="Which branch is closest to my home?",
                    sort_order=2,
                    active=True,
                )
            )
            reloaded = await repo.get("zqxvrepo-branches-nearest")
            assert reloaded is not None
            assert reloaded.prompt_text == "Which branch is closest to my home?"

            active = [
                s.id
                for s in await repo.list_active()
                if s.id.startswith("zqxvrepo-")
            ]
            assert active == ["zqxvrepo-general-about", "zqxvrepo-branches-nearest"]

    asyncio.run(run())
