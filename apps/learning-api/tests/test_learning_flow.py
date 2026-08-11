"""End-to-end HTTP integration test for the S5 deterministic learning flow (SPEC §5.5.1,
Phase 6 §6.7 "Done when": a student can complete the entire flow through APIs).
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.mysql_profile_adapter import current_week_key
from intellichoice_adapters.seed.mysql_fixtures import (
    PARENT_TWO_CHILDREN,
    STUDENT_FIRST_CHILD,
    STUDENT_SECOND_CHILD,
    STUDENT_UNLINKED,
    seed,
)
from intellichoice_curriculum.authored_validation import (
    answer_text_leaked,
    answers_agree,
    leak_phrase_present,
)
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.assessment import BlockedSession
from intellichoice_db.models.interrupts import InterruptApproval
from intellichoice_db.models.mastery import Mastery, StudyAttempt, StudyItem
from intellichoice_db.models.memory import LearningEvent, SemanticMemory
from intellichoice_db.models.stage_transition import StageTransition
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.auth import Audience, Role
from learning_api.main import app
from learning_api.services import study_plan, video_catalog
from learning_api.services.attendance import BLOCKED_MESSAGE, UNKNOWN_MESSAGE
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"

issuer = FakeTokenIssuer()


def _mysql_available() -> bool:
    async def check() -> bool:
        engine = create_async_engine(MYSQL_URL, connect_args={"connect_timeout": 1})
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


def _postgres_available() -> bool:
    async def check() -> bool:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1 FROM topics LIMIT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = pytest.mark.skipif(
    not (_mysql_available() and _postgres_available()),
    reason="MySQL/PostgreSQL not reachable or not migrated (run `make up && make db-upgrade`)",
)


@pytest.fixture(scope="module", autouse=True)
def seeded_fixtures() -> None:
    asyncio.run(seed(MYSQL_URL))

    async def load() -> None:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                await load_curriculum_and_templates(session)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(load())


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _student_token(student_id: str) -> str:
    return issuer.issue(sub=student_id, role=Role.STUDENT, audience=Audience.LEARNING)


def _parent_token(parent_id: str) -> str:
    return issuer.issue(sub=parent_id, role=Role.PARENT, audience=Audience.LEARNING)


def _finalize_exam(client: TestClient, headers: dict[str, str], session_id: str) -> dict:
    """S22/D-064: pre/post exams no longer auto-advance once the last item is answered -
    every test that used to rely on that now drives this explicit step first.
    """
    resp = client.post(f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={})
    assert resp.status_code == 200
    return resp.json()


def _correct_options(variant_ids: list[str]) -> dict[str, str]:
    async def fetch() -> dict[str, str]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                repo = QuestionRepository(session)
                result = {}
                for variant_id in variant_ids:
                    variant = await repo.get_variant(variant_id)
                    assert variant is not None
                    result[variant_id] = variant.correct_option
                return result
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _skills_for(variant_ids: list[str]) -> dict[str, str]:
    """Which skill each served variant actually tests.

    D-207. `test_retry_ladder_reaches_unresolved_with_tutor_flag_and_prerequisite` used to
    assume "indices 2 and 3 of the pre-exam are difficulty 2, therefore `linear_two_step`".
    That is the same premise D-206 recorded as broken for
    `test_identical_inputs_reproduce_identical_routing_and_scores`, in those words: *"which
    skills carry tier-2 items also varies per exam"*. Only one of the two tests was
    dispositioned then; this one kept passing on the draw and started failing in CI once the
    approved bank grew from 5 authored items to 48.

    Observed directly: the same test on the same code produced `len(line_items)` of 4, 1 and
    0 across three CI runs. Reading the skill instead of inferring it from a position makes
    the test drive the skill its own docstring names, on every draw.
    """

    async def fetch() -> dict[str, str]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                repo = QuestionRepository(session)
                result = {}
                for variant_id in variant_ids:
                    variant = await repo.get_variant(variant_id)
                    assert variant is not None
                    template = await repo.get_template(variant.question_template_id)
                    assert template is not None
                    result[variant_id] = template.skill_id
                return result
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _attempt_count(assessment_session_id: str) -> int:
    async def fetch() -> int:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                repo = AssessmentRepository(session)
                return len(await repo.get_attempts(assessment_session_id))
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _blocked_session_count(student_id: str, week_id: str) -> int:
    async def fetch() -> int:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                stmt = select(BlockedSession).where(
                    BlockedSession.student_external_id == student_id,
                    BlockedSession.week_id == week_id,
                )
                result = await session.execute(stmt)
                return len(list(result.scalars().all()))
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _other_option(correct: str) -> str:
    for option in ("a", "b", "c", "d"):
        if option != correct:
            return option
    raise AssertionError("no alternate option available")


def _pre_assessment_session_id(learning_session_id: str) -> str:
    """Resolves the pre-exam assessment_session_id from the graph's checkpointed state,
    for the idempotency attempt-count check.
    """

    async def fetch() -> str:
        graph = app.state.learning_graph
        snapshot = await graph.aget_state({"configurable": {"thread_id": learning_session_id}})
        pre_assessment_session_id = snapshot.values["pre_assessment_session_id"]
        assert pre_assessment_session_id is not None
        return pre_assessment_session_id

    return asyncio.run(fetch())


def _study_session_id(learning_session_id: str) -> str:
    async def fetch() -> str:
        graph = app.state.learning_graph
        snapshot = await graph.aget_state({"configurable": {"thread_id": learning_session_id}})
        study_session_id = snapshot.values["study_session_id"]
        assert study_session_id is not None
        return study_session_id

    return asyncio.run(fetch())


def _bedrock_spend_cents(learning_session_id: str) -> float:
    async def fetch() -> float:
        graph = app.state.learning_graph
        snapshot = await graph.aget_state({"configurable": {"thread_id": learning_session_id}})
        return snapshot.values["bedrock_spend_cents"]

    return asyncio.run(fetch())


def _study_attempt(study_session_id: str, question_variant_id: str) -> StudyAttempt:
    async def fetch() -> StudyAttempt:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                stmt = select(StudyAttempt).where(
                    StudyAttempt.study_session_id == study_session_id,
                    StudyAttempt.question_variant_id == question_variant_id,
                )
                result = await session.execute(stmt)
                attempt = result.scalars().first()
                assert attempt is not None
                return attempt
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _study_items(study_session_id: str) -> list[StudyItem]:
    async def fetch() -> list[StudyItem]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                stmt = (
                    select(StudyItem)
                    .where(StudyItem.study_session_id == study_session_id)
                    .order_by(StudyItem.display_order)
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _study_attempts_all(study_session_id: str) -> list[StudyAttempt]:
    async def fetch() -> list[StudyAttempt]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                stmt = select(StudyAttempt).where(
                    StudyAttempt.study_session_id == study_session_id
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _learning_events(session_id: str) -> list[LearningEvent]:
    """S25: every episodic event `graph/nodes.py` emitted for this learning-session
    thread (`LearningEvent.session_id` is the graph's own `session_id`, not a Postgres
    FK to any exam/study session row).
    """

    async def fetch() -> list[LearningEvent]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                stmt = select(LearningEvent).where(LearningEvent.session_id == session_id)
                result = await session.execute(stmt)
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _semantic_memory_facts(student_id: str) -> list[SemanticMemory]:
    async def fetch() -> list[SemanticMemory]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                stmt = select(SemanticMemory).where(
                    SemanticMemory.student_external_id == student_id
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _mastery_rows(student_id: str) -> list[Mastery]:
    """AUD-L-15 (D-156): mastery now includes the post-exam, so a test has to be able to
    read the rows the post-exam wrote.
    """

    async def fetch() -> list[Mastery]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                stmt = select(Mastery).where(Mastery.student_external_id == student_id)
                result = await session.execute(stmt)
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _stage_transitions(learning_session_id: str) -> list[StageTransition]:
    """S26: every narrative row persisted for this session's thread, real Bedrock
    (mock provider) output or the deterministic template fallback alike.
    """

    async def fetch() -> list[StageTransition]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                stmt = select(StageTransition).where(
                    StageTransition.learning_session_id == learning_session_id
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _interrupt_approvals(learning_session_id: str) -> list[InterruptApproval]:
    async def fetch() -> list[InterruptApproval]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                stmt = select(InterruptApproval).where(
                    InterruptApproval.session_id == learning_session_id
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def test_full_deterministic_learning_flow() -> None:
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        assert create_resp.status_code == 200
        session_id = create_resp.json()["learning_session_id"]

        student_resp = client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        assert student_resp.status_code == 200
        assert student_resp.json()["phase"] == "student_selected"

        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        assert topics_resp.status_code == 200
        topics_body = topics_resp.json()
        assert topics_body["phase"] == "pre_exam"
        pre_items = topics_body["items"]
        assert len(pre_items) == 10

        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])

        # Answer the first two items wrong, the rest correct, so the pre-exam isn't a
        # perfect score (exercises the normal normalized_gain branch, not the
        # not_applicable_pre_max edge case).
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            correct = pre_correct[variant_id]
            selected = _other_option(correct) if index < 2 else correct
            idem_key = f"pre-{index}"

            answer_resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": idem_key},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": selected,
                    "response_time_ms": 3000 + index * 100,
                },
            )
            assert answer_resp.status_code == 200
            body = answer_resp.json()
            # S22/D-064: correctness is withheld from the wire response during pre/post
            # exam - grading still happens immediately (verified below via
            # `_attempt_count`/the finalize response), just not exposed here.
            assert body["is_correct"] is None
            assert body["phase"] == "pre_exam"

            if index == 0:
                # Idempotent resubmission: same (variant, Idempotency-Key) while still in
                # the same phase must return the identical result, not a second row.
                repeat_resp = client.post(
                    f"/learning/sessions/{session_id}/answers",
                    headers={**headers, "Idempotency-Key": idem_key},
                    json={
                        "question_variant_id": variant_id,
                        "selected_option": selected,
                        "response_time_ms": 9999,
                    },
                )
                assert repeat_resp.status_code == 200
                assert repeat_resp.json() == body

        pre_assessment_attempts = _attempt_count(_pre_assessment_session_id(session_id))
        assert pre_assessment_attempts == 10

        # S22/D-064: pre/post exams no longer auto-advance once the last item is
        # answered - every item already has a real grade (verified above via
        # `_attempt_count`), but the phase only transitions on this explicit finalize.
        finalize_resp = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert finalize_resp.status_code == 200
        body = finalize_resp.json()
        assert body["phase"] == "study"

        # S26: the pre_outro narrative fires on the same finalize turn - grounded in
        # this cycle's planned skills and the planner's actual next step (skill *names*,
        # never ids).
        #
        # D-215: this asserted "Skills to strengthen", which is what the line used to say
        # and what made it wrong. `study_plan.py` takes `ranked[:BASE_PROBLEM_COUNT]` and
        # that is 5 of 5 skills, so the list is the whole topic in priority order - a
        # student who scored 7 of 10 was told they had five skills to strengthen, two of
        # which the dashboard scored at 100%. The ordering is useful and unchanged; only the
        # claim made about it moved.
        assert body["stage_narrative"]
        assert body["stage_narrative_evidence"]
        pre_outro_evidence = " ".join(body["stage_narrative_evidence"])
        assert "Study plan, weakest first" in pre_outro_evidence
        assert "Skills to strengthen" not in pre_outro_evidence
        assert "Next up" in pre_outro_evidence

        # A retried finalize call is idempotent - same result, no side effects.
        repeat_finalize_resp = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert repeat_finalize_resp.status_code == 200
        assert repeat_finalize_resp.json() == body

        # S10: the study phase now serves one question at a time and runs a per-skill retry
        # ladder (SPEC §5.11.7), so we drive it as a loop until the phase leaves "study"
        # rather than a fixed 5-item batch. `body["items"]` always carries exactly the one
        # currently-pending question.
        study_step = 0
        answered_wrong_once = False
        while body["phase"] == "study":
            items = body["items"]
            assert items is not None and len(items) == 1
            variant_id = items[0]["question_variant_id"]
            correct = _correct_options([variant_id])[variant_id]
            key = f"study-{study_step}"
            study_step += 1

            if not answered_wrong_once:
                # One deliberately wrong answer proves the SPEC §5.11.3 interrupt: it
                # pauses for a hint/solution/video choice instead of silently advancing.
                answered_wrong_once = True
                wrong_resp = client.post(
                    f"/learning/sessions/{session_id}/answers",
                    headers={**headers, "Idempotency-Key": key},
                    json={
                        "question_variant_id": variant_id,
                        "selected_option": _other_option(correct),
                        "response_time_ms": 2500,
                    },
                )
                assert wrong_resp.status_code == 200
                wrong_body = wrong_resp.json()
                assert wrong_body["is_correct"] is False
                pending = wrong_body["pending_interrupt"]
                assert pending["interrupt_type"] == "intervention_choice"
                assert pending["question_variant_id"] == variant_id

                respond_resp = client.post(
                    f"/learning/sessions/{session_id}/respond",
                    headers=headers,
                    json={"interrupt_type": "intervention_choice", "choice": "hint"},
                )
                assert respond_resp.status_code == 200
                body = respond_resp.json()
                # S8/S21: the hint choice returns validated generated content (mock
                # provider or its deterministic fallback) - never a bare "recorded, no
                # content" ack - and the within-question ladder pauses again for another
                # round (more levels available) instead of immediately advancing.
                intervention = body["intervention"]
                assert intervention["type"] == "hint"
                assert intervention["hint_text"]
                assert intervention["answer_revealed"] is False
                assert intervention["hint_level"] == 1
                assert intervention["max_hint_level"] == 3
                pending = body["pending_interrupt"]
                assert pending["interrupt_type"] == "intervention_choice"

                # "continue" ends the ladder without a further hint/solution/video -
                # SPEC §5.11.7's retry ladder only runs once the support choice is
                # fully resolved.
                continue_resp = client.post(
                    f"/learning/sessions/{session_id}/respond",
                    headers=headers,
                    json={"interrupt_type": "intervention_choice", "choice": "continue"},
                )
                assert continue_resp.status_code == 200
                body = continue_resp.json()
                # SPEC §5.11.7: after the ladder closes the same skill line serves a
                # retry question, so the phase is still study with a fresh pending item,
                # not an advance.
                assert body["phase"] == "study"
                continue

            answer_resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": key},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": correct,
                    "response_time_ms": 2500,
                },
            )
            assert answer_resp.status_code == 200
            body = answer_resp.json()
            assert body["is_correct"] is True

        assert body["phase"] == "post_exam"
        # S26: `study_outro` fires on the exact turn study completes - grounded in this
        # cycle's real hint/solution/video usage (the mock-provider hint round above).
        assert body["stage_narrative"]
        assert body["stage_narrative_evidence"]
        assert any("Hints used" in line for line in body["stage_narrative_evidence"])
        # SPEC §5.25.1 "per-session cost budget" - the mock provider hint call above must
        # have registered real (if placeholder) spend against the session's running total.
        assert _bedrock_spend_cents(session_id) > 0
        post_items = body["items"]
        assert len(post_items) == 10
        post_correct = _correct_options([item["question_variant_id"] for item in post_items])

        for index, item in enumerate(post_items):
            variant_id = item["question_variant_id"]
            correct = post_correct[variant_id]

            answer_resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"post-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": correct,
                    "response_time_ms": 2000,
                },
            )
            assert answer_resp.status_code == 200
            body = answer_resp.json()
            # S22/D-064: withheld during the exam, same as the pre-exam loop above.
            assert body["is_correct"] is None
            assert body["phase"] == "post_exam"

        finalize_resp = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert finalize_resp.status_code == 200
        body = finalize_resp.json()
        assert body["phase"] == "completed"
        gain = body["learning_gain"]
        assert gain is not None
        assert gain["pre_raw_score"] == 8.0
        assert gain["post_raw_score"] == 10.0
        assert gain["raw_gain"] == 2.0
        if gain["normalized_gain"] is None:
            assert gain["normalized_gain_status"] == "not_applicable_pre_max"
        else:
            assert gain["normalized_gain_status"] is None
            assert 0.0 < gain["normalized_gain"] <= 1.0

        # S26: `post_outro` fires on this same finalize turn, grounded in the real
        # SPEC §5.13.3 gain just computed above (8.0 -> 10.0, a real gain of 2.0).
        assert body["stage_narrative"]
        assert body["stage_narrative_evidence"]
        post_outro_evidence = " ".join(body["stage_narrative_evidence"])
        assert "8.0" in post_outro_evidence
        assert "10.0" in post_outro_evidence

        # S26: every in-graph narrative moment fired at least once across this one full
        # pre->study->post cycle, including `study_step` - proving a genuine skill
        # transition (not just a same-skill retry) triggered its own narrative
        # somewhere mid-loop, even though the checkpoint's own `stage_narrative` channel
        # was since overwritten by `study_outro`/`post_outro` (S26: `stage_narrative`
        # only ever exposes the *latest* narrative, like `last_message` - the durable
        # `stage_transitions` table is the source of truth for every one that fired).
        transitions = _stage_transitions(session_id)
        stages_fired = {t.stage for t in transitions}
        assert stages_fired == {"pre_outro", "study_step", "study_outro", "post_outro"}
        assert all(t.student_external_id == STUDENT_UNLINKED for t in transitions)
        assert all(t.evidence for t in transitions)

        # S25 (plan §9): every one of the six emission points should have fired at
        # least once across this one full pre->study->post cycle.
        events = _learning_events(session_id)
        event_types = {event.event_type for event in events}
        assert event_types == {
            "answer_submitted",
            "intervention_chosen",
            "study_outcome",
            "exam_finalized",
            "learning_gain_computed",
        }
        assert all(event.student_external_id == STUDENT_UNLINKED for event in events)

        # The post-exam finalize triggered a real, session-scoped consolidation call
        # (plan §9 trigger (a)) - MockBedrockProvider's deterministic stand-in proposes
        # at least one candidate fact from this cycle's own events. A single learning
        # session can only ever supply one distinct `session_id` of evidence, so the
        # minimum-evidence "≥2 sessions" bar (plan §9) is never met by this one cycle
        # alone - every fact from it must land `provisional`, never `active`.
        facts = _semantic_memory_facts(STUDENT_UNLINKED)
        assert len(facts) > 0
        assert all(fact.status == "provisional" for fact in facts)
        assert all(fact.evidence_event_ids for fact in facts)
        assert all(
            {event.event_id for event in events} >= set(fact.evidence_event_ids)
            for fact in facts
        )


def test_retry_ladder_reaches_unresolved_with_tutor_flag_and_prerequisite() -> None:
    """SPEC §5.11.7: a skill the student never resolves escalates through same-skill
    retries and an easier *prerequisite* problem, then - on the 4th unresolved attempt -
    is marked for tutor review while the flow continues. Driven on `linear_two_step` (whose
    prerequisite is `linear_one_step`) by failing both difficulty-2 pre-exam items so it is
    the weakest, hence first-served, skill.
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        pre_items = topics_resp.json()["items"]
        pre_variant_ids = [item["question_variant_id"] for item in pre_items]
        pre_correct = _correct_options(pre_variant_ids)

        # D-212: **every** pre-exam item is answered wrong.
        #
        # D-207 changed this from "indices 2,3" to "the `linear_two_step` items, by skill",
        # to stop inferring a skill from a position. That was right and still not enough:
        # it assumed failing a skill makes it the one the study phase routes first, and
        # `build_study_plan` ranks on `mastery.weighted_score if mastery is not None else
        # 0.0`, so a skill the draw **never served** has no row, scores 0.0, and is routed
        # ahead of it. That is how this test reached CI as `assert 1 == 4` - the ladder ran
        # in full, just on a different skill than the assertions named.
        #
        # Failing everything removes the question. This test is about the *shape* of the
        # retry ladder, not about which skill enters it, and a student who got the whole
        # pre-exam wrong is a coherent thing to be. The line is then read from whichever
        # item the flow actually served, below.
        wrong_variant_ids = set(pre_variant_ids)

        body = None
        for item in pre_items:
            variant_id = item["question_variant_id"]
            correct = pre_correct[variant_id]
            selected = _other_option(correct) if variant_id in wrong_variant_ids else correct
            answer_resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                # Keyed on the variant rather than the loop index, since the loop no longer
                # enumerates. Unique per item either way, which is all this needs.
                headers={**headers, "Idempotency-Key": f"ladder-pre-{variant_id}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": selected,
                    "response_time_ms": 2000,
                },
            )
            body = answer_resp.json()

        assert body is not None and body["phase"] == "pre_exam"
        body = _finalize_exam(client, headers, session_id)
        assert body["phase"] == "study"
        first_item = body["items"][0]
        assert first_item is not None

        # Drive four straight wrong answers through the full ladder, choosing "solution"
        # each time so the eventual outcome is answer_revealed -> unresolved.
        for attempt_index in range(4):
            variant_id = body["items"][0]["question_variant_id"]
            correct = _correct_options([variant_id])[variant_id]
            wrong_resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"ladder-{attempt_index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": _other_option(correct),
                    "response_time_ms": 2000,
                },
            )
            assert wrong_resp.status_code == 200
            assert wrong_resp.json()["pending_interrupt"]["interrupt_type"] == (
                "intervention_choice"
            )
            respond_resp = client.post(
                f"/learning/sessions/{session_id}/respond",
                headers=headers,
                json={"interrupt_type": "intervention_choice", "choice": "solution"},
            )
            assert respond_resp.status_code == 200
            body = respond_resp.json()

        # After the 4th unresolved attempt the skill line is abandoned and the flow moves
        # on (to the next base skill), rather than looping forever on the same skill.
        assert body["phase"] == "study"

        study_session_id = _study_session_id(session_id)

    items = _study_items(study_session_id)
    attempts = _study_attempts_all(study_session_id)

    # D-212: the line is whichever skill the flow routed first, read from the item the
    # ladder was actually driven on, rather than a skill name this test hoped for.
    line_skill = next(i.target_skill_id for i in items if i.display_order == 0)
    line_items = [i for i in items if i.target_skill_id == line_skill]
    # Base + 2 same-skill retries + 1 prerequisite problem = 4 questions on the line.
    assert len(line_items) == 4
    assert line_items[0].is_remediation is False
    assert [i.is_remediation for i in line_items[1:]] == [True, True, True]

    # The §5.11.7 3rd step serves the prerequisite skill's question - but only when the
    # routed skill *has* a prerequisite with approved templates. `flow._advance_study`
    # falls back to another same-skill retry otherwise, and `linear_one_step` (the root of
    # this topic's chain) has no prerequisite at all, so this cannot be unconditional.
    prerequisite_skill = load_curriculum().prerequisite_for(line_skill)
    if prerequisite_skill is not None:
        prerequisite_items = [i for i in line_items if i.skill_id == prerequisite_skill]
        assert len(prerequisite_items) == 1, (
            f"{line_skill}'s ladder served {len(prerequisite_items)} items from its "
            f"prerequisite {prerequisite_skill}, expected exactly one"
        )
        # The original `difficulty == 1` assertion is deliberately not generalised to
        # "easier than the base". It held only because `linear_one_step` has a single tier:
        # `linear_both_sides` (tiers 3-5) has prerequisite `linear_neg_frac_coeff` (2-4),
        # so a prerequisite item can legitimately outrank the base one. The remediation
        # path passes `recommended_difficulty=None` by design (AUD-L-12), so the code makes
        # no difficulty promise here - asserting one would pin an accident of the bank.
    else:
        assert all(i.skill_id == line_skill for i in line_items), (
            f"{line_skill} has no prerequisite, so every ladder item should stay on it"
        )

    line_variant_ids = {i.question_variant_id for i in line_items}
    line_attempts = [a for a in attempts if a.question_variant_id in line_variant_ids]
    assert len(line_attempts) == 4
    assert all(a.is_correct is False for a in line_attempts)
    # Exactly one terminal attempt: unresolved + flagged for tutor review (SPEC §5.11.7).
    unresolved = [a for a in line_attempts if a.outcome_label == "unresolved"]
    assert len(unresolved) == 1
    assert unresolved[0].tutor_review_flagged is True
    assert all(not a.tutor_review_flagged for a in line_attempts if a not in unresolved)


