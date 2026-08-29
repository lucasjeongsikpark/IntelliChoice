"""E3.1 / E3.2 - the concurrency/overshoot benchmark for the per-day spend ceilings.

Run with:

    uv run python benchmarks/resume_evidence/03_gateway_agents/overshoot_benchmark.py
    uv run python .../overshoot_benchmark.py --smoke          # one tiny cell, ~10 s
    uv run python .../overshoot_benchmark.py --out-dir /tmp/x

**Tier 1, $0.** No model call, no network, no AWS. The only external dependency is the
local docker-compose Postgres, because the thing under measurement *is* a Postgres
advisory lock - a fake ledger would measure the fake.

## What this measures

For each concurrency level N, each of the three ceiling shapes, and each of two ledger
implementations, it fires N genuinely concurrent
`reserve -> model call -> settle` flows at one (scope, subject) pair and reports the
**budget overshoot ratio** = committed spend / ceiling, with numerator and denominator.

- **arm `fixed`** - the shipped `CostReservationRepository` (`pg_advisory_xact_lock`,
  reserve-before-call, `coalesce(actual, reserved)` sum).
- **arm `baseline`** - `ReadThenActLedger` below: the pre-D-110 read-then-act shape,
  implemented **in this harness only**, never in product code.

## Why the latency injection is not optional

D-110 §2 records the trap this harness is built around: the finding's own reproduction
*did not reproduce*. `MockBedrockProvider` returns in ~0 ms, so the race window - which is
the duration of the model call - was almost nothing, and ten genuinely concurrent callers
produced 1 grant and 1.0x the ceiling **against the unfixed code**. It looked fixed before
it was fixed. Giving the call a 250 ms duration produced 10/10 and 10.0x.

So this benchmark runs three delay arms, and the first one is a control that reproduces
that false negative on purpose:

| delay | why this value |
|---|---|
| `0.000 s` | the mock's own speed - D-110's erased window, kept as a **negative control** |
| `0.250 s` | D-110's calibrated probe value, the smallest delay that made the race visible |
| `3.000 s` | a realistic single-call slice (see below) |

The 3 s arm is justified from measured numbers, not picked: D-343 timed whole cited chat
turns at 6.2-10.9 s wall clock across several gateway calls, and D-110 cites a 26.9 s p50
for the real report call. 3 s is therefore a **conservative** stand-in - it understates the
real race window, which makes every baseline overshoot below a lower bound.

## Ceiling shapes

The three shapes are the real product surfaces, and their estimate constants are imported
from product code rather than restated (`report.REPORT_RESERVATION_ESTIMATE_CENTS`,
`tutor_chat.TURN_RESERVATION_ESTIMATE_CENTS`, `chat_api.services.turn_cost.
TURN_RESERVATION_ESTIMATE_CENTS`). Two ceiling bases are measured:

- `derived_k` - ceiling = k x estimate, k = N // 4. Exact divisibility isolates the
  concurrency property from the quantization effect below, so a correct ledger scores
  exactly 1.0.
- `production_constant` - the app's real ceiling (`DAILY_REPORT_COST_CEILING_CENTS`,
  `tutor_chat.DAILY_COST_CEILING_CENTS`, `chat_daily_spend_ceiling_cents`'s default).
  Here the ceiling is *not* a whole multiple of the estimate for every surface, and the
  ledger's admission test (`spend >= ceiling` **before** adding this call's estimate)
  lets the last admitted caller cross the line by up to one estimate. That is a real,
  bounded property of the shipped design, reported rather than hidden.

`chat_turn`'s subject is the constant `SUBJECT_CHAT_API` in production, so every caller in
the whole app hashes to one advisory lock. The other two shapes are per-student; this
benchmark points all N callers at one student on purpose, which is that surface's worst
case.

## Limitations, stated up front

- Single-process, single-event-loop asyncio concurrency against a local Postgres. Real
  traffic is multi-process across ECS tasks. The *ledger* is genuinely shared (it is a
  database row set, and every reservation really commits), so the serialization point
  under test is the real one - but the client-side interleaving is not multi-process, and
  a multi-process rig is deliberately out of scope for this task.
- Wall clock and reservations/sec are local-Postgres numbers, not staging numbers.
- Nothing here is a quality result. It is a concurrency-correctness and cost-containment
  result.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import pathlib
import statistics
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

from chat_api.config import Settings as ChatSettings
from chat_api.services.turn_cost import (
    TURN_RESERVATION_ESTIMATE_CENTS as CHAT_TURN_ESTIMATE_CENTS,
)
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.bedrock.provider import RawGeneration
from intellichoice_db.engine import DEFAULT_DATABASE_URL, create_session_factory
from intellichoice_db.models.cost_reservation import (
    SCOPE_CHAT_TURN,
    SCOPE_STUDENT_REPORT,
    SCOPE_TUTOR_CHAT,
    CostReservation,
)
from intellichoice_db.repositories.cost_reservation import (
    CeilingReachedError,
    CostReservationRepository,
)
from learning_api.services.report import (
    DAILY_REPORT_COST_CEILING_CENTS,
    REPORT_RESERVATION_ESTIMATE_CENTS,
)
from learning_api.services.tutor_chat import (
    DAILY_COST_CEILING_CENTS as TUTOR_DAILY_CEILING_CENTS,
)
from learning_api.services.tutor_chat import (
    TURN_RESERVATION_ESTIMATE_CENTS as TUTOR_TURN_ESTIMATE_CENTS,
)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "resume_evidence" / "03_gateway_agents"

#: Every row this harness writes carries this prefix in `subject_external_id`, and the
#: cleanup deletes exactly that prefix. Benchmark rows must never outlive the run: they
#: live in the shared dev database, and a stray row is a spend ceiling that starts a
#: developer's next 24 hours already partly consumed.
SUBJECT_PREFIX = "e3-bench-"

#: `pool_size + max_overflow` here, not `create_engine`'s 10+10. The point is to let many
#: reservations really be in flight at once; local Postgres' default `max_connections` is
#: 100 and this is one process, so 40 is comfortably inside it.
POOL_SIZE = 20
MAX_OVERFLOW = 20

N_LEVELS = (10, 50, 100, 200)
DELAYS_S = (0.0, 0.25, 3.0)
TRIALS = 3
#: The production-constant grid is the expensive-but-realistic arm, so it runs at the
#: realistic delay only and at two concurrency levels.
PRODUCTION_N_LEVELS = (50, 200)
PRODUCTION_DELAYS_S = (3.0,)


@dataclass(frozen=True)
class CeilingShape:
    """One product spend-ceiling surface, described by the constants it actually uses."""

    key: str
    scope: str
    estimate_cents: float
    production_ceiling_cents: float
    subject_is_global: bool
    note: str


def ceiling_shapes() -> tuple[CeilingShape, ...]:
    chat_default_ceiling = ChatSettings.model_fields["chat_daily_spend_ceiling_cents"].default
    assert isinstance(chat_default_ceiling, float)
    return (
        CeilingShape(
            key="report",
            scope=SCOPE_STUDENT_REPORT,
            estimate_cents=REPORT_RESERVATION_ESTIMATE_CENTS,
            production_ceiling_cents=DAILY_REPORT_COST_CEILING_CENTS,
            subject_is_global=False,
            note="per-student parent/student report generation (learning-api)",
        ),
        CeilingShape(
            key="tutor_chat",
            scope=SCOPE_TUTOR_CHAT,
            estimate_cents=TUTOR_TURN_ESTIMATE_CENTS,
            production_ceiling_cents=TUTOR_DAILY_CEILING_CENTS,
            subject_is_global=False,
            note="per-student tutor chat turn (learning-api)",
        ),
        CeilingShape(
            key="chat_turn",
            scope=SCOPE_CHAT_TURN,
            estimate_cents=CHAT_TURN_ESTIMATE_CENTS,
            production_ceiling_cents=chat_default_ceiling,
            subject_is_global=True,
            note="app-wide daily chat spend (chat-api); subject is the constant "
            "SUBJECT_CHAT_API, so all callers share one advisory lock",
        ),
    )


# --------------------------------------------------------------------------------------
# The latency-injecting provider
# --------------------------------------------------------------------------------------


class DelayedProvider:
    """`MockBedrockProvider` with a configurable floor on how long a call takes.

    This is the whole reason the benchmark can see the defect at all (D-110 §2). It wraps
    rather than replaces the mock so the *response* is still the real deterministic mock
    output - only the duration is injected.
    """

    def __init__(self, delay_s: float, inner: MockBedrockProvider | None = None) -> None:
        self._delay_s = delay_s
        self._inner = inner or MockBedrockProvider()
        self.calls = 0

    @property
    def delay_s(self) -> float:
        return self._delay_s

    async def raw_generate(self, **kwargs: object) -> RawGeneration:
        self.calls += 1
        if self._delay_s > 0:
            await asyncio.sleep(self._delay_s)
        return await self._inner.raw_generate(**kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------
# E3.2 - the pre-D-110 baseline, reproduced in the harness only
# --------------------------------------------------------------------------------------


class ReadThenActLedger:
    """The **pre-D-110** shape, for the before/after arm. Never used by product code.

    D-110's own description of what it replaced: *"read the spend, then spend"*, with the
    row carrying the cost committed by the FastAPI dependency teardown **after** the
    response. Two consequences, both reproduced here:

    1. No serialization. There is no advisory lock and nothing is written before the call,
       so every concurrent caller reads the same pre-call total.
    2. The window is the whole model call, not two fast statements. `reserve` returns
       having written nothing; the row appears only at `settle`.

    Deliberately shares `cost_reservations` with the fixed arm rather than modelling the
    old `student_reports.cost_cents` column, so both arms are measured by one query and
    cleaned up by one delete. The *semantics* are what the arm reproduces, not the table.
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def reserve(
        self,
        *,
        scope: str,
        subject_external_id: str,
        estimate_cents: float,
        ceiling_cents: float,
        window: timedelta = timedelta(hours=24),
    ) -> str:
        async with self._session_factory() as session:
            spend = await _committed_spend(
                session, scope=scope, subject_external_id=subject_external_id, window=window
            )
            await session.commit()
        if spend >= ceiling_cents:
            raise CeilingReachedError(scope, spend, ceiling_cents)
        # Nothing is written. The caller is now free to spend, and so is everybody else.
        return f"unwritten-{uuid.uuid4().hex}"

    async def settle(
        self,
        reservation_id: str,
        actual_cents: float,
        *,
        scope: str,
        subject_external_id: str,
    ) -> None:
        del reservation_id
        async with self._session_factory() as session:
            session.add(
                CostReservation(
                    scope=scope,
                    subject_external_id=subject_external_id,
                    reserved_cents=actual_cents,
                    actual_cents=actual_cents,
                    settled_at=datetime.now(UTC),
                )
            )
            await session.commit()


