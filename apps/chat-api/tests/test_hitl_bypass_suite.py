"""E3.4 - the HITL bypass-attempt suite for chat-api's three `interrupt()` gates.

SPEC §5.1.4: *every* external action (email, calendar event, location use, image
analysis) is gated behind a LangGraph `interrupt()` a human resolves. Before this file the
denominator behind that claim was **one** explicit adversarial case (seven counting the
replay/deny family), which is not enough to say "0 of N" about anything. This file builds
the denominator: each case below is one attempt to make an external side effect happen
without a valid human approval for it, and each asserts what did *not* happen.

## How to read a case

`BYPASS_CASES` is the machine-readable catalog - id, surface, attack shape, expected
invariant - and it is also what the parametrization iterates, so the ids in the collected
node names and the ids in the catalog cannot drift apart. `benchmarks/resume_evidence/
03_gateway_agents/hitl_bypass_inventory.py` reads this list and cross-checks it against
`pytest --collect-only`, so the count quoted in `E3_REPORT.md` is a collected count rather
than a claim.

Three case kinds, kept apart on purpose:

- `bypass` - must produce **no** external side effect. This is the numerator/denominator
  behind "N attempts, 0 side effects".
- `control` - a *legitimate* approval that must still work. Without these the suite could
  pass by refusing everything, which is not the property being asserted.
- `finding` - an attempt whose honest result is a documented weakness rather than a clean
  refusal. Counted separately and never folded into the 0-side-effects claim.

## What "external side effect" means here

`app.state.email_transport` (Gmail stand-in) and `app.state.calendar_transport` (Google
Calendar stand-in) are the two recording fakes the app really wires, so "nothing was sent"
is asserted against the same object the graph would have called. `interrupt_approvals` is
the audit row every resolved interrupt writes; a refused resume must write none, and that
is asserted separately because "no email" and "no audit row claiming an approval happened"
are two different promises.
"""

import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from chat_api.config import get_settings
from chat_api.graph.nodes import (
    EMAIL_DECLINED_MESSAGE,
    EMAIL_SENT_MESSAGE,
    LOCATION_DECLINED_MESSAGE,
)
from chat_api.main import app
from chat_api.services.admin_escalation import MAX_NOTE_CHARS
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_db.models.interrupts import InterruptApproval
from intellichoice_shared.auth import Audience, Role
from sqlalchemy import select, text

from .conftest import postgres_skip_reason

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)

issuer = FakeTokenIssuer()

ESCALATION_QUERY = "Who do I talk to about a billing issue?"
LOCATOR_QUERY = "What is the nearest branch to me?"

#: Expanded by the drivers below. Kept as a token rather than a computed string so
#: `BYPASS_CASES` stays a pure literal that the inventory generator can read with
#: `ast.literal_eval`, without importing this module (which would need the app installed).
OVERSIZED_NOTE = "__OVERSIZED_NOTE__"