def test_difficulty_recommendation_reaches_template_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUD-L-12: `Mastery.recommended_difficulty` was computed, stored and displayed while
    `build_study_plan` dropped it out of the ranking tuple - so §5.11.2 rules 2-3 were
    unimplemented and two docstrings said otherwise.

    This asserts the *wiring* on the path that actually runs, by recording what reaches
    `_select_template` during a real flow. It deliberately does not assert a served tier:
    the live bank is 1:1 skill<->difficulty, so no recommendation can change which template
    is served today, and a tier assertion would therefore pass with the value still
    discarded. `test_study_plan_difficulty_routing.py` covers the selection rule itself
    against synthetic multi-tier templates.

    Three contracts, one flow:
      1. the first base question is selected with the weakest skill's own recommendation,
      2. a *remediation* question is selected with `None` - the retry ladder owns its own
         difficulty movement (`flow._advance_study`),
      3. the next base skill, served later by `flow._serve_next_base_or_complete`, is
         selected with *its* recommendation, re-read after mastery was recomputed.
    """
    calls: list[tuple[str, int | None]] = []
    real_select = study_plan._select_template

    async def recording_select(
        question_repo, skill_id, used_template_ids, rng, recommended_difficulty
    ):
        calls.append((skill_id, recommended_difficulty))
        return await real_select(
            question_repo, skill_id, used_template_ids, rng, recommended_difficulty
        )

    monkeypatch.setattr(study_plan, "_select_template", recording_select)

    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        pre_items = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        ).json()["items"]
        pre_variant_ids = [i["question_variant_id"] for i in pre_items]
        pre_correct = _correct_options(pre_variant_ids)
        pre_skills = _skills_for(pre_variant_ids)

        # Same setup as the retry-ladder test, and fixed the same way (D-207): fail the
        # `linear_two_step` items **by skill** so it is the weakest skill and is routed
        # first. This said "indices 2,3" too, and was the second of the two tests carrying
        # D-206's already-disposed-of premise - it is the one that failed the first local
        # full-suite run of this change with `assert 2 == 1`, because a draw where
        # `linear_two_step` did not own both tier-2 slots leaves its mastery, and therefore
        # its recommended difficulty, somewhere else entirely.
        wrong_variant_ids = {
            variant_id
            for variant_id, skill_id in pre_skills.items()
            if skill_id == "linear_two_step"
        }
        if not wrong_variant_ids:
            pytest.skip(
                "this pre-exam draw served no linear_two_step item "
                f"(skills drawn: {sorted(set(pre_skills.values()))})"
            )

        for item in pre_items:
            variant_id = item["question_variant_id"]
            correct = pre_correct[variant_id]
            selected = _other_option(correct) if variant_id in wrong_variant_ids else correct
            client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"recdiff-pre-{variant_id}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": selected,
                    "response_time_ms": 2000,
                },
            )

        body = _finalize_exam(client, headers, session_id)
        assert body["phase"] == "study"

        base_calls = list(calls)
        assert base_calls, "no template selection happened while building the study plan"
        first_skill, first_recommended = base_calls[-1]

        # D-212: this used to assert `first_skill == "linear_two_step"` - the last hardcoded
        # skill name left over from D-206's disposed-of premise, and it failed in CI on a
        # draw that served no `linear_one_step` item.
        #
        # The mechanism is in `build_study_plan`'s ranking, and it is not a flake:
        #
        #     weighted = mastery.weighted_score if mastery is not None else 0.0
        #
        # A skill the pre-exam never served has **no mastery row at all**, so it ranks at
        # 0.0 - weaker than any skill the student merely answered badly. Whichever skills a
        # draw omits are therefore routed *first*, ahead of the one this test deliberately
        # failed. Failing `linear_two_step` makes it the weakest skill *that was measured*,
        # which is not the same thing as the weakest skill.
        #
        # So the assertion is on the routed skill itself rather than on its name. That is
        # also the contract the docstring states: the first base question is selected with
        # **the weakest skill's own** recommendation, whichever skill that turns out to be.
        # An unmeasured skill's recommendation is legitimately `None`, so the assertion is
        # "whatever that skill's row says, including its absence" rather than "not None".
        # Vacuity is guarded once at the end instead, where both routed skills are known.
        def _recommendation_of(rows: dict, skill_id: str) -> int | None:
            row = rows.get(skill_id)
            return row.recommended_difficulty if row is not None else None

        rows = {row.skill_id: row for row in _mastery_rows(STUDENT_UNLINKED)}
        assert first_recommended == _recommendation_of(rows, first_skill), (
            f"the first base question was selected with {first_recommended!r}, but "
            f"{first_skill}'s mastery row says {_recommendation_of(rows, first_skill)!r}"
        )
        # The `first_recommended == 1` step-down assertion that used to sit here went with
        # the hardcoded name: it only holds for a skill whose items were all failed, and
        # the routed skill is no longer guaranteed to be that one. `_select_template`'s
        # actual difficulty rule is covered against synthetic multi-tier templates in
        # `test_study_plan_difficulty_routing.py`, which is where it belongs - this test is
        # about the value reaching the call at all.

        # One wrong answer + "solution" produces a remediation item on the same line.
        variant_id = body["items"][0]["question_variant_id"]
        correct = _correct_options([variant_id])[variant_id]
        client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "recdiff-study-wrong"},
            json={
                "question_variant_id": variant_id,
                "selected_option": _other_option(correct),
                "response_time_ms": 2000,
            },
        )
        body = client.post(
            f"/learning/sessions/{session_id}/respond",
            headers=headers,
            json={"interrupt_type": "intervention_choice", "choice": "solution"},
        ).json()
        assert body["phase"] == "study"
        remediation_skill, remediation_recommended = calls[-1]
        # D-212: the contract is "remediation stays on the line just answered", not a
        # particular skill name - so it is checked against the skill actually routed above.
        assert remediation_skill == first_skill
        assert remediation_recommended is None, (
            "the retry ladder must not apply the bootstrap recommendation - it has its own "
            "difficulty policy (same skill, then the prerequisite one tier down)"
        )

        # Resolving the line correctly moves to the next base skill, which is where
        # `_serve_next_base_or_complete` has to read that skill's own recommendation.
        variant_id = body["items"][0]["question_variant_id"]
        correct = _correct_options([variant_id])[variant_id]
        body = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "recdiff-study-right"},
            json={
                "question_variant_id": variant_id,
                "selected_option": correct,
                "response_time_ms": 2000,
            },
        ).json()
        assert body["phase"] == "study"
        next_skill, next_recommended = calls[-1]
        assert next_skill != first_skill, "expected the next base skill line"
        rows_after = {row.skill_id: row for row in _mastery_rows(STUDENT_UNLINKED)}
        assert next_recommended == _recommendation_of(rows_after, next_skill), (
            f"the next base skill was selected with {next_recommended!r}, but "
            f"{next_skill}'s mastery row says "
            f"{_recommendation_of(rows_after, next_skill)!r} - "
            "`_serve_next_base_or_complete` is not reading the mastery row"
        )

        # D-212 vacuity guard. Both assertions above would also hold if the code passed a
        # constant `None`, so the test is only meaningful once at least one routed skill was
        # actually measured by this draw. Which skills a draw covers is not controllable
        # here (that is the whole finding), so a draw that measured neither routed skill is
        # skipped explicitly rather than counted as a pass.
        if first_recommended is None and next_recommended is None:
            pytest.skip(
                "this pre-exam draw measured neither routed skill "
                f"({first_skill}, {next_skill}), so both recommendations are legitimately "
                "None and the wiring assertions above cannot distinguish a real read from "
                "a hardcoded None"
            )


def _drive_full_flow(
    student_id: str,
    pre_wrong_indices: set[int],
    post_wrong_indices: set[int] | None = None,
) -> tuple[list, dict]:
    """Run one full pre -> study (all correct) -> post flow and return the base study
    routing and the learning-gain scores, for the Phase 10 determinism check.

    `post_wrong_indices` (AUD-L-15/D-156) makes the post-exam answerable incorrectly, which
    is what lets a test tell whether mastery counts the post-exam at all: with pre and study
    both correct, every skill reads 1.0 unless the post-exam is in the computation.
    """
    post_wrong_indices = post_wrong_indices or set()
    headers = _auth_header(_student_token(student_id))
    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": student_id},
        )
        pre_items = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        ).json()["items"]
        pre_correct = _correct_options([i["question_variant_id"] for i in pre_items])

        body: dict = {}
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            correct = pre_correct[variant_id]
            selected = _other_option(correct) if index in pre_wrong_indices else correct
            body = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"det-pre-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": selected,
                    "response_time_ms": 2000,
                },
            ).json()

        body = _finalize_exam(client, headers, session_id)

        step = 0
        while body["phase"] == "study":
            variant_id = body["items"][0]["question_variant_id"]
            correct = _correct_options([variant_id])[variant_id]
            body = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"det-study-{step}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": correct,
                    "response_time_ms": 2000,
                },
            ).json()
            step += 1

        for index, item in enumerate(body["items"]):
            variant_id = item["question_variant_id"]
            correct = _correct_options([variant_id])[variant_id]
            selected = _other_option(correct) if index in post_wrong_indices else correct
            body = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"det-post-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": selected,
                    "response_time_ms": 2000,
                },
            ).json()

        body = _finalize_exam(client, headers, session_id)
        assert body["phase"] == "completed"
        gain = body["learning_gain"]
        study_session_id = _study_session_id(session_id)

    items = _study_items(study_session_id)
    routing = [(i.target_skill_id, i.difficulty, i.is_remediation) for i in items]
    return routing, gain


def test_mastery_counts_the_post_exam() -> None:
    """AUD-L-15 (D-156). `_recompute_all_skill_mastery` used to accept only a pre-exam and
    a study session, so the post-exam - the most recent and most comprehensive measurement
    of the cycle - never reached `mastery.weighted_score`. That is what let S36's
    `aud-student-premax` report mastery 1.000 for a skill it had just missed on the
    post-exam, and it also meant `topic_resolver` chose the *next* cycle's target skills
    without ever seeing how the last one ended.

    Pre and study are answered entirely correctly here, so every touched skill would read
    1.0 on the old behaviour. Every post-exam item is answered wrong, so on the new
    behaviour mastery must come down - which is only possible if the post-exam counts.
    """
    _routing, gain = _drive_full_flow(
        STUDENT_UNLINKED, pre_wrong_indices=set(), post_wrong_indices=set(range(10))
    )
    assert gain["post_raw_score"] == 0.0

    rows = _mastery_rows(STUDENT_UNLINKED)
    assert rows, "the cycle should have written mastery rows"
    assert any(row.weighted_score < 1.0 for row in rows), (
        "every skill still reads a perfect score after a post-exam that got everything "
        "wrong - the post-exam is not reaching mastery"
    )


@pytest.mark.xfail(
    reason=(
        "D-206: this test's premise stopped holding when the approved bank grew from 5 "
        "authored items to 48, and the premise is what is wrong, not the routing. Each "
        "session builds its own random exam - measured directly: two calls for the same "
        "student return entirely different variant ids - so 'the same wrong indices' were "
        "never the same input. Position 2 in one run is a different question from position "
        "2 in the next. It passed for years because the pool was small enough that a given "
        "position reliably landed on the same skill and tier; a larger pool ended the "
        "coincidence. Answering by tier instead was tried and fails the same way, because "
        "which skills carry tier-2 items also varies per exam. Making this assertion true "
        "needs a fixed exam, i.e. a seed hook through the HTTP flow, which is a product "
        "change and a decision to take deliberately. The deterministic-core guarantee "
        "CLAUDE.md #2 actually makes is separately pinned and still passes - see "
        "test_pre_exam_build_is_deterministic_for_a_fixed_seed, which builds from an "
        "explicit RNG."
    ),
    # D-238 relaxed this from strict. The reason above says the exam is random per session,
    # and a strict xfail over a random subject is a coin flip that reports as a suite
    # failure when it lands heads: this test XPASSed once in a full run and xfailed on the
    # next, from the same tree, with no code between them. Strict is right for an expected
    # failure that is *deterministic* - it tells you the day the bug is fixed. Here it
    # cannot, because passing means the random exam happened to repeat, and a red suite that
    # means nothing is worse than an expected failure that stays quiet.
    strict=False,
)
def test_identical_inputs_reproduce_identical_routing_and_scores() -> None:
    """Phase 10 (§6.11) completion criterion / §5.31.1 deterministic evaluator: the same
    answer sequence yields the same study routing and the same learning-gain scores.
    """
    routing_a, gain_a = _drive_full_flow(STUDENT_UNLINKED, pre_wrong_indices={2, 3})
    routing_b, gain_b = _drive_full_flow(STUDENT_UNLINKED, pre_wrong_indices={2, 3})

    assert routing_a == routing_b
    assert gain_a == gain_b
    # Difficulty routing responded to the pre-exam: failing both difficulty-2 items makes
    # `linear_two_step` the weakest skill, so it is routed first.
    assert routing_a[0][0] == "linear_two_step"


def test_wrong_final_pre_exam_answer_enters_study_without_spurious_interrupt() -> None:
    """Regression (S22/D-064 update): an incorrect *last* pre-exam answer, followed by an
    explicit finalize, transitions to study but records no study attempt, so finalize must
    not be routed into the §5.11.3 hint/solution/video interrupt - only a real study answer
    is. (Pre-S22 this guarded the same property on the auto-advance path; that path no
    longer exists - finalize is now the only thing that can transition pre_exam -> study.)
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        pre_items = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        ).json()["items"]
        pre_correct = _correct_options([i["question_variant_id"] for i in pre_items])

        body = None
        last_index = len(pre_items) - 1
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            correct = pre_correct[variant_id]
            # Answer every item correctly except the very last one.
            selected = _other_option(correct) if index == last_index else correct
            answer_resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"lastwrong-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": selected,
                    "response_time_ms": 2000,
                },
            )
            assert answer_resp.status_code == 200
            body = answer_resp.json()

        assert body is not None
        assert body["is_correct"] is None  # withheld during the exam (D-064)
        assert body["phase"] == "pre_exam"

        body = _finalize_exam(client, headers, session_id)
        assert body["phase"] == "study"  # ...but we still advanced into study
        # `FinalizeExamResponse` has no `pending_interrupt` field at all - `finalize_exam`
        # never calls `interrupt()`, so pausing for an intervention here is structurally
        # impossible, not just untriggered.
        assert body["items"] is not None and len(body["items"]) == 1