async def _committed_spend(
    session, *, scope: str, subject_external_id: str, window: timedelta
) -> float:
    """The pre-fix read: **committed** cost only. `actual_cents` with no `coalesce` onto
    `reserved_cents` is the point - an in-flight call was invisible, which is the defect.
    """
    stmt = select(func.coalesce(func.sum(CostReservation.actual_cents), 0.0)).where(
        CostReservation.scope == scope,
        CostReservation.subject_external_id == subject_external_id,
        CostReservation.created_at >= datetime.now(UTC) - window,
    )
    return float((await session.execute(stmt)).scalar_one())


# --------------------------------------------------------------------------------------
# One cell of the grid
# --------------------------------------------------------------------------------------


@dataclass
class TrialResult:
    arm: str
    shape: str
    ceiling_basis: str
    n_concurrent: int
    delay_s: float
    trial: int
    k_admitted_by_ceiling: int
    ceiling_cents: float
    estimate_cents: float
    granted: int
    rejected: int
    errors: int
    spend_cents: float
    overshoot_ratio: float
    grants_beyond_k: int
    provider_calls: int
    wall_clock_s: float
    reservations_per_s: float


@dataclass
class BenchmarkRun:
    generated_at: str
    git_sha: str
    environment: str
    database_url_host: str
    cost_usd: float
    trials_per_cell: int
    delays_s: list[float]
    n_levels: list[int]
    shapes: list[dict] = field(default_factory=list)
    trials: list[dict] = field(default_factory=list)
    cells: list[dict] = field(default_factory=list)


