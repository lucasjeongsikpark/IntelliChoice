"""E3.3 - failure-injection matrix under concurrency, through the real gateway.

Run with:

    uv run python benchmarks/resume_evidence/03_gateway_agents/failure_matrix.py
    uv run python .../failure_matrix.py --out-dir /tmp/x

**Tier 1, $0.** No model call, no network, no AWS, no database. Everything under
measurement is `ResilientBedrockGateway` plus a scripted provider, so this runs anywhere
the test suite runs.

## What is injected, and where each mode lands in the gateway

The gateway draws one line that matters more than any other (D-115): a **provider-health**
failure counts toward the circuit breaker, a **structured-output** failure does not. A
response that arrives promptly and fails our schema says Bedrock is healthy and our request
is wrong; counting those together turned one rerank defect into a 30-second outage of every
task. The four modes here sit on both sides of that line on purpose.

| mode | how it is injected | gateway path | circuit? |
|---|---|---|---|
| `timeout` | sleeps past a short `call_timeout_s` | retry loop -> `BedrockTimeoutError` | yes |
| `provider_error` | raises `ProviderCallError` | retry loop -> `BedrockTimeoutError` | yes |
| `malformed` | returns `not json` | one repair retry -> `StructuredOutputError` | **no** |
| `truncated` | fragment + `truncated=True` | no repair -> `OutputTruncatedError` | **no** |

## The transience model

Half of the logical requests (even indices) are **transient**: they fail their first
provider attempt and would succeed on the next one. The other half are **persistent**.
Without that split "recovery rate" has no denominator to move against - every request would
be unrecoverable by construction and the metric would only ever read 0.

The request index travels inside the payload (`question="req-<i>"`), so the provider can
tell one logical request's attempts from another's. That is what makes *retry
amplification* (provider calls per logical request) measurable rather than inferred.

`truncated` has no transient arm that can win: the gateway deliberately does not spend a
repair call on a truncation, because an identical retry under the same ceiling truncates
identically. Its recovery rate is therefore 0/N **by design**, and that zero is the
measurement, not a defect.

## Half-open recovery

Measured in its own probe rather than inside the matrix, with a **compressed
`circuit_cooldown_s`** (the shipped value is 30 s). The probe opens the circuit with a
failing burst, notes the open transition, swaps the provider to healthy, and then polls
until a call gets through - so the number reported is the observed time from open to first
success, next to the configured cooldown it should track.

## Limitations

Single-process asyncio concurrency: `_circuit_check`/`_record_failure` contain no `await`,
so they run to completion without yielding, and the interleaving observed here is
cooperative rather than pre-emptive (this is the S34 result the shipped 30-concurrent test
already records). A multi-process rig would be a different experiment and is out of scope.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import pathlib
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.bedrock.provider import ProviderCallError, RawGeneration
from intellichoice_shared.bedrock import (
    BedrockTask,
    BedrockTutorPayload,
    CircuitOpenError,
    HintResponse,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "resume_evidence" / "03_gateway_agents"

MODEL_ID = "anthropic.claude-haiku-4-5"
MODES = ("timeout", "provider_error", "malformed", "truncated")
N_LEVELS = (30, 100)
TRIALS = 3

#: Shipped values, kept so the matrix describes the deployed configuration.
SHIPPED_MAX_RETRIES = 2
SHIPPED_BACKOFF_BASE_S = 0.5
SHIPPED_CIRCUIT_THRESHOLD = 5
SHIPPED_CIRCUIT_COOLDOWN_S = 30.0

#: Compressed so the run finishes: at the shipped 30 s a single burst would hold the whole
#: matrix open for half a minute per cell and measure nothing extra.
MATRIX_CIRCUIT_COOLDOWN_S = 1.0
HALF_OPEN_PROBE_COOLDOWN_S = 0.5

#: Short enough that the injected hang below reliably crosses it, long enough that ordinary
#: mock work never does.
TIMEOUT_MODE_CALL_TIMEOUT_S = 0.05
TIMEOUT_MODE_HANG_S = 0.5

_INDEX_RE = re.compile(r"req-(\d+)")

VALID_HINT_JSON = (
    '{"hint_text": "h", "concept_reminder": "c", "next_step_prompt": "n", '
    '"answer_revealed": false, "difficulty": 1}'
)
TRUNCATED_FRAGMENT = '{"hint_text": "h", "concept_rem'


def _payload(index: int) -> BedrockTutorPayload:
    return BedrockTutorPayload(
        grade="6",
        current_topic="Linear Equations",
        skill="Two-Step Equations",
        estimated_level="0.40",
        question=f"req-{index}",
        selected_answer="3",
        relevant_learning_fact=None,
    )


class ScriptedBurstProvider:
    """Injects one failure mode, per logical request, with a transient/persistent split.

    Attempt counting is keyed on the request index carried in the payload, not on a global
    call counter: a global counter cannot tell "one request retried three times" from
    "three requests failed once", which is exactly the quantity `retry_amplification`
    reports.
    """

    def __init__(self, mode: str, *, healthy: bool = False) -> None:
        self.mode = mode
        self.healthy = healthy
        self.calls = 0
        self.attempts_by_request: Counter[int] = Counter()
        self._inner = MockBedrockProvider()

    def _index(self, user_message: str) -> int:
        match = _INDEX_RE.search(user_message)
        return int(match.group(1)) if match else -1

    async def _valid(self, **kwargs: object) -> RawGeneration:
        return await self._inner.raw_generate(**kwargs)  # type: ignore[arg-type]

    async def raw_generate(self, **kwargs: object) -> RawGeneration:
        self.calls += 1
        user_message = str(kwargs.get("user_message", ""))
        index = self._index(user_message)
        attempt = self.attempts_by_request[index]
        self.attempts_by_request[index] += 1

        if self.healthy:
            return await self._valid(**kwargs)

        transient = index >= 0 and index % 2 == 0
        if transient and attempt >= 1:
            return await self._valid(**kwargs)

        if self.mode == "timeout":
            await asyncio.sleep(TIMEOUT_MODE_HANG_S)
            return await self._valid(**kwargs)
        if self.mode == "provider_error":
            raise ProviderCallError("injected transient provider failure")
        if self.mode == "malformed":
            return RawGeneration(text="not json", input_tokens=10, output_tokens=10)
        if self.mode == "truncated":
            return RawGeneration(
                text=TRUNCATED_FRAGMENT,
                input_tokens=10,
                output_tokens=10,
                truncated=True,
                stop_reason="max_tokens",
            )
        raise AssertionError(f"unknown mode {self.mode!r}")


class InstrumentedGateway(ResilientBedrockGateway):
    """The shipped gateway plus a record of every closed -> open transition.

    Subclassed rather than monkeypatched so the measured object *is* the product class:
    every timeout, retry, budget check and repair below is the shipped code path. The only
    addition is an observation of a transition that the class already performs.
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.circuit_open_events: list[float] = []

    def _record_failure(self) -> None:
        was_open = self._circuit_opened_until is not None
        super()._record_failure()
        if not was_open and self._circuit_opened_until is not None:
            self.circuit_open_events.append(time.monotonic())