def test_blocked_attendance_branch() -> None:
    token = _student_token(STUDENT_FIRST_CHILD)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]

        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_FIRST_CHILD},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )

    assert topics_resp.status_code == 200
    body = topics_resp.json()
    assert body["phase"] == "blocked"
    assert body["items"] is None
    # STUDENT_FIRST_CHILD is marked *absent*, so the recorded-absence framing is correct.
    assert body["message"] == BLOCKED_MESSAGE

    assert _blocked_session_count(STUDENT_FIRST_CHILD, current_week_key()) >= 1


def test_unknown_attendance_block_reads_as_not_yet_marked_not_as_absence() -> None:
    """D-152 §2: `attended = null` is the *routine* production state, so the block a
    student sees must say attendance is not yet marked and steer an attended student to the
    verify path - not the recorded-absence framing, which makes "did not attend" (which
    permanently ends the week) the wrong default. Fail-closed itself is unchanged; only the
    message differs. STUDENT_SECOND_CHILD has no attendance row -> UNKNOWN.
    """
    token = _student_token(STUDENT_SECOND_CHILD)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]

        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_SECOND_CHILD},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )

    assert topics_resp.status_code == 200
    body = topics_resp.json()
    assert body["phase"] == "blocked"
    assert body["items"] is None
    assert body["message"] == UNKNOWN_MESSAGE
    # The two blocks must not read the same, and the unknown one must not imply absence.
    assert UNKNOWN_MESSAGE != BLOCKED_MESSAGE
    assert "not been marked yet" in body["message"]
    assert "did not receive" not in body["message"]

    assert _blocked_session_count(STUDENT_SECOND_CHILD, current_week_key()) >= 1


