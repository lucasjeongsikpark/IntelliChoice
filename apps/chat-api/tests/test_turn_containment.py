"""D-345/D-346: what stops a chat turn spending, hanging, or racing without bound.

Before this, the only thing bounding what chat-api could bill was the per-*session*
50-cent budget, read from checkpointed state - and `POST /chat/sessions` is
unauthenticated, free, and persists nothing, so one session per question reset it every
time. There was no per-day ceiling, no request deadline, and no lock on a thread that
LangGraph cannot safely invoke twice at once.

Each test here names the guard *and* the thing it lets through, because a containment guard
that fires on legitimate traffic is a worse defect than the one it fixes: the suite's own
`reset_caller_rate_limits` fixture exists precisely because the first version of the
per-caller cap would have failed the test suite partway through its first run.
"""

import asyncio
from uuid import uuid4

import pytest
from chat_api.config import get_settings
from chat_api.main import app
from chat_api.routers import sessions as sessions_router
from chat_api.services.turn_cost import TURN_RESERVATION_ESTIMATE_CENTS
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_db.engine import create_engine
from intellichoice_db.models.cost_reservation import SCOPE_CHAT_TURN, SUBJECT_CHAT_API
from intellichoice_shared.auth import Audience, Role
from sqlalchemy import text

from .conftest import postgres_skip_reason

pytestmark = pytest.mark.skipif(
    postgres_skip_reason() is not None, reason=postgres_skip_reason() or ""
)

issuer = FakeTokenIssuer()

IN_SCOPE_QUERY = "zqxvchunk handbook"


def _ask(client: TestClient, session_id: str, query: str = IN_SCOPE_QUERY):
    return client.post(f"/chat/sessions/{session_id}/messages", json={"query": query})


def _new_session(client: TestClient) -> str:
    return client.post("/chat/sessions").json()["chat_session_id"]


def _run(coro):
    async def wrapper():
        return await coro

    return asyncio.run(wrapper())


def _committed_chat_spend_cents() -> float:
    async def fetch() -> float:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                return float(
                    (
                        await conn.execute(
                            text(
                                "SELECT COALESCE(SUM(COALESCE(actual_cents, reserved_cents)), 0) "
                                "FROM cost_reservations "
                                "WHERE scope = :scope AND subject_external_id = :subject"
                            ),
                            {"scope": SCOPE_CHAT_TURN, "subject": SUBJECT_CHAT_API},
                        )
                    ).scalar_one()
                )
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _seed_spend(cents: float) -> None:
    """Put the app at the edge of its per-day ceiling without making 60 real turns."""

    async def run() -> None:
        engine = create_engine()
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO cost_reservations "
                        "(reservation_id, scope, subject_external_id, reserved_cents, "
                        " actual_cents, created_at) "
                        "VALUES (gen_random_uuid()::text, :scope, :subject, :cents, "
                        " :cents, now())"
                    ),
                    {"scope": SCOPE_CHAT_TURN, "subject": SUBJECT_CHAT_API, "cents": cents},
                )
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_a_turn_settles_at_its_real_cost_not_the_reservation() -> None:
    """**The test that makes the ceiling usable rather than merely present.**

    A turn reserves 25 cents up front. If it never settled, 60 sequential turns would
    exhaust a 1500-cent day - the ceiling would be a per-day *turn count*, not a spend
    bound, and it would refuse legitimate traffic long before any real money was spent.
    So the claim under test is not "a reservation is written"; it is that what remains
    charged afterwards is the turn's real cost.
    """
    with TestClient(app) as client:
        _ask(client, _new_session(client))

    charged = _committed_chat_spend_cents()
    assert charged < TURN_RESERVATION_ESTIMATE_CENTS, (
        f"the turn is still charged at {charged} cents, i.e. at (or above) its "
        f"{TURN_RESERVATION_ESTIMATE_CENTS}-cent reservation - `settle` did not run"
    )


