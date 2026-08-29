"""E1.2's delivery ledger and E1.1's summary parser, tested on literals.

Both are *instruments*: they do not ship, but every number in `docs/resume_evidence/01_platform/`
comes out of them, and an instrument that miscounts produces a report that is internally
consistent and wrong. That is the failure this file exists to make loud - the same reasoning
`test_stage_funnel_analysis.py` records for E5.1's funnel parser.

Three things here are worth more than the rest:

- **The initial snapshot must never be credited as a delivery.** `/stream` yields the current
  checkpoint on every connect, so an instrument that counted it would score a stream whose relay
  is completely dead as fully delivered. That is the false pass D-334's 2-of-4 measurement would
  have been reported as.
- **A threshold's exported boolean means "failed".** k6's legacy summary export inverts the
  reading most people bring to it; getting it backwards flips every pass/fail in the report
  while leaving the latencies right.
- **The stop rule.** It is what protects a live staging sweep from being pushed through a D-455
  rotation-class incident, and it is duplicated into `run_e1_sweep.sh` as dependency-free inline
  Python on purpose. These tests pin the Python side.

Pure: literals in, dicts out. No network, no Postgres, no k6, no filesystem writes.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import pathlib
import sys
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmarks" / "resume_evidence" / "01_platform"


def _load(name: str):
    """`benchmarks/` is outside the uv workspace on purpose (measurement code, not shipped code),
    so there is no package to import - the same by-path load the other benchmark tests use."""
    spec = importlib.util.spec_from_file_location(name, BENCH / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ledger_mod = _load("sse_ledger")
k6_mod = _load("k6_summary")

StreamLedger = ledger_mod.StreamLedger
aggregate = ledger_mod.aggregate
content_hash = ledger_mod.content_hash


def snapshot(phase: str = "pre_exam", **extra: Any) -> dict[str, Any]:
    return {"learning_session_id": "s-1", "phase": phase, **extra}


# --------------------------------------------------------------------------- content hashing


def test_a_response_and_the_frame_it_published_hash_identically():
    """The publish path is `SessionSnapshotEvent.model_validate(response.model_dump())`, so the
    action's response and the frame are one object through two serializations. The frame carries
    the full superset with explicit nulls and a constant `event` discriminator; the response
    carries only its own model's fields. They must still agree, or every content comparison in
    the ledger is noise."""
    response = {"learning_session_id": "s-1", "phase": "pre_exam", "is_correct": None}
    frame = {
        "event": "session_update",
        "learning_session_id": "s-1",
        "phase": "pre_exam",
        "message": None,
        "is_correct": None,
        "items": None,
        "learning_gain": None,
        "pending_interrupt": None,
        "intervention": None,
        "assistance_question": None,
        "study_progress": None,
        "attendance_resolution": None,
        "stage_narrative": None,
        "stage_narrative_evidence": None,
        "stage_narrative_stage": None,
    }
    assert content_hash(response) == content_hash(frame)


def test_the_event_discriminator_is_not_part_of_the_hash():
    assert content_hash({"phase": "study"}) == content_hash(
        {"event": "session_update", "phase": "study"}
    )


def test_different_phases_hash_differently():
    assert content_hash(snapshot("pre_exam")) != content_hash(snapshot("study"))


# --------------------------------------------------------------------------- delivery credit


def test_the_initial_snapshot_is_never_a_delivery():
    """A stream that received only its connect snapshot has been delivered nothing."""
    led = StreamLedger(stream_id="s-1", arm="cross")
    led.initial_snapshots = 1
    led.record_expected("answer", 0.0, snapshot())
    summary = led.summary()
    assert summary["initial_snapshots"] == 1
    assert summary["delivered"] == 0
    assert summary["lost"] == 1


def test_a_delivered_event_is_credited_with_its_latency():
    led = StreamLedger(stream_id="s-1", arm="cross")
    idx = led.record_expected("answer", 10.0, snapshot())
    led.record_delivery(idx, 10.25, snapshot())
    summary = led.summary()
    assert summary["delivered"] == 1
    assert summary["lost"] == 0
    assert summary["latency_ms"]["p50"] == pytest.approx(250.0)
    assert summary["content_agreements"] == 1


def test_a_second_frame_for_a_credited_action_is_a_duplicate_not_an_overwrite():
    """A relay echo that escaped the origin guard would deliver the same event twice. Silently
    replacing the first credit would hide exactly that."""
    led = StreamLedger(stream_id="s-1", arm="cross")
    idx = led.record_expected("answer", 0.0, snapshot())
    led.record_delivery(idx, 0.1, snapshot())
    led.record_delivery(idx, 0.2, snapshot())
    summary = led.summary()
    assert summary["delivered"] == 1
    assert summary["unmatched_frames"] == 1
    assert led.unmatched_frames[0]["reason"] == "duplicate_for_index"


def test_lost_events_report_their_indices_and_actions():
    led = StreamLedger(stream_id="s-1", arm="cross")
    a = led.record_expected("select_topic", 0.0, snapshot("pre_exam"))
    led.record_expected("answer", 1.0, snapshot())
    c = led.record_expected("resume", 2.0, snapshot())
    led.record_delivery(a, 0.1, snapshot("pre_exam"))
    led.record_delivery(c, 2.1, snapshot())
    summary = led.summary()
    assert summary["lost"] == 1
    assert summary["lost_indices"] == [1]
    assert summary["lost_actions"] == ["answer"]


# --------------------------------------------------------------------------- reconnect recovery


def test_a_reconnect_that_restores_the_expected_state_is_a_recovery_not_a_delivery():
    """Through CloudFront a stream can be cut mid-action. The push reached nobody - so it is not
    a delivery - but the reconnect's checkpoint read left the client holding the right state, so
    it is not a silent loss either. Two counters, two claims."""
    led = StreamLedger(stream_id="s-1", arm="staging")
    idx = led.record_expected("answer", 0.0, snapshot("study"))
    led.reconnects = 1
    led.record_recovery(idx, 1.0, snapshot("study"))
    summary = led.summary()
    assert summary["delivered"] == 0
    assert summary["recovered_on_reconnect"] == 1
    assert summary["lost"] == 0

    agg = aggregate([led])["total"]
    assert agg["delivery_fraction"] == "0/1"
    assert agg["state_convergence_fraction"] == "1/1"


def test_a_reconnect_that_restores_some_other_state_is_still_a_loss():
    led = StreamLedger(stream_id="s-1", arm="staging")
    idx = led.record_expected("answer", 0.0, snapshot("study"))
    led.record_recovery(idx, 1.0, snapshot("pre_exam"))
    assert led.summary()["lost"] == 1
    assert led.summary()["recovered_on_reconnect"] == 0


def test_reconnects_are_counted_separately_from_losses():
    """The spec's rule: a reconnect is not a delivery failure if no event was lost."""
    led = StreamLedger(stream_id="s-1", arm="staging")
    led.reconnects = 4
    idx = led.record_expected("answer", 0.0, snapshot())
    led.record_delivery(idx, 0.1, snapshot())
    summary = led.summary()
    assert summary["reconnects"] == 4
    assert summary["lost"] == 0
    assert summary["delivered"] == 1


