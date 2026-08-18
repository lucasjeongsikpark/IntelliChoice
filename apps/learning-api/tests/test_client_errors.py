"""U5: the browser-crash sink (`POST /learning/client-errors`).

D-315 built both ends of this telemetry and left the middle: `ErrorBoundary` catches a render
crash, `main.tsx` catches uncaught errors, and both write to a console nobody is watching. These
tests pin the three properties that make the sink safe to point a K-12 browser at - it is
authenticated, it is bounded, and what it writes has been through redaction.
"""

import logging

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_shared.auth import Audience, Role
from learning_api.main import app
from learning_api.routers.client_errors import (
    _REPORTS_PER_MINUTE,
    MAX_MESSAGE_CHARS,
    MAX_STACK_CHARS,
    _scrub,
)

issuer = FakeTokenIssuer()


def _auth(sub: str = "client-error-student") -> dict[str, str]:
    return {
        "Authorization": (
            f"Bearer {issuer.issue(sub=sub, role=Role.STUDENT, audience=Audience.LEARNING)}"
        )
    }


# --- the endpoint ------------------------------------------------------------------------


def test_a_crash_report_is_accepted_and_logged_with_its_trace_id() -> None:
    """The point of the endpoint: a crash in the browser reaches the server log joined to the
    request that produced the page. A console error can never do that."""
    with TestClient(app) as client:
        resp = client.post(
            "/learning/client-errors",
            headers=_auth(),
            json={
                "message": "Cannot read properties of undefined",
                "stack": "at ExamScreen (ExamScreen.tsx:120)",
                "trace_id": "0af7651916cd43dd8448eb211c80319c",
            },
        )
    assert resp.status_code == 202, "accepted, not created - nothing is persisted"
    assert resp.json() == {"recorded": True}


def test_an_unauthenticated_report_is_refused() -> None:
    """Otherwise this is an open log-injection endpoint: anyone on the internet could write
    arbitrary strings into the log a real incident is read from."""
    with TestClient(app) as client:
        resp = client.post("/learning/client-errors", json={"message": "boom"})
    assert resp.status_code in (401, 403)


def test_an_unknown_field_is_refused_rather_than_ignored() -> None:
    """**`extra="forbid"`, and this is the test that makes it load-bearing.** Pydantic's default
    would silently drop `student_name`, so a future client could start sending PII to a logging
    endpoint and nothing would say so. A 422 is how that becomes a build failure instead."""
    with TestClient(app) as client:
        resp = client.post(
            "/learning/client-errors",
            headers=_auth(),
            json={"message": "boom", "student_name": "Ben First"},
        )
    assert resp.status_code == 422


def test_the_logged_record_carries_the_external_id_and_never_a_name(caplog) -> None:
    """SPEC §5.30's external-id-only rule applies to logs as much as to Postgres."""
    with caplog.at_level(logging.ERROR):
        with TestClient(app) as client:
            client.post(
                "/learning/client-errors",
                headers=_auth("student-ext-42"),
                json={"message": "boom"},
            )
    records = [r for r in caplog.records if r.getMessage() == "client_error"]
    assert records, "the crash must reach the log; that is the whole feature"
    assert records[0].student_external_id == "student-ext-42"


# --- what the two free-text fields are put through ----------------------------------------
#
# `PiiDenylistFilter` screens structured log *keys*, so it would pass a stack containing an
# email through untouched - the key is `stack`, not `email`. These are the content-level
# defences, and they are unit-tested against `_scrub` directly so a failure names the mechanism
# rather than the endpoint.


def test_a_stack_containing_a_question_stem_is_truncated() -> None:
    """**The criterion U5 was written for.** A question stem is not PII-shaped - no email, no
    phone, no URL - so a regex screen passes it straight through. Length is the only property
    that separates "a stack frame naming a component" from "a stack that has swallowed a whole
    question", which is why truncation and not redaction is the defence here."""
    stem = "Solve for x: 3x + 7 = 22. " * 200  # a stem, pasted repeatedly - ~5,200 chars

    scrubbed = _scrub(stem, MAX_STACK_CHARS)

    assert len(scrubbed) <= MAX_STACK_CHARS
    assert scrubbed.endswith("…[truncated]")
    assert len(scrubbed) < len(stem)


def test_an_email_inside_a_stack_is_redacted_before_truncation() -> None:
    """Order matters: truncating first could cut an email in half and leave a fragment the
    pattern no longer matches, so redaction runs on the whole string first. This fails if the
    two steps are ever swapped."""
    text = "at handler (a.tsx) contact=parent@example.com " + ("x" * MAX_STACK_CHARS)

    scrubbed = _scrub(text, MAX_STACK_CHARS)

    assert "parent@example.com" not in scrubbed
    assert "[redacted-email]" in scrubbed
    assert len(scrubbed) <= MAX_STACK_CHARS


def test_a_short_message_is_left_exactly_as_it_is() -> None:
    """The control. A defence that mangles ordinary input is one people route around - and the
    ordinary case is the one that has to stay readable for this to be worth reading."""
    message = "Cannot read properties of undefined (reading 'items')"

    assert _scrub(message, MAX_MESSAGE_CHARS) == message


@pytest.mark.parametrize("limit", [MAX_MESSAGE_CHARS, MAX_STACK_CHARS])
def test_truncation_never_exceeds_its_limit(limit: int) -> None:
    """Guards the off-by-one in `limit - len(marker)`: a naive slice plus a marker produces a
    string *longer* than the cap, which is the opposite of the guarantee."""
    assert len(_scrub("y" * (limit * 3), limit)) <= limit


def test_a_crash_loop_is_rate_limited_per_token() -> None:
    """**The app's global middleware does not cover this, which is why the endpoint has its own.**
    That middleware is keyed by `request.client.host` and capped at 6000/60s - a figure chosen as
    roughly 3x a legitimate burst across *all* traffic. A render loop emits thousands of reports
    and stays far under it, and a classroom behind one school NAT shares a single IP key, so one
    student's loop would throttle their classmates. Keying on `sub` makes the limit mean "this
    browser".

    Written because U5's criterion says "rate-limited, with a test" - and going to write the test
    is what surfaced that the docstring's original claim ("the app's global per-token middleware")
    was wrong on both counts.
    """
    headers = _auth("loop-student")
    with TestClient(app) as client:
        codes = [
            client.post(
                "/learning/client-errors", headers=headers, json={"message": f"crash {i}"}
            ).status_code
            for i in range(_REPORTS_PER_MINUTE + 5)
        ]

    assert codes[:_REPORTS_PER_MINUTE] == [202] * _REPORTS_PER_MINUTE
    assert set(codes[_REPORTS_PER_MINUTE:]) == {429}


def test_one_students_crash_loop_does_not_silence_another() -> None:
    """The control, and the reason the key is `sub` rather than the IP the global middleware uses:
    in a classroom every student shares one public address, so an IP-keyed limit would let one
    broken laptop suppress the reports that would have explained everyone else's."""
    with TestClient(app) as client:
        for i in range(_REPORTS_PER_MINUTE + 3):
            client.post(
                "/learning/client-errors",
                headers=_auth("noisy-student"),
                json={"message": f"crash {i}"},
            )
        quiet = client.post(
            "/learning/client-errors",
            headers=_auth("quiet-student"),
            json={"message": "my own first crash"},
        )

    assert quiet.status_code == 202
