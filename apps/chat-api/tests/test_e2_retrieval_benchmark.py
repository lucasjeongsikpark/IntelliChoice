"""E2's instruments, tested on literals: IR metrics, the overlap stemmer, the fixture itself.

None of this ships. It is the measuring equipment behind every number in
`docs/resume_evidence/02_rag/E2_REPORT.md`, and an instrument that miscounts produces a
report that is internally consistent and wrong - the same reasoning
`test_e1_sse_ledger.py` records for E1's delivery ledger and
`test_stage_funnel_analysis.py` for E5.1's funnel parser.

Four things here are worth more than the rest:

- **The rank index boundary.** Ranks are 1-indexed in every IR formula and 0-indexed in
  every Python list. Off by one there moves MRR from 1.0 to 0.5 and nDCG from 1.0 to 0.63
  while leaving every table looking plausible, so the first relevant position is asserted
  directly rather than through an aggregate.
- **The overlap stemmer must not drift from the probe generator's.** `lexical_overlap` in
  `retrieval_benchmark.yaml` is only comparable with the same column in `probe_eval.yaml`
  if both were measured by the same function; this loads both and asserts they agree.
- **The fixture's own honesty controls, re-checked here.** A `lexical_mismatch` phrasing
  whose measured overlap is above the gate would silently inflate that category's
  difficulty claim; a `relabelled_from` phrasing that does NOT exceed the gate would mean
  the relabelling ran on something else. Both directions are asserted.
- **The harness's arms are built from the shipped seams**, so `_filters_for` is asserted
  equal to what `role_access_filter` produces - a benchmark scored under different filters
  than the product uses is measuring a different pipeline.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from datetime import UTC, datetime
from types import ModuleType

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[3]
BENCH = ROOT / "benchmarks" / "resume_evidence" / "02_rag"
FIXTURE = ROOT / "apps" / "chat-api" / "tests" / "fixtures" / "retrieval_benchmark.yaml"

PHRASINGS = {"exact_lookup", "paraphrase", "lexical_mismatch", "multi_keyword"}
STRATA = {"general", "authorization_boundary", "near_duplicate_cluster"}


def _load(path: pathlib.Path, name: str) -> ModuleType:
    """`benchmarks/` and `scripts/` are outside the uv workspace on purpose (measurement
    code, not shipped code), so there is no package to import - the same by-path load the
    other benchmark tests use.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ir = _load(BENCH / "ir_metrics.py", "e2_ir_metrics")
generator = _load(BENCH / "generate_retrieval_benchmark.py", "e2_generator")
ablation = _load(BENCH / "retrieval_ablation.py", "e2_ablation")
probe_generator = _load(ROOT / "scripts" / "generate_probe_eval_fixture.py", "e2_probe_generator")


# ---------------------------------------------------------------------------------------
# IR metrics
# ---------------------------------------------------------------------------------------

RANKED = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]


def test_relevant_first_is_a_perfect_score_everywhere() -> None:
    for k in (1, 3, 5, 10):
        assert ir.recall_at_k(RANKED, {"a"}, k) == 1.0
        assert ir.hit_at_k(RANKED, {"a"}, k) == 1.0
    assert ir.reciprocal_rank(RANKED, {"a"}) == 1.0
    assert ir.ndcg_at_k(RANKED, {"a"}, 10) == 1.0


def test_rank_is_one_indexed_not_zero_indexed() -> None:
    """The boundary that quietly halves MRR. "b" sits at list index 1 and rank 2."""
    assert ir.reciprocal_rank(RANKED, {"b"}) == pytest.approx(0.5)
    assert ir.reciprocal_rank(RANKED, {"c"}) == pytest.approx(1 / 3)
    # nDCG's discount is 1/log2(rank+1): rank 2 -> 1/log2(3) = 0.6309.
    assert ir.ndcg_at_k(RANKED, {"b"}, 10) == pytest.approx(0.63093, abs=1e-4)


