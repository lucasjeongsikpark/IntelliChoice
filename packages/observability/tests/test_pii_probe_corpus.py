"""E6.1's permanent lane: the PII redactors must not get worse than they measurably are.

`benchmarks/resume_evidence/06_eval_observability/` holds a 651-case labeled synthetic
corpus and a harness that drives the three callable redaction layers - the regex redactor,
the JSON log formatter plus its denylist filter, and the span-export credential redactor -
and reports precision/recall/F1 with numerators and denominators. This module runs that
harness in the default `pytest` collection and gates the result.

**Measure first, then gate** (the repository's convention): every threshold below is a
value actually measured, not a number anyone chose. The corpus is unchanged since E6.1; the
constants were re-measured on 2026-08-30 after remediation R4 fixed E6.1's F-1 (`_URL_RE`
had no `re.IGNORECASE`) and F-2 (the span redactor's credential vocabulary had drifted from
the log denylist's). Provenance: `docs/resume_evidence/06_eval_observability/E6_1_REPORT.md`
is the original measurement at `7a486a9` (2026-08-28); `.../post_remediation/
R4_POSTFIX_REPORT.md` is the current one and carries the before -> after table. Re-measuring
and updating these constants in the same change as the behaviour improvement is this lane's
designed workflow, not a way around its gates - the gates stay one-directional, so a later
regression below the *new* values still fails.
The gates are one-directional - a rate may rise, never fall - and the tolerance is exactly
zero, because the corpus is deterministic (fixed pools, fixed templates, fixed order, no
randomness, no I/O) and the layers are pure functions, so a re-run reproduces the same
rate bit for bit. One newly-missed case moves a rate and fails a gate; that is the point.

Adding cases to the corpus therefore requires re-running the harness and updating
`RECORDED` deliberately. That is intended: these constants are a recorded measurement, and
a new case that exposes a pre-existing miss is a discovery to be written down, not a
regression to be silently absorbed by a tolerance band.

Pure and offline: no Docker, no network, no database, no AWS, no model call. The whole
sweep is ~0.4 s.
"""

from __future__ import annotations

import functools
import importlib.util
import json
import pathlib
import sys
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
HARNESS = ROOT / "benchmarks" / "resume_evidence" / "06_eval_observability" / "pii_probe_harness.py"


