#!/usr/bin/env python
"""Price one additional SQL statement, in CPU, through this app's real stack.

**Why this exists, and why it is a separate script from `profile_local_request.py`.**
D-134 §8 left one named successor target for criterion 7's latency work: a
`POST .../answers` request issues **19 SQL statements** (identical count locally and on
staging), each of which costs "SQLAlchemy compilation, a round-trip and a span", so
batching `submit_answer` the way AUD-F-31 batched `select_topic` (47 -> 7) has a *CPU*
rationale exactly where D-132 showed the *latency* rationale was empty. It also said, in
the same breath, that **nobody has measured CPU as a function of statement count** and
that the work should be sized before it is done. That is this script's whole job.

`profile_local_request.py` cannot answer it. It decomposes a request into root / node /
SQL, which prices the statements *as a group and as wall time*. What a batching decision
needs is the **marginal** cost of the statements it would remove, in **CPU**, because
D-134 §6 established that the constraint on staging is CPU at saturation and that
capacity is set by CPU per request.

**The methodological point that makes this measurable at all: report the slope, never a
total divided by a count.** A request's CPU includes work batching cannot remove -
middleware, JWT verification, checkpoint serialisation, Pydantic validation of graph
state. Dividing 20 ms by 19 statements would attribute all of that to statements and
overstate the saving. So this runs the *same* statement shape at several counts and fits
a line: the **slope** is what one more statement costs, and the **intercept** is the
fixed cost that a batch still pays. Only the slope may be multiplied by "statements
removed".

**Arms.** Two shapes, and tracing priced separately:

  - `orm_select` - one small indexed SELECT returning one hydrated ORM row, which is the
    shape the answer path actually issues. Executed via `session.execute(select(...))`,
    never `Session.get`: `get` can answer from the identity map (see
    `QuestionRepository.get_variants`' docstring, which is AUD-F-31's own note on this),
    and a benchmark that silently stops emitting SQL would report a statement as free.
  - `raw_select_1` - `SELECT 1`, a floor: connection checkout, protocol round-trip,
    result handling and a span, with no ORM hydration and no cache-key work.

Run twice, once with `--no-tracing`, to split the span's share out of the slope. D-134 §8
already priced *all* OTel instrumentation at ~2.8 of ~20 ms CPU per answer request
(~14%); this says how much of that belongs to the SQL spans specifically, which is the
part batching removes for free alongside the statements.

**Pre-registered expectation, written before the first run** (D-132/D-134's habit, and the
only reason D-134's own wrong prediction was legible):

  1. The fit is near-linear at concurrency 1 - R^2 > 0.98. Per-statement work is additive
     when nothing is queueing; if it is not linear, something in the loop is not what I
     think it is and no slope should be quoted.
  2. **The marginal traced cost of `orm_select` is 0.15-0.45 ms of CPU.** Reasoning: the
     ~2.8 ms of OTel across ~29 spans per request puts a span near ~0.1 ms, and the
     round-trip plus hydration plus cache-key work should be of the same order or a
     little more.
  3. Therefore 19 statements are **~3-8 ms of the measured ~17.5-20.6 ms CPU per answer
     request**, and a batching change that removes ~12 of them saves **~2-5 ms, i.e.
     10-25% of request CPU** - the same order as the OTel lever and not a factor of two.
  4. **One part of D-134's wording is expected to be wrong, and this is the falsifiable
     half:** SQLAlchemy caches compiled statements per process, so the 19 statements do
     **not** each pay compilation - only cache-key construction. If so, the batching
     saving is smaller than "compilation + round-trip + span" suggests, and the reason to
     say so is that it is the sentence a future session would otherwise plan against.

If (2) lands low - say under 0.1 ms - the finding is that batching `submit_answer` is not
worth doing, and that is a result, not a failure: it closes the last named latency lead
by measurement rather than by attempting it. D-134 §2 refuted its own candidate list the
same way.

**What it measured, 2026-07-31 (D-136). The expectation above was right about the price and
wrong about the quantity, and the quantity is what decided it.**

  | shape | traced | untraced | the span's share |
  |---|---|---|---|
  | `orm_select` | **225-236 us** | 176 us | ~50 us |
  | `raw_select_1` | 136-142 us | 96 us | ~47 us |

Expectations (1) and (2) both held: R^2 >= 0.999 in every arm, and 225-236 us sits inside
the pre-registered 0.15-0.45 ms. The span costs ~48 us and costs the *same* in both shapes,
which is the internal cross-check that the ON/OFF split is real rather than drift.

Then `profile_local_request.py --statements` priced the other factor and the lead died:
the answer path's **19** is **17 statements plus 2 `connect` spans**, only **4** of the 17
are the same statement issued twice, and 1 of them is against the org's MySQL rather than
Postgres. So an identical-statement batch saves **4 x 236 us ~= 0.9 ms of a ~20 ms request,
about 4.6%** - a third of the OTel lever that was already judged not worth taking, and
inside the run-to-run spread of the arms that measured it.

**So: do not batch `submit_answer`.** Expectation (3) predicted 10-25% and that was the
prediction's error - it multiplied a well-estimated price by a quantity borrowed from
AUD-F-31's `select_topic` (47 -> 7), a path whose 47 statements really were one lookup in a
loop. This path is 14 distinct statements doing 14 different things. **The transferable
lesson is that "N statements" is not a unit of waste**, and the two paths differ in the
only property that mattered.

Expectation (4) is **not settled by this run** and should not be quoted as if it were. The
slope here is a compiled-cache *hit*, which is the right cost for a warm process serving
requests continuously - but this measures one statement shape repeatedly, so it cannot say
what the 14 distinct statements cost on a cold process. The claim "the 19 statements do not
each pay compilation" remains an inference from SQLAlchemy's documented cache, not a
measurement made here.

**Scope, stated because it bounds the conclusion.** This prices *reads*. `submit_answer`'s
19 statements include writes (the attempt INSERT, the mastery UPDATE, LangGraph's
checkpoint writes on their own psycopg pool), which are more expensive per statement and
are batched by a different change. So the slope here is the input for the read half, and a
saving computed from it is a **lower bound** on what batching the whole path could return.
Also: this machine's CPU is faster than a Fargate vCPU and local Postgres shares it with
this process, exactly as `profile_local_request.py` notes - so absolute milliseconds are
this laptop's, while the *ratio* to a same-machine request measurement is what transfers.

Structural guards, in this repo's established style - the apparatus has been wrong before
the finding was, six sessions running:

  1. **The ORM arm must return a real row every time.** A `None` result skips hydration
     and would price a cheaper statement than the app issues.
  2. **The traced arm must record exactly one span per statement.** If the count
     disagrees, the instrument is not pricing what it claims to; a benchmark whose spans
     were silently dropped reports tracing as free.
  3. **R^2 below 0.98 is a FAIL, not a caveat.** A slope fitted to a non-linear cloud is
     a number with no referent.
  4. **The intercept is printed beside the slope**, because a large intercept is the
     signal that the loop is measuring setup rather than statements.
  5. Repeats are medianed, and the repeat spread is printed - a slope from single runs
     cannot be told apart from noise.

Usage (needs `make up && make db-upgrade` and a loaded curriculum; reads only, but it
shares the dev Postgres, so do not run it while `make test` runs):

    uv run python scripts/size_statement_cpu.py
    uv run python scripts/size_statement_cpu.py --no-tracing
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Same reason as `profile_local_request.py`: the decision has to be made before the
# tracing module is imported and the SQLAlchemy instrumentor (a process-wide singleton)
# is attached, so it is read from argv rather than through argparse.
TRACING = "--no-tracing" not in sys.argv
os.environ["LEARNING_OTEL_ENABLED"] = "true" if TRACING else "false"

from intellichoice_db.engine import create_engine, create_session_factory  # noqa: E402
from intellichoice_db.models.questions import QuestionVariant  # noqa: E402
from intellichoice_observability.tracing import (  # noqa: E402
    RedactingSpanExporter,
    instrument_sqlalchemy_engines,
)
from opentelemetry.sdk.resources import SERVICE_NAME, Resource  # noqa: E402
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)
from sqlalchemy import select, text  # noqa: E402

MEMORY_EXPORTER = InMemorySpanExporter()

# The counts the line is fitted through. Spread over an order of magnitude so the slope is
# not an artifact of one scale, and starting above zero because the first execution of a
# statement shape pays compilation that every later one does not (expectation 4).
COUNTS = (100, 300, 600, 1000)
REPEATS = 5

# Measured by `profile_local_request.py --flows 1 --statements`, not assumed. The answer
# path's "19 statements" is 17 statements plus 2 `connect` spans (pool checkouts, which
# SQLAlchemy's instrumentation also tags with `db.system`), and of the 17 only 4 are the
# same statement issued more than once - the only kind an identical-statement batch can
# remove. 14 of the 19 spans are distinct, one of them is against the org's MySQL rather
# than Postgres, and two are SAVEPOINT/RELEASE. Re-measure these if the path changes.
REAL_STATEMENTS = 17
REMOVABLE_STATEMENTS = 4
# D-134 §8's paired local arms: 20.24/20.57 ms traced, 17.55/17.48 ms untraced, CPU per
# answer request. Measured on this same machine, which is why the ratio below is legitimate.
REQUEST_CPU_MS = 20.4


@dataclass
class Fit:
    """A least-squares line through (statement count, CPU ms), plus its own quality."""

    slope_ms: float
    intercept_ms: float
    r_squared: float
    spread_ms: dict[int, float]

    @property
    def usable(self) -> bool:
        return self.r_squared >= 0.98


def _fit(points: list[tuple[int, float]]) -> tuple[float, float, float]:
    """Ordinary least squares, written out rather than pulled in: four points and one
    dependency avoided. Returns `(slope, intercept, r_squared)`.
    """
    mean_x = statistics.mean(x for x, _ in points)
    mean_y = statistics.mean(y for _, y in points)
    sxx = sum((x - mean_x) ** 2 for x, _ in points)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in points)
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    residual = sum((y - (slope * x + intercept)) ** 2 for x, y in points)
    total = sum((y - mean_y) ** 2 for _, y in points)
    r_squared = 1.0 if total == 0 else 1.0 - residual / total
    return slope, intercept, r_squared


async def _variant_ids(session_factory: object, wanted: int) -> list[str]:
    """Real seeded ids, so the ORM arm hydrates a real row (guard 1). Cycled rather than
    repeated on one id: a single id would let the row be served from Postgres' own cache
    in a way the app's varied access pattern does not.
    """
    async with session_factory() as session:  # type: ignore[operator]
        result = await session.execute(select(QuestionVariant.question_variant_id).limit(wanted))
        return [row[0] for row in result.all()]


async def _run_orm(session_factory: object, ids: list[str], count: int) -> int:
    """`count` single-row indexed SELECTs in one session, as one request would.

    Returns the number of rows actually hydrated, which the caller asserts against
    `count` (guard 1).
    """
    hydrated = 0
    async with session_factory() as session:  # type: ignore[operator]
        for index in range(count):
            variant_id = ids[index % len(ids)]
            result = await session.execute(
                select(QuestionVariant).where(QuestionVariant.question_variant_id == variant_id)
            )
            if result.scalars().first() is not None:
                hydrated += 1
            # The identity map would answer the *next* iteration for the same id without
            # SQL. Expunging keeps every iteration a real statement, which is the thing
            # being priced.
            session.expunge_all()
    return hydrated


async def _run_raw(session_factory: object, _ids: list[str], count: int) -> int:
    """`count` × `SELECT 1`: the floor - round-trip and span, no ORM."""
    seen = 0
    async with session_factory() as session:  # type: ignore[operator]
        statement = text("SELECT 1")
        for _ in range(count):
            result = await session.execute(statement)
            if result.scalar_one() == 1:
                seen += 1
    return seen


async def _measure(session_factory: object, runner: object, ids: list[str], count: int) -> float:
    """CPU milliseconds for `count` statements. `process_time()` is whole-process CPU and
    this loop is the only thing running, so it is the statements plus the driver.
    """
    start = time.process_time()
    produced = await runner(session_factory, ids, count)  # type: ignore[operator]
    elapsed_ms = (time.process_time() - start) * 1000
    if produced != count:
        raise SystemExit(
            f"FAIL: {count} statements were asked for and {produced} produced a result. "
            "A statement that returns nothing is cheaper than one the app issues, so the "
            "slope would understate the cost (guard 1)."
        )
    return elapsed_ms


async def _arm(session_factory: object, label: str, runner: object, ids: list[str]) -> Fit:
    print(f"\n{label}: {REPEATS} repeats at each of {COUNTS} statements")
    # One warm-up at the smallest count, discarded: it pays the compilation and the pool's
    # first connection, neither of which a marginal statement pays (expectation 4).
    await _measure(session_factory, runner, ids, COUNTS[0])

    points: list[tuple[int, float]] = []
    spread: dict[int, float] = {}
    for count in COUNTS:
        samples = [await _measure(session_factory, runner, ids, count) for _ in range(REPEATS)]
        median = statistics.median(samples)
        spread[count] = max(samples) - min(samples)
        points.append((count, median))
        print(
            f"  {count:>5} statements   median {median:8.2f} ms CPU"
            f"   ({median / count:6.4f} ms each, NOT the marginal cost)"
            f"   spread {spread[count]:6.2f} ms"
        )

    slope, intercept, r_squared = _fit(points)
    return Fit(slope_ms=slope, intercept_ms=intercept, r_squared=r_squared, spread_ms=spread)


def _statement_breakdown(spans: Sequence[ReadableSpan]) -> list[tuple[str, int]]:
    """Recorded spans grouped by name and by the statement they traced, commonest first.

    Exists because guard 2's first run failed by exactly 43 spans and a bare count cannot
    say why. It also caught the first *explanation* being wrong: the obvious guess was
    `pool_pre_ping`'s `SELECT 1` on each checkout, and the grouping refuted it in one run -
    `SELECT 1` appears exactly as often as the raw arm issues it, and the 43 extras carry
    no `db.statement` at all. The span *name* is in the key for that reason; without it
    this printed a plausible wrong answer.
    """
    counts: dict[str, int] = {}
    for span in spans:
        attributes = span.attributes or {}
        statement = str(attributes.get("db.statement", "(no db.statement)"))
        key = f"{span.name:<28} {' '.join(statement.split())[:52]}"
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda item: -item[1])


def _report(fits: dict[str, Fit], spans: int, statements: int) -> int:
    print(f"\n{'=' * 78}\nmarginal CPU per SQL statement  (tracing {'ON' if TRACING else 'OFF'})")
    print(f"{'=' * 78}")

    failed = False
    for label, fit in fits.items():
        verdict = "" if fit.usable else "   <-- FAIL: slope not usable"
        print(
            f"  {label:<14} slope {fit.slope_ms * 1000:7.1f} us/statement"
            f"   intercept {fit.intercept_ms:7.2f} ms"
            f"   R^2 {fit.r_squared:6.4f}{verdict}"
        )
        failed = failed or not fit.usable

    if TRACING:
        # Guard 2. Every statement in every arm should have produced exactly one span, so
        # a mismatch means spans were dropped or double-counted and the ON/OFF difference
        # cannot be attributed to spans.
        print(
            f"\n  spans recorded {spans} against {statements} statements issued "
            "(including one connection-level span per session)"
        )
        if spans != statements:
            print(
                "  FAIL: one span per statement is the assumption the tracing arm rests "
                "on (guard 2)."
            )
            failed = True

    if failed:
        print("\nNo sizing conclusion follows from a failed fit. Fix the apparatus first.")
        return 1

    orm = fits["orm_select"].slope_ms
    print(
        f"\n  What this prices: removing K statements from a request saves about "
        f"K x {orm * 1000:.1f} us of CPU. K is not a free parameter -\n"
        f"  `profile_local_request.py --statements` measures it, and for the answer path it "
        f"is {REMOVABLE_STATEMENTS}, not the {12} an\n"
        f"  analogy to AUD-F-31's `select_topic` result would suggest.\n\n"
        f"    the {REAL_STATEMENTS} statements       ~{REAL_STATEMENTS * orm:5.2f} ms "
        f"({REAL_STATEMENTS * orm / REQUEST_CPU_MS:5.1%} of a ~{REQUEST_CPU_MS:.0f} ms request)\n"
        f"    the {REMOVABLE_STATEMENTS} removable ones  ~{REMOVABLE_STATEMENTS * orm:5.2f} ms "
        f"saved ({REMOVABLE_STATEMENTS * orm / REQUEST_CPU_MS:5.1%} of it)\n"
        "  Compare the OTel lever, already measured at ~2.8 ms (~14%) and not taken.\n"
        "  Both numbers are this machine's CPU; the ratio is what transfers to Fargate."
    )
    print(
        "\n  Reminder, because it is the trap this script exists to avoid: the "
        "'ms each' column\n  above is a total divided by a count and includes fixed cost. "
        "Quote the slope."
    )
    return 0


async def _main_async(args: argparse.Namespace) -> int:
    engine = create_engine()
    provider = None
    if TRACING:
        # Production's pipeline shape, not a test's: `BatchSpanProcessor` wrapped in
        # `RedactingSpanExporter`, exactly as `build_tracer_provider` composes it for a
        # real deployment. A `SimpleSpanProcessor` here would price a different exporter.
        provider = TracerProvider(
            resource=Resource.create({SERVICE_NAME: "size-statement-cpu"}),
        )
        provider.add_span_processor(BatchSpanProcessor(RedactingSpanExporter(MEMORY_EXPORTER)))
        instrument_sqlalchemy_engines(engine, provider=provider)

    session_factory = create_session_factory(engine)
    try:
        ids = await _variant_ids(session_factory, wanted=50)
        if len(ids) < 10:
            raise SystemExit(
                f"FAIL: found {len(ids)} question variants in the dev database. This needs a "
                "loaded curriculum (`make curriculum-load`) - an empty table would make the "
                "ORM arm a miss-lookup benchmark (guard 1)."
            )
        print(f"  {len(ids)} seeded question variants available for the ORM arm")

        fits = {
            "orm_select": await _arm(session_factory, "orm_select", _run_orm, ids),
            "raw_select_1": await _arm(session_factory, "raw_select_1", _run_raw, ids),
        }
    finally:
        await engine.dispose()

    spans = 0
    if provider is not None:
        provider.force_flush()
        recorded = list(MEMORY_EXPORTER.get_finished_spans())
        spans = len(recorded)
        print("\n  recorded spans by statement:")
        for statement, count in _statement_breakdown(recorded)[:6]:
            print(f"    {count:>7}  {statement}")

    # Every statement this process issued that a span could have covered: both arms'
    # warm-up plus their repeats, plus the one id lookup - and one *connection-level* span
    # per session, which the breakdown above identifies by name rather than by guess. It is
    # a per-session cost, not a per-statement one, so it lands in each arm's intercept and
    # not in its slope. Counting it here keeps guard 2 exact instead of relaxing it into
    # uselessness, which is what a `spans >= statements` check would have been.
    per_arm = COUNTS[0] + REPEATS * sum(COUNTS)
    sessions = 1 + 2 * (1 + REPEATS * len(COUNTS))
    statements = 2 * per_arm + 1 + sessions
    return _report(fits, spans=spans, statements=statements)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-tracing",
        action="store_true",
        help=(
            "disable OTel instrumentation, to price the SQL span's share of the slope. "
            "Read from argv before this parser runs, because the SQLAlchemy instrumentor "
            "is a process-wide singleton attached at import time."
        ),
    )
    return asyncio.run(_main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