async def _cleanup(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM cost_reservations WHERE subject_external_id LIKE :p"),
            {"p": f"{SUBJECT_PREFIX}%"},
        )


async def _observed_spend(session_factory, *, scope: str, subject: str) -> float:
    """Read the committed truth with `coalesce(actual, reserved)` - the same expression the
    ceiling itself uses, so "what was spent" and "what the ceiling would see" are one
    number in both arms.
    """
    async with session_factory() as session:
        return await CostReservationRepository._spend_cents(  # noqa: SLF001
            session, scope=scope, subject_external_id=subject, window=timedelta(hours=24)
        )


async def run_trial(
    *,
    engine,
    session_factory,
    arm: str,
    shape: CeilingShape,
    ceiling_basis: str,
    ceiling_cents: float,
    k: int,
    n: int,
    delay_s: float,
    trial: int,
) -> TrialResult:
    subject = f"{SUBJECT_PREFIX}{arm}-{shape.key}-{n}-{trial}-{uuid.uuid4().hex[:8]}"
    provider = DelayedProvider(delay_s)
    fixed = CostReservationRepository(session_factory)
    baseline = ReadThenActLedger(session_factory)

    granted = 0
    rejected = 0
    errors = 0

    async def one_caller(index: int) -> str:
        nonlocal granted, rejected, errors
        try:
            if arm == "fixed":
                reservation = await fixed.reserve(
                    scope=shape.scope,
                    subject_external_id=subject,
                    estimate_cents=shape.estimate_cents,
                    ceiling_cents=ceiling_cents,
                )
            else:
                await baseline.reserve(
                    scope=shape.scope,
                    subject_external_id=subject,
                    estimate_cents=shape.estimate_cents,
                    ceiling_cents=ceiling_cents,
                )
        except CeilingReachedError:
            rejected += 1
            return "rejected"
        except Exception:  # noqa: BLE001 - counted, not swallowed silently; see `errors`
            errors += 1
            return "error"

        granted += 1
        # The model call. This is the race window, and injecting its duration is the
        # entire methodological point (D-110 §2).
        await provider.raw_generate(
            model_id="bench-model",
            system_prompt="s",
            user_message=json.dumps({"i": index}),
            json_schema={"title": "HintResponse"},
            max_output_tokens=64,
        )
        # Settled at the estimate, not below it: settling low would return budget to the
        # ceiling and make the overshoot ratio a statement about the mock's cheapness
        # rather than about admission control.
        if arm == "fixed":
            await fixed.settle(reservation.reservation_id, shape.estimate_cents)
        else:
            await baseline.settle(
                "unwritten",
                shape.estimate_cents,
                scope=shape.scope,
                subject_external_id=subject,
            )
        return "granted"

    started = time.monotonic()
    await asyncio.gather(*(one_caller(i) for i in range(n)))
    wall = time.monotonic() - started

    spend = await _observed_spend(session_factory, scope=shape.scope, subject=subject)
    await _cleanup(engine)

    return TrialResult(
        arm=arm,
        shape=shape.key,
        ceiling_basis=ceiling_basis,
        n_concurrent=n,
        delay_s=delay_s,
        trial=trial,
        k_admitted_by_ceiling=k,
        ceiling_cents=round(ceiling_cents, 4),
        estimate_cents=shape.estimate_cents,
        granted=granted,
        rejected=rejected,
        errors=errors,
        spend_cents=round(spend, 4),
        overshoot_ratio=round(spend / ceiling_cents, 4),
        grants_beyond_k=max(0, granted - k),
        provider_calls=provider.calls,
        wall_clock_s=round(wall, 3),
        reservations_per_s=round(n / wall, 1) if wall > 0 else 0.0,
    )