def _load_harness() -> Any:
    """`benchmarks/` is outside the uv workspace on purpose (measurement code, not shipped
    code), so there is no package to import - loaded by path, the same way
    `packages/curriculum/tests/test_stage_funnel_analysis.py` loads E5.1's harness.
    Registered in `sys.modules` before execution because the module defines dataclasses under
    `from __future__ import annotations`.
    """
    spec = importlib.util.spec_from_file_location("e6_1_pii_probe_harness", HARNESS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


harness = _load_harness()
corpus = harness.corpus


@functools.lru_cache(maxsize=1)
def probe_run() -> Any:
    return harness.run_probe()


# The measured values. layer/scope/metric -> (numerator, denominator) as recorded.
RECORDED: dict[tuple[str, str, str], tuple[int, int]] = {
    ("layer1", "overall", "precision"): (267, 275),
    ("layer1", "overall", "recall"): (267, 277),
    ("layer1", "overall", "f1"): (534, 552),
    ("layer1", "overall_excl_adversarial_negatives", "precision"): (267, 267),
    ("layer1", "class:email", "recall"): (119, 125),
    ("layer1", "class:url", "recall"): (74, 74),
    ("layer1", "class:phone", "recall"): (62, 66),
    ("layer1", "class:email", "precision"): (119, 119),
    ("layer1", "class:url", "precision"): (74, 74),
    ("layer1", "class:phone", "precision"): (62, 70),
    ("layer1", "class:mixed", "recall"): (12, 12),
    ("layer1", "api_consistency", "contains_matches_redact"): (651, 651),
    ("layer2", "denylist_keys", "coverage"): (36, 36),
    ("layer2", "control_keys", "survived_unchanged"): (12, 12),
    ("layer2", "message_field", "recall"): (267, 277),
    ("layer2", "message_field", "precision"): (267, 275),
    ("layer2", "exc_info_field", "recall"): (267, 277),
    ("layer2", "exc_info_field", "precision"): (267, 275),
    ("layer3", "credentials", "recall"): (21, 22),
    ("layer3", "credentials", "precision"): (21, 21),
}

# What R4 moved, on the unchanged 651-case corpus (E6.1 -> now):
#   layer1 url recall        68/74  -> 74/74   (F-1: the six `url_uppercase_scheme` cases)
#   layer1 overall recall   261/277 -> 267/277
#   layer3 credential recall 18/22  -> 21/22   (F-2: uppercase BEARER, ?refresh_token=,
#                                               ?id_token=)
# False positives did not move: 8/264 negatives, all `neg_phone_shaped_identifier`, the
# documented and priced phone trade-off. The precision *denominator* rises from 269 to 275
# because it is (true positives + false positives), not the negative count - the corpus
# composition (264 negatives, 277 in-contract, 22 span credential probes) is untouched.

# Composition floors from the experiment's own acceptance criteria (>=600 cases, >=200
# negatives). Floors, not equalities - the corpus may grow.
MIN_CASES = 600
MIN_NEGATIVES = 200
MIN_IN_CONTRACT = 250


def test_every_positive_control_fires() -> None:
    """The vacuity guard, in `scripts/scan_xray_pii.py`'s shape and for its reason: a
    redactor whose patterns cannot fire scores perfect precision, and AUD-F-12 is this
    project's own record of an instrument that certified a store clean because it was
    silently empty. Nothing below is meaningful unless every pattern is demonstrably live.
    """
    controls = harness.positive_controls()
    silent = sorted(name for name, fired in controls.items() if not fired)
    assert not silent, f"these patterns cannot fire, so a clean result proves nothing: {silent}"
    assert len(controls) >= 11


def test_corpus_composition_meets_the_experiment_floors() -> None:
    composition = probe_run().corpus_composition
    assert composition["total"] >= MIN_CASES
    assert composition["negative"] >= MIN_NEGATIVES
    assert composition["in_contract"] >= MIN_IN_CONTRACT
    assert composition["out_of_contract"] > 0
    assert composition["span_cases"] > 0


def test_case_ids_are_unique_across_every_corpus() -> None:
    ids = [case.id for case in corpus.CASES]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    assert not duplicates, f"duplicate case ids: {duplicates}"
    span_ids = [case.id for case in corpus.SPAN_CASES]
    assert len(set(span_ids)) == len(span_ids)


def test_every_case_is_fully_labeled() -> None:
    """A case with a missing label or an inconsistent one silently changes a denominator."""
    for case in corpus.CASES:
        assert case.text, case.id
        assert case.rationale, case.id
        assert case.category, case.id
        assert case.contract in {"in_contract", "out_of_contract", "negative"}, case.id
        # The three-label rule: only in-contract positives are expected to be redacted.
        assert case.expect_redacted == (case.contract == "in_contract"), case.id
        if case.contract == "negative":
            assert case.pii_class == "none", case.id


def test_every_category_is_represented_and_non_empty() -> None:
    categories = {case.category for case in corpus.CASES}
    required_families = (
        "email_",
        "url_",
        "phone_",
        "mixed_",
        "oos_",
        "neg_",
    )
    for family in required_families:
        assert any(name.startswith(family) for name in categories), family
    # The negative half specifically: the categories nothing in the repository had before.
    for required in (
        "neg_math_expression",
        "neg_date",
        "neg_iso_timestamp",
        "neg_version",
        "neg_currency",
        "neg_coordinates",
        "neg_uuid",
        "neg_code_snippet",
        "neg_prose_ko",
        "neg_near_miss_email",
        "neg_near_miss_url",
        "neg_near_miss_phone",
    ):
        assert required in categories, required


def test_corpus_generation_is_deterministic() -> None:
    """The zero-tolerance gates below are only legitimate if a rebuild is byte-identical."""
    first = corpus.build_corpus()
    second = corpus.build_corpus()
    assert first == second
    assert [case.id for case in first] == [case.id for case in corpus.CASES]


def test_corpus_stays_disjoint_from_the_live_scanner_needles() -> None:
    """`scan_logs_pii.py` / `scan_xray_pii.py` build their 47 needles from the seeded MySQL
    fixtures. The two instruments answer different questions - "is the deployed store
    clean?" versus "how good is the redactor?" - and a shared value would let one
    instrument's blind spot hide inside the other's result.
    """
    from intellichoice_adapters.seed import mysql_fixtures as fixtures

    needles = {user["display_name"] for user in fixtures._USERS}
    for branch in fixtures._BRANCHES:
        needles.update(
            {
                str(branch["manager_email"]),
                str(branch["address"]),
                str(branch["latitude"]),
                str(branch["longitude"]),
            }
        )
    corpus_text = "\n".join(case.text for case in corpus.CASES)
    corpus_text += "\n".join(case.value for case in corpus.SPAN_CASES)
    overlapping = sorted(needle for needle in needles if needle and needle in corpus_text)
    assert not overlapping, f"probe corpus shares values with the live scanners: {overlapping}"


@pytest.mark.parametrize(("key", "recorded"), sorted(RECORDED.items()))
def test_measured_rate_does_not_regress(
    key: tuple[str, str, str], recorded: tuple[int, int]
) -> None:
    """One-directional gate at the recorded measurement. See the module docstring."""
    layer, scope, metric_name = key
    measured = probe_run().metric(layer, scope, metric_name)
    recorded_value = recorded[0] / recorded[1]
    assert measured.value is not None
    assert measured.value >= recorded_value - 1e-9, (
        f"{layer}/{scope}/{metric_name} regressed: measured "
        f"{measured.numerator}/{measured.denominator} = {measured.value:.6f}, "
        f"recorded {recorded[0]}/{recorded[1]} = {recorded_value:.6f}. If this is a "
        "deliberate corpus change, re-run the harness and update RECORDED."
    )


def test_every_reachable_denylisted_key_is_redacted() -> None:
    """Stronger than the rate: named per key, so a key added to the product's denylist and
    then not actually filtered fails here rather than moving a percentage.
    """
    records = probe_run().layer2.tables["denylist_keys"]
    failures = [
        record["key"]
        for record in records
        if record["expect_redacted"] and record["reachable_via_extra"] and not record["redacted"]
    ]
    assert not failures, f"denylisted keys that were not redacted: {failures}"


def test_control_log_keys_survive_the_filter() -> None:
    """Guards the denylist number against the degenerate way to score 100%: redact
    everything. Operational fields must come through intact.
    """
    records = probe_run().layer2.tables["denylist_keys"]
    clobbered = [
        record["key"] for record in records if not record["expect_redacted"] and record["redacted"]
    ]
    assert not clobbered, f"non-PII operational keys were redacted: {clobbered}"


def test_log_free_text_routing_matches_the_regex_layer_exactly() -> None:
    """D-394 routes `message` and `exc_info` through the *same* `redact_free_text`, on
    purpose: one shared regex set rather than a second copy that would drift. If these two
    confusion matrices ever diverge from layer 1's, a second copy has appeared.
    """
    run = probe_run()
    layer1 = {
        name: run.metric("layer1", "overall", name).numerator for name in ("recall", "precision")
    }
    for scope in ("message_field", "exc_info_field"):
        for name in ("recall", "precision"):
            assert run.metric("layer2", scope, name).numerator == layer1[name], scope


def test_span_exporter_leaves_clean_operational_attributes_untouched() -> None:
    """The credential redactor rewrites span attributes at the export boundary; a pattern
    that over-matched would corrupt `db.statement`, `http.route` or a model id for every
    span in the system.
    """
    records = probe_run().layer3.tables["records"]
    altered = [
        record["id"]
        for record in records
        if record["category"] == "span_clean" and record["redacted"]
    ]
    assert not altered, f"clean span attributes were altered: {altered}"


def test_harness_writes_the_three_artifacts_with_required_provenance(
    tmp_path: pathlib.Path,
) -> None:
    """The evidence rules require every number to trace to a saved artifact carrying its git
    SHA, timestamp and environment. Written to `tmp_path`, never over the committed copies.
    """
    paths = harness.write_artifacts(probe_run(), tmp_path)
    assert sorted(path.name for path in paths.values()) == [
        "E6_1_REPORT.md",
        "pii_probe_metrics.csv",
        "pii_probe_results.json",
    ]
    results = json.loads(paths["results"].read_text())
    for required in ("git_sha", "generated_at", "environment", "corpus_provenance", "cases"):
        assert results[required], required
    assert results["corpus_provenance"]["synthetic"] is True
    assert len(results["cases"]) == len(corpus.CASES)
    header = paths["metrics"].read_text().splitlines()[0]
    assert header == "layer,scope,metric,numerator,denominator,value"
    report = paths["report"].read_text()
    assert "no name detection" in report.lower()
    assert results["git_sha"] in report
