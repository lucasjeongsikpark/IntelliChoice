"""The contract between what this API says in `detail` and what the web client matches on.

**Why this file exists.** `apps/learning-web/src/api/errors.ts` maps a failure to a sentence a
K-12 student can read, and it keys on **status plus a substring of the detail**, because
`/answers` alone returns 409 for five different situations. Nothing has ever checked that those
substrings appear in anything this API actually sends, and the consequence is not theoretical:

- **D-378 (found live 2026-08-16).** chat-web shipped a rule matching on a *field name*, which
  Pydantic puts only in `loc` - so the rule could never fire and the student got the generic
  line instead of the one written for them. It survived review because the rule reads correctly;
  only the wire disagreed.
- **The 400 `["attendance"]` rule, found by writing this file (V1/V3, 2026-08-17).** No
  `HTTPException` in this API has ever carried the word "attendance" in a detail - the gate is a
  *phase* (`phase: "blocked"` with a 200), not an error - so that rule was unmatchable from the
  day it was written. Deleted rather than papered over; the phase path is what renders the
  gate's own wording (`attendance.UNKNOWN_MESSAGE`), and `journey-attendance.spec.ts` asserts it.

So each test here drives a **real** request to the point of failure and asserts the fragment is
in the response. Not a source grep: a fragment that appears in a comment, or in a raiser no route
reaches, would satisfy a grep and still leave the student reading the generic line.

**Adding a rule to `errors.ts` means adding a case here.** If a situation cannot be driven from a
test, that is worth knowing before the rule ships - it means nothing can show the sentence is
reachable either.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.seed.mysql_fixtures import STUDENT_UNLINKED, seed
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_shared.auth import Audience, Role
from learning_api.main import app
from sqlalchemy import text
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


def _headers() -> dict[str, str]:
    token = issuer.issue(sub=STUDENT_UNLINKED, role=Role.STUDENT, audience=Audience.LEARNING)
    return {"Authorization": f"Bearer {token}"}


def _answer(
    client: TestClient,
    headers: dict[str, str],
    session_id: str,
    item: dict,
    *,
    idempotency_key: str,
):
    """One submission in the shape the route actually requires: an `Idempotency-Key` header,
    the option *text* (not its index), and a response time."""
    return client.post(
        f"/learning/sessions/{session_id}/answers",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json={
            "question_variant_id": item["question_variant_id"],
            # The route wants the option's *text*, and a served item carries the four options as
            # `option_a`..`option_d` rather than a list.
            "selected_option": item["option_a"],
            "response_time_ms": 3000,
        },
    )


def _start_exam(client: TestClient, headers: dict[str, str]) -> tuple[str, list[dict]]:
    """A session sitting on a served pre-exam, which is where four of the five 409s live."""
    session_id = client.post("/learning/sessions", headers=headers).json()["learning_session_id"]
    client.post(
        f"/learning/sessions/{session_id}/student",
        headers=headers,
        json={"student_id": STUDENT_UNLINKED},
    )
    topics = client.post(
        f"/learning/sessions/{session_id}/topics",
        headers=headers,
        json={"topic_id": "linear_equations"},
    )
    assert topics.status_code == 200, topics.text
    body = topics.json()
    assert body["phase"] == "pre_exam", body
    return session_id, body["items"]


def test_a_request_against_an_unstarted_session_is_a_404_not_a_409() -> None:
    """**A correction to what `errors.ts`'s 409 `["select a student"]` rule is for.**

    The obvious way to reach it - ask for a topic before selecting a student - does not: there is
    no session state until `/student` runs, so the route answers **404 "learning session not
    found"** and the client renders the D-381 404 sentence ("We couldn't find this…"), which is
    the right thing to say about a session that was never started.

    The 409 belongs to a *started* session whose student never resolved (a parent's
    `child_selection` path), which no test drives today. Recorded here as the reachability
    question it is, rather than left as a rule everyone assumes is covered: the 404 half is
    pinned, the 409 half is named as unpinned.
    """
    headers = _headers()
    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
    assert resp.status_code == 404, resp.text
    assert "not found" in resp.json()["detail"].lower()


def test_answering_the_same_item_twice_says_already_been_answered() -> None:
    """`errors.ts` 409 `["already been answered", "already answered"]` -> "You've already
    answered this one - it's saved."

    The first draft of that rule tested for "already answered", which is **not** a substring of
    `ItemAlreadyAnsweredError`'s "item {id} has already been answered" - so a duplicate
    submission fell through to the generic line. That is the exact failure this test would have
    caught, and `errors.ts` now carries both fragments.
    """
    headers = _headers()
    with TestClient(app) as client:
        session_id, items = _start_exam(client, headers)
        first = _answer(client, headers, session_id, items[0], idempotency_key="first")
        assert first.status_code == 200, first.text
        # A *different* idempotency key, or this is the documented idempotent-resubmission path
        # (200 with the same verdict) rather than a duplicate.
        second = _answer(client, headers, session_id, items[0], idempotency_key="second")
    assert second.status_code == 409, second.text
    assert "has already been answered" in second.json()["detail"].lower()


def test_an_answer_for_another_session_says_not_an_item_of_this_session() -> None:
    """`errors.ts` 409 `["not an item of this session"]` -> "That question isn't part of this
    session any more. Refresh the page…"

    Driven with a *real* variant id from a *different* session rather than a made-up one, because
    an unknown id takes the 400 `unknown question variant` branch instead - two different
    situations, two different sentences, and only this one is the 409.
    """
    headers = _headers()
    with TestClient(app) as client:
        first_session, _ = _start_exam(client, headers)
        second_session, other_items = _start_exam(client, headers)
        assert second_session != first_session
        resp = _answer(client, headers, first_session, other_items[0], idempotency_key="cross")
    assert resp.status_code == 409, resp.text
    assert "not an item of this session" in resp.json()["detail"].lower()


def test_no_400_detail_mentions_attendance() -> None:
    """The deleted rule, pinned so it cannot come back by accident.

    `errors.ts` carried `{status: 400, detail: ["attendance"]}` for a year and nothing this API
    returns can match it: the gate answers **200** with `phase: "blocked"` and its own message.
    Asserting the absence is worth one test - the next person to reach for "the API will tell the
    client attendance failed" gets this instead of a rule that silently never fires.
    """
    headers = _headers()
    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        unknown_topic = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "no-such-topic"},
        )
    assert unknown_topic.status_code == 400, unknown_topic.text
    assert "attendance" not in unknown_topic.json()["detail"].lower()