def build_gateway(
    provider: object,
    *,
    call_timeout_s: float,
    cooldown_s: float,
    max_retries: int = SHIPPED_MAX_RETRIES,
) -> InstrumentedGateway:
    return InstrumentedGateway(
        provider=provider,
        model_registry={BedrockTask.TUTOR: MODEL_ID},
        call_timeout_s=call_timeout_s,
        max_retries=max_retries,
        backoff_base_s=SHIPPED_BACKOFF_BASE_S,
        circuit_failure_threshold=SHIPPED_CIRCUIT_THRESHOLD,
        circuit_cooldown_s=cooldown_s,
        session_budget_cents=10_000.0,
    )


@dataclass
class CellResult:
    mode: str
    n_concurrent: int
    trial: int
    succeeded: int
    failed: int
    recovery_rate: float
    provider_calls: int
    retry_amplification: float
    circuit_opens: int
    circuit_blocked: int
    final_failure_rate: float
    wall_clock_s: float
    outcomes: dict[str, int]


async def run_cell(mode: str, n: int, trial: int) -> CellResult:
    provider = ScriptedBurstProvider(mode)
    call_timeout = TIMEOUT_MODE_CALL_TIMEOUT_S if mode == "timeout" else 20.0
    gateway = build_gateway(
        provider, call_timeout_s=call_timeout, cooldown_s=MATRIX_CIRCUIT_COOLDOWN_S
    )
    outcomes: Counter[str] = Counter()

    async def one_request(index: int) -> None:
        try:
            await gateway.generate_structured(
                task=BedrockTask.TUTOR,
                system_prompt="system",
                payload=_payload(index),
                response_model=HintResponse,
                max_output_tokens=200,
                session_spend_cents=0.0,
            )
        except Exception as exc:  # noqa: BLE001 - every exit is classified, none swallowed
            outcomes[type(exc).__name__] += 1
        else:
            outcomes["ok"] += 1

    started = time.monotonic()
    await asyncio.gather(*(one_request(i) for i in range(n)))
    wall = time.monotonic() - started

    succeeded = outcomes["ok"]
    failed = n - succeeded
    return CellResult(
        mode=mode,
        n_concurrent=n,
        trial=trial,
        succeeded=succeeded,
        failed=failed,
        recovery_rate=round(succeeded / n, 4),
        provider_calls=provider.calls,
        retry_amplification=round(provider.calls / n, 4),
        circuit_opens=len(gateway.circuit_open_events),
        circuit_blocked=outcomes.get(CircuitOpenError.__name__, 0),
        final_failure_rate=round(failed / n, 4),
        wall_clock_s=round(wall, 3),
        outcomes=dict(outcomes),
    )