def test_the_daily_ceiling_refuses_a_turn_and_says_so_in_words_a_visitor_understands() -> None:
    """503 rather than 500, because the condition is real and temporary; and a message
    that names a remedy (wait, or contact the branch) rather than an internal cause.
    """
    _seed_spend(get_settings().chat_daily_spend_ceiling_cents)

    with TestClient(app) as client:
        response = _ask(client, _new_session(client))

    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail == sessions_router.DAILY_CEILING_MESSAGE
    # It must not be confusable with the no-approved-source refusal, which is the mistake
    # AUD-C-19 was: three different causes wearing one message.
    assert "approved source" not in detail


def test_the_ceiling_is_not_reached_by_ordinary_use() -> None:
    """The negative control for the test above. A guard is only as good as its false
    positives, and this one gates every question the app answers - so a handful of
    consecutive turns must not come close.
    """
    with TestClient(app) as client:
        session_id = _new_session(client)
        statuses = [_ask(client, session_id).status_code for _ in range(3)]

    assert statuses == [200, 200, 200]
    assert _committed_chat_spend_cents() < get_settings().chat_daily_spend_ceiling_cents


def test_a_second_turn_on_the_same_thread_is_refused_while_one_is_running() -> None:
    """D-346's advisory try-lock. `_reject_if_paused` reads the checkpoint and then
    invokes with nothing in between, so two simultaneous POSTs on one thread both saw
    "not paused" and both ran - and a LangGraph thread is not safe to invoke twice at
    once.

    Driven at the lock itself rather than through two real concurrent requests: the point
    is that the claim is held in the *database* (so it works across replicas, which an
    `asyncio.Lock` would not), and two sessions contending for one key is exactly what a
    second task looks like.
    """

    async def contend() -> tuple[bool, bool]:
        engine = create_engine()
        try:
            factory_a, factory_b = engine.connect(), engine.connect()
            async with factory_a as conn_a, factory_b as conn_b:
                key = {"key": "chat_turn:the-same-thread"}
                sql = text("SELECT pg_try_advisory_xact_lock(hashtext(:key))")
                await conn_a.begin()
                await conn_b.begin()
                first = bool((await conn_a.execute(sql, key)).scalar_one())
                second = bool((await conn_b.execute(sql, key)).scalar_one())
                return first, second
        finally:
            await engine.dispose()

    first, second = asyncio.run(contend())
    assert first is True
    assert second is False, (
        "two connections both claimed the same thread - the lock is not exclusive, so "
        "concurrent turns would still invoke one LangGraph thread twice"
    )


def test_different_threads_do_not_block_each_other() -> None:
    """The negative control: the lock is per-thread, not a global chat mutex. Getting this
    wrong would serialise every user in the org behind whichever one is asking a question.
    """

    async def contend() -> tuple[bool, bool]:
        engine = create_engine()
        try:
            async with engine.connect() as conn_a, engine.connect() as conn_b:
                sql = text("SELECT pg_try_advisory_xact_lock(hashtext(:key))")
                await conn_a.begin()
                await conn_b.begin()
                first = bool((await conn_a.execute(sql, {"key": "chat_turn:one"})).scalar_one())
                second = bool((await conn_b.execute(sql, {"key": "chat_turn:two"})).scalar_one())
                return first, second
        finally:
            await engine.dispose()

    assert asyncio.run(contend()) == (True, True)


def test_a_turn_that_overruns_the_deadline_is_stopped_with_a_504() -> None:
    """D-346. Six sequential gateway calls, each retrying three times at 20s, put the
    worst case near six minutes - while CloudFront cuts the client at 60s. The backend
    kept running, and kept spending, for a caller who was already gone.

    The deadline is driven to a value a mock turn will exceed rather than waiting 50s.
    """
    settings = get_settings()
    original = settings.chat_turn_deadline_s
    settings.chat_turn_deadline_s = 0.001
    try:
        with TestClient(app) as client:
            response = _ask(client, _new_session(client))
    finally:
        settings.chat_turn_deadline_s = original

    assert response.status_code == 504, response.text
    assert response.json()["detail"] == sessions_router.TURN_TIMED_OUT_MESSAGE