BYPASS_CASES = [
    # ---------------------------------------------------------------- malformed payloads
    {
        "id": "HB-CHAT-01",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "empty JSON body - no discriminator, no decision",
        "invariant": "422; no email sent; no interrupt_approvals row",
        "payload": {},
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-02",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "decision without the interrupt_type discriminator",
        "invariant": "422; no email sent; no interrupt_approvals row",
        "payload": {"approved": True},
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-03",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "discriminator without a decision field",
        "invariant": "422; no email sent; no interrupt_approvals row",
        "payload": {"interrupt_type": "email_approval"},
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-04",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "non-boolean approval string that is not an affirmative ('maybe')",
        "invariant": "422; no email sent; no interrupt_approvals row",
        "payload": {"interrupt_type": "email_approval", "approved": "maybe"},
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-05",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "null approval - absence dressed as a decision",
        "invariant": "422; no email sent; no interrupt_approvals row",
        "payload": {"interrupt_type": "email_approval", "approved": None},
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-06",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "empty list as approval - truthiness confusion probe",
        "invariant": "422; no email sent; no interrupt_approvals row",
        "payload": {"interrupt_type": "email_approval", "approved": []},
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-07",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "non-empty object as approval - truthiness confusion probe",
        "invariant": "422; no email sent; no interrupt_approvals row",
        "payload": {"interrupt_type": "email_approval", "approved": {"ok": True}},
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-08",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "integer 2 as approval - out-of-range int-to-bool coercion probe",
        "invariant": "422; no email sent; no interrupt_approvals row",
        "payload": {"interrupt_type": "email_approval", "approved": 2},
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-09",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "the string 'false' - a node reading truthiness would send",
        "invariant": "accepted as a decline; no email sent",
        "payload": {"interrupt_type": "email_approval", "approved": "false"},
        "expected_status": [200],
    },
    {
        "id": "HB-CHAT-10",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "integer 0 as approval",
        "invariant": "accepted as a decline; no email sent",
        "payload": {"interrupt_type": "email_approval", "approved": 0},
        "expected_status": [200],
    },
    {
        "id": "HB-CHAT-11",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "discriminator smuggled inside a list",
        "invariant": "422; no email sent; no interrupt_approvals row",
        "payload": {"interrupt_type": ["email_approval"], "approved": True},
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-12",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "invented discriminator value ('admin_override')",
        "invariant": "422; no email sent; no interrupt_approvals row",
        "payload": {"interrupt_type": "admin_override", "approved": True},
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-13",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "wrong-but-valid discriminator: resolve the calendar gate on an email pause",
        "invariant": "409 pending-interrupt mismatch; no email, no calendar event",
        "payload": {"interrupt_type": "calendar_action", "choice": "google"},
        "expected_status": [409],
    },
    {
        "id": "HB-CHAT-14",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "wrong-but-valid discriminator: location consent on an email pause",
        "invariant": "409 pending-interrupt mismatch; no email sent",
        "payload": {
            "interrupt_type": "location_consent",
            "approved": True,
            "latitude": 41.1,
            "longitude": -87.2,
        },
        "expected_status": [409],
    },
    {
        "id": "HB-CHAT-15",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "approval carrying a note past MAX_NOTE_CHARS",
        "invariant": "422; no email sent - refused rather than silently truncated",
        "payload": {
            "interrupt_type": "email_approval",
            "approved": True,
            "note": OVERSIZED_NOTE,
        },
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-16",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "explicit decline carrying a fully-formed email body",
        "invariant": "200 declined; no email sent",
        "payload": {
            "interrupt_type": "email_approval",
            "approved": False,
            "note": "send it anyway",
        },
        "expected_status": [200],
    },
    {
        "id": "HB-CHAT-17",
        "kind": "bypass",
        "group": "email_payload",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "approval nested one level down, as a real client bug or a probe would send it",
        "invariant": "422; no email sent",
        "payload": {"interrupt_type": "email_approval", "decision": {"approved": True}},
        "expected_status": [422],
    },
    # ----------------------------------------------------------- session / state / owner
    {
        "id": "HB-CHAT-18",
        "kind": "bypass",
        "group": "session_state",
        "surface": "chat-api POST /chat/sessions/{id}/respond",
        "attack": "approve an interrupt on a session id that does not exist",
        "invariant": "404; no email sent",
        "payload": None,
        "expected_status": [404],
    },
    {
        "id": "HB-CHAT-19",
        "kind": "bypass",
        "group": "session_state",
        "surface": "chat-api POST /chat/sessions/{id}/respond",
        "attack": "approve on a real session that has no pending interrupt",
        "invariant": "404 (no checkpoint yet); no email sent",
        "payload": None,
        "expected_status": [404],
    },
    {
        "id": "HB-CHAT-20",
        "kind": "bypass",
        "group": "session_state",
        "surface": "chat-api POST /chat/sessions/{id}/respond",
        "attack": "approve on a session that answered normally and never paused",
        "invariant": "409 no interrupt pending; no email sent",
        "payload": None,
        "expected_status": [409],
    },
    {
        "id": "HB-CHAT-21",
        "kind": "bypass",
        "group": "session_state",
        "surface": "chat-api POST /chat/sessions/{id}/respond (owned thread)",
        "attack": "anonymous caller resumes a signed-in caller's pending approval",
        "invariant": "403; no email sent",
        "payload": None,
        "expected_status": [403],
    },
    {
        "id": "HB-CHAT-22",
        "kind": "bypass",
        "group": "session_state",
        "surface": "chat-api POST /chat/sessions/{id}/respond (owned thread)",
        "attack": "a different authenticated user resumes someone else's pending approval",
        "invariant": "403; no email sent",
        "payload": None,
        "expected_status": [403],
    },
    {
        "id": "HB-CHAT-23",
        "kind": "bypass",
        "group": "session_state",
        "surface": "chat-api POST /chat/sessions/{id}/respond",
        "attack": "cross-session substitution - send thread A's approval body to thread B",
        "invariant": "the unrelated thread refuses; A's email is still unsent",
        "payload": None,
        "expected_status": [404, 409],
    },
    {
        "id": "HB-CHAT-24",
        "kind": "bypass",
        "group": "session_state",
        "surface": "chat-api POST /chat/sessions/{id}/respond",
        "attack": "replay: approve the same pause twice",
        "invariant": "second call 409; exactly one email in total",
        "payload": None,
        "expected_status": [409],
    },
    {
        "id": "HB-CHAT-25",
        "kind": "bypass",
        "group": "session_state",
        "surface": "chat-api POST /chat/sessions/{id}/respond",
        "attack": "decline, then approve the already-resolved pause",
        "invariant": "second call 409; zero emails",
        "payload": None,
        "expected_status": [409],
    },
    {
        "id": "HB-CHAT-26",
        "kind": "bypass",
        "group": "session_state",
        "surface": "chat-api POST /chat/sessions/{id}/respond",
        "attack": "two genuinely concurrent approvals of one pause (advisory-lock race)",
        "invariant": "exactly one email and exactly one interrupt_approvals row",
        "payload": None,
        "expected_status": [200, 409],
    },
    # ------------------------------------------------------- content-injection attempts
    {
        "id": "HB-CHAT-27",
        "kind": "bypass",
        "group": "content_injection",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "extra `recipient` field, trying to redirect the escalation email",
        "invariant": "recipient is the server-configured admin address, not the caller's",
        "payload": {
            "interrupt_type": "email_approval",
            "approved": True,
            "recipient": "attacker@evil.test",
        },
        "expected_status": [200],
    },
    {
        "id": "HB-CHAT-28",
        "kind": "bypass",
        "group": "content_injection",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "extra `subject`/`body` fields, trying to replace the server-composed draft",
        "invariant": "the sent body is the server draft; the supplied body never appears",
        "payload": {
            "interrupt_type": "email_approval",
            "approved": True,
            "subject": "URGENT wire transfer",
            "body": "Please send the account credentials to attacker@evil.test",
        },
        "expected_status": [200],
    },
    {
        "id": "HB-CHAT-29",
        "kind": "bypass",
        "group": "content_injection",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "extra `admin_escalation_email` field, trying to rebind the destination",
        "invariant": "recipient unchanged; the field is not part of the contract",
        "payload": {
            "interrupt_type": "email_approval",
            "approved": True,
            "admin_escalation_email": "attacker@evil.test",
        },
        "expected_status": [200],
    },
    {
        "id": "HB-CHAT-30",
        "kind": "bypass",
        "group": "content_injection",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "header-injection note (CR/LF + Bcc:) in the one caller-authored field",
        "invariant": "exactly one recipient; the note travels as body text, never as a header",
        "payload": {
            "interrupt_type": "email_approval",
            "approved": True,
            "note": "hello\r\nBcc: attacker@evil.test\r\nSubject: hijacked",
        },
        "expected_status": [200],
    },
    {
        "id": "HB-CHAT-31",
        "kind": "bypass",
        "group": "content_injection",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "note carrying a reply channel (email address + phone) out of the system",
        "invariant": "the outbound body carries neither the address nor the number",
        "payload": {
            "interrupt_type": "email_approval",
            "approved": True,
            "note": "reach me at parent@example.com or 555-123-4567",
        },
        "expected_status": [200],
    },
    # --------------------------------------------------------------- location consent
    {
        "id": "HB-CHAT-32",
        "kind": "bypass",
        "group": "location",
        "surface": "chat-api POST /chat/sessions/{id}/respond (location_consent pending)",
        "attack": "decline while still supplying precise coordinates",
        "invariant": "declined answer; the coordinates are purged from checkpoint writes",
        "payload": {
            "interrupt_type": "location_consent",
            "approved": False,
            "latitude": 41.987654,
            "longitude": -87.123456,
        },
        "expected_status": [200],
    },
    {
        "id": "HB-CHAT-33",
        "kind": "bypass",
        "group": "location",
        "surface": "chat-api POST /chat/sessions/{id}/respond (location_consent pending)",
        "attack": "consent field omitted entirely, coordinates supplied",
        "invariant": "422; the request never reaches the node",
        "payload": {
            "interrupt_type": "location_consent",
            "latitude": 41.987654,
            "longitude": -87.123456,
        },
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-34",
        "kind": "bypass",
        "group": "location",
        "surface": "chat-api POST /chat/sessions/{id}/respond (location_consent pending)",
        "attack": "resolve the email gate while the location gate is the pending one",
        "invariant": "409 mismatch; no email sent",
        "payload": {"interrupt_type": "email_approval", "approved": True},
        "expected_status": [409],
    },
    {
        "id": "HB-CHAT-35",
        "kind": "bypass",
        "group": "location",
        "surface": "chat-api POST /chat/sessions/{id}/respond (location_consent pending)",
        "attack": "non-boolean consent ('yes please')",
        "invariant": "422; the request never reaches the node",
        "payload": {
            "interrupt_type": "location_consent",
            "approved": "yes please",
            "latitude": 41.5,
            "longitude": -87.5,
        },
        "expected_status": [422],
    },
    # -------------------------------------------------------------- audit-row invariant
    {
        "id": "HB-CHAT-36",
        "kind": "bypass",
        "group": "audit",
        "surface": "interrupt_approvals audit table",
        "attack": "a schema-refused resume must not leave an approval record behind",
        "invariant": "zero interrupt_approvals rows for the thread after a 422",
        "payload": None,
        "expected_status": [422],
    },
    {
        "id": "HB-CHAT-37",
        "kind": "bypass",
        "group": "audit",
        "surface": "interrupt_approvals audit table",
        "attack": "a mismatched-discriminator resume must not leave an approval record",
        "invariant": "zero interrupt_approvals rows for the thread after a 409",
        "payload": None,
        "expected_status": [409],
    },
    {
        "id": "HB-CHAT-38",
        "kind": "bypass",
        "group": "audit",
        "surface": "interrupt_approvals audit table",
        "attack": "a declined approval must be recorded as cancelled, not as approved",
        "invariant": "exactly one row, decision='cancelled', no email",
        "payload": None,
        "expected_status": [200],
    },
    # ------------------------------------------------------------------------- controls
    {
        "id": "HB-CHAT-C1",
        "kind": "control",
        "group": "control",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "not an attack - a plain, valid approval",
        "invariant": "exactly one email to the configured admin; one approved audit row",
        "payload": {"interrupt_type": "email_approval", "approved": True},
        "expected_status": [200],
    },
    {
        "id": "HB-CHAT-C2",
        "kind": "control",
        "group": "control",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "not an attack - a note exactly at MAX_NOTE_CHARS",
        "invariant": "accepted; the bound above is a bound, not a blanket refusal",
        "payload": {"interrupt_type": "email_approval", "approved": True, "note": "n"},
        "expected_status": [200],
    },
    # -------------------------------------------------------------------------- finding
    {
        "id": "HB-CHAT-F1",
        "kind": "finding",
        "group": "finding",
        "surface": "chat-api POST /chat/sessions/{id}/respond (email_approval pending)",
        "attack": "resume an approval left pending for an arbitrary length of time",
        "invariant": (
            "FINDING: no TTL exists on a pending interrupt - a stale pause stays "
            "resumable indefinitely. Test pins the current behaviour."
        ),
        "payload": {"interrupt_type": "email_approval", "approved": True},
        "expected_status": [200],
    },
]


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _params(group: str) -> list:
    return [pytest.param(c, id=c["id"]) for c in BYPASS_CASES if c["group"] == group]