def test_cutoffs_actually_cut() -> None:
    assert ir.recall_at_k(RANKED, {"d"}, 3) == 0.0
    assert ir.recall_at_k(RANKED, {"d"}, 4) == 1.0
    assert ir.ndcg_at_k(RANKED, {"d"}, 3) == 0.0
    # MRR is deliberately NOT truncated: "never found" and "found at 11" must differ.
    assert ir.reciprocal_rank(RANKED, {"k"}) == pytest.approx(1 / 11)
    assert ir.recall_at_k(RANKED, {"k"}, 10) == 0.0


def test_missing_relevant_id_scores_zero_not_an_error() -> None:
    assert ir.recall_at_k(RANKED, {"zzz"}, 10) == 0.0
    assert ir.hit_at_k(RANKED, {"zzz"}, 10) == 0.0
    assert ir.reciprocal_rank(RANKED, {"zzz"}) == 0.0
    assert ir.ndcg_at_k(RANKED, {"zzz"}, 10) == 0.0
    assert ir.recall_at_k([], {"a"}, 10) == 0.0


def test_set_ground_truth_separates_recall_from_hit() -> None:
    """The Frozen Spec's bio-cluster shape. "hit if any" and "how many of them" are
    different questions, and merging them into one column is how a benchmark quietly
    reports a 1-of-3 result as a perfect one.
    """
    relevant = {"a", "e", "zzz"}
    assert ir.hit_at_k(RANKED, relevant, 1) == 1.0
    assert ir.recall_at_k(RANKED, relevant, 1) == pytest.approx(1 / 3)
    assert ir.recall_at_k(RANKED, relevant, 5) == pytest.approx(2 / 3)
    # IDCG is over min(|R|, k) perfect positions, so a k smaller than |R| is still
    # normalised to a reachable ideal rather than to an impossible one.
    assert ir.ndcg_at_k(["a", "e"], {"a", "e"}, 2) == pytest.approx(1.0)
    assert ir.ndcg_at_k(["a"], {"a", "e", "zzz"}, 1) == pytest.approx(1.0)


def test_empty_relevant_set_scores_zero_rather_than_dividing_by_zero() -> None:
    """No-answer controls carry an empty R. They are scored by `emptied`, never by recall,
    and a caller that mixes them up must get a zero it can see, not a ZeroDivisionError.
    """
    assert ir.recall_at_k(RANKED, set(), 5) == 0.0
    assert ir.ndcg_at_k(RANKED, set(), 5) == 0.0
    assert ir.reciprocal_rank(RANKED, set()) == 0.0
    assert ir.recall_at_k(RANKED, {"a"}, 0) == 0.0


def test_percentile_is_nearest_rank_over_observed_values() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert ir.percentile(values, 50) == 5.0
    assert ir.percentile(values, 95) == 10.0
    assert ir.percentile(values, 100) == 10.0
    assert ir.percentile(values, 0) == 1.0
    assert ir.percentile([], 95) == 0.0
    assert ir.percentile([42.0], 95) == 42.0
    assert ir.mean([]) == 0.0
    assert ir.mean([1.0, 2.0]) == 1.5


# ---------------------------------------------------------------------------------------
# The overlap stemmer, and its drift guard against the probe generator
# ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sample",
    [
        "How do I get a refund if we signed up and then changed our minds?",
        "Students must attend four consecutive scheduled sessions before the assessment.",
        "### Alice Lee  *President, Fairview High*",
        "the and for are you your with that this from",
        "",
    ],
)
def test_overlap_stemmer_agrees_with_the_probe_generator(sample: str) -> None:
    """`lexical_overlap` means the same thing in `retrieval_benchmark.yaml` as in
    `probe_eval.yaml` only while these two functions agree. E2's report compares the two
    fixtures' overlap columns directly, so a silent divergence here is a wrong comparison.
    """
    assert generator.lexemes(sample) == probe_generator._lexemes(sample)


def test_overlap_is_a_fraction_of_the_question_not_of_the_passage() -> None:
    passage = "Attendance corrections must be filed within five school days."
    assert generator.overlap("How do I fix an attendance record?", passage) == pytest.approx(
        1 / 3, abs=0.01
    )
    assert generator.overlap("", passage) == 0.0
    assert generator.overlap("attendance correction", passage) == 1.0


