"""Problem-report + quarantine endpoint tests (SPEC §5.8.7, Phase 5 §6.6 second half).

Postgres-only: the report endpoint takes the reporter id from `claims.sub` and never
touches MySQL/`ProfileAdapter`, so no seed fixtures are needed. Like `test_learning_flow`
(D-018), these drive the real `TestClient` + live Postgres and therefore commit real
rows - so the fixture creates a dedicated throwaway template/variant (never a real
curriculum template) and deletes it, its variant, and every report in teardown, so a run
can't leave a real question quarantined in the shared dev DB.
"""

import asyncio
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.questions import QuestionTemplate, QuestionVariant
from intellichoice_db.models.reports import ProblemReport
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.auth import Audience, Role
from learning_api.main import app
from sqlalchemy import delete, text

issuer = FakeTokenIssuer()


def _postgres_available() -> bool:
    async def check() -> bool:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1 FROM question_templates LIMIT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL not reachable or not migrated (run `make up && make db-upgrade`)",
)


def _student_token(sub: str) -> str:
    return issuer.issue(sub=sub, role=Role.STUDENT, audience=Audience.LEARNING)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def throwaway_question() -> Iterator[tuple[str, str]]:
    """Creates one committed template+variant, yields (template_id, variant_id), then
    hard-deletes the template, its variant, and any reports against it.
    """
    template_id = f"report-test-{uuid.uuid4()}"

    async def create() -> str:
        engine = create_engine()
        try:
            factory = create_session_factory(engine)
            async with session_scope(factory) as session:
                repo = QuestionRepository(session)
                template = await repo.create_template(
                    QuestionTemplate(
                        question_template_id=template_id,
                        curriculum_version="2026.1",
                        topic_id="linear_equations",
                        skill_id="linear_one_step",
                        grade_band="6-7",
                        difficulty_label=1,
                        parameter_schema={"b": {"min": 1, "max": 9}, "x": {"min": 1, "max": 9}},
                        solution_function="one_step_add",
                        correct_option_generator="format_integer",
                        distractor_generators=["distractor_off_by_one"],
                        estimated_time_seconds=25,
                        generator_model="test",
                        validation_status="approved",
                        active_status="active",
                    )
                )
                variant = await repo.create_variant(
                    QuestionVariant(
                        question_template_id=template.question_template_id,
                        random_seed=1,
                        rendered_question=f"Solve for x: x + 3 = 10 [{template_id}]",
                        option_a="7",
                        option_b="6",
                        option_c="8",
                        option_d="13",
                        correct_option="a",
                        parameter_values={"b": 3, "c": 10},
                    )
                )
                await session.commit()
                return variant.question_variant_id
        finally:
            await engine.dispose()

    async def cleanup() -> None:
        engine = create_engine()
        try:
            factory = create_session_factory(engine)
            async with session_scope(factory) as session:
                await session.execute(
                    delete(ProblemReport).where(
                        ProblemReport.question_template_id == template_id
                    )
                )
                await session.execute(
                    delete(QuestionVariant).where(
                        QuestionVariant.question_template_id == template_id
                    )
                )
                await session.execute(
                    delete(QuestionTemplate).where(
                        QuestionTemplate.question_template_id == template_id
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    variant_id = asyncio.run(create())
    try:
        yield template_id, variant_id
    finally:
        asyncio.run(cleanup())


def _is_active(template_id: str, difficulty: int = 1) -> bool:
    async def fetch() -> bool:
        engine = create_engine()
        try:
            factory = create_session_factory(engine)
            async with session_scope(factory) as session:
                repo = QuestionRepository(session)
                active = await repo.get_active_questions("linear_equations", difficulty)
                return template_id in {t.question_template_id for t in active}
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def test_single_report_records_one_distinct_reporter(
    throwaway_question: tuple[str, str],
) -> None:
    _, variant_id = throwaway_question
    with TestClient(app) as client:
        resp = client.post(
            f"/learning/questions/{variant_id}/reports",
            json={"report_type": "unclear_wording"},
            headers=_auth(_student_token("report-student-1")),
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["already_reported"] is False
    assert body["distinct_reporters"] == 1
    assert body["quarantined"] is False


def test_repeat_report_from_same_user_counts_once(
    throwaway_question: tuple[str, str],
) -> None:
    _, variant_id = throwaway_question
    token = _student_token("report-student-1")
    with TestClient(app) as client:
        first = client.post(
            f"/learning/questions/{variant_id}/reports",
            json={"report_type": "unclear_wording"},
            headers=_auth(token),
        )
        second = client.post(
            f"/learning/questions/{variant_id}/reports",
            json={"report_type": "display_issue"},
            headers=_auth(token),
        )
    assert first.json()["distinct_reporters"] == 1
    assert second.json()["already_reported"] is True
    assert second.json()["distinct_reporters"] == 1
    assert second.json()["quarantined"] is False


def test_five_distinct_reporters_quarantine_and_stop_delivery(
    throwaway_question: tuple[str, str],
) -> None:
    template_id, variant_id = throwaway_question
    assert _is_active(template_id) is True

    with TestClient(app) as client:
        for i in range(1, 5):
            resp = client.post(
                f"/learning/questions/{variant_id}/reports",
                json={"report_type": "no_correct_answer"},
                headers=_auth(_student_token(f"report-student-{i}")),
            )
            assert resp.json()["quarantined"] is False, f"quarantined too early at reporter {i}"

        fifth = client.post(
            f"/learning/questions/{variant_id}/reports",
            json={"report_type": "no_correct_answer"},
            headers=_auth(_student_token("report-student-5")),
        )
        assert fifth.json()["distinct_reporters"] == 5
        assert fifth.json()["quarantined"] is True

        # Delivery stops, but nothing is deleted - the template and its variant still
        # exist (SPEC §5.8.7 "without deleting history").
        assert _is_active(template_id) is False

        # A 6th distinct reporter is idempotent - already quarantined, still quarantined.
        sixth = client.post(
            f"/learning/questions/{variant_id}/reports",
            json={"report_type": "other"},
            headers=_auth(_student_token("report-student-6")),
        )
        assert sixth.json()["quarantined"] is True


def test_non_student_role_is_forbidden(throwaway_question: tuple[str, str]) -> None:
    _, variant_id = throwaway_question
    parent_token = issuer.issue(
        sub="some-parent", role=Role.PARENT, audience=Audience.LEARNING
    )
    with TestClient(app) as client:
        resp = client.post(
            f"/learning/questions/{variant_id}/reports",
            json={"report_type": "other"},
            headers=_auth(parent_token),
        )
    assert resp.status_code == 403


def test_unknown_variant_returns_404() -> None:
    with TestClient(app) as client:
        resp = client.post(
            "/learning/questions/does-not-exist/reports",
            json={"report_type": "other"},
            headers=_auth(_student_token("report-student-1")),
        )
    assert resp.status_code == 404


def test_invalid_report_type_returns_400(throwaway_question: tuple[str, str]) -> None:
    _, variant_id = throwaway_question
    with TestClient(app) as client:
        resp = client.post(
            f"/learning/questions/{variant_id}/reports",
            json={"report_type": "not_a_real_reason"},
            headers=_auth(_student_token("report-student-1")),
        )
    assert resp.status_code == 400