def _token(sub: str, role: Role = Role.PARENT) -> str:
    return issuer.issue(sub=sub, role=role, audience=Audience.CHAT)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sent(client: TestClient) -> list:
    return client.app.state.email_transport.sent  # type: ignore[attr-defined]


def _calendar_events(client: TestClient) -> list:
    return client.app.state.calendar_transport.created  # type: ignore[attr-defined]


def _expand(payload: dict | None) -> dict | None:
    """Replace the literal placeholders `BYPASS_CASES` uses to stay `literal_eval`-safe."""
    if payload is None:
        return None
    out = dict(payload)
    if out.get("note") == OVERSIZED_NOTE:
        out["note"] = "x" * (MAX_NOTE_CHARS + 1)
    elif out.get("note") == "n":
        out["note"] = "n" * MAX_NOTE_CHARS
    return out


def _paused_email_thread(client: TestClient, headers: dict[str, str] | None = None) -> str:
    """A fresh thread parked on the admin-escalation email approval."""
    session_id = client.post("/chat/sessions", headers=headers or {}).json()["chat_session_id"]
    paused = client.post(
        f"/chat/sessions/{session_id}/messages",
        json={"query": ESCALATION_QUERY, "escalate": True},
        headers=headers or {},
    ).json()
    assert paused["pending_interrupt"]["interrupt_type"] == "email_approval", (
        f"this journey no longer pauses on the email gate ({paused.get('pending_interrupt')}), "
        "so every assertion below would be vacuous"
    )
    return session_id


