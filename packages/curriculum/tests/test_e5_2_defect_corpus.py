"""E5.2's mutation corpus and detection scoring - the two things the benchmark rests on.

`benchmarks/resume_evidence/05_content_generation/build_defect_corpus.py` turns approved bank
items into labeled defects, and `run_defect_detection.py` turns detector verdicts into
precision/recall/F1. Both can be wrong in ways that leave every printed number looking
reasonable:

- a "mutation" that does not actually break the item makes a *clean* item wear a defect label,
  so every detector loses recall it never had a chance to earn;
- a scorer that treats an unmeasured item as "not flagged" hands a panel whose calls all failed
  a perfect score - the exact defect D-230 records `audit_authored_bank.py` shipping with.

So the mutation tests assert the **defect**, not the edit: that `derive_answer` now disagrees,
that the shadow equation resolves differently, that the arithmetic identity survived a cosmetic
clone. And the scoring tests assert what happens to a `None` verdict.

Pure: literal fixtures, no Postgres, no model, no network, no filesystem write. The harnesses
are loaded by path the same way `test_stage_funnel_analysis.py` loads its own - `benchmarks/`
is outside the uv workspace on purpose (measurement code, not shipped code), so there is no
package to import.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile
from typing import cast

import pytest
from intellichoice_curriculum.authored_bank import AuthoredTemplateDef
from intellichoice_curriculum.authored_validation import route_answer

ROOT = pathlib.Path(__file__).resolve().parents[3]
HARNESS_DIR = ROOT / "benchmarks" / "resume_evidence" / "05_content_generation"
CORPUS_PATH = ROOT / "docs" / "resume_evidence" / "05_content_generation" / "defect_corpus.jsonl"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HARNESS_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered before execution because both modules define dataclasses under
    # `from __future__ import annotations`, and `dataclasses` resolves field types through
    # `sys.modules[cls.__module__]`.
    sys.modules[spec.name] = module
    if str(HARNESS_DIR) not in sys.path:
        sys.path.insert(0, str(HARNESS_DIR))
    spec.loader.exec_module(module)
    return module


builder = _load("e5_2_build_defect_corpus", "build_defect_corpus.py")
detector = _load("e5_2_run_defect_detection", "run_defect_detection.py")


# --- fixtures ---------------------------------------------------------------------------------


def item(
    index: int = 1,
    *,
    name: str = "Liam",
    noun: str = "apples",
    first: int = 4,
    second: int = 5,
) -> AuthoredTemplateDef:
    """A minimal authored item that passes the real §5.8.5 gate.

    Deliberately a literal rather than a bank item: a fixture read from
    `curriculum/internal_math/authored/` would make these tests fail whenever content changed,
    for reasons that have nothing to do with the mutations they are checking.
    """
    total = first + second
    stem = (
        f"{name} has {first} {noun} in a basket. He picks {second} more {noun}. "
        f"How many {noun} does {name} have now?"
    )
    return AuthoredTemplateDef(
        question_template_id=f"fixture-{index}",
        topic_id="g1_addition",
        skill_id="g1_add_within_10",
        grade_band="1-2",
        difficulty_label=1,
        estimated_time_seconds=45,
        generator_model="fixture",
        stem=stem,
        context_block="",
        answer_expression=f"Eq(x, {first} + {second})",
        hint_ladder=[
            f"Start with the {noun} {name} already has.",
            f"Count on from {first}: how many more does he pick?",
            f"Write {first} + {second} and find the sum.",
        ],
        canonical_solution={
            "steps": [
                {
                    "step_number": 1,
                    "explanation": f"{name} starts with {first} {noun}.",
                    "expression": f"{first}",
                    "common_mistake": None,
                },
                {
                    "step_number": 2,
                    "explanation": f"He picks {second} more, so add {second}.",
                    "expression": f"{first} + {second}",
                    "common_mistake": None,
                },
            ],
            "final_answer": f"{total} {noun}",
        },
        random_seed=1000 + index,
        rendered_question=stem,
        option_a=f"{total} {noun}",
        option_b=f"{first} {noun}",
        option_c=f"{second} {noun}",
        option_d=f"{total + 2} {noun}",
        correct_option="a",
    )


def test_the_fixture_itself_passes_the_gate() -> None:
    """Everything below is "the mutation broke it", which means nothing unless it started whole."""
    assert builder.gate(item(), "any").passed


# --- one test per defect class: the defect is real, not just the edit -------------------------


def test_wrong_numeric_answer_makes_the_derived_answer_disagree() -> None:
    source = item()
    mutated, detail = builder.mutate_wrong_numeric_answer(
        source, corpus_id="c", seed=0, answer_form="any"
    )
    assert mutated.correct_option != source.correct_option
    # The point of the class: SymPy re-derives 9 from the equation and the key now says
    # something else. Asserted through `route_answer`, not through the gate's prose.
    derivation, _ = route_answer(mutated.answer_expression or "")
    assert derivation is not None
    # `DerivedAnswer.payload` is `object` and is read according to `.model`; this fixture is a
    # one-unknown equation, so the model is `value` and the payload a one-element tuple.
    assert derivation.model == "value"
    answer = str(cast(tuple, derivation.payload)[0])
    declared = {"a": mutated.option_a, "b": mutated.option_b, "c": mutated.option_c}[
        mutated.correct_option
    ]
    assert answer not in declared
    assert any("does not match declared correct option" in f for f in detail["gate_failures"])


def test_no_correct_option_removes_the_answer_from_all_four() -> None:
    source = item()
    mutated, detail = builder.mutate_no_correct_option(
        source, corpus_id="c", seed=0, answer_form="any"
    )
    derivation, _ = route_answer(mutated.answer_expression or "")
    assert derivation is not None and derivation.model == "value"
    answer = str(cast(tuple, derivation.payload)[0])
    options = [mutated.option_a, mutated.option_b, mutated.option_c, mutated.option_d]
    assert all(not text.startswith(f"{answer} ") for text in options)
    assert len(set(options)) == 4, "the shift must not collapse two options into one"
    assert detail["delta"] in builder._SHIFT_DELTAS


def test_no_correct_option_advances_the_delta_when_a_distractor_lands_on_the_answer() -> None:
    """The shift is uniform, so it can move a *distractor* onto the true answer.

    Options 9 / 6 / 5 / 11 against a derived answer of 9: the first delta (3) turns the 6 into
    a 9 and puts the correct answer straight back into the option set, under a different
    letter. Every item of this class in the shipped corpus happened to clear at delta 3, so
    without this fixture the loop that exists for exactly this case would never run.
    """
    source = item().model_copy(
        update={
            "option_a": "9 apples",
            "option_b": "6 apples",
            "option_c": "5 apples",
            "option_d": "11 apples",
        }
    )
    assert builder.gate(source, "any").passed
    mutated, detail = builder.mutate_no_correct_option(
        source, corpus_id="c", seed=0, answer_form="any"
    )
    assert detail["delta"] != 3, "delta 3 recreates the answer as option b and must be rejected"
    options = [mutated.option_a, mutated.option_b, mutated.option_c, mutated.option_d]
    assert all(not text.startswith("9 ") for text in options)


def test_mismatched_solution_grafts_a_disagreeing_final_answer() -> None:
    source = item()
    donor = item(2, name="Maya", noun="stickers", first=7, second=6)
    mutated, detail = builder.mutate_mismatched_solution(
        source, corpus_id="c", seed=0, answer_form="any", donors=[donor]
    )
    assert mutated.canonical_solution == donor.canonical_solution
    assert detail["final_answer_to"] != detail["final_answer_from"]
    assert any("does not match the declared correct option" in f for f in detail["gate_failures"])


def test_mismatched_hint_ladder_grafts_numeral_disjoint_hints() -> None:
    """The objective defect: the rungs coach toward numbers the question does not contain."""
    source = item()
    donor = item(2, name="Maya", noun="stickers", first=7, second=6)
    mutated, detail = builder.mutate_mismatched_hint_ladder(
        source, corpus_id="c", seed=0, answer_form="any", donors=[donor]
    )
    assert mutated.hint_ladder == donor.hint_ladder
    assert set(detail["donor_numerals"]).isdisjoint(detail["own_numerals"])
    assert detail["donor_numerals"], "a ladder with no numerals proves nothing"


def test_mismatched_hint_ladder_is_a_defect_the_gate_cannot_see() -> None:
    """Recorded as a test because it is a *finding*, not an accident of this fixture.

    Nothing in the §5.8.5 suite relates a hint to its stem - `hint_ladder_monotonicity_
    violations` is verbatim containment and says so - so a ladder from another item passes.
    If this test ever fails because the gate grew such a check, the E5.2 report's
    `mismatched_hint_ladder` row is stale and must be re-measured, not re-worded.
    """
    source = item()
    donor = item(2, name="Maya", noun="stickers", first=7, second=6)
    mutated, _ = builder.mutate_mismatched_hint_ladder(
        source, corpus_id="c", seed=0, answer_form="any", donors=[donor]
    )
    assert builder.gate(mutated, "any").passed


def test_contradictory_constraints_makes_the_stem_imply_a_different_answer() -> None:
    source = item()
    mutated, detail = builder.mutate_contradictory_constraints(
        source, corpus_id="c", seed=0, answer_form="any"
    )
    # The equation, the options and the key are untouched - that is what makes this class
    # invisible to SymPy re-derivation.
    assert mutated.answer_expression == source.answer_expression
    assert mutated.correct_option == source.correct_option
    assert (mutated.option_a, mutated.option_b) == (source.option_a, source.option_b)
    assert mutated.stem != source.stem
    # And the shadow equation - the same shift applied to the declared equation - resolves
    # somewhere else, which is the whole basis of the label.
    assert detail["stem_implied_answer"] != detail["declared_answer"]
    shadow, _ = route_answer(detail["shadow_equation"])
    original, _ = route_answer(detail["equation_unchanged"])
    assert shadow is not None and original is not None
    assert str(shadow.payload) != str(original.payload)
    assert detail["numeral_from"] not in builder._numerals(mutated.stem)


def test_contradictory_constraints_still_passes_the_gate() -> None:
    """The complement of the test above, and the reason the blind solver panel is not optional.

    `check_sympy_independent_solve`'s own docstring: "it verifies equation -> answer, never
    situation -> equation". This is that sentence as an executable assertion.
    """
    mutated, _ = builder.mutate_contradictory_constraints(
        item(), corpus_id="c", seed=0, answer_form="any"
    )
    assert builder.gate(mutated, "any").passed


@pytest.mark.parametrize("tier", builder.NEAR_DUPLICATE_TIERS)
def test_near_duplicate_keeps_the_mathematics_and_changes_only_the_surface(tier: str) -> None:
    source = item()
    mutated, detail = builder.mutate_near_duplicate(
        source, corpus_id="c", seed=0, answer_form="any", tier=tier
    )
    assert mutated.stem != source.stem, "a duplicate that is textually identical is not this class"
    assert mutated.answer_expression == source.answer_expression
    assert builder.arithmetic_identity(
        mutated.answer_expression or ""
    ) == builder.arithmetic_identity(source.answer_expression or "")
    assert builder._numerals(mutated.stem) == builder._numerals(source.stem)
    # A near-duplicate is a *valid* item; if the clone stopped passing the gate the class would
    # be scored as a gate catch for a defect the gate cannot see.
    assert builder.gate(mutated, "any").passed
    assert detail["severity_tier"] == tier


def test_near_duplicate_swaps_reach_every_field_not_just_the_stem() -> None:
    """A swap applied to the stem alone would leave the hints and solution talking about the
    old story - an internally inconsistent item, which is a different defect quietly mixed in.
    """
    mutated, _ = builder.mutate_near_duplicate(
        item(), corpus_id="c", seed=0, answer_form="any", tier="name_and_noun_swap"
    )
    assert "apples" not in mutated.stem
    assert not any("apples" in rung for rung in mutated.hint_ladder)
    assert "apples" not in mutated.canonical_solution["final_answer"]
    assert "apples" not in mutated.option_a


def test_a_mutation_that_does_not_break_the_item_is_refused() -> None:
    """`_require_gate_failure` is what keeps a clean item from wearing a defect label."""
    with pytest.raises(builder.MutationSkipped):
        builder._require_gate_failure(item(), "any", needle="anything", what="a defect")


def test_topic_round_robin_prefix_covers_every_topic() -> None:
    """The sampling defect this function was rewritten twice to fix (see its docstring)."""
    pool = [
        item(index, name="Liam").model_copy(update={"topic_id": f"topic_{index % 7}"})
        for index in range(70)
    ]
    ordered = builder.topic_round_robin(pool)
    assert len({i.topic_id for i in ordered[:7]}) == 7


# --- the committed corpus artifact -------------------------------------------------------------


@pytest.mark.skipif(not CORPUS_PATH.exists(), reason="corpus artifact not built")
def test_committed_corpus_meets_the_measurement_plan_shape() -> None:
    """E5.2's acceptance criterion 1, asserted against the artifact the report cites.

    The mutation tests above prove the mutators are honest; this proves the *shipped* corpus
    was built by them at the size the plan requires, and that its two sides are comparable -
    a clean control in a topic the defects never touch cannot falsify anything.
    """
    header, records = builder.load_corpus(CORPUS_PATH)
    defects = [r for r in records if r["label"] == "defect"]
    clean = [r for r in records if r["label"] == "clean"]
    assert len(defects) >= 100
    assert len(clean) >= 100
    by_class: dict[str, int] = {}
    for record in defects:
        by_class[record["defect_class"]] = by_class.get(record["defect_class"], 0) + 1
    assert len(by_class) >= 6
    assert min(by_class.values()) >= 15
    assert set(by_class) == set(builder.DEFECT_CLASSES)
    # Disjointness: a mutation source that were also a control would be a near-duplicate of the
    # reference set it is scored against.
    control_ids = {r["source_item_id"] for r in clean}
    mutation_ids = {r["source_item_id"] for r in defects if r["defect_class"] != "near_duplicate"}
    assert control_ids.isdisjoint(mutation_ids)
    # Every near-duplicate clones a control, or it has nothing to duplicate.
    for record in (r for r in defects if r["defect_class"] == "near_duplicate"):
        assert record["source_item_id"] in control_ids
    # Same topics on both sides, so the same-topic dedup comparison has a reference everywhere.
    assert {r["topic_id"] for r in defects} <= {r["topic_id"] for r in clean}
    assert header["corpus_seed"] == builder.CORPUS_SEED
    assert every_item_carries_provenance(records)


def every_item_carries_provenance(records: list[dict]) -> bool:
    return all(
        record["source_item_id"] and record["seed"] and "mutation" in record for record in records
    )


# --- scoring ------------------------------------------------------------------------------------


def verdict(
    corpus_id: str,
    *,
    label: str,
    flag: bool | None,
    defect_class: str | None = "wrong_numeric_answer",
    clean_block: str | None = None,
    solver_status: str = "scored",
):
    return detector.ItemVerdicts(
        corpus_id=corpus_id,
        label=label,
        defect_class=defect_class if label == "defect" else None,
        clean_block=clean_block,
        severity_tier=None,
        topic_id="g1_addition",
        source_item_id="src",
        flags={name: flag for name in detector.DETECTORS},
        solver_status=solver_status,
    )


def cell_for(cells, detector_name: str, scope: str):
    return next(c for c in cells if c.detector == detector_name and c.scope == scope)


def test_score_counts_the_four_quadrants_and_derives_the_rates() -> None:
    verdicts = [
        *(verdict(f"d{i}", label="defect", flag=True) for i in range(3)),
        verdict("d3", label="defect", flag=False),
        verdict("c0", label="clean", flag=True, clean_block="wrong_numeric_answer"),
        *(
            verdict(f"c{i}", label="clean", flag=False, clean_block="wrong_numeric_answer")
            for i in range(1, 4)
        ),
    ]
    cell = cell_for(detector.score(verdicts), "solver_panel", "wrong_numeric_answer")
    assert (cell.tp, cell.fn, cell.fp, cell.tn) == (3, 1, 1, 3)
    assert cell.recall == pytest.approx(0.75)
    assert cell.precision == pytest.approx(0.75)
    assert cell.f1 == pytest.approx(0.75)
    assert cell.clean_fp_rate == pytest.approx(0.25)
    assert cell.as_row()["recall_n_over_N"] == "3/4"
    assert cell.as_row()["clean_fp_n_over_N"] == "1/4"


def test_an_unjudged_item_enters_no_numerator_and_no_denominator() -> None:
    """D-230, mechanised.

    `audit_authored_bank.py` shipped one run in which a failed call and an objection were the
    same thing, so a Solver B that failed every call scored a perfect negative control. Here a
    verdict of `None` must move nothing at all - not recall, not precision, not the clean-set
    false-positive rate.
    """
    verdicts = [
        verdict("d0", label="defect", flag=True),
        verdict("d1", label="defect", flag=None, solver_status="call_failure"),
        verdict("c0", label="clean", flag=None, clean_block="wrong_numeric_answer"),
        verdict("c1", label="clean", flag=False, clean_block="wrong_numeric_answer"),
    ]
    cell = cell_for(detector.score(verdicts), "solver_panel", "wrong_numeric_answer")
    assert (cell.tp, cell.fn, cell.fp, cell.tn) == (1, 0, 0, 1)
    assert (cell.unscored_defects, cell.unscored_clean) == (1, 1)
    assert cell.recall == pytest.approx(1.0)
    assert cell.n_defects == 2 and cell.n_clean == 2, "the totals still record what was skipped"


def test_a_panel_whose_every_call_failed_scores_nothing_rather_than_everything() -> None:
    verdicts = [
        *(
            verdict(f"d{i}", label="defect", flag=None, solver_status="call_failure")
            for i in range(5)
        ),
        *(
            verdict(f"c{i}", label="clean", flag=None, clean_block="wrong_numeric_answer")
            for i in range(5)
        ),
    ]
    cell = cell_for(detector.score(verdicts), "solver_panel", "wrong_numeric_answer")
    assert (cell.tp, cell.fn, cell.fp, cell.tn) == (0, 0, 0, 0)
    assert cell.recall is None and cell.precision is None and cell.f1 is None
    assert cell.unscored_defects == 5


def test_combined_is_unscored_when_any_of_its_parts_is() -> None:
    row = verdict("d0", label="defect", flag=True)
    row.flags["solver_panel"] = None
    detector.finalise_combined(row)
    assert row.flags["combined_pipeline"] is None

    row.flags["solver_panel"] = False
    row.flags["deterministic_gate"] = False
    row.flags["dedup_embedding"] = False
    detector.finalise_combined(row)
    assert row.flags["combined_pipeline"] is False

    row.flags["dedup_embedding"] = True
    detector.finalise_combined(row)
    assert row.flags["combined_pipeline"] is True


def test_a_budget_or_circuit_stop_is_not_a_call_failure() -> None:
    """Three different things end a call, and only one of them says anything about the panel."""
    assert (
        detector._classify_error("session budget of 200 cents would be exceeded") == "budget_stop"
    )
    assert detector._classify_error("circuit is open") == "circuit_stop"
    assert detector._classify_error("ThrottlingException: slow down") == "call_failure"


def test_cosine_distance_matches_pgvector_semantics() -> None:
    assert detector.cosine_distance([1.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)
    assert detector.cosine_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)
    assert detector.cosine_distance([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(2.0)
    # Scale-invariant, so an unnormalized vector does not read as a different question.
    assert detector.cosine_distance([3.0, 4.0], [6.0, 8.0]) == pytest.approx(0.0)


def test_interleaved_run_order_keeps_a_stopped_run_balanced() -> None:
    records = [
        {"corpus_id": f"{name}-{i}", "defect_class": None if name == "clean" else name}
        for name in ("clean", "wrong_numeric_answer", "near_duplicate")
        for i in range(4)
    ]
    ordered = detector.interleaved(records)
    assert len(ordered) == 12
    prefix = {r["corpus_id"].rsplit("-", 1)[0] for r in ordered[:3]}
    assert prefix == {"clean", "wrong_numeric_answer", "near_duplicate"}


def test_metrics_rows_carry_numerator_and_denominator() -> None:
    """The measurement plan's standing rule: a rate never travels without its counts."""
    row = cell_for(
        detector.score([verdict("d0", label="defect", flag=True)]),
        "deterministic_gate",
        "ALL",
    ).as_row()
    assert row["recall_n_over_N"] == "1/1"
    assert row["clean_fp_n_over_N"] == "0/0"
    assert set(row) >= {"precision", "recall", "f1", "clean_fp_rate", "unscored_defects"}