def test_overlap_bands_are_labels_over_the_measured_value() -> None:
    assert generator.overlap_band(0.9) == "high"
    assert generator.overlap_band(0.50) == "high"
    assert generator.overlap_band(0.49) == "mid"
    assert generator.overlap_band(0.15) == "mid"
    assert generator.overlap_band(0.14) == "low"
    assert generator.overlap_band(0.0) == "low"


# ---------------------------------------------------------------------------------------
# The harness's arm construction
# ---------------------------------------------------------------------------------------


def test_interleave_is_round_robin_and_deduplicates_by_first_occurrence() -> None:
    assert ablation._interleave(["a", "b", "c"], ["x", "y", "z"]) == ["a", "x", "b", "y", "c", "z"]
    # A shared id keeps its earliest position and never appears twice - otherwise the
    # "hybrid without RRF" arm would report duplicate candidates as extra recall.
    assert ablation._interleave(["a", "b"], ["a", "c"]) == ["a", "b", "c"]
    assert ablation._interleave([], ["a"]) == ["a"]
    assert ablation._interleave([], []) == []
    assert len(ablation._interleave([str(i) for i in range(40)], [])) == ablation.CANDIDATE_LIMIT


def test_rrf_is_the_shipped_function_not_a_reimplementation() -> None:
    """The arms must call the product's own fusion. If this import ever stops resolving to
    `RagRepository`'s function, the harness is measuring its own arithmetic (AUD-C-25).
    """
    from intellichoice_db.repositories.rag import reciprocal_rank_fusion

    assert ablation.reciprocal_rank_fusion is reciprocal_rank_fusion
    assert reciprocal_rank_fusion([["a", "b"], ["b", "a"]], k=60, limit=1) == ["a"]


def test_benchmark_filters_match_the_product_role_access_filter() -> None:
    from chat_api.services.role_access import role_access_filter

    for role in ("public", "parent", "tutor", "branch_manager", "student"):
        mine = ablation._filters_for(role, None)
        theirs = role_access_filter(role, None)
        # `role_access_filter` builds ["public", role] for every role, including "public"
        # itself - deduplicated here, since ["public", "public"] and ["public"] select the
        # same rows but would not compare equal.
        assert sorted(set(mine.audiences or [])) == sorted(set(theirs.audiences or []))
        assert mine.restrict_to_branch == theirs.restrict_to_branch is True
    branch_scoped = ablation._filters_for("branch_manager", "branch-ext-1")
    assert branch_scoped.branch_external_id == "branch-ext-1"
    assert isinstance(branch_scoped.as_of, datetime)
    assert branch_scoped.as_of.tzinfo is UTC


def test_harness_pins_the_shipped_retrieval_constants() -> None:
    """A benchmark run at a different candidate width or relevance floor is a benchmark of a
    different pipeline, so these are read from the product rather than restated.
    """
    from intellichoice_knowledge.retrieval import MIN_RERANK_RELEVANCE_SCORE

    assert ablation.MIN_RERANK_RELEVANCE_SCORE == MIN_RERANK_RELEVANCE_SCORE
    assert ablation.CANDIDATE_LIMIT == 30
    assert ablation.TOP_K == 8
    assert ablation.SHIPPED_RRF_K == 60


# ---------------------------------------------------------------------------------------
# The fixture's own honesty controls
# ---------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fixture_payload() -> dict:
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_meets_its_stated_size(fixture_payload: dict) -> None:
    ground_truths = fixture_payload["ground_truths"]
    instances = [q for gt in ground_truths for q in gt["queries"]]
    assert len(ground_truths) >= 110
    assert len(instances) >= 250
    assert len(fixture_payload["no_answer_controls"]) >= 15
    # Every ground truth is a distinct chunk: that is what makes "effective n" equal to the
    # ground-truth count rather than to the instance count.
    chunk_ids = [cid for gt in ground_truths for cid in gt["chunk_ids"]]
    assert len(chunk_ids) == len(set(chunk_ids)) == len(ground_truths)