def _paused_locator_thread(client: TestClient) -> str:
    session_id = client.post("/chat/sessions").json()["chat_session_id"]
    paused = client.post(
        f"/chat/sessions/{session_id}/messages",
        json={"query": LOCATOR_QUERY},
    ).json()
    assert paused["pending_interrupt"]["interrupt_type"] == "location_consent", (
        f"this journey no longer pauses on the location gate ({paused.get('pending_interrupt')})"
    )
    return session_id


def _approvals(session_id: str) -> list[InterruptApproval]:
    """Read the audit rows through an engine of this call's own, not the app's.

    `app.state.db_session_factory` is bound to `TestClient`'s internal event loop; a
    separate `asyncio.run` here cannot share it (the same trap `test_chat_endpoints.py`
    documents for `_initial_snapshot`).
    """

    async def run() -> list[InterruptApproval]:
        engine = create_engine()
        try:
            async with create_session_factory(engine)() as session:
                result = await session.execute(
                    select(InterruptApproval).where(InterruptApproval.session_id == session_id)
                )
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(run())


# --------------------------------------------------------------------------------------
# Group: malformed / hostile resume payloads at the email gate
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", _params("email_payload"))
def test_email_gate_refuses_malformed_or_hostile_resume_payloads(case: dict) -> None:
    """Every one of these is a resume the caller controls entirely, aimed at the one route
    that can turn a pending draft into a real outbound email.

    The assertion is deliberately *two* facts, not one: the status code says the request
    was refused, and `email_transport.sent` says nothing left the system. A route that
    500s after sending would satisfy the first and fail the second.
    """
    with TestClient(app) as client:
        session_id = _paused_email_thread(client)
        before = len(_sent(client))
        calendar_before = len(_calendar_events(client))
        response = client.post(
            f"/chat/sessions/{session_id}/respond", json=_expand(case["payload"])
        )
        after = len(_sent(client))
        calendar_after = len(_calendar_events(client))

    assert response.status_code in case["expected_status"], (
        f"{case['id']}: expected {case['expected_status']}, got "
        f"{response.status_code}: {response.text[:400]}"
    )
    assert after == before, f"{case['id']}: an email was sent by a refused/declined resume"
    assert calendar_after == calendar_before, f"{case['id']}: a calendar event was created"