def test_a_timed_out_turn_still_settles_its_reservation() -> None:
    """The failure path of the reservation, which is the one that leaks if it is wrong: a
    turn stopped by the deadline has still spent whatever it spent, and its 25-cent
    reservation must not stay charged at the estimate forever. `_reserved_turn` settles in
    a `finally`, so the exception path is covered by construction - this asserts it.
    """
    settings = get_settings()
    original = settings.chat_turn_deadline_s
    settings.chat_turn_deadline_s = 0.001
    try:
        with TestClient(app) as client:
            assert _ask(client, _new_session(client)).status_code == 504
    finally:
        settings.chat_turn_deadline_s = original

    assert _committed_chat_spend_cents() < TURN_RESERVATION_ESTIMATE_CENTS


def test_the_per_caller_cap_refuses_a_flood_and_names_the_remedy() -> None:
    settings = get_settings()
    original = settings.chat_message_rate_limit_max_per_window
    # The limiter is built once per lifespan, so the cap has to be in place before the
    # `TestClient` context opens.
    settings.chat_message_rate_limit_max_per_window = 2
    try:
        with TestClient(app) as client:
            session_id = _new_session(client)
            first = _ask(client, session_id)
            second = _ask(client, session_id)
            third = _ask(client, session_id)
    finally:
        settings.chat_message_rate_limit_max_per_window = original

    assert (first.status_code, second.status_code) == (200, 200)
    assert third.status_code == 429, third.text
    assert third.json()["detail"] == sessions_router.TOO_MANY_TURNS_MESSAGE


def test_minting_a_fresh_session_per_question_does_not_reset_the_cap() -> None:
    """**The vector this cap exists to close.** `POST /chat/sessions` is unauthenticated,
    free, and persists nothing, and the per-session Bedrock budget is read from the new
    session's own empty state - so before D-345 a caller got a full 50-cent budget per
    question simply by asking each one in a new session. The cap is keyed by *caller*, so
    a new session id buys nothing.
    """
    settings = get_settings()
    original = settings.chat_message_rate_limit_max_per_window
    settings.chat_message_rate_limit_max_per_window = 2
    try:
        with TestClient(app) as client:
            statuses = [_ask(client, _new_session(client)).status_code for _ in range(3)]
    finally:
        settings.chat_message_rate_limit_max_per_window = original

    assert statuses == [200, 200, 429]


def test_a_signed_in_caller_has_their_own_budget_not_the_shared_ip_one() -> None:
    """The other half of the key derivation, and the reason the cap can be keyed by IP at
    all: D-087 recorded that real school branches put many concurrent students behind one
    egress IP. Anonymous visitors there share a key; a signed-in one does not.
    """
    settings = get_settings()
    original = settings.chat_message_rate_limit_max_per_window
    settings.chat_message_rate_limit_max_per_window = 1
    # A sub nothing else in the suite uses, so this test does not depend on the conftest
    # fixture having cleared someone else's counter - the exact coupling that made the
    # first version of this test pass alone and fail in the full run.
    token = issuer.issue(sub=f"parent-{uuid4()}", role=Role.PARENT, audience=Audience.CHAT)
    try:
        with TestClient(app) as client:
            anonymous_ok = _ask(client, _new_session(client)).status_code
            anonymous_capped = _ask(client, _new_session(client)).status_code
            signed_in = client.post(
                f"/chat/sessions/{_new_session(client)}/messages",
                json={"query": IN_SCOPE_QUERY},
                headers={"Authorization": f"Bearer {token}"},
            ).status_code
    finally:
        settings.chat_message_rate_limit_max_per_window = original

    assert (anonymous_ok, anonymous_capped) == (200, 429)
    assert signed_in == 200, "a signed-in caller was charged the anonymous IP's counter"