def test_restart_and_resume_continues_from_same_question() -> None:
    """SPEC §5.16 "Done when": killing the process mid-session and calling resume
    continues from the same question. Exiting the first `TestClient` block tears down
    the app's lifespan - including the `AsyncPostgresSaver` connection - and entering a
    second one opens a brand new checkpointer connection to the same Postgres, standing
    in for a real process restart.
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]

        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        assert topics_resp.status_code == 200
        pre_items_before = topics_resp.json()["items"]

    # The app (and its checkpointer connection) has fully shut down here.

    with TestClient(app) as client:
        resume_resp = client.post(f"/learning/sessions/{session_id}/resume", headers=headers)

    assert resume_resp.status_code == 200
    body = resume_resp.json()
    assert body["phase"] == "pre_exam"
    assert body["items"] == pre_items_before


def test_resume_after_an_exam_answer_still_returns_the_full_batch() -> None:
    """S23 regression: under free navigation (D-064), every pre/post-exam `/answers`
    call reports `items: None` on the wire (nothing new to show, the nav bar is driven
    by `exam/overview` instead) - but the graph node used to write that `None` straight
    into the checkpointed `last_items` channel, silently erasing the original 10-question
    batch the instant any answer was submitted. A resume (or a browser refresh, which
    reads the same checkpointed state via `/stream`) after even one answer would then have
    no question content left to show at all. Fixed by omitting the key from the node's
    update dict instead of clearing it (see `graph/nodes.py::submit_answer`) - LangGraph's
    default `LastValue` merge leaves an omitted channel holding its previous value.
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        pre_items_before = topics_resp.json()["items"]
        correct = _correct_options([item["question_variant_id"] for item in pre_items_before])
        first = pre_items_before[0]

        answer_resp = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "resume-regression-0"},
            json={
                "question_variant_id": first["question_variant_id"],
                "selected_option": correct[first["question_variant_id"]],
                "response_time_ms": 1500,
            },
        )
        assert answer_resp.status_code == 200
        # The per-request response still has nothing new to report - only the
        # checkpointed batch itself must survive, not necessarily every response body.
        assert answer_resp.json()["is_correct"] is None

    # The app (and its checkpointer connection) has fully shut down here.

    with TestClient(app) as client:
        resume_resp = client.post(f"/learning/sessions/{session_id}/resume", headers=headers)

    assert resume_resp.status_code == 200
    body = resume_resp.json()
    assert body["phase"] == "pre_exam"
    assert body["items"] == pre_items_before