# --------------------------------------------------------------------------------------
# Group: session, state and ownership
# --------------------------------------------------------------------------------------


def test_hb_chat_18_unknown_session_id() -> None:
    case = _case("HB-CHAT-18")
    with TestClient(app) as client:
        before = len(_sent(client))
        response = client.post(
            f"/chat/sessions/{uuid.uuid4()}/respond",
            json={"interrupt_type": "email_approval", "approved": True},
        )
        assert response.status_code in case["expected_status"], response.text
        assert len(_sent(client)) == before


def test_hb_chat_19_session_with_no_checkpoint() -> None:
    case = _case("HB-CHAT-19")
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        before = len(_sent(client))
        response = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "email_approval", "approved": True},
        )
        assert response.status_code in case["expected_status"], response.text
        assert len(_sent(client)) == before


def test_hb_chat_20_thread_that_answered_and_never_paused() -> None:
    case = _case("HB-CHAT-20")
    with TestClient(app) as client:
        session_id = client.post("/chat/sessions").json()["chat_session_id"]
        answered = client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"query": "What's the best recipe for chocolate chip cookies?"},
        ).json()
        assert answered.get("pending_interrupt") is None, (
            "this journey now pauses, so the 409 below would not be testing what it says"
        )
        before = len(_sent(client))
        response = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "email_approval", "approved": True},
        )
        assert response.status_code in case["expected_status"], response.text
        assert len(_sent(client)) == before
        assert _approvals(session_id) == []


def test_hb_chat_21_anonymous_caller_resumes_an_owned_thread() -> None:
    """AUD-C-01's shape, aimed at the gate rather than at `/messages`: holding a session id
    is not holding the approval. The owner is a fresh uuid `sub` per run so the escalation
    cap (keyed on `sub`, 5/hour, persistent) cannot make this fail on the third run.
    """
    case = _case("HB-CHAT-21")
    owner = _token(f"parent-hb-{uuid.uuid4().hex[:8]}")
    with TestClient(app) as client:
        session_id = _paused_email_thread(client, headers=_auth(owner))
        before = len(_sent(client))
        response = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "email_approval", "approved": True},
        )
        assert response.status_code in case["expected_status"], response.text
        assert len(_sent(client)) == before
        assert _approvals(session_id) == []