# --------------------------------------------------------------------------- ordering honesty


def test_a_run_of_identical_snapshots_contributes_no_decidable_transitions():
    """Measured on the local rig: `select_topic` and all ten pre-exam answers publish the *same*
    JSON, because an answer whose correctness is masked (D-064) changes no snapshot field.
    Within such a run there is nothing a reordering could disturb, so it must not be counted as
    ordering evidence - the ledger reports the size of the claim, not a reassuring zero."""
    led = StreamLedger(stream_id="s-1", arm="cross")
    led.initial_hash = content_hash(snapshot())
    for i in range(5):
        idx = led.record_expected("answer", float(i), snapshot())
        led.record_delivery(idx, i + 0.1, snapshot())
    summary = led.summary()
    assert summary["delivered"] == 5
    assert summary["ordering_decidable_transitions"] == 0
    assert summary["out_of_order"] == 0


def test_a_transition_between_two_different_snapshots_is_decidable_and_agrees():
    """The boundary is where ordering becomes observable: the frame credited to the first
    `study` action must carry `study`."""
    led = StreamLedger(stream_id="s-1", arm="cross")
    led.initial_hash = content_hash(snapshot("student_selected"))
    a = led.record_expected("select_topic", 0.0, snapshot("pre_exam"))
    led.record_delivery(a, 0.1, snapshot("pre_exam"))
    b = led.record_expected("answer", 1.0, snapshot("pre_exam"))
    led.record_delivery(b, 1.1, snapshot("pre_exam"))
    c = led.record_expected("finalize_exam", 2.0, snapshot("study"))
    led.record_delivery(c, 2.1, snapshot("study"))
    summary = led.summary()
    # student_selected -> pre_exam, and pre_exam -> study. The middle answer changes nothing.
    assert summary["ordering_decidable_transitions"] == 2
    assert summary["ordering_transition_agreements"] == 2
    assert summary["out_of_order"] == 0


