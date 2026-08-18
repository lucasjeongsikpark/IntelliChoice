"""Does a chat SSE snapshot reach a stream pinned to a different replica? (D-349)

**The measurement D-334 used, applied to chat.** An SSE connection and the POST that produces
an event are routed independently by the ALB - there is no target-group stickiness - so with
two replicas the publish lands on the connection's replica about half the time. On learning-api
that showed up as a personalized hint arriving in 2 of 4 runs. chat-api had the same in-process
bus until D-349.

Each round: create a session, answer one turn so a checkpoint exists, **open the stream**, then
post a second turn and wait for a frame describing it. Without the relay a round fails whenever
the POST is served by the other task; with it, every round should pass regardless.

Run against a **two-replica** service or the result means nothing - at one task the in-process
bus always works and the run is green for the wrong reason. The script refuses to draw a
conclusion it cannot support:

    AWS_PROFILE=jeongsik-staging-admin aws ecs update-service \\
      --cluster intellichoice-staging --service intellichoice-staging-chat-api --desired-count 2
    CONFIRM_PAID_RUN=1 uv run python scripts/measure_chat_sse_delivery.py

Each round is one real chat turn, so ten rounds is a few cents.
"""

import json
import os
import sys
import threading
import time
import urllib.request

BASE = "https://d222glidpp4azv.cloudfront.net"
ROUNDS = int(os.environ.get("ROUNDS", "10"))
FRAME_TIMEOUT_S = 90.0

FIRST = "What are the Saturday hours?"
SECOND = "Do you offer online tutoring?"


def post(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else b""
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


class StreamWatcher(threading.Thread):
    """Reads the SSE stream and records the `client_turn_id` of every frame it sees.

    A thread rather than async because the whole point is that this connection is opened
    *before* the POST and held across it - the ordering is the measurement.
    """

    def __init__(self, session_id: str) -> None:
        super().__init__(daemon=True)
        self.session_id = session_id
        self.seen: list[str | None] = []
        self.connected = threading.Event()
        self._stop = threading.Event()

    def run(self) -> None:
        try:
            with urllib.request.urlopen(
                f"{BASE}/chat/sessions/{self.session_id}/stream", timeout=FRAME_TIMEOUT_S
            ) as response:
                self.connected.set()
                for raw in response:
                    if self._stop.is_set():
                        return
                    line = raw.decode(errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    try:
                        frame = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    self.seen.append(frame.get("client_turn_id"))
        except Exception:
            self.connected.set()  # unblock the caller; the empty `seen` is the result

    def stop(self) -> None:
        self._stop.set()


def replica_count() -> int | None:
    """Best-effort, so the script can say whether the run means anything."""
    import subprocess

    try:
        out = subprocess.run(
            [
                "aws",
                "ecs",
                "describe-services",
                "--cluster",
                "intellichoice-staging",
                "--services",
                "intellichoice-staging-chat-api",
                "--query",
                "services[0].runningCount",
                "--output",
                "text",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return int(out.stdout.strip())
    except Exception:
        return None


def one_round(index: int) -> bool:
    session_id = post("/chat/sessions")["chat_session_id"]
    post(f"/chat/sessions/{session_id}/messages", {"query": FIRST, "client_turn_id": f"r{index}-a"})

    watcher = StreamWatcher(session_id)
    watcher.start()
    watcher.connected.wait(timeout=30)
    time.sleep(1.0)  # let the initial snapshot land before the POST that matters

    turn_id = f"r{index}-b"
    post(f"/chat/sessions/{session_id}/messages", {"query": SECOND, "client_turn_id": turn_id})

    deadline = time.time() + 30
    while time.time() < deadline:
        if turn_id in watcher.seen:
            watcher.stop()
            return True
        time.sleep(0.5)
    watcher.stop()
    return False


def main() -> None:
    replicas = replica_count()
    delivered = 0
    for index in range(ROUNDS):
        ok = one_round(index)
        delivered += ok
        print(f"round {index + 1:>2}: {'delivered' if ok else 'MISSED'}", flush=True)

    print(f"\nDELIVERY {delivered}/{ROUNDS}   (running replicas: {replicas})")
    if replicas is not None and replicas < 2:
        print(
            "⚠️  one replica - this run cannot distinguish a working relay from an "
            "in-process bus, and proves nothing about D-349."
        )
        sys.exit(2)
    if delivered < ROUNDS:
        sys.exit(1)


if os.environ.get("CONFIRM_PAID_RUN") == "1":
    main()
else:
    print("refusing to spend without CONFIRM_PAID_RUN=1")