def test_hb_chat_22_a_different_user_resumes_an_owned_thread() -> None:
    case = _case("HB-CHAT-22")
    owner = _token(f"parent-hb-{uuid.uuid4().hex[:8]}")
    stranger = _token(f"parent-hb-{uuid.uuid4().hex[:8]}")
    with TestClient(app) as client:
        session_id = _paused_email_thread(client, headers=_auth(owner))
        before = len(_sent(client))
        response = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "email_approval", "approved": True},
            headers=_auth(stranger),
        )
        assert response.status_code in case["expected_status"], response.text
        assert len(_sent(client)) == before
        assert _approvals(session_id) == []


def test_hb_chat_23_cross_session_thread_substitution() -> None:
    """Thread A is paused on a real approval; the attacker posts A's approval body against
    an unrelated thread B, hoping the resume is matched by payload rather than by thread.
    """
    case = _case("HB-CHAT-23")
    with TestClient(app) as client:
        paused = _paused_email_thread(client)
        other = client.post("/chat/sessions").json()["chat_session_id"]
        before = len(_sent(client))
        response = client.post(
            f"/chat/sessions/{other}/respond",
            json={"interrupt_type": "email_approval", "approved": True},
        )
        assert response.status_code in case["expected_status"], response.text
        assert len(_sent(client)) == before, "the substituted thread sent A's email"
        assert _approvals(paused) == [], "thread A recorded an approval it never received"


def test_hb_chat_24_replay_of_an_approved_pause() -> None:
    case = _case("HB-CHAT-24")
    with TestClient(app) as client:
        session_id = _paused_email_thread(client)
        before = len(_sent(client))
        first = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "email_approval", "approved": True},
        )
        assert first.status_code == 200, first.text
        assert len(_sent(client)) == before + 1, "the legitimate approval did not send"

        replay = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "email_approval", "approved": True},
        )
        assert replay.status_code in case["expected_status"], replay.text
        assert len(_sent(client)) == before + 1, "the replay produced a second email"
    assert len(_approvals(session_id)) == 1


def test_hb_chat_25_approve_after_declining() -> None:
    case = _case("HB-CHAT-25")
    with TestClient(app) as client:
        session_id = _paused_email_thread(client)
        before = len(_sent(client))
        declined = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "email_approval", "approved": False},
        )
        assert declined.status_code == 200, declined.text
        assert declined.json()["answer"] == EMAIL_DECLINED_MESSAGE

        second = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "email_approval", "approved": True},
        )
        assert second.status_code in case["expected_status"], second.text
        assert len(_sent(client)) == before, "a declined approval was overturned into a send"
    rows = _approvals(session_id)
    assert [r.decision for r in rows] == ["cancelled"]


def test_hb_chat_26_two_concurrent_approvals_of_one_pause() -> None:
    """The `pg_try_advisory_xact_lock` race in `_claim_turn`, driven for real.

    Two threads POST the same approval at the same moment. The lock is transaction-scoped
    on the request's own session, so one request holds it for its whole turn and the other
    gets an immediate 409 rather than queueing - which is the behaviour D-346 chose. What
    must be true either way is the invariant asserted here: **one email, one audit row**.
    """
    case = _case("HB-CHAT-26")
    body = {"interrupt_type": "email_approval", "approved": True}
    with TestClient(app) as client:
        session_id = _paused_email_thread(client)
        before = len(_sent(client))

        def fire() -> int:
            return client.post(f"/chat/sessions/{session_id}/respond", json=body).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(f.result() for f in [pool.submit(fire), pool.submit(fire)])

        after = len(_sent(client))

    assert all(s in case["expected_status"] for s in statuses), statuses
    assert after - before == 1, f"{after - before} emails from one approval, statuses={statuses}"
    assert len(_approvals(session_id)) == 1, "more than one approval recorded for one pause"