def test_a_stale_frame_served_at_a_transition_is_caught_as_out_of_order():
    """The real reordering signature: the state had already moved on, and the frame delivered
    there carried the state from before it."""
    led = StreamLedger(stream_id="s-1", arm="cross")
    led.initial_hash = content_hash(snapshot("student_selected"))
    a = led.record_expected("select_topic", 0.0, snapshot("pre_exam"))
    led.record_delivery(a, 0.1, snapshot("pre_exam"))
    b = led.record_expected("finalize_exam", 1.0, snapshot("study"))
    led.record_delivery(b, 1.1, snapshot("pre_exam"))  # stale
    summary = led.summary()
    assert summary["ordering_decidable_transitions"] == 2
    assert summary["out_of_order"] == 1
    assert summary["out_of_order_indices"] == [1]
    assert summary["content_disagreements"] == 1


def test_the_first_event_is_undecidable_when_the_connect_snapshot_was_never_seen():
    """No initial hash means no baseline to transition away from, so the first event cannot be
    counted as ordering evidence."""
    led = StreamLedger(stream_id="s-1", arm="cross")
    idx = led.record_expected("select_topic", 0.0, snapshot("pre_exam"))
    led.record_delivery(idx, 0.1, snapshot("pre_exam"))
    assert led.summary()["ordering_decidable_transitions"] == 0


# --------------------------------------------------------------------------- aggregation


def test_aggregate_splits_by_arm_so_a_relay_failure_is_separable_from_a_bus_failure():
    cross = StreamLedger(stream_id="c", arm="cross")
    same = StreamLedger(stream_id="s", arm="same")
    for led, delivered in ((cross, False), (same, True)):
        for i in range(3):
            idx = led.record_expected("answer", float(i), snapshot())
            if delivered:
                led.record_delivery(idx, i + 0.1, snapshot())
    result = aggregate([cross, same])
    assert result["total"]["delivery_fraction"] == "3/6"
    assert result["by_arm"]["cross"]["delivery_fraction"] == "0/3"
    assert result["by_arm"]["same"]["delivery_fraction"] == "3/3"
    assert result["by_arm"]["cross"]["streams_with_loss"] == 1
    assert result["total"]["ordering_decidable_transitions"] == 0


def test_every_rate_ships_with_its_denominator():
    """MEASUREMENT_PLAN's evidence rule, asserted rather than remembered."""
    led = StreamLedger(stream_id="s", arm="cross")
    for i in range(4):
        idx = led.record_expected("answer", float(i), snapshot())
        if i < 3:
            led.record_delivery(idx, i + 0.1, snapshot())
    total = aggregate([led])["total"]
    assert total["delivery_rate"] == pytest.approx(0.75)
    assert total["delivery_fraction"] == "3/4"


def test_percentiles_return_a_value_that_was_actually_observed():
    """Nearest-rank, not interpolated: at these sample sizes an interpolated p95 is a latency no
    event ever had, and a report that quotes one cannot point at the event behind it."""
    values = [10.0, 20.0, 30.0, 40.0]
    assert ledger_mod.percentile(values, 0.95) in values
    assert ledger_mod.percentile([], 0.5) is None