def test_intervention_choice_pause_records_choice_and_blocks_skip() -> None:
    """SPEC §5.11.3 + Phase 8 (§6.9): an incorrect study answer pauses for a
    hint/solution/video choice; the choice is recorded on the attempt, and a client
    cannot silently skip past the pause by submitting the next answer instead (S7's
    `/answers`-guard against LangGraph discarding an unresolved paused task).
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]

        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        pre_items = topics_resp.json()["items"]
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])

        body = None
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            answer_resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"iv-pre-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )
            assert answer_resp.status_code == 200
            body = answer_resp.json()

        assert body is not None
        assert body["phase"] == "pre_exam"
        body = _finalize_exam(client, headers, session_id)
        assert body["phase"] == "study"
        # S10: one question is served at a time; this is the first (weakest) skill's item.
        study_items = body["items"]
        assert len(study_items) == 1
        wrong_variant_id = study_items[0]["question_variant_id"]
        wrong_correct = _correct_options([wrong_variant_id])[wrong_variant_id]

        wrong_resp = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "iv-study-0"},
            json={
                "question_variant_id": wrong_variant_id,
                "selected_option": _other_option(wrong_correct),
                "response_time_ms": 2000,
            },
        )
        assert wrong_resp.status_code == 200
        wrong_body = wrong_resp.json()
        assert wrong_body["is_correct"] is False
        pending = wrong_body["pending_interrupt"]
        assert pending["interrupt_type"] == "intervention_choice"
        assert pending["question_variant_id"] == wrong_variant_id

        # Trying to move on without resolving the pause is rejected, not silently
        # dropped (a fresh, non-`Command` `ainvoke` would otherwise discard the paused
        # task and lose the choice-capture opportunity entirely).
        skip_resp = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "iv-study-skip"},
            json={
                "question_variant_id": wrong_variant_id,
                "selected_option": wrong_correct,
                "response_time_ms": 2000,
            },
        )
        assert skip_resp.status_code == 409

        respond_resp = client.post(
            f"/learning/sessions/{session_id}/respond",
            headers=headers,
            json={"interrupt_type": "intervention_choice", "choice": "video"},
        )
        assert respond_resp.status_code == 200
        respond_body = respond_resp.json()
        assert respond_body["phase"] == "study"
        # SPEC §5.11.6/§5.18.3: real Postgres-backed catalog (S15), so *which* of the two
        # valid shapes comes back is not this test's business (D-222). It used to assert
        # the fallback message on a precondition this file only stated in a comment - "no
        # `youtube_videos` row seeded for this skill" - which nothing enforces and which
        # is false on any machine where `make youtube-sync` has been run against the fake
        # provider: 4 approved rows, `difficulty` 2-4, covering 4 of this topic's 5
        # skills. Serving picks the study item with an unseeded `random.Random()`
        # (`routers/sessions.py`, correct for production), and `search_video` filters
        # hard on skill_id + difficulty, so ~1 round in 12 landed inside that window and
        # got a real match. CI never saw it: its database is fresh, so the table is empty.
        # The verbatim-fallback proof belongs to `test_video_catalog.py`, which owns it
        # deterministically inside a rollback transaction. What this flow test is *about*
        # is that choosing "video" resolves the pause and is recorded on the attempt.
        intervention = respond_body["intervention"]
        assert intervention["type"] == "video"
        # On the *value*, not on the key: `InterventionContentResponse` declares
        # `video_title`/`video_url` as optional fields, so both keys are always present in
        # the JSON and `"video_url" in intervention` is true even for the fallback. Getting
        # that wrong is how the first version of this fix passed a rigged catalog 8/8 while
        # never once exercising the branch it was written for.
        if intervention["video_url"]:
            assert intervention["video_title"]
            assert intervention["video_source"]
        else:
            assert intervention["message"] == video_catalog.FALLBACK_MESSAGE

        # `_study_session_id` reads via `app.state.learning_graph`, so it must run while
        # this block's checkpointer connection is still open.
        study_session_id = _study_session_id(session_id)

    attempt = _study_attempt(study_session_id, wrong_variant_id)
    assert attempt.is_correct is False
    assert attempt.video_used is True
    assert attempt.hint_used is False
    assert attempt.solution_used is False


def test_hint_ladder_escalates_through_three_levels_without_leaking_answer() -> None:
    """ROADMAP S21 "Done when": three successive hints escalate and never reveal the
    answer before the final level. Each "hint" choice pauses again (more levels
    available) instead of immediately advancing; only the third (final) level's choice
    runs the retry ladder and serves a fresh question. `hint_used` stays True and no
    `advance_study` transition happens on rounds 1-2.
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]

        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        pre_items = topics_resp.json()["items"]
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])

        body = None
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            answer_resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"ladder-pre-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )
            body = answer_resp.json()

        assert body is not None
        body = _finalize_exam(client, headers, session_id)
        study_items = body["items"]
        wrong_variant_id = study_items[0]["question_variant_id"]
        wrong_correct = _correct_options([wrong_variant_id])[wrong_variant_id]
        correct_answer_text = {
            "a": study_items[0]["option_a"],
            "b": study_items[0]["option_b"],
            "c": study_items[0]["option_c"],
            "d": study_items[0]["option_d"],
        }[wrong_correct]

        wrong_resp = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "ladder-study-0"},
            json={
                "question_variant_id": wrong_variant_id,
                "selected_option": _other_option(wrong_correct),
                "response_time_ms": 2000,
            },
        )
        assert wrong_resp.json()["pending_interrupt"]["interrupt_type"] == "intervention_choice"

        hint_levels_seen: list[int] = []
        hint_texts: list[str] = []
        respond_body = None
        for _ in range(3):
            respond_resp = client.post(
                f"/learning/sessions/{session_id}/respond",
                headers=headers,
                json={"interrupt_type": "intervention_choice", "choice": "hint"},
            )
            assert respond_resp.status_code == 200
            respond_body = respond_resp.json()
            intervention = respond_body["intervention"]
            assert intervention["type"] == "hint"
            assert intervention["answer_revealed"] is False
            # AUD-X-06: assert the rule the product enforces (`tutor.py`'s runtime check),
            # not a plain substring. A plain `in` check is *stricter* than the product's
            # guarantee - `answer_text_leaked` deliberately ignores a digit adjacent to
            # another alphanumeric - so it flagged the mock's own "Hint L3" prefix as a
            # leak of the answer "3" whenever the drawn variant's answer was 1, 2 or 3
            # (measured: 8 failures in 40 runs, always answer == str(level)). Tightening
            # the mock's prefix was AUD-L-17's fix and only moved which answers collide.
            hint_text = intervention["hint_text"]
            assert not leak_phrase_present(hint_text)
            assert not answer_text_leaked(hint_text, correct_answer_text)
            hint_levels_seen.append(intervention["hint_level"])
            hint_texts.append(intervention["hint_text"])

        assert hint_levels_seen == [1, 2, 3]
        # Each level's text is genuinely different, not the same content repeated -
        # `MockBedrockProvider`'s personalization branch varies by hint_level/canonical
        # text, and the canonical ladder itself has 3 distinct levels.
        assert len(set(hint_texts)) == 3
        # The third (final) level closed the ladder on its own - no explicit "continue"
        # needed - and served a fresh retry question for the same skill line.
        assert respond_body is not None
        assert respond_body["phase"] == "study"
        assert respond_body["pending_interrupt"] is None
        assert respond_body["items"] is not None
        assert len(respond_body["items"]) == 1

        study_session_id = _study_session_id(session_id)

    attempt = _study_attempt(study_session_id, wrong_variant_id)
    assert attempt.hint_used is True
    assert attempt.video_used is False
    assert attempt.solution_used is False


