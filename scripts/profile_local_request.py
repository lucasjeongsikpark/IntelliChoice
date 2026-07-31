#!/usr/bin/env python
"""Decompose one learning-api request locally, with the same arithmetic the X-Ray
profiler uses (AUD-F-32; §2.6 criterion 7).

**The question this exists to answer, and why it comes before any optimisation.**
D-132 measured, on staging at 25 concurrent, that a `POST .../answers` request is 836 ms
at the median while only 110 ms of it is SQL and 98 ms of it is inside
`langgraph.submit_answer`. That leaves ~726 ms per answer - ~7.3 s of a ~15 s flow -
which is neither database time nor time in the graph node, and it is now the whole of
criterion 7's remaining latency question. D-132's own lesson was that `select_topic` was
the *biggest span* in the profile and the *wrong target*, because a per-span profile
cannot show which resource is scarce. So the first move here is not to optimise anything.
It is to find out whether that gap is **work** or **waiting**.

**Pre-registered expectation, written before the first run** (D-132's habit, which is the
only reason its own result was legible):

  Staging's task is CPU-saturated at 25 concurrent (ECS CPU peaks 72-96%). If the ~726 ms
  is per-request *work* - middleware depth, JWT verification, checkpoint
  serialisation, Pydantic validation of graph state - then an unloaded local request must
  show the same shape at a smaller magnitude: a clear majority of the request outside SQL
  and outside the node. If instead the local gap is a small fraction of a much smaller
  request, then the staging gap is mostly **event-loop and CPU queueing under
  saturation**, not work that exists to be removed, and the honest fix is capacity or
  concurrency shape rather than a code optimisation. I expect the second, weakly: 25
  concurrent requests on a 2-task service is a lot of contention, and no candidate on
  D-132's list plausibly costs hundreds of milliseconds of CPU on its own.

Either answer is useful and they lead to opposite work, which is what makes it worth
measuring before touching code.

**And one unloaded arm cannot settle it, so `--concurrency` exists.** "The gap is smaller
locally" is also what a slower staging CPU would produce, so the sequential arm alone
cannot separate *work* from *waiting*. The controlled version is to hold everything
constant - same process, same database, same client - and vary only the number of flows in
flight. Per-request work cannot grow with concurrency; queueing must. Both arms are driven
through the identical async client for exactly the reason D-132 had to re-run its first
after arm: an arm measured differently from its control is not a comparison.

**Why the arithmetic is copied from `profile_xray_span.py` rather than reinvented.** That
script exists because a hand-rolled version of the same profile first reported 131% of
wall time in SQL. Here the tree comes from an in-memory OTel exporter rather than X-Ray,
so there is no double-counted-segment problem to correct, but the *definitions* have to
match or the local and staging numbers cannot be compared at all:

  - SQL time counts a statement only if its span is a **descendant of the root** span.
  - The reported "neither SQL nor node" figure is `root - sql_total`, which is exactly how
    D-132's ~726 ms was derived (836.0 - 110.1). A second, stricter figure
    (`root - node - sql_outside_node`) is printed beside it, because that one does not
    double-subtract the SQL the node itself issues, and if the two disagree wildly the
    shape is not what either number suggests.

Structural guards, in the same spirit as this repo's other measuring scripts - three
sessions running, the apparatus was wrong before the finding was:

  1. **Zero profiled requests is a FAIL**, not a clean result. An empty corpus certifying
     an improvement is the false negative that made AUD-F-12 possible.
  2. **SQL time may not exceed the span it sits inside** - the exact check that caught the
     131%.
  3. **A positive control on the instrument**: the run must observe SQL spans, a root
     span, and the node span. A tree missing any of the three would silently report a
     100% gap, which is also what a real finding looks like.
  4. **`--cprofile` is opt-in and reported as a ranking, never as a duration.** cProfile's
     per-call overhead inflates exactly the code this is looking for (many small calls -
     Pydantic, msgpack), so its output can order candidates but cannot size them.

The app is driven in-process over ASGI, so the root span here excludes uvicorn's HTTP
parsing, TLS, the ALB and CloudFront - same as the staging root span, which is also
server-side and also starts when the app receives the request. Two things it does not
model: the local machine's CPU is faster than a Fargate vCPU, and local Postgres shares
that CPU with the app, so at high concurrency the database competes with the process
measuring it. Both push in the same direction and are noted with the results.

Usage (needs `make up && make db-upgrade`; writes to the shared dev Postgres and sweeps
after itself, so do not run it while `make test` is running - they share that database):

    uv run python scripts/profile_local_request.py --flows 2
    uv run python scripts/profile_local_request.py --flows 25 --concurrency 25
    uv run python scripts/profile_local_request.py --flows 1 --cprofile
"""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import importlib.util
import io
import os
import pstats
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Tracing must be decided before `learning_api.main` is imported, because
# `configure_tracing_provider` runs at that module's import time (it has to: Starlette
# caches its middleware stack on the first ASGI call, including "lifespan"). So this one
# flag is read straight from argv rather than through argparse - by the time argparse runs,
# the app is already built and instrumented.
TRACING = "--no-tracing" not in sys.argv
os.environ["LEARNING_OTEL_ENABLED"] = "true" if TRACING else "false"