@pytest.mark.skipif(not CORPUS_PATH.exists(), reason="corpus artifact not built")
def test_free_detectors_run_over_the_committed_corpus() -> None:
    """End to end on the real artifact, with no provider: the four free columns must produce a
    verdict for every item, and must never be `None` (which the scorer would drop).
    """
    _, records = builder.load_corpus(CORPUS_PATH)
    verdicts = detector.run_free_detectors(records)
    assert len(verdicts) == len(records)
    for row in verdicts.values():
        for name in detector.FREE_DETECTORS:
            assert isinstance(row.flags[name], bool)
        for name in detector.PAID_DETECTORS:
            assert row.flags[name] is None


@pytest.mark.skipif(not CORPUS_PATH.exists(), reason="corpus artifact not built")
def test_the_gate_flags_no_clean_control() -> None:
    """The negative control on the negative controls.

    Every control is an unmutated item that this same gate approved, so a failure here means
    the corpus and the gate disagree about the bank - which would invalidate every
    false-positive rate in the report before any model was called.
    """
    _, records = builder.load_corpus(CORPUS_PATH)
    verdicts = detector.run_free_detectors(records)
    flagged = [
        v.corpus_id
        for v in verdicts.values()
        if v.label == "clean" and v.flags["deterministic_gate"]
    ]
    assert flagged == []


def test_corpus_artifact_round_trips() -> None:
    header = {"record": "header", "corpus_seed": builder.CORPUS_SEED}
    result = builder.BuildResult(
        items=[
            builder.CorpusItem(
                corpus_id="e52-clean-000",
                label="clean",
                defect_class=None,
                clean_block="wrong_numeric_answer",
                source_item_id="fixture-1",
                seed=1,
                mutation={"field": None},
                item=item(),
                answer_form="any",
            )
        ]
    )
    with tempfile.TemporaryDirectory() as directory:
        target = pathlib.Path(directory) / "corpus.jsonl"
        builder.write_corpus(target, result, header)
        read_header, read_items = builder.load_corpus(target)
        assert read_header["corpus_seed"] == builder.CORPUS_SEED
        assert len(read_items) == 1
        restored = AuthoredTemplateDef.model_validate(read_items[0]["item"])
        assert restored == item()
