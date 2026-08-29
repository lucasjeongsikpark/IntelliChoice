"""E1.2 staging tier: per-event SSE delivery accounting against the deployed 2-task learning-api.

**The headline this replaces.** The strongest cross-replica evidence in the repository is
D-349's `10 / 10` rounds with a 12/8 POST split - one concurrent session, ten sequential rounds,
on chat-api. It is real evidence and it is small. This drives >= 20 concurrent streams through
CloudFront against learning-api's two real ECS tasks, accounts every event individually, and
re-uses D-349's own method - counting request log lines per **task log stream** - to prove the
load actually crossed both replicas rather than assuming the ALB spread it.

**Refuse-to-conclude, twice.** A run that saw one log stream cannot say anything about
cross-replica delivery no matter how good its delivery rate looks, and neither can a run whose
canary never delivered. Both are hard failures here rather than caveats in a report, which is
the posture `measure_hint_delivery.py` already takes for the same reason.

### Secret handling

The staging `/dev/token` secret is fetched **by this process**, from Secrets Manager, through
`subprocess` with an argument list and no shell - so the only thing on any command line is the
secret's *id*. It is never exported into the environment, never logged, never written to an
artifact, and never included in an exception message. That is D-310's rule, and D-310 exists
because the "pass it as an environment assignment" alternative was measured leaking into four
process-table lines on a live run.

### Cost

Not $0, unlike E1.1. `/stream`'s first connect to a session that has a student but no narrative
fires `pre_intro`, which is one real Bedrock call (`routers/stream.py`, S26/D-075) - idempotent
per session, so exactly one per stream. At 20 streams that is ~20 Haiku 4.5 stage-narrative
calls, single-digit cents. The report states it rather than inheriting E1.1's $0 label.

Usage:
    AWS_PROFILE=jeongsik-staging-admin uv run python \
      benchmarks/resume_evidence/01_platform/sse_scale_staging.py \
      --streams 20 --events-per-stream 12 \
      --out docs/resume_evidence/01_platform/sse_staging_results.json
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import pathlib
import subprocess
import sys
import time
from datetime import UTC, datetime
from typing import Any

import boto3
import httpx

_spec = importlib.util.spec_from_file_location(
    "sse_ledger", pathlib.Path(__file__).with_name("sse_ledger.py")
)
assert _spec and _spec.loader
sse_ledger = importlib.util.module_from_spec(_spec)
sys.modules["sse_ledger"] = sse_ledger
_spec.loader.exec_module(sse_ledger)
StreamLedger = sse_ledger.StreamLedger
aggregate = sse_ledger.aggregate
content_hash = sse_ledger.content_hash

BASE_URL = "https://d35dfnjzmgrm01.cloudfront.net"
SECRET_ID = "intellichoice-staging/learning-api/staging-token-shared-secret"
LOG_GROUP = "/ecs/intellichoice-staging-learning-api"
TOPIC_ID = "linear_equations"
# The two attendance-present staging fixtures (the same pair k6 cycles). Sessions are
# independent, so streams sharing a student is not a confound for delivery accounting.
PRESENT_STUDENTS = ["student-ext-1", "student-ext-4"]


def fetch_secret(profile: str | None) -> str:
    """In-process, argument-list subprocess, no shell. See the module docstring."""
    cmd = ["aws"]
    if profile:
        cmd += ["--profile", profile]
    cmd += [
        "secretsmanager",
        "get-secret-value",
        "--secret-id",
        SECRET_ID,
        "--query",
        "SecretString",
        "--output",
        "text",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        # stderr can echo the command but never the value; still, only the return code is
        # surfaced, so nothing that might carry the secret reaches a log.
        raise SystemExit(f"could not read the staging token secret (aws exit {proc.returncode})")
    secret = proc.stdout.strip()
    if len(secret) < 10:
        raise SystemExit("the token secret came back too short to be real - refusing to run")
    return secret


class StagingStream:
    """One SSE stream through CloudFront, with reconnect.

    CloudFront's read timeout on this distribution is 60 s. `/stream` emits a keepalive every
    15 s (`KEEPALIVE_INTERVAL_S`), so an idle stream should survive - but a reconnect is a
    normal event on the open internet and the accounting has to survive one without lying in
    either direction, hence `record_recovery` in `sse_ledger`.
    """

    def __init__(self, client: httpx.AsyncClient, sid: str, token: str, ledger: StreamLedger):
        self._client = client
        self._sid = sid
        self._token = token
        self.ledger = ledger
        self.frames: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.ready = asyncio.Event()
        self.reconnected = asyncio.Event()
        self.last_initial: dict[str, Any] | None = None
        self._stop = False
        self._task: asyncio.Task | None = None

    async def _run(self) -> None:
        attempt = 0
        while not self._stop:
            try:
                async with self._client.stream(
                    "GET",
                    f"{BASE_URL}/learning/sessions/{self._sid}/stream",
                    params={"token": self._token},
                    timeout=httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0),
                ) as resp:
                    if resp.status_code != 200:
                        self.ledger.stream_errors.append(f"stream status {resp.status_code}")
                        self.ready.set()
                        return
                    first = True
                    async for line in resp.aiter_lines():
                        if self._stop:
                            return
                        if line.startswith("event: keepalive"):
                            self.ledger.keepalives += 1
                            continue
                        if not line.startswith("data:"):
                            continue
                        body = line[5:].strip()
                        if body == "{}":
                            continue
                        try:
                            frame = json.loads(body)
                        except json.JSONDecodeError:
                            self.ledger.stream_errors.append("undecodable frame")
                            continue
                        if first:
                            self.ledger.initial_snapshots += 1
                            if self.ledger.initial_hash is None:
                                self.ledger.initial_hash = content_hash(frame)
                            self.last_initial = frame
                            first = False
                            if attempt == 0:
                                self.ready.set()
                            else:
                                self.reconnected.set()
                            continue
                        await self.frames.put({"at": time.monotonic(), "frame": frame})
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - a dropped stream is data
                self.ledger.stream_errors.append(f"{type(exc).__name__}: {exc}")
            if self._stop:
                return
            if attempt == 0:
                # The *first* connect failed before any frame. `ready` gates the caller, so
                # leaving it clear here would hang session setup for its whole timeout on what
                # is already a known failure. Retrying continues underneath; the caller sees the
                # error it needs to decide with.
                self.ready.set()
            attempt += 1
            self.ledger.reconnects += 1
            self.reconnected.clear()
            await asyncio.sleep(min(2 ** min(attempt, 3), 8))
        self.ready.set()

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def next_frame(self, timeout: float) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self.frames.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def drain(self) -> list[dict[str, Any]]:
        out = []
        while not self.frames.empty():
            out.append(self.frames.get_nowait())
        return out

    async def stop(self) -> None:
        self._stop = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass


async def post_with_retry(
    client: httpx.AsyncClient, method: str, url: str, *, attempts: int = 3, **kw
) -> httpx.Response:
    """`/dev/token` is intermittent through CloudFront (a known edge behaviour, recorded in the
    e2e mechanics). A single 5xx or a reset connection on the token call would otherwise remove
    a whole stream from the measurement, shrinking the concurrency being reported."""
    last: Exception | httpx.Response | None = None
    for i in range(attempts):
        try:
            r = await client.request(method, url, **kw)
            if r.status_code < 500:
                return r
            last = r
        except Exception as exc:  # noqa: BLE001
            last = exc
        await asyncio.sleep(0.5 * (i + 1))
    if isinstance(last, httpx.Response):
        return last
    raise RuntimeError(f"{method} {url.split('?')[0]} failed after {attempts} attempts: {last}")


async def open_session(client: httpx.AsyncClient, secret: str, sub: str) -> tuple[str, str]:
    r = await post_with_retry(
        client,
        "POST",
        f"{BASE_URL}/dev/token",
        headers={"Content-Type": "application/json", "X-Staging-Token-Secret": secret},
        json={"role": "student", "sub": sub},
    )
    if r.status_code != 200:
        # Never echo the body: a 200 body here IS a credential, and a non-200 can quote the
        # request. Only the status code is surfaced.
        raise RuntimeError(f"/dev/token returned {r.status_code}")
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    r = await post_with_retry(client, "POST", f"{BASE_URL}/learning/sessions", headers=h)
    r.raise_for_status()
    sid = r.json()["learning_session_id"]
    # Before the stream: `/stream` 404s on a checkpoint that does not exist yet.
    r = await post_with_retry(
        client,
        "POST",
        f"{BASE_URL}/learning/sessions/{sid}/student",
        headers=h,
        json={"student_id": sub},
    )
    r.raise_for_status()
    return sid, token


async def drive(
    client: httpx.AsyncClient,
    stream: StagingStream,
    sid: str,
    token: str,
    events_target: int,
    event_timeout: float,
) -> None:
    h = {"Authorization": f"Bearer {token}"}

    async def step(
        action: str, method: str, url: str, extra_headers: dict[str, str] | None = None, **kw
    ) -> dict[str, Any] | None:
        issued = time.monotonic()
        resp = await post_with_retry(
            client, method, url, headers={**h, **(extra_headers or {})}, **kw
        )
        if resp.status_code != 200:
            stream.ledger.stream_errors.append(f"{action} -> {resp.status_code}")
            return None
        body = resp.json()
        idx = stream.ledger.record_expected(action, issued, body)
        got = await stream.next_frame(event_timeout)
        if got is not None:
            stream.ledger.record_delivery(idx, got["at"], got["frame"])
        elif stream.ledger.reconnects and stream.last_initial is not None:
            # The push was missed across a reconnect gap; did the reconnect's checkpoint read
            # restore the same state? Only then is it a recovery rather than a loss.
            stream.ledger.record_recovery(idx, time.monotonic(), stream.last_initial)
        return body

    body = await step(
        "select_topic",
        "POST",
        f"{BASE_URL}/learning/sessions/{sid}/topics",
        json={"topic_id": TOPIC_ID},
    )
    if body is None:
        return
    if body.get("phase") == "blocked":
        stream.ledger.stream_errors.append("attendance blocked - fixture is stale")
        return

    seeded = await step("resume_seed", "POST", f"{BASE_URL}/learning/sessions/{sid}/resume")
    items = (seeded or body or {}).get("items") or []

    for item in items:
        if len(stream.ledger.expected) >= events_target:
            break
        # An answer is the one action that needs a per-question `Idempotency-Key`, so it does not
        # go through `step`'s uniform header.
        await step(
            "answer",
            "POST",
            f"{BASE_URL}/learning/sessions/{sid}/answers",
            extra_headers={"Idempotency-Key": f"{sid}-{item['question_variant_id']}"},
            json={
                "question_variant_id": item["question_variant_id"],
                "selected_option": "a",
                "response_time_ms": 1500,
            },
        )
    while len(stream.ledger.expected) < events_target:
        if await step("resume", "POST", f"{BASE_URL}/learning/sessions/{sid}/resume") is None:
            break

    for extra in await stream.drain():
        stream.ledger.record_unmatched(extra["at"], extra["frame"], "no_action_outstanding")


def replica_split(start: datetime, end: datetime, session_ids: list[str]) -> dict[str, Any]:
    """D-349's method: count this run's own request log lines per ECS **task log stream**.

    One log stream per task, so a split across two streams is direct evidence that both replicas
    served traffic - the thing that makes a delivery rate mean something. Counting only lines
    that carry one of *this run's* session ids keeps concurrent traffic (health checks, another
    session's load) out of the denominator.
    """
    logs = boto3.client("logs", region_name="us-east-1")
    counts: dict[str, int] = {}
    matched = 0
    paginator = logs.get_paginator("filter_log_events")
    wanted = set(session_ids)
    for page in paginator.paginate(
        logGroupName=LOG_GROUP,
        startTime=int(start.timestamp() * 1000),
        endTime=int(end.timestamp() * 1000),
        filterPattern='"/learning/sessions/"',
        PaginationConfig={"MaxItems": 20000},
    ):
        for ev in page.get("events", []):
            msg = ev["message"]
            if not any(sid in msg for sid in wanted):
                continue
            task = ev["logStreamName"].rsplit("/", 1)[-1]
            counts[task] = counts.get(task, 0) + 1
            matched += 1
    return {
        "method": "per-task log-stream split over this run's own session ids (D-349's method)",
        "log_group": LOG_GROUP,
        "window_utc": [
            start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        ],
        "requests_per_task": counts,
        "tasks_seen": len(counts),
        "matched_log_lines": matched,
        "conclusive": len(counts) >= 2,
    }


async def run(args: argparse.Namespace, secret: str) -> dict[str, Any]:
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=200)
    started_utc = datetime.now(UTC)
    async with httpx.AsyncClient(timeout=60.0, limits=limits) as c:
        # Canary first: one stream, three events. A rig that cannot deliver one event must not
        # go on to report a number over 240.
        sub = PRESENT_STUDENTS[0]
        sid, token = await open_session(c, secret, sub)
        led = StreamLedger(stream_id=sid, arm="canary")
        canary = StagingStream(c, sid, token, led)
        canary.start()
        await asyncio.wait_for(canary.ready.wait(), timeout=45)
        if led.stream_errors:
            await canary.stop()
            raise SystemExit(f"preflight: stream did not open: {led.stream_errors}")
        await drive(c, canary, sid, token, 3, args.event_timeout)
        await canary.stop()
        csum = led.summary()
        print(f"preflight: canary delivered {csum['delivered']}/{csum['expected']}", flush=True)
        if csum["delivered"] == 0:
            raise SystemExit("preflight: canary delivered nothing - refusing to conclude")

        print(f"opening {args.streams} streams through CloudFront...", flush=True)

        async def prepare(i: int):
            s = PRESENT_STUDENTS[i % len(PRESENT_STUDENTS)]
            sid, token = await open_session(c, secret, s)
            led = StreamLedger(stream_id=sid, arm="staging")
            st = StagingStream(c, sid, token, led)
            st.start()
            await asyncio.wait_for(st.ready.wait(), timeout=60)
            return led, st, sid, token

        prepared = await asyncio.gather(
            *(prepare(i) for i in range(args.streams)), return_exceptions=True
        )
        ledgers: list[StreamLedger] = []
        live = []
        for res in prepared:
            if isinstance(res, BaseException):
                print(f"  stream setup failed: {type(res).__name__}: {res}", flush=True)
                continue
            led, st, sid, token = res
            ledgers.append(led)
            live.append((st, sid, token))
        print(f"  {len(live)}/{args.streams} streams open", flush=True)
        if not live:
            raise SystemExit("no streams opened - refusing to conclude")

        t0 = time.monotonic()
        await asyncio.wait_for(
            asyncio.gather(
                *(
                    drive(c, st, sid, token, args.events_per_stream, args.event_timeout)
                    for st, sid, token in live
                ),
                return_exceptions=True,
            ),
            timeout=args.max_runtime,
        )
        elapsed = time.monotonic() - t0
        for st, _, _ in live:
            await st.stop()
        session_ids = [sid for _, sid, _ in live]

    ended_utc = datetime.now(UTC)
    # Logs land with a short delay; give CloudWatch a moment before reading the split.
    await asyncio.sleep(args.log_settle_seconds)

    result = aggregate(ledgers)
    result["environment"] = (
        "deployed staging through CloudFront, 2x learning-api ECS tasks; simulated load-test "
        "traffic"
    )
    result["config"] = {
        "base_url": BASE_URL,
        "streams_requested": args.streams,
        "streams_open": len(ledgers),
        "events_per_stream_target": args.events_per_stream,
        "event_timeout_s": args.event_timeout,
        "students_cycled": PRESENT_STUDENTS,
    }
    result["window_utc"] = [
        started_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        ended_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ]
    result["drive_seconds"] = elapsed
    result["preflight"] = f"canary delivered {csum['delivered']}/{csum['expected']}"
    result["model_spend_note"] = (
        f"not $0: one `pre_intro` Bedrock call fires on each session's first /stream connect "
        f"(routers/stream.py, S26/D-075), idempotent per session - so <= {len(ledgers) + 1} "
        f"Haiku 4.5 stage-narrative calls for this run."
    )
    result["replica_split"] = replica_split(started_utc, ended_utc, session_ids)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--streams", type=int, default=20)
    ap.add_argument("--events-per-stream", type=int, default=12)
    ap.add_argument("--event-timeout", type=float, default=25.0)
    ap.add_argument("--max-runtime", type=float, default=780.0, help="hard cap, seconds")
    ap.add_argument("--log-settle-seconds", type=float, default=20.0)
    ap.add_argument("--aws-profile", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import os

    secret = fetch_secret(args.aws_profile or os.environ.get("AWS_PROFILE"))
    result = asyncio.run(run(args, secret))
    del secret

    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(result, fh, indent=2)

    t = result["total"]
    rs = result["replica_split"]
    print()
    print("=== E1.2 staging tier ===")
    print(f"streams              : {t['streams']}")
    print(f"expected deliveries  : {t['expected']}")
    print(
        f"delivered (pushed)   : {t['delivery_fraction']} ({(t['delivery_rate'] or 0) * 100:.2f}%)"
    )
    print(
        f"recovered on reconnect: {t['recovered_on_reconnect']}   "
        f"state convergence: {t['state_convergence_fraction']}"
    )
    print(f"lost                 : {t['lost']} (streams with any loss: {t['streams_with_loss']})")
    print(f"unmatched/duplicate  : {t['unmatched_frames']}")
    print(f"reconnects           : {t['reconnects']} (counted separately from losses)")
    print(f"keepalives           : {t['keepalives']}")
    print(
        f"ordering             : {t['out_of_order']} out of order at "
        f"{t['ordering_decidable_transitions']} content-decidable transitions "
        f"({t['ordering_transition_agreements']} agreed)"
    )
    lat = t["latency_ms"]
    if lat["n"]:
        print(
            f"delivery latency ms  : p50={lat['p50']:.1f} p95={lat['p95']:.1f} "
            f"p99={lat['p99']:.1f} max={lat['max']:.1f}"
        )
    print(f"replica split        : {rs['requests_per_task']} across {rs['tasks_seen']} task(s)")
    print(f"wrote {args.out}")

    verdict = t["expected"] >= 200 and t["lost"] == 0 and rs["conclusive"]
    if not rs["conclusive"]:
        print(
            "RESULT=INCONCLUSIVE - traffic was seen on fewer than two task log streams, so "
            "this run cannot speak to cross-replica delivery no matter its delivery rate"
        )
    else:
        print(
            f"RESULT={'PASS' if verdict else 'REVIEW'} "
            f"(target: >=200 expected deliveries, 0 lost, >=2 task streams)"
        )
    sys.exit(0 if verdict else 1)


if __name__ == "__main__":
    main()
