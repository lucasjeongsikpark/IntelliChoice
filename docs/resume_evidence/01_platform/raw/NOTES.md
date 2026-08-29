# Raw artifact notes — E1.1

## `aborted_20260829T0637Z_machine_suspend/`

The sweep's first attempt, aborted by the runner's own stop rule at `burst_10vu_t3`. **Not a
staging fault:** the workstation suspended mid-run. The signature is unambiguous — the run's
wall clock is 16m23s for a flow that takes ~4s, `http_req_duration` has a single ~982 s block
against a p50 of 104 ms, `learning_dev_token` stayed at p95 122 ms throughout, and there were
**zero 5xx**; the 61 4xx are expired tokens on requests that resumed after the freeze. Kept
because a stop-rule firing should be auditable, not deleted.

The sweep was re-run from scratch under `caffeinate -i -s` so a suspend could not corrupt it
again. Nothing from this directory feeds `sweep_metrics.csv` or the report's tables.

## The missing `burst_10vu_t1`

**Destroyed by operator error, and the loss is recorded rather than papered over.** After the
main sweep, the sustained leg was launched with `TRIALS=0` to skip the bursts. On macOS
`seq 1 0` counts *down* — it emits `1` then `0` instead of nothing — so the runner executed two
extra 10-VU bursts, and the first of them wrote over `burst_10vu_t1.json`/`.log` before anyone
noticed. The original trial's summary file is unrecoverable.

What survives of it: `19:14:40Z, 140/140 requests, 0 errors, 17.18 rps, p95 1257 ms`, in
`aborted_.../sweep_console.log`'s successor console log. Those numbers are **not** used in
`sweep_metrics.csv` or in any median in the report, because the artifact they came from no
longer exists and an evidence program that quotes numbers it cannot show is the thing this
program exists not to be. The 10-VU level is therefore reported with the trials whose raw
summaries are intact.

`run_e1_sweep.sh` now refuses to overwrite an existing summary and guards the `TRIALS` loop, so
neither half of this can recur.

## `burst_10vu_3task_a` / `burst_10vu_3task_b`

The two accidental bursts, kept and **relabelled rather than discarded** — they are the only
10-VU measurements taken while the service was scaled to **3** tasks, and they turned out to be
directly relevant to the capacity finding. See `E1_REPORT.md`. They are excluded from the
2-task burst table because the replica count is not comparable.