def _cell_key(t: TrialResult) -> tuple:
    return (t.arm, t.shape, t.ceiling_basis, t.n_concurrent, t.delay_s)


def _summarize(trials: list[TrialResult]) -> list[dict]:
    cells: dict[tuple, list[TrialResult]] = {}
    for t in trials:
        cells.setdefault(_cell_key(t), []).append(t)

    out = []
    for key, group in cells.items():
        arm, shape, basis, n, delay = key
        ratios = [g.overshoot_ratio for g in group]
        grants = [g.granted for g in group]
        walls = [g.wall_clock_s for g in group]
        rates = [g.reservations_per_s for g in group]
        out.append(
            {
                "arm": arm,
                "shape": shape,
                "ceiling_basis": basis,
                "n_concurrent": n,
                "delay_s": delay,
                "trials": len(group),
                "k_admitted_by_ceiling": group[0].k_admitted_by_ceiling,
                "ceiling_cents": group[0].ceiling_cents,
                "estimate_cents": group[0].estimate_cents,
                "granted_median": statistics.median(grants),
                "granted_min": min(grants),
                "granted_max": max(grants),
                "rejected_median": statistics.median([g.rejected for g in group]),
                "errors_total": sum(g.errors for g in group),
                "grants_beyond_k_max": max(g.grants_beyond_k for g in group),
                "spend_cents_median": round(statistics.median([g.spend_cents for g in group]), 4),
                "overshoot_median": round(statistics.median(ratios), 4),
                "overshoot_min": round(min(ratios), 4),
                "overshoot_max": round(max(ratios), 4),
                "wall_clock_s_median": round(statistics.median(walls), 3),
                "reservations_per_s_median": round(statistics.median(rates), 1),
            }
        )
    out.sort(
        key=lambda c: (
            c["ceiling_basis"],
            c["shape"],
            c["delay_s"],
            c["n_concurrent"],
            c["arm"],
        )
    )
    return out


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):  # pragma: no cover
        return "unknown"


