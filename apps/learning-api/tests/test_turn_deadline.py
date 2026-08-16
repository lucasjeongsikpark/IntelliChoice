"""SPEC §5.25.1's outer bound on learning-api (D-374).

learning-api had no request deadline of any kind. The gateway ladder is 3 attempts x
`bedrock_call_timeout_s` plus 0.5s and 1.0s of backoff = **61.5s**, against CloudFront's 60s
origin read timeout — so the student got an opaque edge 504 while the backend kept working and
kept spending. D-208 measured it on `POST /exam/finalize`: 65-81s, with 61502.69ms of Bedrock
"identical to the millisecond, the signature of a ceiling being hit".

These tests pin the two properties that make the fix correct rather than merely present: the
deadline fires, and it sits in the right place in the chain.
"""

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from intellichoice_db.engine import create_engine
from learning_api.config import get_settings
from learning_api.routers import sessions as sessions_module
from learning_api.routers.sessions import _invoke_with_deadline
from sqlalchemy import text


class _SlowGraph:
    """A graph whose turn never finishes inside the deadline."""

    async def ainvoke(self, payload, config, context):  # noqa: ANN001, ARG002
        await asyncio.sleep(5)
        return {"never": "reached"}


class _FastGraph:
    async def ainvoke(self, payload, config, context):  # noqa: ANN001, ARG002
        return {"ok": True}


def test_a_turn_that_overruns_becomes_this_app_s_own_504() -> None:
    """Not the edge's opaque one. A student who sees CloudFront's 504 gets no sentence they
    can act on and no signal that their answer was saved; this one says both."""
    settings = get_settings()
    original = settings.learning_turn_deadline_s
    settings.learning_turn_deadline_s = 0.01
    try:
        with pytest.raises(HTTPException) as caught:
            asyncio.run(_invoke_with_deadline(_SlowGraph(), {}, "d374-session", None))
    finally:
        settings.learning_turn_deadline_s = original

    assert caught.value.status_code == 504
    # The wording is part of the contract: an exam answer commits before the narrative work
    # that overruns, so "your progress is saved" is true here and must keep being said.
    assert "progress is saved" in str(caught.value.detail)


def test_a_normal_turn_is_untouched() -> None:
    """The control. A deadline that fires on healthy turns would be worse than none."""
    result = asyncio.run(_invoke_with_deadline(_FastGraph(), {}, "d374-session", None))
    assert result == {"ok": True}


def test_the_deadline_sits_below_cloudfront_and_above_nothing_it_should_outlive() -> None:
    """**The ordering, pinned as arithmetic rather than as a comment.**

    Three bounds have to nest or the fix is decorative:

    - the deadline must be **under CloudFront's 60s** origin read timeout, or the edge cuts
      the client first and the student still gets the opaque 504 this exists to replace;
    - it must be under the **61.5s** worst-case gateway ladder, which is the thing being
      bounded — a deadline above it would never fire;
    - and learning-web's client timeout (55s) must be **above** it, so the server stops the
      work and answers before the browser gives up. A client timeout below the server's
      abandons turns the backend was about to complete and pay for.

    Each of these was a comment somewhere and none of them was checked.
    """
    deadline = get_settings().learning_turn_deadline_s
    cloudfront_origin_read_timeout_s = 60
    worst_case_gateway_ladder_s = 3 * 20 + 0.5 + 1.0
    learning_web_client_timeout_s = 55

    assert deadline < cloudfront_origin_read_timeout_s, (
        "the deadline is above CloudFront's 60s, so the edge cuts the client first and the "
        "student still sees an opaque 504"
    )
    assert deadline < worst_case_gateway_ladder_s, (
        "the deadline is above the worst-case gateway ladder, so it can never fire"
    )
    assert deadline < learning_web_client_timeout_s, (
        "the browser gives up before the server does, so it abandons turns the backend was "
        "about to complete and pay for"
    )


# --- the concurrency claim, which shares this helper (D-376) --------------------------------


def test_a_second_turn_on_the_same_session_is_refused_while_one_is_running() -> None:
    """learning-api had **no advisory lock anywhere** — `grep -rn "advisory"` found nothing.

    Seven routes read the checkpoint, await, then invoke, and `_get_state_values` is the read
    half of that window. Two requests on one `learning_session_id` could both see "no pending
    interrupt" and both reach `ainvoke`; `AsyncPostgresSaver` has no optimistic-concurrency
    check, so both supersteps branch from the same parent checkpoint and both write children.

    Reachable because `busyRef` is per *tab*: Chrome's "Duplicate tab" copies `sessionStorage`,
    so two tabs hold the same session id with independent busy gates, and two `ExamTimer`s
    expiring on the same second both POST `/exam/finalize`.

    Driven at the lock itself rather than through two real concurrent requests, for D-346's
    reason: the point is that the claim is held in the **database**, so it holds across
    replicas — which an `asyncio.Lock` would not.
    """

    async def contend() -> tuple[bool, bool]:
        engine = create_engine()
        try:
            async with engine.connect() as conn_a, engine.connect() as conn_b:
                key = {"key": "learning_turn:the-same-session"}
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
        "two connections both claimed the same session - concurrent turns would invoke one "
        "LangGraph thread twice, losing one turn's channel writes"
    )


def test_different_sessions_do_not_block_each_other() -> None:
    """The negative control: per-session, not a global mutex. Getting this wrong would
    serialise every student in the org behind whichever one is answering a question."""

    async def contend() -> tuple[bool, bool]:
        engine = create_engine()
        try:
            async with engine.connect() as conn_a, engine.connect() as conn_b:
                sql = text("SELECT pg_try_advisory_xact_lock(hashtext(:key))")
                await conn_a.begin()
                await conn_b.begin()
                a = bool((await conn_a.execute(sql, {"key": "learning_turn:one"})).scalar_one())
                b = bool((await conn_b.execute(sql, {"key": "learning_turn:two"})).scalar_one())
                return a, b
        finally:
            await engine.dispose()

    assert asyncio.run(contend()) == (True, True)


def test_the_lock_and_the_deadline_are_applied_at_the_same_seven_call_sites() -> None:
    """**Why both bounds live in one helper**, asserted rather than trusted to review.

    learning came to have neither while chat had both, so the failure mode to design against
    is an eighth `graph.ainvoke` added later that picks up one and misses the other. Routing
    every invocation through `_invoke_with_deadline` makes that impossible by construction —
    this test is what keeps it that way.
    """
    source = Path(sessions_module.__file__).read_text()
    direct = source.count("await graph.ainvoke(")
    routed = source.count("await _invoke_with_deadline(")
    assert direct == 1, (
        f"{direct} direct `graph.ainvoke` calls; exactly one is expected (the helper's own). "
        "A new call site bypassing the helper gets neither the deadline nor the lock."
    )
    assert routed == 7, f"expected 7 routed call sites, found {routed}"
