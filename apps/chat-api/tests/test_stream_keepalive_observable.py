"""D-404: the keep-alive is an event a client can see, in both apps.

**The defect.** `: keep-alive` is an SSE *comment*. It puts bytes on the wire so the connection
stays warm, and it fires **no event** in the browser - `EventSource` discards comment lines before
any handler runs. So a client cannot tell "quiet because nothing has happened" from "dead", which
is `EDGE-CHAT-02`. W11 (D-403) shipped chat's reconnect control and had to **defer** the liveness
timer for exactly this reason: a timer keyed on "last event received" would have announced a
disconnect during every normal quiet period, making the indicator lie in the opposite direction.

**Why these are constants and not a live stream, and it cost seven minutes to relearn.** The first
version of this file drove `/stream` over `TestClient.stream()` and hung until it was killed -
which `test_chat_endpoints`'s own docstring already warns about: *"the endpoint intentionally never
closes on its own, and `TestClient.stream()` hangs against it"* (D-033). The frames were inline
f-strings inside a closure inside the handler, so there was nothing else to reach. Naming them
(`KEEPALIVE_FRAME`, `data_frame`) is what makes the wire format assertable at all.

**Both apps, from one file.** The two `/stream` endpoints are independent copies of the same shape,
and D-347 ("fixed in one direction") is the finding the 08-16 audit called the finding behind its
findings. chat-api does not depend on learning-api, and a test that imported across that seam would
resolve only because the workspace shares one venv - a worse defect than the asymmetry it guards
(see `test_session_event_relay.test_the_channel_is_namespaced_to_this_app`, corrected for exactly
that). So learning's half is asserted on the text of its own module.
"""

import re
from pathlib import Path

from chat_api.routers.stream import KEEPALIVE_FRAME, data_frame

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LEARNING_STREAM = (
    _REPO_ROOT / "apps" / "learning-api" / "src" / "learning_api" / "routers" / "stream.py"
)


def test_the_keepalive_is_a_named_event_a_client_can_listen_for() -> None:
    """`event: keepalive` is what makes `addEventListener("keepalive", ...)` possible.

    The `data: {}` is not decoration: a frame with an `event:` line and no `data:` line is not
    dispatched at all by the SSE spec's own algorithm, so the payload is what makes the event
    exist. It is inert on purpose - a keepalive carries no state.
    """
    assert KEEPALIVE_FRAME.startswith("event: keepalive\n"), KEEPALIVE_FRAME
    assert re.fullmatch(r"event: keepalive\ndata: \{\}\n\n", KEEPALIVE_FRAME), KEEPALIVE_FRAME
    # Not a comment any more. A comment is invisible to every browser handler, which was the bug.
    assert not KEEPALIVE_FRAME.startswith(":")
    # No `id:`: this must never become a `Last-Event-ID` resume point.
    assert "id:" not in KEEPALIVE_FRAME
    # Terminated by a blank line, or the client buffers it and dispatches nothing.
    assert KEEPALIVE_FRAME.endswith("\n\n")


def test_a_snapshot_frame_stays_unnamed_so_onmessage_still_receives_it() -> None:
    """The regression this change could plausibly have caused, asserted rather than assumed.

    `onmessage` receives only **unnamed** events. Naming the keepalive is safe precisely because
    snapshots are not named - if a later change gave them an `event:` line, every existing client
    would silently stop receiving them: a reloaded chat tab's "Thinking…" would never resolve and
    learning-web's exam screen would stop updating, with no error anywhere.
    """
    frame = data_frame('{"chat_session_id":"abc"}')
    assert frame == 'data: {"chat_session_id":"abc"}\n\n'
    assert "event:" not in frame, "a named snapshot frame would be invisible to onmessage"
    assert frame.endswith("\n\n")


def test_learning_api_emits_the_same_named_keepalive() -> None:
    """The other direction. Read as text for the seam reason in this module's docstring: enough to
    fail loudly if one app is changed and the other is not, without pretending the two are one
    system."""
    source = _LEARNING_STREAM.read_text()
    assert 'KEEPALIVE_FRAME = "event: keepalive\\ndata: {}\\n\\n"' in source, (
        "learning-api no longer emits the same keepalive frame, so a liveness timer would work "
        "in one app and silently misreport in the other - the D-347 shape"
    )
    assert 'yield ": keep-alive\\n\\n"' not in source, "the invisible comment form came back"
    assert "yield KEEPALIVE_FRAME" in source, "the constant exists but is not what gets sent"