# --------------------------------------------------------------------------------------
# Group: content injection through the approved resume
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", _params("content_injection"))
def test_an_approved_resume_cannot_redirect_or_rewrite_the_email(case: dict) -> None:
    """These approvals are *valid* - the human said yes - so exactly one email is expected.
    The bypass being tested is narrower and more interesting: whether the caller can steer
    where it goes or what it says by adding fields the contract does not have.

    The server composes the recipient, the subject and the frame of the body; the note is
    the only caller-authored part and it is redacted at the request boundary (D-420).
    """
    with TestClient(app) as client:
        session_id = _paused_email_thread(client)
        before = len(_sent(client))
        response = client.post(
            f"/chat/sessions/{session_id}/respond", json=_expand(case["payload"])
        )
        sent = _sent(client)
        after = len(sent)
        message = sent[-1] if after > before else None

    assert response.status_code in case["expected_status"], response.text
    assert after == before + 1, f"{case['id']}: expected exactly one email, got {after - before}"
    assert message is not None
    assert response.json()["answer"] == EMAIL_SENT_MESSAGE

    # Compared against the *configured* address rather than merely "not the attacker's":
    # a recipient that is neither would also be a redirect, and this is the one field the
    # server is supposed to own completely.
    assert message.recipient == get_settings().admin_escalation_email, (
        f"{case['id']}: the caller redirected the escalation email to {message.recipient!r}"
    )
    assert "attacker@evil.test" not in message.body, (
        f"{case['id']}: an attacker-controlled address reached the outbound body"
    )
    assert "URGENT wire transfer" not in message.subject, (
        f"{case['id']}: the caller replaced the server-composed subject"
    )
    assert "account credentials" not in message.body, (
        f"{case['id']}: the caller replaced the server-composed body"
    )
    # The note is the one field the caller does author, and D-420 redacts it here.
    assert "parent@example.com" not in message.body
    assert "555-123-4567" not in message.body
    # `EmailMessage.recipient` is a single string, so a CR/LF note cannot become a header:
    # the transport takes structured fields, not a serialized header block.
    assert "\r\n" not in message.recipient and "\n" not in message.recipient


# --------------------------------------------------------------------------------------
# Group: location consent
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", _params("location"))
def test_location_gate_refuses_malformed_or_mismatched_resumes(case: dict) -> None:
    with TestClient(app) as client:
        session_id = _paused_locator_thread(client)
        before = len(_sent(client))
        response = client.post(
            f"/chat/sessions/{session_id}/respond", json=_expand(case["payload"])
        )
        after = len(_sent(client))
        body = response.json() if response.status_code == 200 else None

    assert response.status_code in case["expected_status"], (
        f"{case['id']}: got {response.status_code}: {response.text[:400]}"
    )
    assert after == before, f"{case['id']}: an email was sent from the location gate"
    if case["id"] == "HB-CHAT-32":
        assert body is not None
        assert body["answer"] == LOCATION_DECLINED_MESSAGE
        _assert_no_resume_writes(session_id)


def _assert_no_resume_writes(session_id: str) -> None:
    """AUD-C-03/SEC-13-PURGE: the declined coordinates must not survive in `__resume__`.

    Read through a fresh engine for the reason `test_chat_endpoints.py` documents: a purge
    issued on the request's own session is still visible to that session even if it was
    rolled back, so only a connection that took no part in the request can tell the two
    apart.
    """

    async def run() -> list[str]:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                rows = await conn.execute(
                    text("SELECT channel FROM checkpoint_writes WHERE thread_id = :t"),
                    {"t": session_id},
                )
                return [r[0] for r in rows]
        finally:
            await engine.dispose()

    channels = asyncio.run(run())
    assert channels, "no checkpoint writes for the thread - wrong thread id?"
    assert "__resume__" not in channels, (
        "the declined caller's coordinates are still in a `__resume__` write"
    )


# --------------------------------------------------------------------------------------
# Group: the interrupt_approvals audit-row invariant
# --------------------------------------------------------------------------------------


def test_hb_chat_36_a_schema_refused_resume_writes_no_audit_row() -> None:
    case = _case("HB-CHAT-36")
    with TestClient(app) as client:
        session_id = _paused_email_thread(client)
        response = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "email_approval", "approved": "maybe"},
        )
    assert response.status_code in case["expected_status"], response.text
    assert _approvals(session_id) == [], "a refused request left an approval record"


def test_hb_chat_37_a_mismatched_resume_writes_no_audit_row() -> None:
    case = _case("HB-CHAT-37")
    with TestClient(app) as client:
        session_id = _paused_email_thread(client)
        response = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "calendar_action", "choice": "google"},
        )
    assert response.status_code in case["expected_status"], response.text
    assert _approvals(session_id) == [], "a mismatched request left an approval record"


