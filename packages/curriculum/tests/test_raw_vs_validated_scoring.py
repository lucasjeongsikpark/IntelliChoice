"""The E5.3 scoring harness: two arms over one run, scored by the same free instrument.

`benchmarks/resume_evidence/05_content_generation/raw_vs_validated_scoring.py` answers one
question - *what would have shipped with no gate, no solvers and no judge* - and the answer
is only worth having if three things hold:

1. a defect the pipeline exists to catch is scored as a defect (and a clean item is not);
2. rebuilding a machine-accepted candidate from what was persisted does not change what any
   deterministic check sees, because four generator fields have no column and are
   substituted;
3. duplication - a property of a *set*, invisible to any per-item gate - is counted with
   the no-threshold signal reported separately from the thresholded one.

Pure: literals only, no Postgres, no model, no filesystem write. The harness is loaded by
path for the same reason `test_stage_funnel_analysis.py` does it - `benchmarks/` is outside
the uv workspace on purpose.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from datetime import UTC, datetime

from intellichoice_curriculum.authored_validation import validate_authored_item
from intellichoice_curriculum.content import load_curriculum
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
    SolutionStep,
)

ROOT = pathlib.Path(__file__).resolve().parents[3]
HARNESS = (
    ROOT
    / "benchmarks"
    / "resume_evidence"
    / "05_content_generation"
    / "raw_vs_validated_scoring.py"
)


def _load_harness():
    spec = importlib.util.spec_from_file_location("e5_3_raw_vs_validated_scoring", HARNESS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered before execution: the module defines dataclasses under
    # `from __future__ import annotations`, and `dataclasses` resolves field types through
    # `sys.modules[cls.__module__]`.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rvv = _load_harness()
CURRICULUM = load_curriculum()


def _item(**overrides: object) -> AuthoredGeneratedItemResponse:
    base: dict[str, object] = dict(
        stem="Solve for x: 4x + 6 = 26. What is the value of x?",
        option_a="5",
        option_b="6",
        option_c="8",
        option_d="4",
        correct_option="a",
        equation="Eq(4*x + 6, 26)",
        hint_ladder=[
            "What is being added to the term with x?",
            "Undo the addition on both sides first.",
            "Divide both sides by the coefficient of x.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1, explanation="Subtract 6 from both sides.", expression="4*x = 20"
                ),
                SolutionStep(
                    step_number=2, explanation="Divide both sides by 4.", expression="x = 5"
                ),
            ],
            final_answer="5",
        ),
        misconception_tags=["forgets_to_undo_addition"],
        estimated_time_seconds=90,
        proposed_difficulty=2,
        difficulty_rationale=(
            "Two operations have to be undone in order, with a coefficient on the variable."
        ),
        required_prerequisites=["inverse operations", "whole-number division"],
        reasoning="Chose small whole numbers so the solution is exact.",
    )
    base.update(overrides)
    return AuthoredGeneratedItemResponse(**base)  # type: ignore[arg-type]


def _candidate(
    item: AuthoredGeneratedItemResponse,
    *,
    run_id: str = "r1",
    accepted: bool = False,
    skill_id: str = "linear_two_step",
    difficulty: int = 2,
    position: int = 1,
) -> object:
    return rvv.Candidate(
        run_id=run_id,
        source="persisted" if accepted else "snapshot",
        accepted=accepted,
        topic_id="linear_equations",
        skill_id=skill_id,
        requested_difficulty=difficulty,
        stored_difficulty=difficulty if accepted else None,
        question_template_id="authored-linear_equations-d2-1" if accepted else None,
        cost_cents=3.5,
        created_at=datetime(2026, 8, 29, 12, 0, tzinfo=UTC),
        position=position,
        pipeline_reasons=[],
        item=item,
    )


# --- 1. the instrument separates a defect from a clean item --------------------------


def test_a_clean_item_scores_no_defect_family() -> None:
    score = rvv.score_candidate(_candidate(_item()), CURRICULUM)
    assert score.error is None
    assert score.families == ()
    assert not score.defective


def test_a_corrupted_answer_key_is_the_family_d276_measured() -> None:
    """D-276's finding is that this defect passes both blind solvers and the judge. The raw
    arm is only meaningful if the free instrument still names it."""
    score = rvv.score_candidate(_candidate(_item(correct_option="c")), CURRICULUM)
    assert "answer key: derived answer disagrees" in score.families
    assert score.defective


def test_a_hint_that_states_the_answer_is_scored_as_leakage() -> None:
    leaky = _item(
        hint_ladder=[
            "What is being added to the term with x?",
            "Undo the addition on both sides first.",
            "The answer is 5.",
        ]
    )
    score = rvv.score_candidate(_candidate(leaky), CURRICULUM)
    assert "answer leakage" in score.families


def test_a_scoring_exception_is_recorded_not_swallowed() -> None:
    """SymPy raises on real generated content. A candidate that cannot be scored must show
    up as an error in the denominator, never as a silent pass."""
    broken = _item(equation="Eq(((((", correct_option="a")
    score = rvv.score_candidate(_candidate(broken), CURRICULUM)
    # Either it scores (as a defect) or it errors - what it must never do is come back clean.
    assert score.defective or score.error is not None


# --- 2. rebuilding an accepted candidate changes nothing the gate reads ---------------


class _Row:
    """The joined `question_templates` + canonical `question_variants` row, as literals."""

    def __init__(self, item: AuthoredGeneratedItemResponse, difficulty_label: int = 2) -> None:
        self.question_template_id = "authored-linear_equations-d2-1"
        self.topic_id = "linear_equations"
        self.skill_id = "linear_two_step"
        self.difficulty_label = difficulty_label
        self.stem = item.stem
        self.context_block = item.context_block
        self.answer_expression = item.equation
        self.hint_ladder = list(item.hint_ladder)
        self.canonical_solution = item.canonical_solution.model_dump()
        self.common_error_tags = list(item.misconception_tags)
        self.estimated_time_seconds = item.estimated_time_seconds
        self.option_a = item.option_a
        self.option_b = item.option_b
        self.option_c = item.option_c
        self.option_d = item.option_d
        self.correct_option = item.correct_option


def test_reconstruction_preserves_every_field_the_gate_reads() -> None:
    """The honesty test for the validated arm. Four generator fields have no column; if any
    deterministic check read one of them, the accepted arm's score would be an artifact of
    the reconstruction rather than a measurement of the item."""
    original = _item()
    rebuilt = rvv.item_from_persisted(
        _Row(original),
        {
            "generator_proposed_difficulty": 2,
            "generator_difficulty_rationale": original.difficulty_rationale,
        },
        original.required_prerequisites,
    )
    before = validate_authored_item(
        2, original, answer_form=CURRICULUM.answer_form("linear_two_step")
    )
    after = validate_authored_item(
        2, rebuilt, answer_form=CURRICULUM.answer_form("linear_two_step")
    )
    assert before.failures == after.failures == []
    for field in (
        "stem",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "correct_option",
        "equation",
        "hint_ladder",
        "estimated_time_seconds",
        "misconception_tags",
    ):
        assert getattr(rebuilt, field) == getattr(original, field), field
    assert rebuilt.canonical_solution == original.canonical_solution


def test_reconstruction_of_a_defective_item_still_scores_defective() -> None:
    corrupted = _item(correct_option="c")
    rebuilt = rvv.item_from_persisted(
        _Row(corrupted),
        {
            "generator_proposed_difficulty": 2,
            "generator_difficulty_rationale": corrupted.difficulty_rationale,
        },
        corrupted.required_prerequisites,
    )
    score = rvv.score_candidate(_candidate(rebuilt, accepted=True), CURRICULUM)
    assert "answer key: derived answer disagrees" in score.families


def test_a_missing_rationale_becomes_a_named_marker_not_an_empty_string() -> None:
    """`difficulty_rationale` has a 20-character floor in the response contract. An empty
    string would fail validation and change what is being measured; a silent filler would
    hide the substitution."""
    original = _item()
    rebuilt = rvv.item_from_persisted(_Row(original), {}, [])
    assert "not persisted" in rebuilt.difficulty_rationale
    assert rebuilt.proposed_difficulty == 2  # falls back to the stored label


def test_the_declared_placeholder_list_matches_what_is_actually_substituted() -> None:
    """`reasoning` is the only generator field with no column and no recorded evidence to
    recover it from. If that changes, this list has to change with it."""
    assert rvv._RECONSTRUCTION_PLACEHOLDERS == ("reasoning",)
    rebuilt = rvv.item_from_persisted(
        _Row(_item()),
        {"generator_proposed_difficulty": 2, "generator_difficulty_rationale": "x" * 40},
        ["a prerequisite"],
    )
    assert rebuilt.reasoning == ""
    assert rebuilt.required_prerequisites == ["a prerequisite"]


# --- 3. duplication: the defect no per-item gate can see ------------------------------


def test_same_sentence_different_numbers_is_a_skeleton_collision() -> None:
    a = _candidate(
        _item(stem="A teacher has 48 pencils and 36 erasers to divide into identical bags."),
        run_id="a",
    )
    b = _candidate(
        _item(stem="A teacher has 72 pencils and 90 erasers to divide into identical bags."),
        run_id="b",
    )
    report, flagged = rvv.duplicate_groups([a, b], 0.75)
    assert report["skeleton_collisions"] == [["a", "b"]]
    assert flagged["skeleton"] == {"a", "b"}


def test_unrelated_stems_collide_on_neither_signal() -> None:
    a = _candidate(
        _item(stem="A teacher has 48 pencils to divide into identical bags."), run_id="a"
    )
    b = _candidate(_item(stem="Find the area of a circle whose radius measures 7 cm."), run_id="b")
    report, flagged = rvv.duplicate_groups([a, b], 0.75)
    assert report["skeleton_collisions"] == []
    assert report["near_duplicate_pairs"] == []
    assert flagged["near_duplicate"] == set()


def test_the_thresholded_signal_is_reported_separately_from_the_knobless_one() -> None:
    """A reworded near-duplicate must not inflate the skeleton number, which is the figure
    with no tuning in it."""
    a = _candidate(
        _item(stem="A baker sold 24 muffins and 18 scones at the morning market stall."),
        run_id="a",
    )
    b = _candidate(
        _item(stem="At the morning market stall a baker sold 30 scones and 12 muffins."),
        run_id="b",
    )
    report, _ = rvv.duplicate_groups([a, b], 0.5)
    assert report["skeleton_collisions"] == []
    assert report["near_duplicate_pairs"] == [["a", "b"]]


# --- 4. the arms carry their own denominators ----------------------------------------


def test_summarise_separates_scoring_errors_from_the_denominator() -> None:
    scores = [
        rvv.Score("a", False, "t", "s", 2, 1, ("answer key: derived answer disagrees",), ("x",)),
        rvv.Score("b", False, "t", "s", 2, 2, (), ()),
        rvv.Score("c", False, "t", "s", 2, 3, (), (), error="SympifyError: boom"),
    ]
    summary = rvv.summarise("raw", scores)
    assert summary.n == 3
    assert summary.scored == 2
    assert summary.errors == 1
    assert summary.defective == 1
    assert summary.as_dict()["invalid_content_rate"] == 0.5
    assert summary.as_dict()["by_family"] == {"answer key: derived answer disagrees": 1}


def test_an_empty_arm_reports_no_rate_rather_than_zero() -> None:
    """A rate with an empty denominator is not 0.0 - a run that accepted nothing must not
    read as 'the validated arm shipped no defects'."""
    summary = rvv.summarise("validated", [])
    assert summary.as_dict()["invalid_content_rate"] is None


# --- 5. the hand-audit draw is reproducible and stratified ---------------------------

SAMPLER = ROOT / "benchmarks" / "resume_evidence" / "05_content_generation" / "hand_audit_sample.py"


def _load_sampler():
    spec = importlib.util.spec_from_file_location("e5_3_hand_audit_sample", SAMPLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sampler = _load_sampler()


def _rows(n: int, tiers: tuple[int, ...] = (1, 2, 3, 4, 5)) -> list[dict[str, object]]:
    return [
        {"run_id": f"r{i:03d}", "requested_difficulty": tiers[i % len(tiers)]} for i in range(n)
    ]


def test_the_same_seed_draws_the_same_thirty() -> None:
    """The whole point of seeding the draw: a sample that changes between runs cannot be
    checked by anyone, including its author."""
    import random

    rows = _rows(200)
    first = sampler.stratified_sample(rows, 15, random.Random(20260829))
    second = sampler.stratified_sample(rows, 15, random.Random(20260829))
    assert [r["run_id"] for r in first] == [r["run_id"] for r in second]


def test_a_different_seed_draws_a_different_sample() -> None:
    import random

    rows = _rows(200)
    a = sampler.stratified_sample(rows, 15, random.Random(1))
    b = sampler.stratified_sample(rows, 15, random.Random(2))
    assert [r["run_id"] for r in a] != [r["run_id"] for r in b]


def test_the_quota_sums_to_the_requested_size() -> None:
    """Truncating a proportional quota per stratum loses up to one item per tier, which on
    five tiers is a third of a 15-item arm."""
    import random

    for size in (7, 15, 23):
        drawn = sampler.stratified_sample(_rows(200), size, random.Random(3))
        assert len(drawn) == size, size


def test_a_stratum_smaller_than_its_quota_does_not_shrink_the_sample() -> None:
    import random

    rows = _rows(30, tiers=(1, 2, 3)) + [{"run_id": "rare", "requested_difficulty": 5}]
    drawn = sampler.stratified_sample(rows, 15, random.Random(4))
    assert len(drawn) == 15


def test_asking_for_more_than_exists_returns_everything() -> None:
    import random

    rows = _rows(9)
    drawn = sampler.stratified_sample(rows, 15, random.Random(5))
    assert len(drawn) == 9


def test_every_tier_present_in_the_population_is_represented_when_it_can_be() -> None:
    import random

    drawn = sampler.stratified_sample(_rows(200), 15, random.Random(6))
    assert len({r["requested_difficulty"] for r in drawn}) == 5