def test_every_case_carries_complete_provenance(fixture_payload: dict) -> None:
    assert fixture_payload["generator_model"]
    assert fixture_payload["embedding_model"] == "amazon.titan-embed-text-v2:0"
    assert fixture_payload["seed"]
    assert fixture_payload["repo_sha"]
    assert fixture_payload["spend_cents"] > 0
    ids = set()
    for ground_truth in fixture_payload["ground_truths"]:
        assert ground_truth["stratum"] in STRATA
        assert ground_truth["chunk_ids"]
        assert ground_truth["cluster_size"] >= 1
        assert ground_truth["source_chars"] >= fixture_payload["min_chunk_chars"]
        assert ground_truth["queries"], f"{ground_truth['id']} has no phrasing"
        for query in ground_truth["queries"]:
            assert query["id"] not in ids, f"duplicate instance id {query['id']}"
            ids.add(query["id"])
            assert query["phrasing"] in PHRASINGS
            assert query["text"].strip()
            assert 0.0 <= query["lexical_overlap"] <= 1.0
            assert query["generator_pass"] in {"A", "B", "C", "C2", "D"}
    for control in fixture_payload["no_answer_controls"]:
        assert control["text"].strip()
        assert control["validated_neighbours"]


def test_measurement_beat_intent_in_both_directions(fixture_payload: dict) -> None:
    """The fixture's fourth control. Every `lexical_mismatch` phrasing must actually be one,
    and every phrasing that was relabelled must actually have failed the gate - a relabel
    that fired on a passing case would mean the gate is reading the wrong number.
    """
    gate = fixture_payload["mismatch_max_overlap"]
    relabelled = 0
    for ground_truth in fixture_payload["ground_truths"]:
        for query in ground_truth["queries"]:
            if query["phrasing"] == "lexical_mismatch":
                assert query["lexical_overlap"] <= gate, query["id"]
                assert query["overlap_band"] == "low"
            if query.get("relabelled_from"):
                assert query["relabelled_from"] == "lexical_mismatch"
                assert query["phrasing"] == "paraphrase"
                assert query["lexical_overlap"] > gate, query["id"]
                relabelled += 1
    assert relabelled > 0, "no relabels at all would mean the control never fired"


def test_every_rewritten_phrasing_was_answerability_checked(fixture_payload: dict) -> None:
    """A drifted phrasing is a case whose ground truth is wrong, and a wrong ground truth
    flatters every arm that fails to find it. Only pass A (written directly from the
    passage) is exempt.
    """
    for ground_truth in fixture_payload["ground_truths"]:
        for query in ground_truth["queries"]:
            if query["generator_pass"] == "A":
                continue
            if query.get("reused_from"):
                continue
            assert query["answerability_checked"] is True, query["id"]


def test_no_answer_controls_were_validated_against_real_neighbours(fixture_payload: dict) -> None:
    """A control some chunk actually answers is a false negative dressed as a hard case."""
    for control in fixture_payload["no_answer_controls"]:
        judged = control["validated_neighbours"]
        assert len(judged) >= 3, control["id"]
        assert all(not n["answerable"] for n in judged), control["id"]
        assert all(0.0 <= n["distance"] <= 2.0 for n in judged)


def test_all_reported_categories_are_populated(fixture_payload: dict) -> None:
    """Acceptance criterion 2 needs a per-arm row for each. `near_duplicate_cluster` x
    `lexical_mismatch` is the one cell that is legitimately empty and the report says why:
    a bio question must keep the person's name to identify the right passage, and the name
    is in the passage, so no phrasing of it can clear the overlap gate.
    """
    from collections import Counter

    strata = Counter(gt["stratum"] for gt in fixture_payload["ground_truths"])
    phrasings = Counter(
        q["phrasing"] for gt in fixture_payload["ground_truths"] for q in gt["queries"]
    )
    for stratum in STRATA:
        assert strata[stratum] >= 20, f"{stratum} too small to report a row"
    for phrasing in PHRASINGS:
        assert phrasings[phrasing] >= 20, f"{phrasing} too small to report a row"