def test_hb_chat_38_a_decline_is_recorded_as_cancelled() -> None:
    case = _case("HB-CHAT-38")
    with TestClient(app) as client:
        session_id = _paused_email_thread(client)
        before = len(_sent(client))
        response = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "email_approval", "approved": False},
        )
        after = len(_sent(client))
    assert response.status_code in case["expected_status"], response.text
    assert after == before
    rows = _approvals(session_id)
    assert [r.decision for r in rows] == ["cancelled"]
    assert rows[0].source_app == "chat"
    assert rows[0].interrupt_type == "email_approval"


# --------------------------------------------------------------------------------------
# Controls - a suite that refused everything would pass every case above
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", _params("control"))
def test_a_legitimate_approval_still_works(case: dict) -> None:
    with TestClient(app) as client:
        session_id = _paused_email_thread(client)
        before = len(_sent(client))
        response = client.post(
            f"/chat/sessions/{session_id}/respond", json=_expand(case["payload"])
        )
        sent = _sent(client)
        after = len(sent)
        recipient = sent[-1].recipient if after > before else None

    assert response.status_code in case["expected_status"], response.text
    assert after == before + 1, f"{case['id']}: the legitimate approval did not send"
    assert response.json()["answer"] == EMAIL_SENT_MESSAGE
    assert recipient is not None and "@" in recipient
    rows = _approvals(session_id)
    assert [r.decision for r in rows] == ["approved"]


# --------------------------------------------------------------------------------------
# Findings - documented weaknesses, kept out of the "0 side effects" claim
# --------------------------------------------------------------------------------------


def test_hb_chat_f1_a_pending_approval_has_no_expiry() -> None:
    """**Finding, not a passing guard.** Nothing in either app expires a pending
    `interrupt()`: `/respond` checks the session exists, that the caller owns it, and that
    the discriminator matches the pending type - never how old the pause is, and no TTL
    column or sweep exists for a live thread.

    So a pause left open is resumable later, and this test pins that rather than pretending
    otherwise. It uses a short idle gap because a test cannot wait out a plausible real
    delay; the *absence of any expiry check* is the evidence, and the gap only demonstrates
    that time passing changes nothing. Reported in `E3_REPORT.md`; deliberately excluded
    from the "N attempts, 0 side effects" denominator.
    """
    with TestClient(app) as client:
        session_id = _paused_email_thread(client)
        before = len(_sent(client))
        time.sleep(1.0)
        response = client.post(
            f"/chat/sessions/{session_id}/respond",
            json={"interrupt_type": "email_approval", "approved": True},
        )
        after = len(_sent(client))

    assert response.status_code == 200, response.text
    assert after == before + 1, (
        "the stale pause was refused - if this now fails, an expiry has been added and "
        "the finding in E3_REPORT.md should be closed"
    )


# --------------------------------------------------------------------------------------
# Catalog self-check
# --------------------------------------------------------------------------------------


def _case(case_id: str) -> dict:
    for case in BYPASS_CASES:
        if case["id"] == case_id:
            return case
    raise AssertionError(f"unknown bypass case id {case_id!r}")


def test_the_bypass_catalog_is_internally_consistent() -> None:
    """The denominator is only citable if the catalog and the tests cannot drift.

    Every id unique, every case fully described, and every id actually used by a test in
    this module - checked by reading this file's own source, which is how a case that was
    added to the catalog and never wired to a test gets caught.
    """
    ids = [c["id"] for c in BYPASS_CASES]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    for case in BYPASS_CASES:
        assert case["kind"] in {"bypass", "control", "finding"}, case["id"]
        for field in ("surface", "attack", "invariant", "group"):
            assert case[field], f"{case['id']} is missing {field}"

    source = __file__.replace(".pyc", ".py")
    with open(source) as handle:
        body = handle.read()
    catalog_end = body.index("# Helpers")
    tests_body = body[catalog_end:]
    grouped = {c["group"] for c in BYPASS_CASES if c["group"] not in {"control", "finding"}}
    for group in grouped:
        assert f'_params("{group}")' in tests_body or any(
            c["id"].lower().replace("-", "_") in tests_body
            for c in BYPASS_CASES
            if c["group"] == group
        ), f"group {group!r} is in the catalog but no test drives it"
    for case in BYPASS_CASES:
        used = (
            f'_params("{case["group"]}")' in tests_body
            or (case["id"].lower().replace("-", "_") in tests_body)
            or f'_case("{case["id"]}")' in tests_body
        )
        assert used, f"{case['id']} is catalogued but never driven by a test"