import intellichoice_observability.tracing as tracing_module  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

MEMORY_EXPORTER = InMemorySpanExporter()


def _in_memory_exporter(*_args: object, **_kwargs: object) -> InMemorySpanExporter:
    """Swaps the OTLP exporter for an in-memory one, keeping everything else - the
    `BatchSpanProcessor`, and the `RedactingSpanExporter` wrapper - exactly as production
    builds it, so the spans measured here went through the same pipeline.
    """
    return MEMORY_EXPORTER


tracing_module.OTLPSpanExporter = _in_memory_exporter  # type: ignore[assignment,misc]

import httpx  # noqa: E402
from intellichoice_adapters.fake_auth import FakeTokenIssuer  # noqa: E402
from intellichoice_adapters.seed.mysql_fixtures import STUDENT_UNLINKED, seed  # noqa: E402
from intellichoice_curriculum.loader import load_curriculum_and_templates  # noqa: E402
from intellichoice_db.engine import (  # noqa: E402
    create_engine,
    create_session_factory,
    session_scope,
)
from intellichoice_db.repositories.questions import QuestionRepository  # noqa: E402
from intellichoice_shared.auth import Audience, Role  # noqa: E402
from learning_api.main import app  # noqa: E402
from opentelemetry.sdk.trace import ReadableSpan  # noqa: E402

MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"
TOPIC_ID = "linear_equations"
ANSWER_PATH_SUFFIX = "/answers"


