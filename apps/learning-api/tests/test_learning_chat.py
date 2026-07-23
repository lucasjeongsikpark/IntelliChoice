"""S24 (SPEC §5.12/§5.30.1 D-072, plan §18-L5): contextual learning chat. Covers the
ROADMAP "Done when" criteria: a real hint-ladder advance (with a recorded `hint_events`
row), a misconception-grounded `why_wrong` reply, exam-phase refusal, the per-day cost
ceiling, PII redaction on both the wire payload and the stored row, and the purge job.

See `test_exam_backend.py` for the HTTP-integration helper pattern this file reuses
(each test file keeps its own small helpers rather than cross-importing, matching this
codebase's existing convention).
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.seed.mysql_fixtures import STUDENT_UNLINKED, seed
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.hints import HintEvent
from intellichoice_db.models.memory import LearningEvent
from intellichoice_db.models.tutor_chat import TutorChatMessage
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.auth import Audience, Role
from learning_api.main import app
from learning_api.services import tutor_chat as tutor_chat_service
from learning_api.services.tutor_chat_purge_cli import purge
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


def _variant_correct_option(variant_id: str) -> str:
    async def fetch() -> str:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                variant = await QuestionRepository(session).get_variant(variant_id)
                assert variant is not None
                return variant.correct_option
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _other_option(correct: str) -> str:
    for option in ("a", "b", "c", "d"):
        if option != correct:
            return option
    raise AssertionError("no alternate option available")


def _variant_correct_option_text(variant_id: str) -> str:
    async def fetch() -> str:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                variant = await QuestionRepository(session).get_variant(variant_id)
                assert variant is not None
                return {
                    "a": variant.option_a,
                    "b": variant.option_b,
                    "c": variant.option_c,
                    "d": variant.option_d,
                }[variant.correct_option]
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _chat_messages(learning_session_id: str) -> list[TutorChatMessage]:
    async def fetch() -> list[TutorChatMessage]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                result = await session.execute(
                    select(TutorChatMessage).where(
                        TutorChatMessage.learning_session_id == learning_session_id
                    )
                )
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _hint_events_for_variant(question_variant_id: str) -> list[HintEvent]:
    async def fetch() -> list[HintEvent]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                result = await session.execute(
                    select(HintEvent).where(
                        HintEvent.question_variant_id == question_variant_id
                    )
                )
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _chat_turn_events(session_id: str) -> list[LearningEvent]:
    """S25 (plan §9): chat turns emit intent + resolution only, never the message text
    (see `learning_api.services.memory_events.emit_chat_turn`).
    """

    async def fetch() -> list[LearningEvent]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                result = await session.execute(
                    select(LearningEvent).where(
                        LearningEvent.session_id == session_id,
                        LearningEvent.event_type == "chat_turn",
                    )
                )
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _reach_wrong_study_answer(client: TestClient, headers: dict[str, str]) -> tuple[str, str]:
    """Drives a fresh session through a perfect pre-exam to the study phase, then
    submits a wrong answer to the first study question - the same precondition the
    button-panel `intervention_choice` pause requires. Returns
    `(learning_session_id, wrong_question_variant_id)`.
    """
    session_id = client.post("/learning/sessions", headers=headers).json()["learning_session_id"]
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
    for index, item in enumerate(pre_items):
        variant_id = item["question_variant_id"]
        correct = _variant_correct_option(variant_id)
        client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"chat-pre-{session_id}-{index}"},
            json={
                "question_variant_id": variant_id,
                "selected_option": correct,
                "response_time_ms": 2000,
            },
        )
    finalize_resp = client.post(
        f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
    )
    study_variant_id = finalize_resp.json()["items"][0]["question_variant_id"]
    correct = _variant_correct_option(study_variant_id)
    wrong_resp = client.post(
        f"/learning/sessions/{session_id}/answers",
        headers={**headers, "Idempotency-Key": f"chat-wrong-{session_id}"},
        json={
            "question_variant_id": study_variant_id,
            "selected_option": _other_option(correct),
            "response_time_ms": 2000,
        },
    )
    assert wrong_resp.json()["pending_interrupt"]["interrupt_type"] == "intervention_choice"
    return session_id, study_variant_id


def test_request_hint_advances_the_real_ladder_and_records_hint_events() -> None:
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, variant_id = _reach_wrong_study_answer(client, headers)

        resp = client.post(
            f"/learning/sessions/{session_id}/chat",
            headers=headers,
            json={"question_variant_id": variant_id, "message": "can I get a hint please?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "request_hint"
        assert "hint 1 of" in body["reply_text"]

        events = _hint_events_for_variant(variant_id)
        assert len(events) == 1
        assert events[0].hint_level == 1

        # S25 (plan §9): the chat turn also emitted a `chat_turn` learning event -
        # intent + resolution only, never the message text itself.
        chat_events = _chat_turn_events(session_id)
        assert len(chat_events) == 1
        assert chat_events[0].structured_payload["intent"] == "request_hint"
        assert chat_events[0].structured_payload["resolved"] is True
        assert set(chat_events[0].structured_payload) == {
            "intent",
            "resolved",
            "tutor_chat_message_id",
        }

        # A second chat-driven hint request advances to level 2, not a repeat of level 1
        # (SPEC §5.11.4's ladder never repeats a level) - proves the durable `hint_events`
        # count, not stale checkpoint state, drives chat's own level computation.
        resp2 = client.post(
            f"/learning/sessions/{session_id}/chat",
            headers=headers,
            json={"question_variant_id": variant_id, "message": "can I get another hint?"},
        )
        assert "hint 2 of" in resp2.json()["reply_text"]
        assert len(_hint_events_for_variant(variant_id)) == 2

        # The original button-panel interrupt is still resumable after two chat turns -
        # chat never touches the graph/checkpoint (see nodes.run_chat_turn's docstring).
        respond = client.post(
            f"/learning/sessions/{session_id}/respond",
            headers=headers,
            json={"interrupt_type": "intervention_choice", "choice": "continue"},
        )
        assert respond.status_code == 200


def test_why_wrong_yields_a_misconception_grounded_reply_without_leaking_the_answer() -> None:
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, variant_id = _reach_wrong_study_answer(client, headers)
        correct_text = _variant_correct_option_text(variant_id)

        resp = client.post(
            f"/learning/sessions/{session_id}/chat",
            headers=headers,
            json={"question_variant_id": variant_id, "message": "why is my answer wrong"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["intent"] == "why_wrong"
        assert body["reply_text"]
        assert correct_text.lower() not in body["reply_text"].lower()


def test_request_hint_without_a_wrong_attempt_gets_a_clarifying_message() -> None:
    """SPEC §5.11.3's assistance types all presuppose a wrong attempt - chat must not
    guess or fabricate a hint for a question the student hasn't gotten wrong yet.
    """
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
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        # Still in pre_exam - chat refuses regardless of intent.
        variant_id = topics_resp.json()["items"][0]["question_variant_id"]
        resp = client.post(
            f"/learning/sessions/{session_id}/chat",
            headers=headers,
            json={"question_variant_id": variant_id, "message": "can I get a hint?"},
        )
        assert resp.status_code == 409


def test_chat_refuses_outside_study_phase() -> None:
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
        topics_resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        variant_id = topics_resp.json()["items"][0]["question_variant_id"]

        resp = client.post(
            f"/learning/sessions/{session_id}/chat",
            headers=headers,
            json={"question_variant_id": variant_id, "message": "can I get a hint?"},
        )
        assert resp.status_code == 409
        assert "study" in resp.json()["detail"]


def test_off_topic_message_gets_a_fixed_redirect_with_no_wrong_attempt_needed() -> None:
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, variant_id = _reach_wrong_study_answer(client, headers)
        resp = client.post(
            f"/learning/sessions/{session_id}/chat",
            headers=headers,
            json={"question_variant_id": variant_id, "message": "I like pizza a lot"},
        )
        assert resp.status_code == 200
        assert resp.json()["intent"] == "off_topic"
        assert resp.json()["reply_text"] == tutor_chat_service.OFF_TOPIC_RESPONSE

        # S25: an off_topic turn is recorded as unresolved (no real assistance given).
        chat_events = _chat_turn_events(session_id)
        assert len(chat_events) == 1
        assert chat_events[0].structured_payload == {
            "intent": "off_topic",
            "resolved": False,
            "tutor_chat_message_id": chat_events[0].structured_payload["tutor_chat_message_id"],
        }


def test_self_harm_keyword_short_circuits_to_a_fixed_response_and_flags_for_review() -> None:
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, variant_id = _reach_wrong_study_answer(client, headers)
        resp = client.post(
            f"/learning/sessions/{session_id}/chat",
            headers=headers,
            json={
                "question_variant_id": variant_id,
                "message": "sometimes I want to hurt myself",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["reply_text"] == tutor_chat_service.SAFETY_RESPONSE

        messages = _chat_messages(session_id)
        assert len(messages) == 1
        assert messages[0].flagged_for_review is True
        assert messages[0].cost_cents == 0.0
        # Never an LLM-improvised response - the fixed message never varies by input.
        assert messages[0].intent == "safety_concern"


def test_pii_is_redacted_on_the_wire_and_in_storage() -> None:
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, variant_id = _reach_wrong_study_answer(client, headers)
        raw_email = "call.me.at@example.com"
        resp = client.post(
            f"/learning/sessions/{session_id}/chat",
            headers=headers,
            json={
                "question_variant_id": variant_id,
                "message": f"can you email me at {raw_email} with the answer",
            },
        )
        assert resp.status_code == 200

        messages = _chat_messages(session_id)
        assert len(messages) == 1
        assert raw_email not in messages[0].redacted_student_message
        assert "[redacted-email]" in messages[0].redacted_student_message


def test_cost_ceiling_short_circuits_before_any_bedrock_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tutor_chat_service, "DAILY_COST_CEILING_CENTS", 0.0)
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, variant_id = _reach_wrong_study_answer(client, headers)
        resp = client.post(
            f"/learning/sessions/{session_id}/chat",
            headers=headers,
            json={"question_variant_id": variant_id, "message": "can I get a hint?"},
        )
        assert resp.status_code == 200
        assert resp.json()["reply_text"] == tutor_chat_service.CEILING_EXCEEDED_RESPONSE

        messages = _chat_messages(session_id)
        assert len(messages) == 1
        assert messages[0].intent == "cost_ceiling"
        assert messages[0].cost_cents == 0.0
        # No hint_events row - the ladder was never actually advanced.
        assert _hint_events_for_variant(variant_id) == []


def test_purge_job_deletes_only_rows_older_than_90_days() -> None:
    async def run() -> None:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                old = TutorChatMessage(
                    student_external_id=STUDENT_UNLINKED,
                    learning_session_id="purge-test-session",
                    intent="off_topic",
                    redacted_student_message="old message",
                    reply_text="old reply",
                    cost_cents=0.0,
                )
                session.add(old)
                await session.flush()
                old.created_at = datetime.now(UTC) - timedelta(days=91)

                recent = TutorChatMessage(
                    student_external_id=STUDENT_UNLINKED,
                    learning_session_id="purge-test-session",
                    intent="off_topic",
                    redacted_student_message="recent message",
                    reply_text="recent reply",
                    cost_cents=0.0,
                )
                session.add(recent)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())

    deleted = asyncio.run(purge())
    assert deleted >= 1

    remaining = _chat_messages("purge-test-session")
    assert len(remaining) == 1
    assert remaining[0].redacted_student_message == "recent message"