def _plan(smoke: bool) -> list[tuple[str, CeilingShape, str, int, float, int]]:
    """(arm, shape, ceiling_basis, n, delay_s, trial) for every trial to run."""
    shapes = ceiling_shapes()
    if smoke:
        return [(arm, shapes[0], "derived_k", 10, 0.25, 1) for arm in ("fixed", "baseline")]
    plan = []
    for basis, n_levels, delays in (
        ("derived_k", N_LEVELS, DELAYS_S),
        ("production_constant", PRODUCTION_N_LEVELS, PRODUCTION_DELAYS_S),
    ):
        for shape in shapes:
            for delay in delays:
                for n in n_levels:
                    for arm in ("fixed", "baseline"):
                        for trial in range(1, TRIALS + 1):
                            plan.append((arm, shape, basis, n, delay, trial))
    return plan


async def _main_async(out_dir: pathlib.Path, smoke: bool) -> BenchmarkRun:
    engine = create_async_engine(
        DEFAULT_DATABASE_URL,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_pre_ping=True,
    )
    session_factory = create_session_factory(engine)
    results: list[TrialResult] = []
    try:
        await _cleanup(engine)
        plan = _plan(smoke)
        for index, (arm, shape, basis, n, delay, trial) in enumerate(plan, start=1):
            if basis == "derived_k":
                k = max(2, n // 4)
                ceiling = k * shape.estimate_cents
            else:
                ceiling = shape.production_ceiling_cents
                # How many callers the ceiling admits: the test is `spend >= ceiling`
                # *before* this call's estimate is added, so the last admitted caller can
                # cross it. That is `floor(ceiling / estimate) + 1` when the division is
                # not exact.
                exact, remainder = divmod(round(ceiling * 10000), round(shape.estimate_cents * 1e4))
                k = int(exact) + (1 if remainder else 0)
            result = await run_trial(
                engine=engine,
                session_factory=session_factory,
                arm=arm,
                shape=shape,
                ceiling_basis=basis,
                ceiling_cents=ceiling,
                k=k,
                n=n,
                delay_s=delay,
                trial=trial,
            )
            results.append(result)
            print(
                f"[{index:>3}/{len(plan)}] {basis:<20} {shape.key:<11} "
                f"arm={arm:<8} N={n:>3} delay={delay:>5.3f}s trial={trial} "
                f"-> granted {result.granted}/{n} (k={k}) "
                f"overshoot {result.overshoot_ratio:>6.3f}x  {result.wall_clock_s:>6.2f}s",
                flush=True,
            )
    finally:
        await _cleanup(engine)
        await engine.dispose()

    run = BenchmarkRun(
        generated_at=datetime.now(UTC).isoformat(),
        git_sha=_git_sha(),
        environment=(
            "local simulation - real Postgres advisory-lock ledger (docker-compose "
            "pgvector/pgvector:pg16), mock model with injected latency"
        ),
        database_url_host="localhost:5432",
        cost_usd=0.0,
        trials_per_cell=1 if smoke else TRIALS,
        delays_s=list(DELAYS_S),
        n_levels=list(N_LEVELS),
        shapes=[asdict(s) for s in ceiling_shapes()],
        trials=[asdict(t) for t in results],
        cells=_summarize(results),
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "overshoot_results.json").write_text(json.dumps(asdict(run), indent=2) + "\n")
    _write_csv(out_dir / "overshoot_table.csv", run.cells)
    return run


def _write_csv(path: pathlib.Path, cells: list[dict]) -> None:
    columns = [
        "ceiling_basis",
        "shape",
        "delay_s",
        "n_concurrent",
        "arm",
        "k_admitted_by_ceiling",
        "ceiling_cents",
        "estimate_cents",
        "trials",
        "granted_median",
        "granted_min",
        "granted_max",
        "rejected_median",
        "errors_total",
        "grants_beyond_k_max",
        "spend_cents_median",
        "overshoot_median",
        "overshoot_min",
        "overshoot_max",
        "wall_clock_s_median",
        "reservations_per_s_median",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for cell in cells:
            writer.writerow({c: cell[c] for c in columns})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="one tiny cell per arm - for checking the rig, not for the report",
    )
    args = parser.parse_args()

    run = asyncio.run(_main_async(args.out_dir, args.smoke))

    print()
    print(f"{len(run.trials)} trials, {len(run.cells)} cells -> {args.out_dir}")
    worst_fixed = max(
        (c for c in run.cells if c["arm"] == "fixed"),
        key=lambda c: c["overshoot_max"],
        default=None,
    )
    worst_baseline = max(
        (c for c in run.cells if c["arm"] == "baseline"),
        key=lambda c: c["overshoot_max"],
        default=None,
    )
    if worst_fixed:
        print(
            f"worst fixed overshoot    : {worst_fixed['overshoot_max']}x "
            f"({worst_fixed['shape']}, N={worst_fixed['n_concurrent']}, "
            f"delay={worst_fixed['delay_s']}s, {worst_fixed['ceiling_basis']})"
        )
    if worst_baseline:
        print(
            f"worst baseline overshoot : {worst_baseline['overshoot_max']}x "
            f"({worst_baseline['shape']}, N={worst_baseline['n_concurrent']}, "
            f"delay={worst_baseline['delay_s']}s, {worst_baseline['ceiling_basis']})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