def _load_test_sweep() -> object:
    """Reuses the learning-api conftest's dependency-ordered DELETE sweep rather than
    copying twenty statements that would then drift. This script writes real rows for the
    fixture student into the shared dev Postgres, exactly as those tests do.
    """
    path = REPO_ROOT / "apps" / "learning-api" / "tests" / "conftest.py"
    spec = importlib.util.spec_from_file_location("_learning_api_conftest", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._sweep  # type: ignore[attr-defined]


@dataclass
class RequestProfile:
    """One `POST .../answers` request, decomposed from its own span tree."""

    root_ms: float
    node_ms: float
    sql_ms: float
    sql_inside_node_ms: float
    statements: int
    span_names: list[str] = field(default_factory=list)

    @property
    def sql_outside_node_ms(self) -> float:
        return self.sql_ms - self.sql_inside_node_ms

    @property
    def gap_xray_style_ms(self) -> float:
        """`root - sql`, which is how D-132's ~726 ms was derived."""
        return self.root_ms - self.sql_ms

    @property
    def gap_strict_ms(self) -> float:
        """`root - node - sql_outside_node`: does not double-subtract the node's own SQL."""
        return self.root_ms - self.node_ms - self.sql_outside_node_ms


def _ms(span: ReadableSpan) -> float:
    assert span.end_time is not None and span.start_time is not None
    return (span.end_time - span.start_time) / 1_000_000


def _is_sql(span: ReadableSpan) -> bool:
    """SQLAlchemy's instrumentation names its spans after the statement's first word and
    sets `db.system`; the attribute is the reliable half, the name is a readability aid.
    """
    return bool((span.attributes or {}).get("db.system"))


def _decompose_trace(spans: list[ReadableSpan]) -> RequestProfile | None:
    """Builds the tree for the one answer request in one trace and measures it.

    Returns None when the trace holds no answer-request root span - a setup call, or the
    graph's own background work. The caller counts those rather than treating them as
    zeros, because "no root span" and "a root span of zero cost" must never be the same
    reading (D-131 §4).
    """
    by_id = {span.context.span_id: span for span in spans if span.context is not None}
    children: dict[int, list[ReadableSpan]] = defaultdict(list)
    roots: list[ReadableSpan] = []
    for span in spans:
        parent = span.parent
        if parent is None or parent.span_id not in by_id:
            roots.append(span)
        else:
            children[parent.span_id].append(span)

    answer_roots = [
        span
        for span in roots
        if span.name.startswith("POST") and span.name.endswith(ANSWER_PATH_SUFFIX)
    ]
    if len(answer_roots) != 1:
        return None
    root = answer_roots[0]

    def descendants(span: ReadableSpan) -> list[ReadableSpan]:
        assert span.context is not None
        out: list[ReadableSpan] = []
        for child in children[span.context.span_id]:
            out.append(child)
            out.extend(descendants(child))
        return out

    under_root = descendants(root)
    sql_spans = [span for span in under_root if _is_sql(span)]
    node_spans = [span for span in under_root if span.name == "langgraph.submit_answer"]
    node_ms = sum(_ms(span) for span in node_spans)
    sql_inside_node = [
        span for node in node_spans for span in descendants(node) if _is_sql(span)
    ]

    return RequestProfile(
        root_ms=_ms(root),
        node_ms=node_ms,
        sql_ms=sum(_ms(span) for span in sql_spans),
        sql_inside_node_ms=sum(_ms(span) for span in sql_inside_node),
        statements=len(sql_spans),
        span_names=sorted({span.name for span in under_root if not _is_sql(span)}),
    )


def _flush_and_take() -> list[ReadableSpan]:
    if not TRACING:
        # With instrumentation off the global provider is OTel's no-op `ProxyTracerProvider`,
        # which has no `force_flush`. Returning empty here is safe *only* because the caller
        # never reports a span table in that mode - see `main`.
        return []
    tracing_module.trace.get_tracer_provider().force_flush()  # type: ignore[attr-defined]
    spans = list(MEMORY_EXPORTER.get_finished_spans())
    MEMORY_EXPORTER.clear()
    return spans


def _profiles_from_spans(spans: list[ReadableSpan]) -> tuple[list[RequestProfile], int]:
    """Groups a whole run's spans by `trace_id` and decomposes each answer request.

    Grouping by trace rather than flushing between requests is what lets the concurrent
    arm be measured by the identical code as the sequential one - with flows in flight at
    the same time there is no quiet moment to flush in. Returns the profiles and the count
    of traces that held no answer root (setup calls), so coverage is printed and not
    assumed.
    """
    by_trace: dict[int, list[ReadableSpan]] = defaultdict(list)
    for span in spans:
        if span.context is not None:
            by_trace[span.context.trace_id].append(span)

    profiles: list[RequestProfile] = []
    skipped = 0
    for trace_spans in by_trace.values():
        profile = _decompose_trace(trace_spans)
        if profile is None:
            skipped += 1
        else:
            profiles.append(profile)
    return profiles, skipped


async def _correct_options(variant_ids: list[str]) -> dict[str, str]:
    """Reads the right answers out of band, on its own engine.

    Its spans land in their own traces and are discarded by `_profiles_from_spans`, so this
    harness query can never be counted as part of a request it is only setting up.
    """
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            repo = QuestionRepository(session)
            out: dict[str, str] = {}
            for variant_id in variant_ids:
                variant = await repo.get_variant(variant_id)
                assert variant is not None
                out[variant_id] = variant.correct_option
            return out
    finally:
        await engine.dispose()


def _seed_fixtures() -> None:
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


async def _run_flow(client: httpx.AsyncClient, headers: dict[str, str]) -> None:
    """Drives one flow to `pre_exam` and answers its ten items, sequentially.

    Sequential *within* a flow and concurrent *across* flows, which is the shape
    `learning_sessions_staging.js` produces: one student never has two answers in flight,
    but twenty-five students do. Emits no measurements of its own - the spans are read
    from the exporter afterwards and grouped by trace.
    """
    create = await client.post("/learning/sessions", headers=headers)
    create.raise_for_status()
    session_id = create.json()["learning_session_id"]

    student = await client.post(
        f"/learning/sessions/{session_id}/student",
        headers=headers,
        json={"student_id": STUDENT_UNLINKED},
    )
    student.raise_for_status()

    topics = await client.post(
        f"/learning/sessions/{session_id}/topics",
        headers=headers,
        json={"topic_id": TOPIC_ID},
    )
    topics.raise_for_status()
    items = topics.json()["items"]
    if len(items) != 10:
        raise SystemExit(f"FAIL: expected a 10-item pre-exam, got {len(items)}")

    correct = await _correct_options([item["question_variant_id"] for item in items])

    for index, item in enumerate(items):
        variant_id = item["question_variant_id"]
        response = await client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"profile-{session_id}-{index}"},
            json={
                "question_variant_id": variant_id,
                "selected_option": correct[variant_id],
                "response_time_ms": 3000 + index * 100,
            },
        )
        response.raise_for_status()


