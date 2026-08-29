"""E4's permanent lane: the synthetic-history generator and the benchmark's scorer.

`benchmarks/resume_evidence/04_memory/` holds the generator that plants ground truth into
a synthetic `learning_events` corpus and the scorer that grades what consolidation did
with it. Both are measurement code and neither is importable (`benchmarks/` is outside the
uv workspace on purpose), so they are loaded by path here - the same way
`packages/curriculum/tests/test_stage_funnel_analysis.py` loads E5.1's harness and
`packages/observability/tests/test_pii_probe_corpus.py` loads E6.1's.

**What these tests are for.** A measurement is only worth its reproducibility: a corpus
that drifts between runs makes every recorded number in `E4_REPORT.md` unverifiable, and a
scorer with a quiet logic bug makes them wrong in a way no re-run would reveal. So this
module covers exactly two things:

1. the generator is **deterministic** and **prefix-stable** in `students` - the property
   that lets E4.2's 25-student real-model arm run the same students E4.1's 1,000-student
   mock arm ran;
2. the scorer's pure logic - it agrees with the ground truth when it should and disagrees
   when it should, including the two cases that are easy to get backwards (an expectation
   of *no* fact, and a served-fact check that must fail on a stale fact of the wrong
   polarity).

Pure and offline: no Docker, no Postgres, no network, no model call. The database-backed
half of the benchmark is exercised by running the benchmark, not from here.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
BENCH_DIR = ROOT / "benchmarks" / "resume_evidence" / "04_memory"


def _load(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, BENCH_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gen = _load("e4_synthetic_histories_test", "synthetic_histories.py")


# --- the generator's event vocabulary must not drift from the product's -------------------


def test_event_type_constants_match_product_vocabulary() -> None:
    """The generator restates the six event-type strings rather than importing them, so
    that its output cannot become correct-by-construction against the renderer it feeds.
    That is only safe while the two really are equal - which is what this asserts. A
    product rename now fails here instead of silently producing a corpus the consolidation
    worker renders as bare `event_type` strings with no signal in them.
    """
    from intellichoice_memory import events as product

    assert gen.ANSWER_SUBMITTED == product.ANSWER_SUBMITTED
    assert gen.INTERVENTION_CHOSEN == product.INTERVENTION_CHOSEN
    assert gen.STUDY_OUTCOME == product.STUDY_OUTCOME
    assert gen.CHAT_TURN == product.CHAT_TURN
    assert gen.EXAM_FINALIZED == product.EXAM_FINALIZED
    assert gen.LEARNING_GAIN_COMPUTED == product.LEARNING_GAIN_COMPUTED


def test_outcome_labels_match_product_labels() -> None:
    from learning_api.services import study_outcomes

    assert gen.OUTCOME_UNRESOLVED == study_outcomes.UNRESOLVED
    assert gen.OUTCOME_INDEPENDENT_CORRECT == study_outcomes.INDEPENDENT_CORRECT
    assert gen.OUTCOME_CORRECT_AFTER_HINT == study_outcomes.CORRECT_AFTER_HINT


def test_planted_scenarios_render_the_signal_they_claim_to_plant() -> None:
    """The planted events must actually *say* the thing the scenario depends on once the
    product's own renderer has turned them into prose - that rendering is the only part of
    an event a consolidating model ever sees.

    Without this the generator could plant a perfectly structured `unresolved` payload that
    renders to something carrying no negative signal at all, and every scenario would score
    as a model failure when the fault was in the fixture.
    """
    from intellichoice_memory.events import render_event_summary

    config = gen.CorpusConfig(students=4)
    plan = next(p for p in gen.plan_corpus(config) if p.student_class == gen.CLASS_STANDARD)

    weak_slot = next(f.skill_slot for f in plan.planted if f.scenario == gen.SCENARIO_REPEATED_WEAK)
    weak_events = [
        e
        for e in plan.events
        if e.planted_for == gen.SCENARIO_REPEATED_WEAK and e.skill_slot == weak_slot
    ]
    assert len(weak_events) == 4
    for event in weak_events:
        payload = dict(event.payload)
        payload["target_skill_id"] = "skill-x"
        payload.pop("target_skill_slot", None)
        assert "unresolved" in render_event_summary(event.event_type, payload)

    strength_slot = next(
        f.skill_slot for f in plan.planted if f.scenario == gen.SCENARIO_REPEATED_STRENGTH
    )
    strength_events = [
        e
        for e in plan.events
        if e.planted_for == gen.SCENARIO_REPEATED_STRENGTH and e.skill_slot == strength_slot
    ]
    assert len(strength_events) == 4
    for event in strength_events:
        rendered = render_event_summary(event.event_type, event.payload)
        assert "correctly" in rendered and "incorrectly" not in rendered


# --- determinism and prefix stability ------------------------------------------------------


def test_corpus_is_deterministic_for_a_fixed_seed() -> None:
    config = gen.CorpusConfig(students=12, seed=4242)
    assert gen.corpus_fingerprint(gen.plan_corpus(config)) == gen.corpus_fingerprint(
        gen.plan_corpus(config)
    )


def test_a_different_seed_produces_a_different_corpus() -> None:
    a = gen.corpus_fingerprint(gen.plan_corpus(gen.CorpusConfig(students=12, seed=1)))
    b = gen.corpus_fingerprint(gen.plan_corpus(gen.CorpusConfig(students=12, seed=2)))
    assert a != b


def test_students_are_prefix_stable_in_n() -> None:
    """Student `i` must be the same student whether 8 or 64 were planned.

    This is the property E4.2 depends on: its 25-student real-model arm is a subset of the
    1,000-student corpus the mock arm measured, so the two arms' compression and token
    numbers are comparable rather than merely similar. It holds because each student draws
    from its own `Random(f"{seed}:{index}")` and its class is a function of its index -
    a single shared generator, or a shuffled class assignment, would break it silently.
    """
    small = gen.plan_corpus(gen.CorpusConfig(students=8, seed=99))
    large = gen.plan_corpus(gen.CorpusConfig(students=64, seed=99))
    assert gen.corpus_fingerprint(small) == gen.corpus_fingerprint(large[:8])


def test_stratified_subset_excludes_tail_classes_and_preserves_order() -> None:
    plans = gen.plan_corpus(gen.CorpusConfig(students=200))
    subset = gen.stratified_subset(plans, 25)
    assert len(subset) == 25
    assert all(p.student_class == gen.CLASS_STANDARD for p in subset)
    assert [p.external_id for p in subset] == sorted(p.external_id for p in subset)


def test_every_standard_student_carries_one_of_each_scenario_on_its_own_skill() -> None:
    """Two scenarios on one skill would interfere: a fact's natural key is
    `(student, fact_type, skill_id)`, so a shared skill lets one scenario's candidate
    reconfirm or contradict another's and neither outcome is attributable.
    """
    for plan in gen.plan_corpus(gen.CorpusConfig(students=40)):
        if plan.student_class != gen.CLASS_STANDARD:
            assert plan.planted == ()
            continue
        scenarios = [f.scenario for f in plan.planted]
        assert sorted(scenarios) == sorted(s for s in gen.SCENARIOS if s != gen.SCENARIO_IRRELEVANT)
        slots = [f.skill_slot for f in plan.planted]
        assert len(set(slots)) == len(slots)
        assert not set(slots) & set(plan.filler_slots)


def test_mastery_rows_are_planted_only_for_the_two_conflict_scenarios() -> None:
    """The AUD-L-13 screen abstains when there is no mastery row, so a stray mastery row on
    another scenario's skill would silently start screening that scenario too.
    """
    for plan in gen.plan_corpus(gen.CorpusConfig(students=25)):
        if plan.student_class != gen.CLASS_STANDARD:
            continue
        conflict_slots = {
            f.skill_slot
            for f in plan.planted
            if f.scenario
            in (gen.SCENARIO_MASTERY_CONFLICT_WEAK, gen.SCENARIO_MASTERY_CONFLICT_STRENGTH)
        }
        assert {slot for slot, _ in plan.mastery} == conflict_slots


def test_mastery_scores_sit_on_the_intended_side_of_the_weak_threshold() -> None:
    from intellichoice_shared.mastery_policy import WEAK_SKILL_THRESHOLD

    plan = next(p for p in gen.plan_corpus(gen.CorpusConfig(students=4)) if p.planted)
    by_scenario = {f.scenario: f.skill_slot for f in plan.planted}
    scores = dict(plan.mastery)
    assert scores[by_scenario[gen.SCENARIO_MASTERY_CONFLICT_WEAK]] >= WEAK_SKILL_THRESHOLD
    assert scores[by_scenario[gen.SCENARIO_MASTERY_CONFLICT_STRENGTH]] < WEAK_SKILL_THRESHOLD


def test_under_evidenced_scenario_stays_below_both_evidence_thresholds() -> None:
    """The scenario is only meaningful while it is genuinely under-evidenced - if a
    generator change gave it a third event or a second session it would quietly become a
    duplicate of `repeated_weak` and would score 100% for the wrong reason.
    """
    from intellichoice_memory.consolidation import MIN_EVIDENCE_EVENTS, MIN_EVIDENCE_SESSIONS

    for plan in gen.plan_corpus(gen.CorpusConfig(students=30)):
        if not plan.planted:
            continue
        slot = next(
            f.skill_slot for f in plan.planted if f.scenario == gen.SCENARIO_UNDER_EVIDENCED
        )
        events = [
            e
            for e in plan.events
            if e.planted_for == gen.SCENARIO_UNDER_EVIDENCED and e.skill_slot == slot
        ]
        assert len(events) < MIN_EVIDENCE_EVENTS
        assert len({(e.window, e.session_index) for e in events}) < MIN_EVIDENCE_SESSIONS


def test_repeated_scenarios_clear_both_evidence_thresholds() -> None:
    from intellichoice_memory.consolidation import MIN_EVIDENCE_EVENTS, MIN_EVIDENCE_SESSIONS

    for scenario in (gen.SCENARIO_REPEATED_WEAK, gen.SCENARIO_REPEATED_STRENGTH):
        for plan in gen.plan_corpus(gen.CorpusConfig(students=20)):
            if not plan.planted:
                continue
            slot = next(f.skill_slot for f in plan.planted if f.scenario == scenario)
            events = [e for e in plan.events if e.planted_for == scenario and e.skill_slot == slot]
            assert len(events) >= MIN_EVIDENCE_EVENTS
            assert len({(e.window, e.session_index) for e in events}) >= MIN_EVIDENCE_SESSIONS


def test_polarity_flip_regression_is_fully_evidenced() -> None:
    """The flip scenario exists to isolate ONE mechanism (does a later contradicting signal
    reach the tutor?). If its regression events were under-evidenced, a failure would be
    ambiguous between "the contradiction did not demote" and "the new fact never cleared the
    bar" - and an ambiguous measurement is not a measurement.
    """
    from intellichoice_memory.consolidation import MIN_EVIDENCE_EVENTS, MIN_EVIDENCE_SESSIONS

    for plan in gen.plan_corpus(gen.CorpusConfig(students=20)):
        if not plan.planted:
            continue
        slot = next(f.skill_slot for f in plan.planted if f.scenario == gen.SCENARIO_POLARITY_FLIP)
        regression = [
            e
            for e in plan.events
            if e.planted_for == gen.SCENARIO_POLARITY_FLIP
            and e.skill_slot == slot
            and e.event_type == gen.STUDY_OUTCOME
        ]
        assert len(regression) >= MIN_EVIDENCE_EVENTS
        assert len({e.session_index for e in regression}) >= MIN_EVIDENCE_SESSIONS
        assert {e.window for e in regression} == {plan_windows(plan) - 1}


def plan_windows(plan) -> int:
    return max(e.window for e in plan.events) + 1


def test_tail_classes_exceed_the_call_cap_and_standard_students_do_not() -> None:
    """The heavy/extreme classes exist to exercise `_MAX_CALLS_PER_STUDENT`; if their
    per-window volume slipped under the packing threshold they would stop measuring the
    thing they were added for, and `events_dropped` would read 0 for a reason nobody
    recorded.
    """
    from intellichoice_memory.consolidation import _MAX_CALLS_PER_STUDENT, _MAX_EVENT_CHARS_PER_CALL

    # ~280 serialised chars per event summary on this corpus; deliberately generous so the
    # assertion fails on a real change rather than on estimate noise.
    events_per_call = _MAX_EVENT_CHARS_PER_CALL // 320
    cap = events_per_call * _MAX_CALLS_PER_STUDENT
    plans = gen.plan_corpus(gen.CorpusConfig(students=250))
    tails = [p for p in plans if p.student_class != gen.CLASS_STANDARD]
    assert tails, "the corpus must contain tail students"
    for plan in tails:
        assert len(plan.events_for_window(0)) > cap
    for plan in (p for p in plans if p.student_class == gen.CLASS_STANDARD):
        assert len(plan.events_for_window(0)) < cap


def test_no_chat_message_in_the_pool_matches_the_pii_denylist() -> None:
    """The corpus writes chat text into `tutor_chat_messages`, which consolidation joins
    into the one Bedrock payload that carries student prose. A pool sentence that tripped
    `contains_pii_pattern` would both defeat the point of the pool and quietly change what
    the PII screen is measured against.
    """
    from intellichoice_shared.pii_redaction import contains_pii_pattern

    for message in gen._CHAT_MESSAGES:
        assert not contains_pii_pattern(message)


def test_manifest_round_trips_with_its_configuration(tmp_path: pathlib.Path) -> None:
    import json

    config = gen.CorpusConfig(students=6, seed=7)
    plans = gen.plan_corpus(config)
    path = tmp_path / "manifest.jsonl"
    gen.write_manifest(path, config, plans)
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["record"] == "corpus_header"
    assert lines[0]["config"]["seed"] == 7
    assert len(lines) == len(plans) + 1
    assert all(line["student_external_id"].startswith("bench-student-") for line in lines[1:])


# --- the scorer's pure logic ------------------------------------------------------------------


bench = _load("e4_memory_benchmark_test", "memory_benchmark.py")


def _fact(fact_type: str, polarity: str, status: str, confidence: float = 0.6):
    return bench.FactObservation(
        fact_type=fact_type,
        skill_id="skill-1",
        polarity=polarity,
        status=status,
        confidence=confidence,
        evidence_event_ids=["e1", "e2", "e3"],
        evidence_resolved=3,
        evidence_total=3,
    )


def _expectation(**overrides):
    base = {
        "scenario": "repeated_weak",
        "skill_id": "skill-1",
        "expected_fact_type": "weak_skill",
        "expected_polarity": "negative",
        "expected_status": "active",
        "expected_served": True,
    }
    base.update(overrides)
    return base


def test_scorer_accepts_the_expected_status_and_served_fact() -> None:
    fact = _fact("weak_skill", "negative", "active")
    scored = bench.score_expectations([_expectation()], {"skill-1": [fact]}, {"skill-1": fact})[0]
    assert scored.status_correct and scored.served_correct


def test_scorer_rejects_a_fact_stuck_in_the_wrong_lifecycle_state() -> None:
    fact = _fact("weak_skill", "negative", "provisional")
    scored = bench.score_expectations([_expectation()], {"skill-1": [fact]}, {"skill-1": None})[0]
    assert not scored.status_correct
    assert not scored.served_correct
    assert scored.observed_status == "provisional"


def test_scorer_rejects_a_served_fact_of_the_wrong_polarity() -> None:
    """The `polarity_flip` case, and the one most easily scored wrong: the *right* fact
    exists in the *right* state, and the read path still hands the tutor the stale opposite
    one. Status and served are judged separately precisely so this shows up as what it is.
    """
    correct = _fact("weak_skill", "negative", "active", confidence=0.6)
    stale = _fact("strength", "positive", "active", confidence=0.7)
    scored = bench.score_expectations(
        [_expectation()], {"skill-1": [correct, stale]}, {"skill-1": stale}
    )[0]
    assert scored.status_correct
    assert not scored.served_correct
    assert scored.served_fact_type == "strength"


def test_scorer_treats_absence_as_correct_when_no_fact_is_expected() -> None:
    """Both mastery-conflict scenarios expect *nothing* to be written, so an empty result is
    the pass and any live fact is the failure - the inverted sense that a scorer written for
    the common case gets backwards.
    """
    scored = bench.score_expectations(
        [
            _expectation(
                scenario="mastery_conflict_weak",
                expected_fact_type=None,
                expected_polarity=None,
                expected_status=None,
                expected_served=False,
            )
        ],
        {},
        {"skill-1": None},
    )[0]
    assert scored.status_correct and scored.served_correct


def test_scorer_fails_when_a_screened_fact_was_written_anyway() -> None:
    fact = _fact("weak_skill", "negative", "active")
    scored = bench.score_expectations(
        [
            _expectation(
                scenario="mastery_conflict_weak",
                expected_fact_type=None,
                expected_polarity=None,
                expected_status=None,
                expected_served=False,
            )
        ],
        {"skill-1": [fact]},
        {"skill-1": fact},
    )[0]
    assert not scored.status_correct
    assert not scored.served_correct


def test_provisional_fact_must_not_be_served() -> None:
    """`under_evidenced`'s whole point: a provisional fact is never returned by
    `top_fact_for_skill`, so `expected_served=False` passes only on `None`.
    """
    scored = bench.score_expectations(
        [
            _expectation(
                scenario="under_evidenced", expected_status="provisional", expected_served=False
            )
        ],
        {"skill-1": [_fact("weak_skill", "negative", "provisional")]},
        {"skill-1": None},
    )[0]
    assert scored.status_correct and scored.served_correct

    served_anyway = bench.score_expectations(
        [
            _expectation(
                scenario="under_evidenced", expected_status="provisional", expected_served=False
            )
        ],
        {"skill-1": [_fact("weak_skill", "negative", "provisional")]},
        {"skill-1": _fact("weak_skill", "negative", "provisional")},
    )[0]
    assert not served_anyway.served_correct


# --- percentiles ---------------------------------------------------------------------------------


def test_percentiles_report_n_and_refuse_to_invent_a_distribution() -> None:
    """A single sample has a median and no deciles. Returning the one value for p10 and p90
    would make a one-student run read like a measured spread, which is exactly the shape of
    over-claim the measurement plan's evidence rules exist to prevent.
    """
    assert bench.percentiles([]) == {"p10": None, "median": None, "p90": None, "n": 0}
    single = bench.percentiles([4.0])
    assert single["median"] == 4.0 and single["p10"] is None and single["n"] == 1
    many = bench.percentiles([float(i) for i in range(1, 101)])
    assert many["n"] == 100
    assert many["p10"] < many["median"] < many["p90"]


def test_metric_rows_carry_numerator_and_denominator_for_every_rate() -> None:
    """The plan's rule - "rates always carry numerator AND denominator" - expressed as a
    property of the CSV rather than as a promise about how it is written.
    """
    summary = {
        "arm": "mock",
        "students": 10,
        "events": {"total": 100, "dropped_over_call_cap": 5, "students_with_drops": 1},
        "calls": {"total": 30, "failed": 0},
        "compression_ratio": {"p10": 1.0, "median": 2.0, "p90": 3.0, "n": 10},
        "scenario_scores": {
            "repeated_weak": {
                "status_correct": 9,
                "served_correct": 8,
                "any_live_fact_on_skill": 10,
                "polarity_match_any": 9,
                "n": 10,
            }
        },
        "provenance": {
            "facts_total": 20,
            "facts_with_evidence_ids": 20,
            "facts_with_all_evidence_resolving_to_this_student": 20,
        },
        "facts_with_no_resolving_evidence": 0,
        "unplanted_extra_live_facts": 3,
        "lifecycle_distribution": {"active": 12, "provisional": 8},
        "input_ceiling": {
            "windows_over_ceiling": 2,
            "windows_total": 30,
            "students_whose_cumulative_history_exceeds_ceiling": 1,
            "windows_with_oversized_existing_fact_payload": 0,
            "max_safe_existing_facts": 21,
        },
        "cost": {
            "measured_cents_total": 1.0,
            "measured_cents_per_student": 0.1,
            "measured_is_real": False,
        },
    }
    rows = bench.summary_to_metric_rows(summary)
    by_metric = {row["metric"]: row for row in rows}
    for metric in (
        "events_dropped_over_call_cap",
        "model_calls_failed",
        "scenario_status_correct:repeated_weak",
        "scenario_served_correct:repeated_weak",
        "scenario_any_fact_on_skill:repeated_weak",
        "scenario_polarity_match:repeated_weak",
        "provenance_all_evidence_resolves",
        "windows_over_32k_input_ceiling",
    ):
        assert by_metric[metric]["numerator"] != ""
        assert by_metric[metric]["denominator"] != ""
    assert "MOCK provider" in by_metric["cost_per_student"]["note"]


def test_mock_cost_rows_are_labelled_as_not_real() -> None:
    """AUD-C-05's rule, enforced where it can actually be broken: the mock arm reports a
    `cost_cents` the gateway computed from `MockBedrockProvider`'s invented token counts. It
    is not a price of anything, and the CSV has to say so on the row itself - a caveat that
    lives only in the report is a caveat that gets separated from the number.
    """
    summary = {
        "arm": "mock",
        "students": 1,
        "events": {"total": 1, "dropped_over_call_cap": 0, "students_with_drops": 0},
        "calls": {"total": 1, "failed": 0},
        "compression_ratio": {"p10": None, "median": 1.0, "p90": None, "n": 1},
        "scenario_scores": {},
        "provenance": {
            "facts_total": 1,
            "facts_with_evidence_ids": 1,
            "facts_with_all_evidence_resolving_to_this_student": 1,
        },
        "facts_with_no_resolving_evidence": 0,
        "unplanted_extra_live_facts": 0,
        "lifecycle_distribution": {"active": 1},
        "input_ceiling": {
            "windows_over_ceiling": 0,
            "windows_total": 1,
            "students_whose_cumulative_history_exceeds_ceiling": 0,
            "windows_with_oversized_existing_fact_payload": 0,
            "max_safe_existing_facts": 21,
        },
        "cost": {
            "measured_cents_total": 9.9,
            "measured_cents_per_student": 9.9,
            "measured_is_real": False,
        },
    }
    rows = {row["metric"]: row for row in bench.summary_to_metric_rows(summary)}
    assert "not a real cost" in rows["cost_total"]["note"]


# --- the real arm's spend guards ------------------------------------------------------------------


def test_run_budget_cannot_be_raised_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """`MEMORY_BENCH_RUN_BUDGET_CENTS` may only tighten the ceiling. A run that can raise
    its own spend limit from the environment has no spend limit - the same reason
    `CHAT_EVAL_RUN_BUDGET_CENTS` clamps with `min` rather than replacing its default.
    """
    monkeypatch.setenv("MEMORY_BENCH_RUN_BUDGET_CENTS", "99999")
    reloaded = _load("e4_memory_benchmark_budget", "memory_benchmark.py")
    assert reloaded.RUN_BUDGET_CENTS == reloaded.RUN_BUDGET_CENTS_HARD == 300.0

    monkeypatch.setenv("MEMORY_BENCH_RUN_BUDGET_CENTS", "50")
    tightened = _load("e4_memory_benchmark_budget_tight", "memory_benchmark.py")
    assert tightened.RUN_BUDGET_CENTS == 50.0


def test_benchmark_refuses_a_database_that_is_not_a_benchmark_database() -> None:
    """The isolation guard. This benchmark TRUNCATEs six tables; pointing it at the dev
    database would delete the e2e and pytest rows that live there, and the failure would be
    silent because a truncated database still produces a perfectly well-formed measurement.
    """
    with pytest.raises(SystemExit):
        bench.resolve_database_url(
            "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"
        )
    with pytest.raises(SystemExit):
        bench.resolve_database_url("")
    ok = "postgresql+asyncpg://u:p@localhost:5432/intellichoice_e4_bench"
    assert bench.resolve_database_url(ok) == ok


def test_pii_probe_texts_trip_the_screen_they_are_probing() -> None:
    """The scripted lane's PII probes are only a test of the screen while the screen would
    actually catch them; a probe string that stopped matching would turn a real assertion
    into a tautology that passes because nothing was ever proposed.
    """
    from intellichoice_shared.pii_redaction import contains_pii_pattern

    for probe in bench._PII_PROBE_TEXTS:
        assert contains_pii_pattern(probe)