def test_hint_ladder_survives_restart_mid_ladder() -> None:
    """SPEC §5.16-style restart guarantee, applied to S21's new ladder state: a
    checkpoint restart between hint rounds must not lose `assistance_level_by_variant`
    - the next hint requested after restart must be level 2, not a repeat of level 1.
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]

        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        pre_items = topics_resp.json()["items"]
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])

        body = None
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            answer_resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"restart-ladder-pre-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )
            body = answer_resp.json()

        assert body is not None
        body = _finalize_exam(client, headers, session_id)
        study_items = body["items"]
        wrong_variant_id = study_items[0]["question_variant_id"]
        wrong_correct = _correct_options([wrong_variant_id])[wrong_variant_id]

        client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "restart-ladder-study-0"},
            json={
                "question_variant_id": wrong_variant_id,
                "selected_option": _other_option(wrong_correct),
                "response_time_ms": 2000,
            },
        )
        first_hint_resp = client.post(
            f"/learning/sessions/{session_id}/respond",
            headers=headers,
            json={"interrupt_type": "intervention_choice", "choice": "hint"},
        )
        assert first_hint_resp.json()["intervention"]["hint_level"] == 1

    # The app (and its checkpointer connection) has fully shut down here.

    with TestClient(app) as client:
        second_hint_resp = client.post(
            f"/learning/sessions/{session_id}/respond",
            headers=headers,
            json={"interrupt_type": "intervention_choice", "choice": "hint"},
        )

    assert second_hint_resp.status_code == 200
    assert second_hint_resp.json()["intervention"]["hint_level"] == 2


def test_hint_reflects_the_students_actual_wrong_option() -> None:
    """ROADMAP S21 "Done when": a personalized hint addresses the mapped misconception.
    Scripted against `MockBedrockProvider`'s own deterministic personalization branch
    (it embeds the resolved `misconception_tag` verbatim into `hint_text`) - the
    hand-authored `linear_equations` bank's `common_error_tags` are
    `["sign_error", "off_by_one", "magnitude_error"]` for every template
    (`templates/linear_equations.py`), ordinal-mapped to the three non-correct options.
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]

        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        pre_items = topics_resp.json()["items"]
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])

        body = None
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            answer_resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"misconception-pre-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )
            body = answer_resp.json()

        assert body is not None
        body = _finalize_exam(client, headers, session_id)
        study_items = body["items"]
        wrong_variant_id = study_items[0]["question_variant_id"]
        wrong_correct = _correct_options([wrong_variant_id])[wrong_variant_id]
        wrong_option = _other_option(wrong_correct)
        expected_tag = topic_resolver_expected_tag(
            wrong_variant_id, wrong_correct, wrong_option
        )

        client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "misconception-study-0"},
            json={
                "question_variant_id": wrong_variant_id,
                "selected_option": wrong_option,
                "response_time_ms": 2000,
            },
        )
        respond_resp = client.post(
            f"/learning/sessions/{session_id}/respond",
            headers=headers,
            json={"interrupt_type": "intervention_choice", "choice": "hint"},
        )

    assert respond_resp.status_code == 200
    hint_text = respond_resp.json()["intervention"]["hint_text"]
    assert expected_tag in hint_text


