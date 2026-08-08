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
            f"/learning/students/{STUDENT_UNLINKED}/report",
            headers={**_auth_header(student_token), "Idempotency-Key": "audience-gate-student"},
        )
        tutor_resp = client.post(
            f"/learning/students/{STUDENT_UNLINKED}/report",
            headers={**_auth_header(tutor_token), "Idempotency-Key": "audience-gate-tutor"},
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


def _seed_one_study_attempt(student_id: str) -> str:
    """D-218 made a zero-attempt report short-circuit past the model, and therefore past the
    cost ledger. The replay test below is AUD-X-04's *money* assertion, so it has to run on
    the paid path - which means this student needs something to interpret. One graded attempt
    is enough; the aggregation itself is `test_dashboard.py`'s job, not this file's.

    Returns the study_session_id so the caller can delete both rows again.
    """

    async def run() -> str:
        engine = create_engine()
        try:
            async with engine.begin() as conn:
                variant_id = (
                    await conn.execute(
                        text("SELECT question_variant_id FROM question_variants LIMIT 1")
                    )
                ).scalar_one()
                topic_id = (
                    await conn.execute(text("SELECT topic_id FROM topics LIMIT 1"))
                ).scalar_one()
                study_session_id = f"d218-replay-{student_id}"
                # Idempotent: two tests in this file seed the same subject, and a failure
                # that skipped a `finally` must not make the next run collide on the key.
                await conn.execute(
                    text("DELETE FROM study_attempts WHERE study_session_id = :sid"),
                    {"sid": study_session_id},
                )
                await conn.execute(
                    text("DELETE FROM study_items WHERE study_session_id = :sid"),
                    {"sid": study_session_id},
                )
                await conn.execute(
                    text("DELETE FROM study_sessions WHERE study_session_id = :sid"),
                    {"sid": study_session_id},
                )
                await conn.execute(
                    text(
                        "INSERT INTO study_sessions (study_session_id, student_external_id, "
                        "topic_id, target_skill_ids, starting_difficulty, base_problem_count, "
                        "maximum_attempts_per_skill, intervention_policy, status) "
                        "VALUES (:sid, :student, :topic, '[]'::json, 2, 5, 4, "
                        "'{}'::json, 'completed')"
                    ),
                    {"sid": study_session_id, "student": student_id, "topic": topic_id},
                )
                # The dashboard's study query inner-joins `study_items` on the variant, so an
                # attempt without a matching item is invisible to `attempts_count`.
                skill_id = (
                    await conn.execute(
                        text(
                            "SELECT skill_id FROM question_templates t "
                            "JOIN question_variants v "
                            "ON v.question_template_id = t.question_template_id "
                            "WHERE v.question_variant_id = :variant"
                        ),
                        {"variant": variant_id},
                    )
                ).scalar_one()
                await conn.execute(
                    text(
                        "INSERT INTO study_items (study_item_id, study_session_id, "
                        "question_variant_id, display_order, target_skill_id, skill_id, "
                        "difficulty, is_remediation) VALUES (:iid, :sid, :variant, 0, :skill, "
                        ":skill, 2, false)"
                    ),
                    {
                        "iid": f"d218-replay-item-{student_id}",
                        "sid": study_session_id,
                        "variant": variant_id,
                        "skill": skill_id,
                    },
                )
                await conn.execute(
                    text(
                        "INSERT INTO study_attempts (attempt_id, student_external_id, "
                        "study_session_id, question_variant_id, selected_option, is_correct, "
                        "hint_used, video_used, solution_used, retry_count, outcome_label, "
                        "tutor_review_flagged) VALUES (:aid, :student, :sid, :variant, 'a', true, "
                        "false, false, false, 0, 'independent_correct', false)"
                    ),
                    {
                        "aid": f"d218-replay-attempt-{student_id}",
                        "student": student_id,
                        "sid": study_session_id,
                        "variant": variant_id,
                    },
                )
                return str(study_session_id)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _clear_seeded_study_attempt(study_session_id: str) -> None:
    async def run() -> None:
        engine = create_engine()
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM study_attempts WHERE study_session_id = :sid"),
                    {"sid": study_session_id},
                )
                await conn.execute(
                    text("DELETE FROM study_items WHERE study_session_id = :sid"),
                    {"sid": study_session_id},
                )
                await conn.execute(
                    text("DELETE FROM study_sessions WHERE study_session_id = :sid"),
                    {"sid": study_session_id},
                )
        finally:
            await engine.dispose()

    asyncio.run(run())


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

    def request_report(key: str) -> dict:
        with TestClient(app) as client:
            resp = client.post(
                f"/learning/students/{subject}/report",
                headers={
                    **_auth_header(_token(subject, Role.STUDENT)),
                    # A fresh key per arm, which this test genuinely needs: under one key the
                    # second call would be an AUD-X-04 replay and return the first arm's stored
                    # `generated: True` row without consulting the ledger at all.
                    "Idempotency-Key": key,
                },
            )
        # Always 200 - the ceiling degrades to the facts-only template rather than
        # erroring (SPEC §5.25.3), so `generated` is the signal, not the status code.
        assert resp.status_code == 200
        return resp.json()

    asyncio.run(clear())
    seeded_study_session = _seed_one_study_attempt(subject)
    try:
        # Another student's spend must not deny this one a report.
        asyncio.run(seed(unrelated, DAILY_REPORT_COST_CEILING_CENTS))
        assert request_report("ledger-unrelated-spend")["generated"] is True

        # This student's own spend must.
        asyncio.run(seed(subject, DAILY_REPORT_COST_CEILING_CENTS))
        assert request_report("ledger-own-spend")["generated"] is False
    finally:
        _clear_seeded_study_attempt(seeded_study_session)
        asyncio.run(clear())