async def _drive(flows: int, concurrency: int, headers: dict[str, str]) -> tuple[float, float]:
    """Runs `flows` flows with at most `concurrency` in flight, through the real app.

    `lifespan_context` is entered by hand because ASGI transports do not run lifespan, and
    everything the request path needs - both engines, the SQLAlchemy instrumentation, the
    graph - is built there.

    Returns `(wall_s, cpu_s)` for the driving window only, so CPU per request can be
    reported. `process_time()` is whole-process CPU, which here includes the httpx client
    and the OTel exporter as well as the app, so it is an **upper bound** on the server's
    own cost - useful because it is measured identically across arms, not because the
    absolute number is clean.
    """
    limit = asyncio.Semaphore(concurrency)

    async def one() -> None:
        async with limit:
            await _run_flow(client, headers)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://profiler", timeout=60.0
        ) as client:
            wall_start, cpu_start = time.perf_counter(), time.process_time()
            await asyncio.gather(*(one() for _ in range(flows)))
            return time.perf_counter() - wall_start, time.process_time() - cpu_start


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _report(profiles: list[RequestProfile], skipped: int, concurrency: int) -> int:
    print(
        f"\n`POST .../answers` decomposed, n={len(profiles)} requests at concurrency "
        f"{concurrency} ({skipped} non-answer traces ignored)\n"
    )
    if not profiles:
        print("FAIL: zero requests profiled - an empty corpus cannot evidence anything.")
        return 1

    # Guard 2: the 131% check.
    invalid = [p for p in profiles if p.sql_ms > p.root_ms + 0.001]
    if invalid:
        print(
            f"INVALID: {len(invalid)} of {len(profiles)} requests report more SQL time than "
            "the request took. The tree is being built wrong; no numbers below are usable."
        )
        return 1

    # Guard 3: positive control on all three legs of the decomposition.
    missing = []
    if not any(p.statements for p in profiles):
        missing.append("no SQL spans")
    if not any(p.node_ms for p in profiles):
        missing.append("no langgraph.submit_answer span")
    if missing:
        print(
            f"FAIL: the instrument is blind - {', '.join(missing)}. A tree missing a leg "
            "reports a 100% gap, which is also what a real finding looks like."
        )
        return 1

    def line(label: str, values: list[float], unit: str = "ms") -> None:
        print(
            f"  {label:<34} median {statistics.median(values):8.1f} {unit}"
            f"   p95 {_percentile(values, 0.95):8.1f} {unit}"
            f"   min {min(values):8.1f}   max {max(values):8.1f}"
        )

    root = [p.root_ms for p in profiles]
    line("whole request (root span)", root)
    line("SQL time inside it", [p.sql_ms for p in profiles])
    line("langgraph.submit_answer span", [p.node_ms for p in profiles])
    line("SQL issued outside the node", [p.sql_outside_node_ms for p in profiles])
    line("neither SQL nor node (root-sql)", [p.gap_xray_style_ms for p in profiles])
    line("  same, not double-subtracted", [p.gap_strict_ms for p in profiles])
    line("SQL statements per request", [float(p.statements) for p in profiles], unit="  ")

    share = statistics.median([p.gap_xray_style_ms for p in profiles]) / statistics.median(root)
    print(f"\n  the gap is {share:6.1%} of the median request here.")
    print("  staging, at 25 concurrent (D-132): 725.9 / 836.0 = 86.8%.")

    other = sorted({name for p in profiles for name in p.span_names})
    print(f"\n  non-SQL spans seen under the root: {', '.join(other) or '(none)'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--flows", type=int, default=2, help="flows of ten answers to run (default 2)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="flows in flight at once (default 1). Vary only this between arms.",
    )
    parser.add_argument(
        "--cprofile",
        action="store_true",
        help="run under cProfile and print a self-time ranking (an ordering, not durations)",
    )
    parser.add_argument(
        "--no-tracing",
        action="store_true",
        help=(
            "disable OTel instrumentation, to price it. Read from argv before this parser "
            "runs, because the app is instrumented at import time. Skips the span table."
        ),
    )
    args = parser.parse_args()

    sweep = _load_test_sweep()
    asyncio.run(sweep())  # type: ignore[operator]
    _seed_fixtures()

    issuer = FakeTokenIssuer()
    token = issuer.issue(sub=STUDENT_UNLINKED, role=Role.STUDENT, audience=Audience.LEARNING)
    headers = {"Authorization": f"Bearer {token}"}

    _flush_and_take()  # discard the seeding's spans
    profiler = cProfile.Profile() if args.cprofile else None
    answers = args.flows * 10
    try:
        if profiler is not None:
            profiler.enable()
        wall_s, cpu_s = asyncio.run(_drive(args.flows, args.concurrency, headers))
        if profiler is not None:
            profiler.disable()

        # Reported first because it is the quantity that decides the whole question: under
        # a CPU-bound single-loop service, latency at N concurrent is roughly N times the
        # CPU each request costs. Wall time per request is what the spans measure; CPU per
        # request is what can actually be reduced.
        print(
            f"\ntracing {'ON' if TRACING else 'OFF'}: {answers} answers in {wall_s:.2f} s wall, "
            f"{cpu_s:.2f} s process CPU"
            f"  ->  {1000 * cpu_s / answers:6.2f} ms CPU per answer request (upper bound)"
        )
        if profiler is not None:
            print("  (under cProfile - inflated; compare only against another cProfile run)")

        if not TRACING:
            print("  span decomposition skipped: --no-tracing produces no spans to read.")
            return 0
        profiles, skipped = _profiles_from_spans(_flush_and_take())
        exit_code = _report(profiles, skipped, args.concurrency)
    finally:
        asyncio.run(sweep())  # type: ignore[operator]

    if profiler is not None:
        # cProfile charges per-call overhead, which lands hardest on precisely the
        # many-small-calls code this is looking for (Pydantic, msgpack). `tottime` (self
        # time) is the useful column; `cumtime` on an async stack is dominated by whatever
        # awaited the event loop. So this orders candidates and does not size them.
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).sort_stats("tottime").print_stats(25)
        print("\n--- cProfile, ranked by self time: an ordering, not durations ---")
        print(stream.getvalue())
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