def topic_resolver_expected_tag(variant_id: str, correct_option: str, selected_option: str) -> str:
    """Mirrors `topic_resolver.resolve_misconception_tag`'s ordinal-rank mapping, reading
    the tags from the template the test actually answered.

    This used to hard-code `["sign_error", "off_by_one", "magnitude_error"]` - the list
    every hand-authored `linear_equations` shape template shares. That was true when it was
    written and stopped being true at D-189/D-191, which made approved *authored* templates
    servable; those carry their own `misconception_tags`, so the study set now mixes two
    kinds. The test failed only when an authored template happened to land at
    `study_items[0]`, which is why it looked flaky rather than wrong - it failed in CI here
    with `assert 'sign_error' in '...addressing Adding both numbers instead of
    subtracting...'`, an authored template's tag.

    Reading the real `common_error_tags` is what the production resolver does, so the
    expectation now tracks the content instead of restating a assumption about it.
    """

    async def fetch() -> list[str]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                repo = QuestionRepository(session)
                variant = await repo.get_variant(variant_id)
                assert variant is not None
                template = await repo.get_template(variant.question_template_id)
                assert template is not None
                return list(template.common_error_tags or [])
        finally:
            await engine.dispose()

    tags = asyncio.run(fetch())
    assert tags, f"template behind {variant_id} has no common_error_tags to resolve"
    wrong_labels = [label for label in ("a", "b", "c", "d") if label != correct_option]
    return tags[wrong_labels.index(selected_option)]