@dataclass
class HalfOpenProbe:
    mode: str
    configured_cooldown_s: float
    failures_before_open: int
    observed_recovery_s: float | None
    #: observed - configured. The residue is one healthy call plus loop granularity, so a
    #: small positive number is the expected result and a large one would be the finding.
    cooldown_overshoot_s: float | None
    calls_during_cooldown: int
    recovered: bool


async def probe_half_open(mode: str) -> HalfOpenProbe:
    """Open the circuit, heal the provider, and time the first call that gets through."""
    provider = ScriptedBurstProvider(mode)
    call_timeout = TIMEOUT_MODE_CALL_TIMEOUT_S if mode == "timeout" else 20.0
    # `max_retries=0` **for the opening burst only**, and this is a measurement decision
    # rather than a convenience. The interval being measured starts at the closed -> open
    # transition, which happens *inside* the call that trips the threshold - and under the
    # shipped ladder that call then sleeps 0.5 s and 1.0 s more before returning, so the
    # first poll could not even be issued until 1.5 s after the transition. Measured that
    # way the probe reports the retry ladder's tail, not the cooldown. Single-attempt calls
    # remove that tail; the cooldown itself is untouched.
    gateway = build_gateway(
        provider,
        call_timeout_s=call_timeout,
        cooldown_s=HALF_OPEN_PROBE_COOLDOWN_S,
        max_retries=0,
    )

    async def call(index: int) -> str:
        try:
            await gateway.generate_structured(
                task=BedrockTask.TUTOR,
                system_prompt="system",
                # Odd index: the persistent arm, so the failure is not spent by transience.
                payload=_payload(index),
                response_model=HintResponse,
                max_output_tokens=200,
                session_spend_cents=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            return type(exc).__name__
        return "ok"

    failures = 0
    index = 1
    while not gateway.circuit_open_events and failures < 50:
        await call(index)
        index += 2
        failures += 1
    if not gateway.circuit_open_events:
        return HalfOpenProbe(mode, HALF_OPEN_PROBE_COOLDOWN_S, failures, None, None, 0, False)

    opened_at = gateway.circuit_open_events[0]
    provider.healthy = True
    blocked_calls = 0
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        outcome = await call(index)
        index += 2
        if outcome == "ok":
            observed = time.monotonic() - opened_at
            return HalfOpenProbe(
                mode,
                HALF_OPEN_PROBE_COOLDOWN_S,
                failures,
                round(observed, 4),
                round(observed - HALF_OPEN_PROBE_COOLDOWN_S, 4),
                blocked_calls,
                True,
            )
        blocked_calls += 1
        await asyncio.sleep(0.01)
    return HalfOpenProbe(
        mode, HALF_OPEN_PROBE_COOLDOWN_S, failures, None, None, blocked_calls, False
    )


@dataclass
class MatrixRun:
    generated_at: str
    git_sha: str
    environment: str
    cost_usd: float
    configuration: dict
    cells: list[dict] = field(default_factory=list)
    summary: list[dict] = field(default_factory=list)
    half_open: list[dict] = field(default_factory=list)


def _summarize(cells: list[CellResult]) -> list[dict]:
    grouped: dict[tuple[str, int], list[CellResult]] = {}
    for cell in cells:
        grouped.setdefault((cell.mode, cell.n_concurrent), []).append(cell)

    rows = []
    for (mode, n), group in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        trials = len(group)
        succeeded = sum(g.succeeded for g in group)
        provider_calls = sum(g.provider_calls for g in group)
        denominator = n * trials
        merged: Counter[str] = Counter()
        for g in group:
            merged.update(g.outcomes)
        rows.append(
            {
                "mode": mode,
                "n_concurrent": n,
                "trials": trials,
                "requests": denominator,
                "recovered": succeeded,
                "recovery_rate": f"{succeeded}/{denominator}",
                "recovery_pct": round(100 * succeeded / denominator, 2),
                "final_failures": denominator - succeeded,
                "final_failure_rate": f"{denominator - succeeded}/{denominator}",
                "provider_calls": provider_calls,
                "retry_amplification": round(provider_calls / denominator, 3),
                "circuit_opens_total": sum(g.circuit_opens for g in group),
                "circuit_blocked": sum(g.circuit_blocked for g in group),
                "wall_clock_s_median": round(sorted(g.wall_clock_s for g in group)[trials // 2], 3),
                "outcomes": json.dumps(dict(sorted(merged.items()))),
            }
        )
    return rows


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


async def _main_async(out_dir: pathlib.Path, smoke: bool) -> MatrixRun:
    # Every failure exit from the gateway logs once at WARNING by design (D-115), which is
    # right in production and is thousands of lines here. Silenced for this process only;
    # the counts below come from the exceptions, not from the log.
    logging.getLogger("intellichoice_adapters.bedrock.gateway").setLevel(logging.CRITICAL)

    modes = MODES[:1] if smoke else MODES
    n_levels = (10,) if smoke else N_LEVELS
    trials = 1 if smoke else TRIALS

    cells: list[CellResult] = []
    total = len(modes) * len(n_levels) * trials
    index = 0
    for mode in modes:
        for n in n_levels:
            for trial in range(1, trials + 1):
                index += 1
                cell = await run_cell(mode, n, trial)
                cells.append(cell)
                print(
                    f"[{index:>2}/{total}] {mode:<15} N={n:>3} trial={trial} -> "
                    f"recovered {cell.succeeded}/{n} "
                    f"amplification {cell.retry_amplification:.2f} "
                    f"opens {cell.circuit_opens} blocked {cell.circuit_blocked} "
                    f"{cell.wall_clock_s:>6.2f}s",
                    flush=True,
                )

    probes = [await probe_half_open(mode) for mode in modes]
    for probe in probes:
        if probe.observed_recovery_s is None:
            # Not a failure to recover: `malformed`/`truncated` never open the circuit at
            # all (D-115), so there was nothing to recover from.
            print(
                f"half-open {probe.mode:<15} circuit never opened after "
                f"{probe.failures_before_open} consecutive failures (expected for "
                f"structured-output modes)",
                flush=True,
            )
            continue
        print(
            f"half-open {probe.mode:<15} configured {probe.configured_cooldown_s}s -> "
            f"observed {probe.observed_recovery_s}s "
            f"(+{probe.cooldown_overshoot_s}s)",
            flush=True,
        )

    run = MatrixRun(
        generated_at=datetime.now(UTC).isoformat(),
        git_sha=_git_sha(),
        environment=(
            "local simulation - real ResilientBedrockGateway, scripted in-process provider; "
            "no network, no model spend"
        ),
        cost_usd=0.0,
        configuration={
            "model_id": MODEL_ID,
            "max_retries": SHIPPED_MAX_RETRIES,
            "backoff_base_s": SHIPPED_BACKOFF_BASE_S,
            "circuit_failure_threshold": SHIPPED_CIRCUIT_THRESHOLD,
            "shipped_circuit_cooldown_s": SHIPPED_CIRCUIT_COOLDOWN_S,
            "matrix_circuit_cooldown_s": MATRIX_CIRCUIT_COOLDOWN_S,
            "half_open_probe_cooldown_s": HALF_OPEN_PROBE_COOLDOWN_S,
            "timeout_mode_call_timeout_s": TIMEOUT_MODE_CALL_TIMEOUT_S,
            "timeout_mode_hang_s": TIMEOUT_MODE_HANG_S,
            "transient_fraction": 0.5,
            "trials_per_cell": trials,
        },
        cells=[asdict(c) for c in cells],
        summary=_summarize(cells),
        half_open=[asdict(p) for p in probes],
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "failure_matrix.json").write_text(json.dumps(asdict(run), indent=2) + "\n")
    _write_csv(out_dir / "failure_matrix.csv", run.summary)
    return run


def _write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    columns = [
        "mode",
        "n_concurrent",
        "trials",
        "requests",
        "recovered",
        "recovery_rate",
        "recovery_pct",
        "final_failures",
        "final_failure_rate",
        "provider_calls",
        "retry_amplification",
        "circuit_opens_total",
        "circuit_blocked",
        "wall_clock_s_median",
        "outcomes",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row[c] for c in columns})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    run = asyncio.run(_main_async(args.out_dir, args.smoke))
    print()
    print(f"{len(run.cells)} cells -> {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
