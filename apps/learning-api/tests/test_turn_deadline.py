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

import pytest
from fastapi import HTTPException
from learning_api.config import get_settings
from learning_api.routers.sessions import _invoke_with_deadline


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