# --------------------------------------------------------------------------- k6 summary parsing


def k6_summary(**over: Any) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "http_reqs": {"count": 140, "rate": 16.2, "thresholds": {"rate>1": False}},
        "http_req_duration": {
            "p(50)": 103.7,
            "p(95)": 1349.0,
            "p(99)": 1800.0,
            "max": 1900.0,
            "thresholds": {"p(95)<3000": False},
        },
        "http_req_failed": {
            "passes": 0,
            "fails": 140,
            "value": 0.0,
            "thresholds": {"rate<0.01": False},
        },
        "learning_status_4xx": {"count": 0},
        "learning_status_5xx": {"count": 0},
        "learning_answers_submitted": {"count": 100},
        "learning_attendance_blocked": {"count": 0},
        "iterations": {"count": 10},
    }
    metrics.update(over)
    return {"metrics": metrics}


def test_a_false_threshold_means_the_threshold_passed():
    """k6's exported boolean answers 'did this FAIL?'. This is the inversion that would flip
    every pass/fail in the report while leaving every latency correct."""
    parsed = k6_mod.parse_summary(k6_summary())
    assert parsed["threshold_p95_failed"] is False
    assert parsed["threshold_error_rate_failed"] is False

    breached = k6_summary(
        http_reqs={"count": 14, "rate": 8.3, "thresholds": {"rate>1000": True}},
        http_req_duration={"p(95)": 9000.0, "thresholds": {"p(95)<3000": True}},
    )
    assert k6_mod.parse_summary(breached)["threshold_p95_failed"] is True


def test_the_success_fraction_is_reconstructed_from_the_rate_metrics_inverted_counters():
    """`http_req_failed.passes` counts the requests that FAILED - the counter follows the
    metric's boolean, not the request's fate. Reading `passes` as successes would report a
    100%-failed run as a perfect one."""
    parsed = k6_mod.parse_summary(
        k6_summary(
            http_req_failed={
                "passes": 7,
                "fails": 133,
                "value": 0.05,
                "thresholds": {"rate<0.01": True},
            }
        )
    )
    assert parsed["requests_failed"] == 7
    assert parsed["requests_ok"] == 133
    assert parsed["success_fraction"] == "133/140"
    assert parsed["success_rate"] == pytest.approx(133 / 140)


def test_an_absent_counter_is_reported_as_none_not_as_zero():
    """k6 omits a metric that never took a sample. `None` ('the harness did not measure this')
    and `0` ('the harness measured none') are different claims, and the stop rule below treats
    them differently on purpose."""
    summary = k6_summary()
    del summary["metrics"]["learning_status_5xx"]
    assert k6_mod.parse_summary(summary)["status_5xx"] is None


def test_the_cold_warm_split_is_parsed_when_present_and_absent_on_a_burst():
    assert k6_mod.parse_summary(k6_summary())["warm_p95_ms"] is None
    sustained = k6_summary(
        **{
            "http_reqs{phase:cold}": {"count": 154, "rate": 6.05},
            "http_reqs{phase:warm}": {"count": 210, "rate": 8.25},
            "http_req_duration{phase:warm}": {"p(50)": 123.7, "p(95)": 242.8, "p(99)": 547.7},
            "http_req_duration{phase:cold}": {"p(95)": 1900.0},
        }
    )
    parsed = k6_mod.parse_summary(sustained)
    assert parsed["cold_requests"] == 154
    assert parsed["warm_requests"] == 210
    assert parsed["warm_p95_ms"] == pytest.approx(242.8)


def test_only_comparable_trials_share_a_median_group():
    """Two of this sweep's 10-VU bursts ran while the service had scaled to **3** tasks. They are
    10-VU runs, and they are not the same system as the 2-task ones - folding them into one
    median mixes two systems into a number that describes neither. Measured: it moved the 10-VU
    median p95 from 1051 ms to 811 ms before `group_of` existed."""
    assert k6_mod.group_of("burst_10vu_t2") == "10"
    assert k6_mod.group_of("burst_50vu_t3") == "50"
    assert k6_mod.group_of("burst_10vu_3task_a") == "10_3task"
    assert k6_mod.group_of("burst_10vu_3task_b") == "10_3task"
    # ...and the two variants never land in the same bucket.
    assert k6_mod.group_of("burst_10vu_t2") != k6_mod.group_of("burst_10vu_3task_a")


