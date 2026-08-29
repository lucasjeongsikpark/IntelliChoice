"""E1.2 local tier: cross-process SSE delivery at scale, on two real uvicorn processes.

**What makes this different from every SSE measurement already in the repository.**
`load-tests/sse_load.py` opens 150 streams against *one* process and asks whether each got its
first frame. The D-335/D-349 relay probes drive ~1 concurrent session for 10 sequential rounds.
Neither exercises the regime the relay actually lives in: many sessions publishing at once,
through **one** `asyncpg` publisher connection per process, to streams held on a *different*
process. That regime is where D-395 found four of five events in a burst being lost to
`another operation is in progress` - a defect a first-frame counter cannot see.

So: two real uvicorn `learning_api` processes against the one docker-compose Postgres. Two
processes, not two `SessionEventBus` objects in one - a simulated replica pair proves nothing
about `LISTEN`/`NOTIFY`, which is the whole mechanism under test (D-349 says so in as many
words). Each session's stream is held on one process while its actions are POSTed to the other,
so **every** credited delivery had to cross a real Postgres notification.

**The control arm is load-bearing.** `--cross-fraction` leaves some sessions POSTing to the
same process that holds their stream. Those deliveries take `deliver_local` and never touch the
relay. If both arms fail, the bus is broken; if only the cross arm fails, the relay is. Without
the control, a rig misconfiguration (both ports pointing at one process) reports a perfect score
for the wrong reason.

**Preflight refuses to conclude.** Before the run, one canary session proves cross-process
delivery works at all and that the two ports are genuinely different processes. A run that
reported `0/1000` because the second uvicorn never booted would look exactly like a catastrophic
product finding, and this is the same refuse-at-one-replica posture `measure_hint_delivery.py`
already takes.

### Setup

    docker compose up -d postgres mysql
    uv run python load-tests/loadtest_fixtures.py --count 80     # or --seed-fixtures below
    uv run uvicorn learning_api.main:app --port 8101 &
    uv run uvicorn learning_api.main:app --port 8102 &
    uv run python benchmarks/resume_evidence/01_platform/sse_scale_local.py \
      --sessions 50 --events-per-session 22 \
      --out docs/resume_evidence/01_platform/sse_local_results.json

**Never run this while `make test` is running** - they share the dev Postgres, and the
interference reads as a regression in whichever one you look at second.
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
from typing import Any

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

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
TOPIC_ID = "linear_equations"


class StreamReader:
    """Holds one SSE connection and hands frames to the driver one at a time.

    A queue rather than a callback because the driver's contract is *await the frame for the
    action I just issued*: with at most one action outstanding per stream, `next_frame` returning
    the queue head is an unambiguous credit (rule 2 in `sse_ledger`).
    """

    def __init__(self, client: httpx.AsyncClient, url: str, token: str, ledger: StreamLedger):
        self._client = client
        self._url = url
        self._token = token
        self.ledger = ledger
        self.frames: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.ready = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def _run(self) -> None:
        try:
            async with self._client.stream(
                "GET", self._url, params={"token": self._token}, timeout=None
            ) as resp:
                if resp.status_code != 200:
                    self.ledger.stream_errors.append(f"stream status {resp.status_code}")
                    self.ready.set()
                    return
                first = True
                async for line in resp.aiter_lines():
                    if line.startswith("event: keepalive"):
                        self.ledger.keepalives += 1
                        continue
                    if not line.startswith("data:"):
                        continue
                    body = line[5:].strip()
                    if body == "{}":  # the keepalive frame's own data line
                        continue
                    try:
                        frame = json.loads(body)
                    except json.JSONDecodeError:
                        self.ledger.stream_errors.append("undecodable frame")
                        continue
                    if first:
                        # Never a delivery - see rule 1 in `sse_ledger`.
                        self.ledger.initial_snapshots += 1
                        if self.ledger.initial_hash is None:
                            self.ledger.initial_hash = sse_ledger.content_hash(frame)
                        first = False
                        self.ready.set()
                        continue
                    await self.frames.put({"at": time.monotonic(), "frame": frame})
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a dropped stream is data, not a crash
            self.ledger.stream_errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            self.ready.set()

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def next_frame(self, timeout: float) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self.frames.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def drain(self) -> list[dict[str, Any]]:
        """Whatever arrived after the last credited action - duplicates land here."""
        out = []
        while not self.frames.empty():
            out.append(self.frames.get_nowait())
        return out

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass


async def mint(client: httpx.AsyncClient, base: str, sub: str) -> str:
    r = await client.post(
        f"{base}/dev/token", json={"role": "student", "sub": sub, "audience": "learning"}
    )
    r.raise_for_status()
    return r.json()["token"]


async def open_session(client: httpx.AsyncClient, post_base: str, sub: str, token: str) -> str:
    """Create the session AND select the student before the stream is opened.

    Not an optimization - a requirement. `/stream` reads the checkpoint via `graph.aget_state`
    and 404s when it is empty, and a bare `POST /learning/sessions` writes no checkpoint. The
    first version of this harness connected immediately after create and measured 0 frames on
    every stream, which reads exactly like a dead relay.
    """
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post(f"{post_base}/learning/sessions", headers=h)
    r.raise_for_status()
    sid = r.json()["learning_session_id"]
    r = await client.post(
        f"{post_base}/learning/sessions/{sid}/student", headers=h, json={"student_id": sub}
    )
    r.raise_for_status()
    return sid


async def drive_stream(
    client: httpx.AsyncClient,
    reader: StreamReader,
    post_base: str,
    sid: str,
    token: str,
    events_target: int,
    event_timeout: float,
) -> None:
    """Issue publishing actions one at a time, awaiting each one's frame.

    The action sequence is chosen for two properties: every step publishes a snapshot
    (`_publish_snapshot` in `routers/sessions.py`), and none of them costs a model call - the
    pre-exam is SPEC §5.0's deterministic core, and `pre_intro` fires only on the *first*
    connect of a session with no student, which `open_session` has already passed.
    `/resume` re-serves the checkpoint and publishes, so it is the cheap repeatable event
    source that takes a session past the 12 events its exam alone provides.
    """
    h = {"Authorization": f"Bearer {token}"}

    async def step(action: str, coro) -> bool:
        issued = time.monotonic()
        resp = await coro
        if resp.status_code != 200:
            reader.ledger.stream_errors.append(f"{action} -> {resp.status_code}")
            return False
        idx = reader.ledger.record_expected(action, issued, resp.json())
        got = await reader.next_frame(event_timeout)
        if got is not None:
            reader.ledger.record_delivery(idx, got["at"], got["frame"])
        return True

    ok = await step(
        "select_topic",
        client.post(
            f"{post_base}/learning/sessions/{sid}/topics", headers=h, json={"topic_id": TOPIC_ID}
        ),
    )
    if not ok:
        return
    # Re-read the items from the checkpoint rather than the response we already consumed.
    state = await client.post(f"{post_base}/learning/sessions/{sid}/resume", headers=h)
    items = (state.json() or {}).get("items") or []
    if state.status_code == 200:
        idx = reader.ledger.record_expected("resume_seed", time.monotonic(), state.json())
        got = await reader.next_frame(event_timeout)
        if got is not None:
            reader.ledger.record_delivery(idx, got["at"], got["frame"])

    for item in items:
        if len(reader.ledger.expected) >= events_target:
            break
        await step(
            "answer",
            client.post(
                f"{post_base}/learning/sessions/{sid}/answers",
                headers={**h, "Idempotency-Key": f"{sid}-{item['question_variant_id']}"},
                json={
                    "question_variant_id": item["question_variant_id"],
                    "selected_option": "a",
                    "response_time_ms": 1500,
                },
            ),
        )
    # **One deliberately different event per stream, and it is load-bearing.**
    #
    # Every pre-exam event this flow produces serializes to byte-identical JSON: an answer whose
    # correctness is masked (D-064) changes no snapshot field, so `select_topic` and all ten
    # answers publish the same object. That makes reordering *unobservable* - not absent, just
    # invisible - and `sse_ledger` refuses to print a reassuring `out_of_order: 0` over frames
    # carrying no ordering information.
    #
    # `finalize_exam` moves the session to `study`, so its snapshot differs from every other
    # event on the stream and from every event after it. One content-decidable event per stream
    # is a small ordering claim, but it is a real one, and it costs nothing here: the local rig
    # runs `MockBedrockProvider`, so the narrative this turn may generate is free.
    if len(reader.ledger.expected) < events_target:
        await step(
            "finalize_exam",
            client.post(f"{post_base}/learning/sessions/{sid}/exam/finalize", headers=h, json={}),
        )
    while len(reader.ledger.expected) < events_target:
        if not await step(
            "resume", client.post(f"{post_base}/learning/sessions/{sid}/resume", headers=h)
        ):
            break

    # Anything still queued after the last awaited action had no action outstanding: a duplicate
    # frame, or an echo the relay's origin guard failed to drop.
    for extra in await reader.drain():
        reader.ledger.record_unmatched(extra["at"], extra["frame"], "no_action_outstanding")


async def background_load(
    stop: asyncio.Event, bases: list[str], workers: int, subs: list[str], stats: dict[str, int]
) -> None:
    """Concurrent request load on both processes while deliveries are being accounted.

    The point is not the load's own latency (E1.1 measures that on real infrastructure) - it is
    that the relay's single publisher connection and the SSE hold are contending with ordinary
    request traffic, which is the condition MEASUREMENT_PLAN Theme 1 weakness (3) names as
    never having been tested.
    """

    async def worker(n: int) -> None:
        async with httpx.AsyncClient(timeout=30.0) as c:
            i = 0
            while not stop.is_set():
                base = bases[(n + i) % len(bases)]
                sub = subs[(n + i) % len(subs)]
                try:
                    token = await mint(c, base, sub)
                    h = {"Authorization": f"Bearer {token}"}
                    sid = (await c.post(f"{base}/learning/sessions", headers=h)).json()[
                        "learning_session_id"
                    ]
                    await c.post(
                        f"{base}/learning/sessions/{sid}/student",
                        headers=h,
                        json={"student_id": sub},
                    )
                    r = await c.post(
                        f"{base}/learning/sessions/{sid}/topics",
                        headers=h,
                        json={"topic_id": TOPIC_ID},
                    )
                    stats["requests"] += 3
                    for item in (r.json() or {}).get("items", [])[:4]:
                        if stop.is_set():
                            break
                        key = f"{sid}-{item['question_variant_id']}"
                        await c.post(
                            f"{base}/learning/sessions/{sid}/answers",
                            headers={**h, "Idempotency-Key": key},
                            json={
                                "question_variant_id": item["question_variant_id"],
                                "selected_option": "a",
                                "response_time_ms": 1200,
                            },
                        )
                        stats["requests"] += 1
                    stats["flows"] += 1
                except Exception:  # noqa: BLE001
                    stats["errors"] += 1
                i += 1

    await asyncio.gather(*(worker(n) for n in range(workers)))


async def canary(port_a: str, port_b: str, sub: str, event_timeout: float) -> tuple[bool, str]:
    """One cross-process session, before the real run. Refuses to conclude if the rig is wrong."""
    async with httpx.AsyncClient(timeout=30.0) as c:
        try:
            token = await mint(c, port_a, sub)
            sid = await open_session(c, port_b, sub, token)
        except Exception as exc:  # noqa: BLE001
            return False, f"could not create a session: {type(exc).__name__}: {exc}"
        led = StreamLedger(stream_id="canary", arm="cross")
        reader = StreamReader(c, f"{port_a}/learning/sessions/{sid}/stream", token, led)
        reader.start()
        await asyncio.wait_for(reader.ready.wait(), timeout=20)
        if led.stream_errors:
            await reader.stop()
            return False, f"stream did not open: {led.stream_errors}"
        await drive_stream(c, reader, port_b, sid, token, 3, event_timeout)
        await reader.stop()
        s = led.summary()
        if s["delivered"] == 0:
            return False, (
                f"cross-process canary delivered {s['delivered']}/{s['expected']} - the rig is "
                "not proving anything; check that both ports are separate processes and that "
                "both logged session_event_relay_started"
            )
        return True, f"cross-process canary delivered {s['delivered']}/{s['expected']}"


async def run(args: argparse.Namespace) -> dict[str, Any]:
    port_a = f"http://localhost:{args.port_a}"
    port_b = f"http://localhost:{args.port_b}"
    subs = [f"loadtest-student-{i + 1}" for i in range(args.sessions + args.background_workers)]

    ok, message = await canary(port_a, port_b, subs[0], args.event_timeout)
    print(f"preflight: {message}", flush=True)
    if not ok:
        raise SystemExit(2)

    ledgers: list[StreamLedger] = []
    readers: list[StreamReader] = []
    n_cross = int(round(args.sessions * args.cross_fraction))

    async with httpx.AsyncClient(timeout=60.0, limits=httpx.Limits(max_connections=400)) as c:
        print(
            f"opening {args.sessions} sessions ({n_cross} cross-process, "
            f"{args.sessions - n_cross} same-process control)...",
            flush=True,
        )
        setups = []
        for i in range(args.sessions):
            arm = "cross" if i < n_cross else "same"
            stream_base = port_a if i % 2 == 0 else port_b
            post_base = (
                (port_b if stream_base == port_a else port_a) if arm == "cross" else stream_base
            )
            setups.append((i, arm, stream_base, post_base, subs[i]))

        async def prepare(entry):
            i, arm, stream_base, post_base, sub = entry
            token = await mint(c, post_base, sub)
            sid = await open_session(c, post_base, sub, token)
            led = StreamLedger(stream_id=sid, arm=arm)
            reader = StreamReader(c, f"{stream_base}/learning/sessions/{sid}/stream", token, led)
            reader.start()
            await asyncio.wait_for(reader.ready.wait(), timeout=30)
            return led, reader, post_base, sid, token

        prepared = await asyncio.gather(*(prepare(e) for e in setups), return_exceptions=True)
        live = []
        for res in prepared:
            if isinstance(res, BaseException):
                print(f"  session setup failed: {type(res).__name__}: {res}", flush=True)
                continue
            led, reader, post_base, sid, token = res
            ledgers.append(led)
            readers.append(reader)
            live.append((reader, post_base, sid, token))
        print(f"  {len(live)}/{args.sessions} streams open", flush=True)

        stop = asyncio.Event()
        load_stats = {"flows": 0, "requests": 0, "errors": 0}
        load_task = asyncio.create_task(
            background_load(
                stop,
                [port_a, port_b],
                args.background_workers,
                subs[args.sessions :] or subs,
                load_stats,
            )
        )
        await asyncio.sleep(2)  # let the background load actually be running

        started = time.monotonic()
        print(
            f"driving >= {args.events_per_session} events per stream under "
            f"{args.background_workers} background load workers...",
            flush=True,
        )
        await asyncio.gather(
            *(
                drive_stream(
                    c, reader, post_base, sid, token, args.events_per_session, args.event_timeout
                )
                for reader, post_base, sid, token in live
            ),
            return_exceptions=True,
        )
        elapsed = time.monotonic() - started

        stop.set()
        load_task.cancel()
        try:
            await load_task
        except (asyncio.CancelledError, Exception):
            pass
        for reader in readers:
            await reader.stop()

    result = aggregate(ledgers)
    result["environment"] = "local 2-process rig (two uvicorn learning_api processes, one "
    result["environment"] += "docker-compose Postgres)"
    result["config"] = {
        "sessions_requested": args.sessions,
        "streams_open": len(ledgers),
        "events_per_session_target": args.events_per_session,
        "cross_fraction": args.cross_fraction,
        "port_a": args.port_a,
        "port_b": args.port_b,
        "event_timeout_s": args.event_timeout,
        "background_workers": args.background_workers,
    }
    result["background_load"] = {**load_stats, "concurrent_with_delivery": True}
    result["drive_seconds"] = elapsed
    result["preflight"] = message
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sessions", type=int, default=50)
    ap.add_argument("--events-per-session", type=int, default=22)
    ap.add_argument("--port-a", type=int, default=8101)
    ap.add_argument("--port-b", type=int, default=8102)
    ap.add_argument(
        "--cross-fraction",
        type=float,
        default=0.5,
        help="fraction of streams whose actions are POSTed to the OTHER process; the remainder "
        "is the same-process control arm",
    )
    ap.add_argument("--background-workers", type=int, default=20)
    ap.add_argument("--event-timeout", type=float, default=15.0)
    ap.add_argument(
        "--seed-fixtures",
        action="store_true",
        help="run load-tests/loadtest_fixtures.py first (local docker MySQL only)",
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.seed_fixtures:
        count = args.sessions + args.background_workers + 4
        print(f"seeding {count} loadtest students...", flush=True)
        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "load-tests" / "loadtest_fixtures.py"),
                "--count",
                str(count),
            ],
            check=True,
            cwd=REPO_ROOT,
        )

    result = asyncio.run(run(args))
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(result, fh, indent=2)

    t = result["total"]
    print()
    print("=== E1.2 local tier ===")
    print(f"streams              : {t['streams']}")
    print(f"expected deliveries  : {t['expected']}")
    print(
        f"delivered            : {t['delivery_fraction']} ({(t['delivery_rate'] or 0) * 100:.2f}%)"
    )
    print(f"lost                 : {t['lost']} (streams with any loss: {t['streams_with_loss']})")
    print(f"unmatched/duplicate  : {t['unmatched_frames']}")
    print(f"initial snapshots    : {t['initial_snapshots']} (not counted as deliveries)")
    print(f"keepalives           : {t['keepalives']}   reconnects: {t['reconnects']}")
    print(
        f"ordering             : {t['out_of_order']} out of order at "
        f"{t['ordering_decidable_transitions']} content-decidable transitions "
        f"({t['ordering_transition_agreements']} agreed)"
    )
    lat = t["latency_ms"]
    print(
        f"delivery latency ms  : p50={lat['p50']:.1f} p95={lat['p95']:.1f} "
        f"p99={lat['p99']:.1f} max={lat['max']:.1f}"
        if lat["n"]
        else "delivery latency: n/a"
    )
    for arm, a in result["by_arm"].items():
        print(
            f"  arm={arm:6s} {a['delivery_fraction']} "
            f"({(a['delivery_rate'] or 0) * 100:.2f}%)  lost={a['lost']}"
        )
    bl = result["background_load"]
    print(
        f"background load      : {bl['flows']} flows / {bl['requests']} requests "
        f"/ {bl['errors']} errors, concurrent with delivery"
    )
    print(f"wrote {args.out}")

    verdict = t["expected"] >= 1000 and t["lost"] == 0 and t["unmatched_frames"] == 0
    print(
        f"RESULT={'PASS' if verdict else 'REVIEW'} "
        f"(target: >=1000 expected deliveries, 0 lost, 0 unmatched)"
    )
    sys.exit(0 if verdict else 1)


if __name__ == "__main__":
    main()
