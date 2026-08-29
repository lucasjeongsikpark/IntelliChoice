"""The E5.1 funnel harness attributes a rejection to the stage that actually ended it.

`benchmarks/resume_evidence/05_content_generation/stage_funnel_analysis.py` reconstructs a
per-stage funnel from `question_validation_runs`. Everything it claims rests on one
judgement per row - *which stage rejected this candidate* - reached from evidence written by
four different generations of the pipeline. A parser that silently mis-buckets one era
produces a funnel that still sums to the row count and is wrong, which is the failure mode
these tests exist to make loud.

Pure: fixture rows are literals, no Postgres, no model, no filesystem write. The harness is
loaded by path the same way `test_content_coverage.py` loads `build_content_coverage.py` -
`benchmarks/` is outside the uv workspace on purpose (it is measurement code, not shipped
code), so there is no package to import.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from datetime import UTC, datetime
from typing import Any

import pytest
from intellichoice_curriculum.ai_pipeline import candidate_snapshot
from intellichoice_curriculum.content import load_curriculum
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
    SolutionStep,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
HARNESS = (
    ROOT / "benchmarks" / "resume_evidence" / "05_content_generation" / "stage_funnel_analysis.py"
)


def _load_harness():
    spec = importlib.util.spec_from_file_location("e5_1_stage_funnel_analysis", HARNESS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered before execution because the module defines dataclasses under
    # `from __future__ import annotations`: `dataclasses` resolves field types through
    # `sys.modules[cls.__module__]`, which raises if the module is not there yet.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sfa = _load_harness()


def _row(
    run_id: str = "r1",
    *,
    outcome: str = "rejected",
    stage_results: dict[str, Any] | None = None,
    reasons: list[str] | None = None,
    cost_cents: float = 1.0,
    created_at: datetime | None = None,
    pipeline_run_id: str | None = None,
    question_template_id: str | None = None,
):
    return sfa.RunRow(
        run_id=run_id,
        question_template_id=question_template_id,
        outcome=outcome,
        stage_results=stage_results or {},
        reasons=reasons or [],
        cost_cents=cost_cents,
        created_at=created_at or datetime(2026, 8, 12, 12, 0, tzinfo=UTC),
        pipeline_run_id=pipeline_run_id,
    )


def _item(**overrides: object) -> AuthoredGeneratedItemResponse:
    base: dict[str, object] = dict(
        stem="Solve: what is 2 + 2?",
        option_a="4",
        option_b="5",
        option_c="6",
        option_d="3",
        correct_option="a",
        equation="Eq(x, 2 + 2)",
        hint_ladder=[
            "Think about combining two small groups of objects.",
            "Try counting up from 2 by 2 more.",
            "Add the two numbers together directly.",
        ],
        canonical_solution=SolutionResponse(
            steps=[SolutionStep(step_number=1, explanation="Add the numbers.", expression="2 + 2")],
            final_answer="4",
        ),
        misconception_tags=["off_by_one"],
        estimated_time_seconds=30,
        proposed_difficulty=1,
        difficulty_rationale=(
            "One addition with single-digit whole numbers and no equation to rearrange."
        ),
        required_prerequisites=["single-digit addition"],
    )
    base.update(overrides)
    return AuthoredGeneratedItemResponse(**base)  # type: ignore[arg-type]


def _snapshot(item: AuthoredGeneratedItemResponse, **overrides: object) -> dict[str, Any]:
    """Built by the pipeline's own `candidate_snapshot`, never by hand - see
    `test_the_snapshot_contract_is_the_pipelines_own`."""
    snap = candidate_snapshot(
        item,
        topic_id="linear_equations",
        skill_id="linear_both_sides",
        requested_difficulty=1,
        seed=1,
        generator_model_id="model-x",
        planned_template_id="authored-linear_equations-d1-1",
    )
    snap.update(overrides)
    return snap


# --- stage attribution, one case per era -------------------------------------------


@pytest.mark.parametrize(
    ("stage_results", "reasons", "expected", "basis"),
    [
        # Design pre-stage gave up after its attempt budget (D-200).
        (
            {"equation_design": {"passed": False, "attempts": ["no positive whole root"] * 3}},
            ["equation design failed after 3 attempts"],
            "design",
            "stage_evidence",
        ),
        # Same stage, but every attempt was refused by the breaker - a skip, not a verdict
        # (D-199). Recomputed from the recorded attempts, not from the prose.
        (
            {
                "equation_design": {
                    "passed": False,
                    "attempts": ["circuit_open: call failed: Bedrock circuit breaker is open"] * 3,
                }
            },
            ["equation design never reached a model: circuit_open: call failed"],
            "circuit_open",
            "stage_evidence",
        ),
        # `equation_design` also appears with `passed: true` on candidates that got past it,
        # purely as the D-294 cost record. That must never read as a design failure.
        (
            {
                "equation_design": {"passed": True, "cost_cents": 1.26},
                "deterministic_gate": {"passed": False, "failures": ["hint_ladder[1] leaks"]},
            },
            ["hint_ladder[1] leaks the correct answer text verbatim"],
            "validation",
            "stage_evidence",
        ),
        # Generator failure with D-243's request record.
        (
            {"generator_request": {"planned_template_id": "x", "provider_error": "boom"}},
            ["authored generator call failed: structured output still invalid"],
            "generator",
            "stage_evidence",
        ),
        # Generator stage, but the breaker refused - attributed by what happened.
        (
            {"generator_request": {"planned_template_id": "x"}},
            ["authored generator call failed: Bedrock circuit breaker is open"],
            "circuit_open",
            "stage_evidence",
        ),
        (
            {"deterministic_gate": {"passed": True}, "deduplication": {"passed": False}},
            ["duplicate rendered_question (exact text match)"],
            "dedup",
            "stage_evidence",
        ),
        # Solver and judge write their readings whether they pass or fail, so there is no
        # `passed` flag to test and the prose is the only signal.
        (
            {
                "deterministic_gate": {"passed": True},
                "deduplication": {"passed": True},
                "solver_a": {"selected_option": "a"},
                "solver_b": {"selected_option": "c"},
            },
            ["independent solver disagreement: solver_a='a' solver_b='c' declared='d'"],
            "solver",
            "stage_evidence",
        ),
        # Lower-case "solver a" is what the pipeline writes; matching must not be
        # case-sensitive against the literal `A`/`B` in the message.
        (
            {"deterministic_gate": {"passed": True}, "deduplication": {"passed": True}},
            ["solver A call failed: model hit max_output_tokens=1200"],
            "solver",
            "reason_text",
        ),
        (
            {
                "deterministic_gate": {"passed": True},
                "deduplication": {"passed": True},
                "solver_a": {"selected_option": "a"},
                "solver_b": {"selected_option": "a"},
                "judge": {"is_ambiguous": True},
            },
            ["judge flagged ambiguity: two readings"],
            "judge",
            "stage_evidence",
        ),
        # The pre-D-246 wording of a judge rejection that is no longer a rejection at all.
        (
            {
                "deterministic_gate": {"passed": True},
                "deduplication": {"passed": True},
                "judge": {"hint_reveals_answer": True},
            },
            ["judge found a hint gives the answer away: hint 2 states the equation"],
            "judge",
            "stage_evidence",
        ),
        (
            {
                "deterministic_gate": {"passed": True},
                "deduplication": {"passed": True},
                "judge": {"is_ambiguous": False},
                "difficulty": {"decision": "rejected"},
            },
            ["difficulty disagreement: generator proposed 4"],
            "difficulty",
            "stage_evidence",
        ),
        # 2026-08-06: no stage evidence at all, and a stage that no longer exists.
        (
            {},
            ["narrative dressing call failed: session budget of 40.0 cents would be exceeded"],
            "budget",
            "reason_text",
        ),
        (
            {},
            ["authored generator call failed: model hit max_output_tokens=400"],
            "generator",
            "reason_text",
        ),
    ],
)
def test_attribution_covers_every_recorded_era(
    stage_results: dict[str, Any], reasons: list[str], expected: str, basis: str
) -> None:
    attribution = sfa.attribute(_row(stage_results=stage_results, reasons=reasons))
    assert attribution.stage == expected
    assert attribution.basis == basis


def test_a_passing_row_is_accepted_not_rejected() -> None:
    attribution = sfa.attribute(
        _row(outcome="pending", stage_results={"deterministic_gate": {"passed": True}})
    )
    assert attribution.stage == "accepted"
    assert attribution.basis == "accepted"


def test_the_older_gate_shape_with_an_empty_failure_list_still_reads_as_passed() -> None:
    """2026-08-06 rows write `{"passed": true, "failures": []}` where later ones write
    `{"passed": true, "checks": [...]}`. Reading the empty list as a failure would move
    every solver rejection of that era into `validation`."""
    row = _row(
        stage_results={
            "deterministic_gate": {"passed": True, "failures": []},
            "deduplication": {"passed": True},
            "solver_a": {"selected_option": "a"},
            "solver_b": {"selected_option": "c"},
        },
        reasons=["independent solver disagreement: solver_a='a' solver_b='c' declared='d'"],
    )
    assert sfa.attribute(row).stage == "solver"


def test_an_unrecognisable_rejection_is_reported_not_guessed() -> None:
    attribution = sfa.attribute(_row(stage_results={}, reasons=["something nobody has seen"]))
    assert attribution.stage == "unattributed"


# --- the funnel closes -------------------------------------------------------------


def test_the_funnel_accounts_for_every_row() -> None:
    rows = [
        _row("a", stage_results={"equation_design": {"passed": False, "attempts": ["x"]}}),
        _row("b", stage_results={"generator_request": {}}, reasons=["authored generator call fa"]),
        _row("c", stage_results={"deterministic_gate": {"passed": False, "failures": ["f"]}}),
        _row("d", stage_results={"deduplication": {"passed": False}}),
        _row("e", outcome="pending"),
        _row("f", outcome="pending"),
        _row("g", stage_results={}, reasons=["session budget of 40.0 cents would be exceeded"]),
    ]
    attributions = {r.run_id: sfa.attribute(r) for r in rows}
    funnel = sfa.build_funnel(rows, attributions)
    by_stage = {s.stage: s for s in funnel}

    assert by_stage["design"].reached == 7
    assert by_stage["design"].rejected == 1
    assert by_stage["generator"].reached == 6
    # The budget skip leaves the funnel with the generator, so validation sees 4, not 5.
    assert by_stage["validation"].reached == 4
    assert by_stage["dedup"].reached == 3
    assert by_stage["difficulty"].reached == 2

    accounted = (
        sum(s.rejected for s in funnel)
        + sum(1 for a in attributions.values() if a.stage in sfa.SKIP_STAGES)
        + sum(1 for a in attributions.values() if a.stage == "accepted")
        + sum(1 for a in attributions.values() if a.stage == "unattributed")
    )
    assert accounted == len(rows)


def test_stage_spend_is_attributed_to_the_stage_that_ended_the_candidate() -> None:
    rows = [
        _row("a", stage_results={"deterministic_gate": {"passed": False}}, cost_cents=2.5),
        _row("b", stage_results={"deterministic_gate": {"passed": False}}, cost_cents=1.5),
        _row("c", outcome="pending", cost_cents=9.0),
    ]
    funnel = sfa.build_funnel(rows, {r.run_id: sfa.attribute(r) for r in rows})
    assert next(s for s in funnel if s.stage == "validation").cost_cents == pytest.approx(4.0)


# --- snapshot reconstruction -------------------------------------------------------


def test_the_snapshot_contract_is_the_pipelines_own() -> None:
    """The re-gate rebuilds the Generator's response out of a `candidate_snapshot`, and
    `AuthoredGeneratedItemResponse` is `extra="forbid"` - so a field added to the snapshot
    breaks reconstruction for every future row unless the harness is told about it. Built
    here with the pipeline's own `candidate_snapshot`, so that day fails loudly here first.
    """
    item = _item()
    rebuilt = sfa.item_from_snapshot(_snapshot(item))
    assert rebuilt.model_dump() == item.model_dump()


def test_the_earlier_snapshot_shape_without_attempt_still_rebuilds() -> None:
    snapshot = _snapshot(_item())
    del snapshot["attempt"]
    del snapshot["repaired_defects"]
    assert sfa.item_from_snapshot(snapshot).stem == "Solve: what is 2 + 2?"


def test_a_snapshot_that_is_not_an_item_is_a_reported_error_not_a_crash() -> None:
    row = _row(stage_results={"candidate_snapshot": {"stem": "only a stem"}})
    result = sfa.regate(row, sfa.attribute(row), load_curriculum())
    assert result is not None
    assert result.error is not None
    assert result.would_reject is False


def test_a_row_without_a_snapshot_is_skipped_rather_than_invented() -> None:
    row = _row(stage_results={"equation_design": {"passed": False, "attempts": ["x"]}})
    assert sfa.regate(row, sfa.attribute(row), load_curriculum()) is None


# --- the overlap counterfactual ----------------------------------------------------


def test_a_clean_item_rejected_by_a_paid_stage_counts_as_a_unique_catch() -> None:
    row = _row(
        stage_results={
            "deterministic_gate": {"passed": True},
            "deduplication": {"passed": True},
            "solver_a": {"selected_option": "a"},
            "solver_b": {"selected_option": "c"},
            "candidate_snapshot": _snapshot(_item()),
        },
        reasons=["independent solver disagreement: solver_a='a' solver_b='c' declared='d'"],
    )
    result = sfa.regate(row, sfa.attribute(row), load_curriculum())
    assert result is not None and result.error is None
    assert result.stage == "solver"
    assert result.would_reject is False

    report = sfa.overlap_report([result])
    assert report["paid_stage_rejections_with_snapshot"] == 1
    assert report["unique_catch_by_paid_stage"] == 1
    assert report["deterministic_gate_would_also_reject"] == 0


def test_an_item_the_free_gate_can_catch_counts_as_overlap() -> None:
    """A leaked answer in the hint ladder is caught by the pre-gate string check, which
    costs nothing - so a paid stage rejecting this item was paid to re-find something free.
    """
    leaky = _item(
        hint_ladder=[
            "Think about combining two small groups of objects.",
            "Try counting up from 2 by 2 more.",
            "The answer is 4.",
        ]
    )
    row = _row(
        stage_results={
            "deterministic_gate": {"passed": True},
            "deduplication": {"passed": True},
            "judge": {"is_ambiguous": True},
            "candidate_snapshot": _snapshot(leaky),
        },
        reasons=["judge flagged ambiguity: unclear"],
    )
    result = sfa.regate(row, sfa.attribute(row), load_curriculum())
    assert result is not None and result.error is None
    assert result.stage == "judge"
    assert result.would_reject is True

    report = sfa.overlap_report([result])
    assert report["deterministic_gate_would_also_reject"] == 1
    assert report["by_stage"]["judge"]["overlap_rate"] == pytest.approx(1.0)


def test_the_hint_leak_precheck_is_part_of_the_deterministic_stage() -> None:
    leaky = _item(hint_ladder=["A hint.", "Another hint.", "The answer is 4."])
    assert sfa.hint_leak_failures(leaky)
    assert not sfa.hint_leak_failures(_item())


def test_overlap_only_counts_the_paid_stages() -> None:
    """A validation-stage rejection is not part of the counterfactual - the deterministic
    gate catching what the deterministic gate caught says nothing about paid stages."""
    results = [
        sfa.RegateResult("v", "validation", True, ["f"], ["answer leakage"], None),
        sfa.RegateResult("s", "solver", True, ["f"], ["answer leakage"], None),
    ]
    report = sfa.overlap_report(results)
    assert report["paid_stage_rejections_with_snapshot"] == 1


# --- strata, runs, eras -------------------------------------------------------------


def test_strata_prefer_the_snapshot_then_the_request_then_the_template() -> None:
    templates = {"t1": sfa.Strata("from_template", "skill_t", 5)}
    snapshot_row = _row(
        stage_results={
            "candidate_snapshot": {
                "topic_id": "from_snapshot",
                "skill_id": "skill_s",
                "requested_difficulty": 3,
            }
        },
        question_template_id="t1",
    )
    request_row = _row(
        stage_results={
            "generator_request": {
                "topic_id": "from_request",
                "skill_id": "skill_r",
                "requested_difficulty": 2,
            }
        }
    )
    template_row = _row(outcome="pending", question_template_id="t1")
    bare_row = _row(stage_results={"equation_design": {"passed": False}})

    assert sfa.strata_of(snapshot_row, templates).topic_id == "from_snapshot"
    assert sfa.strata_of(request_row, templates).requested_difficulty == 2
    assert sfa.strata_of(template_row, templates).topic_id == "from_template"
    assert sfa.strata_of(bare_row, templates) == sfa.Strata(None, None, None)


def test_the_warm_up_toll_excludes_rows_with_no_run_id() -> None:
    rows = [
        _row("a", pipeline_run_id="run-1", created_at=datetime(2026, 8, 12, 1, tzinfo=UTC)),
        _row(
            "b",
            outcome="pending",
            pipeline_run_id="run-1",
            created_at=datetime(2026, 8, 12, 2, tzinfo=UTC),
        ),
        _row("c", created_at=datetime(2026, 8, 12, 3, tzinfo=UTC)),
    ]
    toll = sfa.warm_up_toll(rows, {r.run_id: sfa.attribute(r) for r in rows})
    assert toll["runs_with_an_identifier"] == 1
    assert toll["candidates_counted"] == 2
    assert toll["candidates_excluded_no_run_id"] == 1
    positions = {b["position"]: b for b in toll["by_position"]}
    assert positions["1"]["rejected"] == 1
    assert positions["2"]["rejected"] == 0


def test_per_run_breakdown_groups_null_run_ids_into_one_bucket() -> None:
    rows = [
        _row("a", pipeline_run_id="run-1", cost_cents=2.0),
        _row("b", outcome="pending", pipeline_run_id="run-1", cost_cents=4.0),
        _row("c", cost_cents=1.0),
    ]
    breakdown = sfa.per_run_breakdown(rows, {r.run_id: sfa.attribute(r) for r in rows})
    by_id = {entry["pipeline_run_id"]: entry for entry in breakdown}
    assert by_id["run-1"]["candidates"] == 2
    assert by_id["run-1"]["acceptance_rate"] == pytest.approx(0.5)
    assert by_id["run-1"]["cost_cents_per_accepted"] == pytest.approx(6.0)
    assert by_id["(unidentified)"]["candidates"] == 1
    assert by_id["(unidentified)"]["cost_cents_per_accepted"] is None


def test_era_coverage_counts_each_marker() -> None:
    rows = [
        _row("a", stage_results={"candidate_snapshot": {"stem": "s"}}),
        _row("b", stage_results={}, pipeline_run_id="run-1"),
    ]
    counts = {marker: n for marker, n, _ in sfa.era_coverage(rows)}
    assert counts["`candidate_snapshot` present"] == 1
    assert counts["`stage_results` empty"] == 1
    assert counts["`pipeline_run_id` present"] == 1


# --- failure families ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("reason", "family"),
    [
        ("hint_ladder[2] leaks the correct answer text verbatim", "answer leakage"),
        (
            "more than one option matches the derived value answer (2/3,)",
            ("answer key: several options match"),
        ),
        (
            "SymPy-solved answer 7 does not match declared correct option",
            ("answer key: derived answer disagrees"),
        ),
        ("a sentence has 32 words, exceeding the 30-word readability cap", "readability"),
        ("final_answer contains '*', which a student sees as programme", "math notation"),
        ("equation is missing - every item must model its question", "equation unusable"),
        ("Bedrock circuit breaker is open", "other"),
    ],
)
def test_failure_families_bucket_the_pipelines_own_prose(reason: str, family: str) -> None:
    assert sfa.failure_family(reason) == family


# --- reconciliation ------------------------------------------------------------------


def test_reconciliation_says_so_when_the_slice_is_smaller_than_the_recorded_figure() -> None:
    note = sfa.reconciliation_note([_row("a"), _row("b")])
    assert "1,184" in note
    assert "does not apply to this slice" in note