# --------------------------------------------------------------------------- the stop rule


def test_the_stop_rule_passes_a_clean_run():
    assert k6_mod.stop_verdict(k6_summary())[0] is True


def test_the_stop_rule_halts_on_any_5xx():
    """D-455: a rotation-class incident shows up as new-connection database errors, and pushing
    through both corrupts the measurement and delays noticing."""
    ok, reason = k6_mod.stop_verdict(k6_summary(learning_status_5xx={"count": 3}))
    assert ok is False
    assert "D-455" in reason


def test_the_stop_rule_halts_when_the_5xx_counter_is_missing_entirely():
    """An absent counter is not a clean run - it is an unmeasured one, and the sweep must not
    treat 'I did not look' as 'nothing was there'."""
    summary = k6_summary()
    del summary["metrics"]["learning_status_5xx"]
    ok, reason = k6_mod.stop_verdict(summary)
    assert ok is False
    assert "absent" in reason


def test_the_stop_rule_halts_at_the_one_percent_error_rate():
    ok, _ = k6_mod.stop_verdict(
        k6_summary(http_req_failed={"passes": 2, "fails": 138, "value": 0.0143})
    )
    assert ok is False


def test_the_stop_rule_halts_on_a_vacuous_run():
    """A run where every VU was attendance-gated, or answered nothing, posts excellent latency
    and measures nothing. Both anti-vacuity thresholds are stop conditions."""
    assert k6_mod.stop_verdict(k6_summary(learning_attendance_blocked={"count": 4}))[0] is False
    assert k6_mod.stop_verdict(k6_summary(learning_answers_submitted={"count": 0}))[0] is False


def test_a_p95_breach_is_a_result_and_never_stops_the_sweep():
    """D-456 already predicts a breach at the top of the range. Stopping on it would abort the
    sweep exactly where its most interesting data point is."""
    breached = k6_summary(http_req_duration={"p(95)": 4200.0, "thresholds": {"p(95)<3000": True}})
    assert k6_mod.stop_verdict(breached)[0] is True
    assert k6_mod.parse_summary(breached)["threshold_p95_failed"] is True


def test_the_runner_and_this_module_apply_the_same_stop_rule():
    """The rule is duplicated into `run_e1_sweep.sh` as dependency-free inline Python so a live
    staging sweep cannot lose its D-455 guard to an import error. Duplication is only safe while
    something checks the copies agree - this is that something."""
    script = (BENCH / "run_e1_sweep.sh").read_text()
    body = script.split("check_run() {", 1)[1].split("PY\n}", 1)[0]
    body = body.split("<<'PY'\n", 1)[1]
    namespace: dict[str, Any] = {}
    cases = [
        k6_summary(),
        k6_summary(learning_status_5xx={"count": 1}),
        k6_summary(http_req_failed={"passes": 2, "fails": 138, "value": 0.0143}),
        k6_summary(learning_attendance_blocked={"count": 1}),
        k6_summary(learning_answers_submitted={"count": 0}),
        k6_summary(http_req_duration={"p(95)": 9000.0, "thresholds": {"p(95)<3000": True}}),
    ]
    for case in cases:
        path = pathlib.Path("/tmp/_e1_stop_rule_case.json")
        path.write_text(json.dumps(case))
        namespace = {"__name__": "__main__"}
        code = body.replace("sys.argv[1]", repr(str(path)))
        exited = 0
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(code, "run_e1_sweep.sh:check_run", "exec"), namespace)
        except SystemExit as exc:
            exited = exc.code or 0
        runner_ok = exited == 0
        assert runner_ok is k6_mod.stop_verdict(case)[0], (
            f"the runner and k6_summary.stop_verdict disagree on {case['metrics']}"
        )
    path.unlink(missing_ok=True)