def _report_row_count(student_id: str) -> int:
    async def fetch() -> int:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT count(*) FROM student_reports WHERE student_external_id = :sid"),
                    {"sid": student_id},
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _report_reservation_count(student_id: str) -> int:
    """Reservations in the AUD-X-08 ledger for this student's reports - i.e. how many times a
    paid call was *committed to*, which is the money question AUD-X-04 asks. Counting rows in
    `student_reports` alone cannot distinguish "one call, one row" from "two calls, one row".
    """

    async def fetch() -> int:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT count(*) FROM cost_reservations "
                        "WHERE scope = :scope AND subject_external_id = :sid"
                    ),
                    {"scope": SCOPE_STUDENT_REPORT, "sid": student_id},
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _clear_report_reservations(student_id: str) -> None:
    async def run() -> None:
        engine = create_engine()
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM cost_reservations WHERE subject_external_id = :sid"),
                    {"sid": student_id},
                )
        finally:
            await engine.dispose()

    asyncio.run(run())


def _clear_reports_with_key_prefix(student_id: str, prefix: str) -> None:
    """`conftest.py`'s sweep does not cover `student_reports` (they are the parent-visible
    history, and D-114 gives them a year's retention), so rows from previous runs are still
    there - which means an idempotency-key test would replay *last run's* row and see its first
    call create nothing. Found exactly that way.
    """

    async def run() -> None:
        engine = create_engine()
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "DELETE FROM student_reports WHERE student_external_id = :sid "
                        "AND idempotency_key LIKE :prefix"
                    ),
                    {"sid": student_id, "prefix": f"{prefix}%"},
                )
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_a_replayed_report_request_pays_once_and_serves_the_stored_report() -> None:
    """AUD-X-04. `POST /students/{id}/report` had no idempotency key: two identical calls each
    generated a report and each paid Bedrock. Now the same `Idempotency-Key` serves the stored
    row without a second model call, and a *different* key still writes a new report - which is
    the property that has to survive, because `StudentReport`'s docstring records that this
    table is history a parent re-opens (`list_for_student`), not a cache. The fix had to
    deduplicate a replay without capping deliberate re-generation.
    """
    subject = STUDENT_ONLY_CHILD
    token = _token(subject, Role.STUDENT)
    _clear_report_reservations(subject)
    _clear_reports_with_key_prefix(subject, "report-key-")
    seeded_study_session = _seed_one_study_attempt(subject)
    try:
        rows_before = _report_row_count(subject)
        reservations_before = _report_reservation_count(subject)

        with TestClient(app) as client:

            def generate(key: str) -> dict:
                resp = client.post(
                    f"/learning/students/{subject}/report",
                    headers={**_auth_header(token), "Idempotency-Key": key},
                )
                assert resp.status_code == 200, resp.text
                return resp.json()

            first = generate("report-key-1")
            assert _report_row_count(subject) == rows_before + 1
            assert _report_reservation_count(subject) == reservations_before + 1

            replay = generate("report-key-1")
            # Byte-identical, including `created_at`: the stored row is served, not a second
            # report that happens to read the same.
            assert replay == first
            assert _report_row_count(subject) == rows_before + 1
            # The money assertion. Without it "one row" could still mean two paid calls.
            assert _report_reservation_count(subject) == reservations_before + 1

            # A new key is a new request, not a replay - history still works.
            second = generate("report-key-2")
            assert second["created_at"] != first["created_at"]
            assert _report_row_count(subject) == rows_before + 2
            assert _report_reservation_count(subject) == reservations_before + 2
    finally:
        _clear_seeded_study_attempt(seeded_study_session)
        _clear_report_reservations(subject)
        _clear_reports_with_key_prefix(subject, "report-key-")