def test_intervention_choice_solution_content_is_verified_correct() -> None:
    """SPEC §5.12.2 "verify calculations with tools": whatever the model (or its
    deterministic fallback) returns as `final_answer`, it must equal the question's
    actual correct answer - a wrong model answer is silently replaced, not surfaced.
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]

        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        pre_items = topics_resp.json()["items"]
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])

        body = None
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            answer_resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"sol-pre-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )
            body = answer_resp.json()

        assert body is not None
        body = _finalize_exam(client, headers, session_id)
        study_items = body["items"]
        study_correct = _correct_options([item["question_variant_id"] for item in study_items])
        wrong_variant_id = study_items[0]["question_variant_id"]
        wrong_correct = study_correct[wrong_variant_id]

        wrong_resp = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "sol-study-0"},
            json={
                "question_variant_id": wrong_variant_id,
                "selected_option": _other_option(wrong_correct),
                "response_time_ms": 2000,
            },
        )
        assert wrong_resp.json()["pending_interrupt"]["interrupt_type"] == "intervention_choice"

        respond_resp = client.post(
            f"/learning/sessions/{session_id}/respond",
            headers=headers,
            json={"interrupt_type": "intervention_choice", "choice": "solution"},
        )
        assert respond_resp.status_code == 200
        intervention = respond_resp.json()["intervention"]

    correct_option_text = {
        "a": study_items[0]["option_a"],
        "b": study_items[0]["option_b"],
        "c": study_items[0]["option_c"],
        "d": study_items[0]["option_d"],
    }[wrong_correct]

    assert intervention["type"] == "solution"
    assert intervention["steps"]
    # `answers_agree`, not `==` (D-225). The contract this asserts is D-207's: a solution
    # that answers "16 liters" to a question whose option reads "16" is *correct*, and
    # comparing with `==` is the exact bug D-207 fixed on the serving path after it
    # discarded a correct model solution live on staging.
    #
    # It failed as a flake rather than as a wrong assertion because which study item is
    # served is drawn from an unseeded rng, so this only fires when the draw lands on one
    # of the bank items whose `final_answer` carries a unit - which the §5.8.5 gate allows,
    # deliberately. Same shape as D-222's video flake: a test asserting something stricter
    # than the contract, protected by luck rather than by a precondition.
    assert answers_agree(intervention["final_answer"], correct_option_text), (
        f"{intervention['final_answer']!r} does not name the same value as "
        f"{correct_option_text!r}"
    )


def test_attendance_ask_branch_manager_end_to_end() -> None:
    """SPEC §5.6.3-§5.6.4 + Phase 8 (§6.9) completion criterion: the email is only sent
    after approval, and an approval record is written either way.
    """
    token = _student_token(STUDENT_FIRST_CHILD)
    headers = _auth_header(token)

    with TestClient(app) as client:
        # A fresh `FakeEmailTransport` is created by this block's own lifespan startup
        # (main.py), so counts are absolute from here, not deltas against a stale
        # instance left over from a previous test's now-shutdown app lifecycle.
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_FIRST_CHILD},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        assert topics_resp.json()["phase"] == "blocked"

        ask_resp = client.post(
            f"/learning/sessions/{session_id}/attendance-resolution",
            headers=headers,
            json={"choice": "ask_branch_manager"},
        )
        assert ask_resp.status_code == 200
        pending = ask_resp.json()["pending_interrupt"]
        assert pending["interrupt_type"] == "email_approval"
        preview = pending["email_preview"]
        assert preview["recipient"] == "manager.main@example.test"
        assert "Ben First" in preview["body"]

        # Only previewed so far - nothing sent.
        assert app.state.email_transport.sent == []

        respond_resp = client.post(
            f"/learning/sessions/{session_id}/respond",
            headers=headers,
            json={"interrupt_type": "email_approval", "approved": True},
        )
        assert respond_resp.status_code == 200
        assert respond_resp.json()["phase"] == "blocked"

    assert len(app.state.email_transport.sent) == 1
    assert app.state.email_transport.sent[-1].recipient == "manager.main@example.test"

    approvals = _interrupt_approvals(session_id)
    assert len(approvals) == 1
    assert approvals[0].decision == "approved"
    assert approvals[0].interrupt_type == "email_approval"


def test_restart_survives_pending_child_selection_interrupt() -> None:
    """SPEC §5.16: "Parent exits during child selection" - a pending interrupt must
    survive a process restart and still be resumable afterward, not silently lost (a
    fresh, non-`Command` `ainvoke` - which is what `/resume` must NOT do here - would
    otherwise discard the paused task).
    """
    token = _parent_token(PARENT_TWO_CHILDREN)
    headers = _auth_header(token)

    with TestClient(app) as client:
        create_resp = client.post("/learning/sessions", headers=headers)
        session_id = create_resp.json()["learning_session_id"]

        student_resp = client.post(
            f"/learning/sessions/{session_id}/student", headers=headers, json={}
        )
        assert student_resp.status_code == 200
        pending_before = student_resp.json()["pending_interrupt"]
        assert pending_before["interrupt_type"] == "child_selection"
        candidates_before = {
            c["student_external_id"] for c in pending_before["child_candidates"]
        }
        assert candidates_before == {STUDENT_FIRST_CHILD, STUDENT_SECOND_CHILD}

    # The app (and its checkpointer connection) has fully shut down here.

    with TestClient(app) as client:
        resume_resp = client.post(f"/learning/sessions/{session_id}/resume", headers=headers)
        assert resume_resp.status_code == 200
        pending_after = resume_resp.json()["pending_interrupt"]
        assert pending_after["interrupt_type"] == "child_selection"
        candidates_after = {c["student_external_id"] for c in pending_after["child_candidates"]}
        assert candidates_after == candidates_before

        respond_resp = client.post(
            f"/learning/sessions/{session_id}/respond",
            headers=headers,
            json={"interrupt_type": "child_selection", "student_id": STUDENT_FIRST_CHILD},
        )
        assert respond_resp.status_code == 200
        assert respond_resp.json()["phase"] == "student_selected"


def test_a_study_answer_cannot_be_recorded_twice() -> None:
    """D-216: the study counterpart of AUD-L-10's one-attempt-per-item rule.

    The exam path had a pre-flight, a flow-level re-check, and a unique constraint; the
    study path had only a membership check, so a stale tab re-answering an already-resolved
    study item appended a second `StudyAttempt` to its skill line - re-labeling the line and
    inflating the "resolving attempt" denominators the gain's dependency rates divide by.
    The model docstring has always stated the invariant ("the current pending question is
    the item lacking a matching StudyAttempt"); this pins its enforcement: 409, one row.
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        pre_items = topics_resp.json()["items"]
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])
        for item in pre_items:
            variant_id = item["question_variant_id"]
            client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"dup-pre-{variant_id}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )
        finalize = _finalize_exam(client, headers, session_id)
        assert finalize["phase"] == "study"
        study_variant_id = finalize["items"][0]["question_variant_id"]

        first = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"dup-study-1-{session_id}"},
            json={
                "question_variant_id": study_variant_id,
                "selected_option": _correct_options([study_variant_id])[study_variant_id],
                "response_time_ms": 2000,
            },
        )
        assert first.status_code == 200
        assert first.json()["phase"] == "study"

        # The stale-tab shape: same variant, a *different* Idempotency-Key - so this is a
        # second answer, not a replay of the first (which would legitimately re-serve).
        second = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"dup-study-2-{session_id}"},
            json={
                "question_variant_id": study_variant_id,
                "selected_option": _other_option(
                    _correct_options([study_variant_id])[study_variant_id]
                ),
                "response_time_ms": 2000,
            },
        )
        assert second.status_code == 409
        assert "already been answered" in second.json()["detail"]

        study_session_id = _study_session_id(session_id)
        attempts = [
            a
            for a in _study_attempts_all(study_session_id)
            if a.question_variant_id == study_variant_id
        ]
        assert len(attempts) == 1
        assert attempts[0].is_correct is True


def test_assistance_question_names_the_question_the_help_is_about() -> None:
    """D-272: the study screen shows the question beside the help, so the server has to say
    which question that is. `items` cannot: it is `None` at the intervention menu and the
    *next* question once the ladder closes.

    Walks the three states that used to break, and asserts the one that is easy to get wrong:
    after a terminal `solution`, `items` has already advanced and `assistance_question` must
    still name the question the solution explains. Pairing the two by position - which is what
    the client did before this field existed - puts one problem's worked solution beside a
    different problem.
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        pre_items = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        ).json()["items"]
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"aq-pre-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )

        study_variant_id = _finalize_exam(client, headers, session_id)["items"][0][
            "question_variant_id"
        ]
        wrong_option = _other_option(_correct_options([study_variant_id])[study_variant_id])
        menu = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"aq-study-{session_id}"},
            json={
                "question_variant_id": study_variant_id,
                "selected_option": wrong_option,
                "response_time_ms": 2000,
            },
        ).json()

        # 1. The menu. `items` is absent here - that is the whole reason this field exists.
        assert menu["pending_interrupt"]["interrupt_type"] == "intervention_choice"
        assert menu.get("items") is None
        assistance = menu["assistance_question"]
        assert assistance["question_variant_id"] == study_variant_id
        # The four options, which the stem-only fallback this replaces could never show.
        assert all(assistance[f"option_{key}"] for key in ("a", "b", "c", "d"))
        # Their own answer, echoed back.
        assert assistance["selected_option"] == wrong_option

        # 2. Mid-ladder: still the same question, not the retry the ladder is preparing.
        hint = client.post(
            f"/learning/sessions/{session_id}/respond",
            headers=headers,
            json={"interrupt_type": "intervention_choice", "choice": "hint"},
        ).json()
        assert hint["intervention"]["hint_level"] == 1
        assert hint["assistance_question"]["question_variant_id"] == study_variant_id

        # 3. Terminal: the solution closes the pause and `items` becomes the NEXT question.
        solution = client.post(
            f"/learning/sessions/{session_id}/respond",
            headers=headers,
            json={"interrupt_type": "intervention_choice", "choice": "solution"},
        ).json()
        assert solution["pending_interrupt"] is None
        assert solution["intervention"]["type"] == "solution"
        served_next = solution["items"][0]["question_variant_id"]
        assert served_next != study_variant_id, "the ladder should have served a retry"
        assert solution["assistance_question"]["question_variant_id"] == study_variant_id


def test_assistance_question_is_absent_when_no_help_is_on_screen() -> None:
    """The other half of D-272, and the one that keeps it honest: a plain correct study
    answer carries no help, so it must carry no `assistance_question` either.

    Without this the field would go stale exactly the way `last_intervention` does - holding
    the previous question forever - and the client, which uses its presence to decide whether
    to render two columns at all, would show a help panel next to a question the student has
    already moved past.
    """
    token = _student_token(STUDENT_UNLINKED)
    headers = _auth_header(token)

    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        pre_items = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        ).json()["items"]
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"aq2-pre-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            ).json()
            assert resp.get("assistance_question") is None

        study_variant_id = _finalize_exam(client, headers, session_id)["items"][0][
            "question_variant_id"
        ]
        correct = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"aq2-study-{session_id}"},
            json={
                "question_variant_id": study_variant_id,
                "selected_option": _correct_options([study_variant_id])[study_variant_id],
                "response_time_ms": 2000,
            },
        ).json()
        assert correct["is_correct"] is True
        assert correct.get("assistance_question") is None
