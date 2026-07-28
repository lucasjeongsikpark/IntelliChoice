"""ROADMAP S28 (SPEC §5.14.2-§5.14.4, plan §18-L9) - HTTP-level wiring for the
progress-dashboard and student-report endpoints: route -> service -> real gateway (mock
provider) -> DB, plus the server-side audience/authorization gating (CLAUDE.md
non-negotiable #3 - audience always comes from the caller's role, never a request
field). Full aggregation correctness is covered by `test_dashboard.py`/`test_report.py`
against seeded rows in isolation; this file only proves the endpoints are wired
correctly.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.seed.mysql_fixtures import (
    STUDENT_ONLY_CHILD,
    STUDENT_SECOND_CHILD,
    STUDENT_UNLINKED,
    seed,
)
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.cost_reservation import SCOPE_STUDENT_REPORT
from intellichoice_db.repositories.cost_reservation import CostReservationRepository
from intellichoice_shared.auth import Audience, Role
from learning_api.main import app
from learning_api.services.report import DAILY_REPORT_COST_CEILING_CENTS
from sqlalchemy import text

MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"

issuer = FakeTokenIssuer()


def _mysql_available() -> bool:
    async def check() -> bool:
        from sqlalchemy.ext.asyncio import create_async_engine

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


def _token(sub: str, role: Role) -> str:
    return issuer.issue(sub=sub, role=role, audience=Audience.LEARNING)


def test_dashboard_endpoint_returns_expected_shape() -> None:
    token = _token(STUDENT_UNLINKED, Role.STUDENT)
    with TestClient(app) as client:
        resp = client.get(
            f"/learning/students/{STUDENT_UNLINKED}/dashboard", headers=_auth_header(token)
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["student_external_id"] == STUDENT_UNLINKED
    for key in (
        "mastery_by_skill",
        "pre_post_by_skill",
        "gains_over_time",
        "accuracy_trend",
        "difficulty_progression",
        "usage",
        "attempts_count",
        "time_spent_minutes",
    ):
        assert key in body


def test_dashboard_endpoint_rejects_a_student_requesting_another_students_data() -> None:
    token = _token(STUDENT_UNLINKED, Role.STUDENT)
    with TestClient(app) as client:
        resp = client.get(
            "/learning/students/some-other-student/dashboard", headers=_auth_header(token)
        )
    assert resp.status_code == 403


def test_report_endpoint_gates_verified_facts_by_caller_role() -> None:
    student_token = _token(STUDENT_UNLINKED, Role.STUDENT)
    tutor_token = _token("tutor-ext-1", Role.TUTOR)

    with TestClient(app) as client:
        student_resp = client.post(
            f"/learning/students/{STUDENT_UNLINKED}/report", headers=_auth_header(student_token)
        )
        tutor_resp = client.post(
            f"/learning/students/{STUDENT_UNLINKED}/report", headers=_auth_header(tutor_token)
        )

    assert student_resp.status_code == 200
    assert tutor_resp.status_code == 200

    student_body = student_resp.json()
    tutor_body = tutor_resp.json()

    assert student_body["audience"] == "student"
    assert tutor_body["audience"] == "tutor"
    # `verified_facts` is always the same wire shape (every field present, gated-out
    # ones left at their Pydantic default rather than omitted - same "one shape,
    # audience-filtered per call" design as `StageNarrativePayload`) - so gating shows
    # up as a required-typed field reverting to `None` when excluded, not a missing key.
    # SPEC §5.14.4: tutor/branch_manager never gets usage/mastery/time detail; SPEC
    # §5.14.2: student never gets the tutor-review flag.
    assert student_body["verified_facts"]["hint_count"] is not None
    assert tutor_body["verified_facts"]["hint_count"] is None
    assert tutor_body["verified_facts"]["time_spent_minutes"] is None
    assert student_body["verified_facts"]["tutor_review_flagged"] is None
    assert tutor_body["verified_facts"]["tutor_review_flagged"] is False

    for body in (student_body, tutor_body):
        assert isinstance(body["interpretation_text"], str) and body["interpretation_text"]
        assert isinstance(body["recommendations_text"], str) and body["recommendations_text"]
        assert isinstance(body["generated"], bool)


def test_the_report_route_consults_this_students_spend_ledger() -> None:
    """S42/AUD-X-08 wiring: the route reads *this student's* ledger spend, and another
    student's spend does not deny them a report. The ceiling's own behaviour and its
    serialization are covered by `test_report.py` and
    `packages/db/tests/test_cost_reservation.py`; what only an HTTP test can show is that
    the route is wired to the ledger at all, under the right subject.

    Deliberately not claiming more than that. The route makes *two* ledger reads - the
    per-day ceiling in the service, and `session_spend_cents` for the gateway's own budget
    check - and at 50 cents each they trip together, so this cannot isolate one from the
    other. It was confirmed to fail only when both are bypassed.

    Two false-pass traps were found writing it, both the D-101 §5 shape. Using
    `STUDENT_UNLINKED` for the capped arm passed with the ceiling *disabled*, because that
    student has no dashboard data and its report never generates - so `generated is False`
    proved nothing. And bypassing the ceiling alone still passed, because the gateway's
    session budget caught it instead.
    """
    subject = STUDENT_ONLY_CHILD
    unrelated = STUDENT_SECOND_CHILD

    # Each helper builds and disposes its own engine: every `asyncio.run` below is a
    # fresh event loop, and an asyncpg connection pool cannot outlive the loop it was
    # created on.
    async def seed(target: str, cents: float) -> None:
        engine = create_engine()
        try:
            ledger = CostReservationRepository(create_session_factory(engine))
            reservation = await ledger.reserve(
                scope=SCOPE_STUDENT_REPORT,
                subject_external_id=target,
                estimate_cents=cents,
                ceiling_cents=float("inf"),
            )
            await ledger.settle(reservation.reservation_id, cents)
        finally:
            await engine.dispose()

    async def clear() -> None:
        engine = create_engine()
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM cost_reservations WHERE subject_external_id = ANY(:ids)"),
                    {"ids": [subject, unrelated]},
                )
        finally:
            await engine.dispose()

    def request_report() -> dict:
        with TestClient(app) as client:
            resp = client.post(
                f"/learning/students/{subject}/report",
                headers=_auth_header(_token(subject, Role.STUDENT)),
            )
        # Always 200 - the ceiling degrades to the facts-only template rather than
        # erroring (SPEC §5.25.3), so `generated` is the signal, not the status code.
        assert resp.status_code == 200
        return resp.json()

    asyncio.run(clear())
    try:
        # Another student's spend must not deny this one a report.
        asyncio.run(seed(unrelated, DAILY_REPORT_COST_CEILING_CENTS))
        assert request_report()["generated"] is True

        # This student's own spend must.
        asyncio.run(seed(subject, DAILY_REPORT_COST_CEILING_CENTS))
        assert request_report()["generated"] is False
    finally:
        asyncio.run(clear())


def test_reports_history_endpoint_returns_generated_reports() -> None:
    token = _token(STUDENT_UNLINKED, Role.STUDENT)
    with TestClient(app) as client:
        client.post(f"/learning/students/{STUDENT_UNLINKED}/report", headers=_auth_header(token))
        resp = client.get(
            f"/learning/students/{STUDENT_UNLINKED}/reports", headers=_auth_header(token)
        )

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    assert all(row["audience"] == "student" for row in rows)