def test_reusing_a_report_key_for_a_different_date_range_is_refused() -> None:
    """The trap in serving a replay from a stored row: the key does not carry the date range,
    so a client that reuses one key across two ranges would be handed the wrong month's report
    with a 200. Refused instead - a wrong number in front of a parent is the failure mode this
    codebase keeps producing (AUD-L-15, AUD-C-19), and a 409 is recoverable.
    """
    subject = STUDENT_ONLY_CHILD
    token = _token(subject, Role.STUDENT)
    _clear_report_reservations(subject)
    _clear_reports_with_key_prefix(subject, "range-key-")
    try:
        with TestClient(app) as client:
            first = client.post(
                f"/learning/students/{subject}/report",
                headers={**_auth_header(token), "Idempotency-Key": "range-key-1"},
            )
            assert first.status_code == 200
            rows_after_first = _report_row_count(subject)

            reused = client.post(
                f"/learning/students/{subject}/report?start=2026-07-01T00:00:00Z",
                headers={**_auth_header(token), "Idempotency-Key": "range-key-1"},
            )
            assert reused.status_code == 409
            assert "Idempotency-Key" in reused.json()["detail"]
            assert _report_row_count(subject) == rows_after_first
    finally:
        _clear_report_reservations(subject)
        _clear_reports_with_key_prefix(subject, "range-key-")


def test_reports_history_endpoint_returns_generated_reports() -> None:
    token = _token(STUDENT_UNLINKED, Role.STUDENT)
    with TestClient(app) as client:
        # Asserted rather than fire-and-forget: this POST used to be unchecked, so once
        # `Idempotency-Key` became required it would have 422'd silently and the assertions
        # below would still have passed on rows an earlier test left behind.
        created = client.post(
            f"/learning/students/{STUDENT_UNLINKED}/report",
            headers={**_auth_header(token), "Idempotency-Key": "history-endpoint-1"},
        )
        assert created.status_code == 200, created.text
        resp = client.get(
            f"/learning/students/{STUDENT_UNLINKED}/reports", headers=_auth_header(token)
        )

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    assert all(row["audience"] == "student" for row in rows)
