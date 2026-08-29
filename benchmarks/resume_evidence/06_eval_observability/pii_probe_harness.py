"""E6.1 - drives the three callable redaction layers over the labeled probe corpus and
reports precision/recall/F1 with numerators and denominators.

Run with:

    uv run python benchmarks/resume_evidence/06_eval_observability/pii_probe_harness.py
    uv run python .../pii_probe_harness.py --out-dir /tmp/x     # write elsewhere

**$0 and fully offline.** No model call, no network, no database, no AWS, no Docker. The
three layers under measurement are pure functions plus an in-memory OpenTelemetry exporter,
so this runs anywhere the repository's own test suite runs.

## The three layers, and what each one is actually for

1. **`intellichoice_shared.pii_redaction`** - `redact_free_text` / `contains_pii_pattern`.
   Three regexes: email, http(s)/`www.` URL, punctuated 3-3-4 phone. Applied to a student's
   free-text message before it crosses the Bedrock wire and before it is persisted (D-072),
   and reused as the memory-consolidation denylist screen. **Scope: email, URL, phone only.
   No name detection, by design.**
2. **`intellichoice_observability.logging_config`** - `JsonLogFormatter` +
   `PiiDenylistFilter`. Two different mechanisms measured separately: an exact-match
   denylist over top-level `extra=` *keys* (structure), and D-394's free-text routing of the
   interpolated `message` and of `exc_info` through layer 1's regexes (text).
3. **`intellichoice_observability.tracing.RedactingSpanExporter`** - three *credential*
   patterns (token-bearing query params, bare JWTs, `Bearer` values) applied at the span
   export boundary to attributes, event names and event attributes. **Scope: credentials,
   not student PII** - measured here rather than asserted.

## What the numbers mean, and the one thing they must not be read as

Recall is reported over the **in-contract** positives only: forms the module documents
itself as covering. Real PII the module states it does not attempt - names, addresses,
student IDs, birth dates, unpunctuated or non-3-3-4 phone groupings - is labeled
`out_of_contract` and reported in its own table, neither inflating recall (it is not in the
denominator) nor deflating precision (a bonus catch there is not a false positive). The
corpus module's header explains why a two-way split cannot describe this redactor honestly.

Precision is reported over the **negatives** only: cases carrying no PII of any kind. One
negative subgroup is adversarial by construction (`neg_phone_shaped_identifier`: SKUs, lot
numbers and invoice numbers that genuinely carry a punctuated 3-3-4 grouping), so precision
is reported twice - overall, and with that subgroup excluded - because the difference is the
measurable price of having a phone class at all.

**Aggregate rates depend on corpus composition.** 651 cases is not a sample of production
traffic and no frequency claim is made from it; the per-category tables are the load-bearing
result and the aggregates are a summary of them.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import logging
import pathlib
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from intellichoice_observability.logging_config import (
    _DENYLISTED_LOG_KEYS,
    REDACTED_MARKER,
    JsonLogFormatter,
    PiiDenylistFilter,
)
from intellichoice_observability.tracing import build_tracer_provider
from intellichoice_shared.pii_redaction import contains_pii_pattern, redact_free_text
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "resume_evidence" / "06_eval_observability"
ENVIRONMENT = "local, offline, $0 - no model call, no network, no database"

MARKERS = {"email": "[redacted-email]", "url": "[redacted-url]", "phone": "[redacted-phone]"}


def load_corpus() -> Any:
    """`benchmarks/` is outside the uv workspace on purpose (measurement code, not shipped
    code), so there is no package to import - the corpus is loaded by path, the same way
    `packages/curriculum/tests/test_stage_funnel_analysis.py` loads its harness. Registered
    in `sys.modules` before execution because the module defines dataclasses under
    `from __future__ import annotations`, and `dataclasses` resolves field types through
    `sys.modules[cls.__module__]`.
    """
    path = pathlib.Path(__file__).with_name("pii_probe_corpus.py")
    spec = importlib.util.spec_from_file_location("e6_1_pii_probe_corpus", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


corpus = load_corpus()


# --------------------------------------------------------------------------------------
# Result records
# --------------------------------------------------------------------------------------


@dataclass
class Metric:
    """Every rate carries its numerator and denominator, per the measurement plan's rules."""

    layer: str
    scope: str
    metric: str
    numerator: int
    denominator: int

    @property
    def value(self) -> float | None:
        return self.numerator / self.denominator if self.denominator else None

    def as_row(self) -> dict[str, object]:
        value = self.value
        return {
            "layer": self.layer,
            "scope": self.scope,
            "metric": self.metric,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "value": "" if value is None else f"{value:.6f}",
        }


@dataclass
class FreeTextOutcome:
    case_id: str
    category: str
    contract: str
    pii_class: str
    text: str
    redacted_text: str
    redacted: bool
    markers: list[str]
    contains_flag: bool
    agrees_with_label: bool


@dataclass
class LayerReport:
    name: str
    scope_statement: str
    metrics: list[Metric] = field(default_factory=list)
    tables: dict[str, Any] = field(default_factory=dict)
    disagreeing_case_ids: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------------------
# Layer 1 - the regex redactor
# --------------------------------------------------------------------------------------


def _markers_in(text: str) -> list[str]:
    return [name for name, marker in MARKERS.items() if marker in text]


def run_layer1_cases(cases: list[Any]) -> list[FreeTextOutcome]:
    outcomes = []
    for case in cases:
        redacted_text = redact_free_text(case.text)
        redacted = redacted_text != case.text
        outcomes.append(
            FreeTextOutcome(
                case_id=case.id,
                category=case.category,
                contract=case.contract,
                pii_class=case.pii_class,
                text=case.text,
                redacted_text=redacted_text,
                redacted=redacted,
                markers=_markers_in(redacted_text),
                contains_flag=contains_pii_pattern(case.text),
                agrees_with_label=redacted == case.expect_redacted,
            )
        )
    return outcomes


def confusion(outcomes: list[FreeTextOutcome]) -> dict[str, int]:
    """TP/FN over in-contract positives; FP/TN over negatives. Out-of-contract positives are
    in neither denominator - that is the whole point of the third label.
    """
    tp = sum(1 for o in outcomes if o.contract == "in_contract" and o.redacted)
    fn = sum(1 for o in outcomes if o.contract == "in_contract" and not o.redacted)
    fp = sum(1 for o in outcomes if o.contract == "negative" and o.redacted)
    tn = sum(1 for o in outcomes if o.contract == "negative" and not o.redacted)
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn}


def prf_metrics(layer: str, scope: str, counts: dict[str, int]) -> list[Metric]:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    metrics = [
        Metric(layer, scope, "precision", tp, tp + fp),
        Metric(layer, scope, "recall", tp, tp + fn),
        # F1 as a rate with an integer numerator/denominator pair: 2TP / (2TP + FP + FN).
        Metric(layer, scope, "f1", 2 * tp, 2 * tp + fp + fn),
        Metric(layer, scope, "true_positives", tp, tp + fn),
        Metric(layer, scope, "false_negatives", fn, tp + fn),
        Metric(layer, scope, "false_positives", fp, fp + counts["tn"]),
    ]
    return metrics


def layer1_report(outcomes: list[FreeTextOutcome]) -> LayerReport:
    report = LayerReport(
        name="layer1_regex_free_text",
        scope_statement=(
            "intellichoice_shared.pii_redaction implements exactly three classes - email, "
            "http(s)/www. URL, punctuated 3-3-4 phone. Name detection is deliberately not "
            "attempted (module docstring, SPEC §5.30.1); names and opaque identifiers are "
            "governed by the structural payload-allowlist layer, which this experiment does "
            "not re-measure."
        ),
    )
    counts = confusion(outcomes)
    report.metrics += prf_metrics("layer1", "overall", counts)

    # Precision excluding the deliberately adversarial negative subgroup.
    adversarial = "neg_phone_shaped_identifier"
    non_adv = [o for o in outcomes if o.category != adversarial]
    report.metrics += prf_metrics(
        "layer1", "overall_excl_adversarial_negatives", confusion(non_adv)
    )

    # Per class. Recall counts a positive as caught only when its own class's marker fired,
    # so a case rescued by a different pattern is visible rather than silently credited.
    for pii_class in ("email", "url", "phone", "mixed"):
        positives = [
            o for o in outcomes if o.contract == "in_contract" and o.pii_class == pii_class
        ]
        caught_any = sum(1 for o in positives if o.redacted)
        expected_marker = pii_class if pii_class in MARKERS else None
        report.metrics.append(
            Metric("layer1", f"class:{pii_class}", "recall", caught_any, len(positives))
        )
        if expected_marker:
            caught_own = sum(1 for o in positives if expected_marker in o.markers)
            report.metrics.append(
                Metric(
                    "layer1",
                    f"class:{pii_class}",
                    "recall_by_own_pattern",
                    caught_own,
                    len(positives),
                )
            )
            fired_on_negative = sum(
                1 for o in outcomes if o.contract == "negative" and expected_marker in o.markers
            )
            report.metrics.append(
                Metric(
                    "layer1",
                    f"class:{pii_class}",
                    "precision",
                    caught_own,
                    caught_own + fired_on_negative,
                )
            )

    # Per category, every category, so composition is visible rather than implied.
    per_category: dict[str, dict[str, object]] = {}
    for outcome in outcomes:
        row = per_category.setdefault(
            outcome.category,
            {"contract": outcome.contract, "cases": 0, "redacted": 0, "agree": 0},
        )
        row["cases"] = int(row["cases"]) + 1
        row["redacted"] = int(row["redacted"]) + int(outcome.redacted)
        row["agree"] = int(row["agree"]) + int(outcome.agrees_with_label)
    report.tables["per_category"] = per_category

    # The out-of-scope table: real PII the module does not claim.
    oos = [o for o in outcomes if o.contract == "out_of_contract"]
    oos_rows: dict[str, dict[str, int]] = {}
    for outcome in oos:
        row = oos_rows.setdefault(outcome.category, {"cases": 0, "caught_anyway": 0})
        row["cases"] += 1
        row["caught_anyway"] += int(outcome.redacted)
    report.tables["out_of_scope"] = oos_rows
    report.metrics.append(
        Metric(
            "layer1",
            "out_of_scope",
            "caught_anyway",
            sum(1 for o in oos if o.redacted),
            len(oos),
        )
    )

    # The identity-function baseline the measurement plan asks for: with no redactor, every
    # in-contract positive leaks.
    in_contract = [o for o in outcomes if o.contract == "in_contract"]
    report.metrics.append(
        Metric(
            "layer1",
            "baseline_identity",
            "positives_leaked",
            len(in_contract),
            len(in_contract),
        )
    )
    report.metrics.append(
        Metric(
            "layer1",
            "with_redactor",
            "positives_leaked",
            sum(1 for o in in_contract if not o.redacted),
            len(in_contract),
        )
    )

    # `contains_pii_pattern` must agree with `redact_free_text` on every case: same three
    # patterns, so a disagreement is a defect in one of them, not a measurement.
    agree = sum(1 for o in outcomes if o.contains_flag == o.redacted)
    report.metrics.append(
        Metric("layer1", "api_consistency", "contains_matches_redact", agree, len(outcomes))
    )

    report.disagreeing_case_ids = [o.case_id for o in outcomes if not o.agrees_with_label]
    return report


# --------------------------------------------------------------------------------------
# Layer 2 - the JSON log formatter and the denylist filter
# --------------------------------------------------------------------------------------


def _format_record(
    formatter: JsonLogFormatter,
    filter_: PiiDenylistFilter,
    *,
    msg: object,
    args: tuple[object, ...] = (),
    extra: dict[str, object] | None = None,
    exc_info: Any = None,
) -> dict[str, Any]:
    """One synthetic `LogRecord` through the real filter and the real formatter. Built by
    hand rather than through `configure_logging`, which mutates the root logger process-wide.
    """
    record = logging.LogRecord(
        name="e6_1.probe",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args or None,
        exc_info=exc_info,
    )
    for key, value in (extra or {}).items():
        record.__dict__[key] = value
    filter_.filter(record)
    return json.loads(formatter.format(record))


def _reachable_via_extra(key: str) -> bool:
    """Whether a call site could put this key into a record at all.

    `Logger.makeRecord` raises `KeyError: "Attempt to overwrite '<key>' in LogRecord"` for any
    standard record attribute, so `extra={"name": ...}` is refused by the standard library
    before the filter ever sees it. This harness sets `record.__dict__` directly, which no
    ordinary call site can do - so reachability has to be probed separately or the denominator
    would count a key that cannot be exercised.
    """
    try:
        logging.getLogger("e6_1.reachability").makeRecord(
            "e6_1.reachability", logging.INFO, __file__, 1, "probe", None, None, extra={key: "x"}
        )
    except KeyError:
        return False
    return True


def _raised(text: str) -> Any:
    try:
        raise ValueError(text)
    except ValueError:
        return sys.exc_info()


def layer2_report(cases: list[Any]) -> tuple[LayerReport, list[dict[str, Any]]]:
    formatter = JsonLogFormatter()
    filter_ = PiiDenylistFilter()
    report = LayerReport(
        name="layer2_json_log_formatter",
        scope_statement=(
            "Two mechanisms, measured separately. PiiDenylistFilter is an exact-match "
            "denylist over top-level `extra=` KEYS (D-011's precedent) - it sees structure, "
            "never text. D-394 added free-text routing of the interpolated `message` and of "
            "`exc_info` through layer 1's regexes, so those two fields inherit layer 1's "
            "scope and layer 1's limits exactly."
        ),
    )

    # (a) the denylist, driven from the product's own key set.
    log_cases = corpus.build_log_key_cases(_DENYLISTED_LOG_KEYS)
    key_records = []
    denylist_hits = 0
    control_survived = 0
    denylist_total = 0
    control_total = 0
    unreachable = []
    for case in log_cases:
        reachable = _reachable_via_extra(case.key)
        payload = _format_record(
            formatter, filter_, msg="probe_event", extra={case.key: case.value}
        )
        redacted = payload.get(case.key) == REDACTED_MARKER
        if not reachable:
            # `logging` itself refuses `extra={key: ...}` for a standard LogRecord attribute,
            # so the entry can neither leak nor be redacted through the ordinary call path.
            # Counting it either way would be a measurement artifact of this harness setting
            # `record.__dict__` directly, which no call site can do through `logger.info`.
            unreachable.append(case.key)
        elif case.expect_redacted:
            denylist_total += 1
            denylist_hits += int(redacted)
        else:
            control_total += 1
            control_survived += int(payload.get(case.key) == case.value)
        key_records.append(
            {
                "id": case.id,
                "key": case.key,
                "expect_redacted": case.expect_redacted,
                "reachable_via_extra": reachable,
                "redacted": redacted,
                "emitted_value": payload.get(case.key),
                "agrees_with_label": redacted == case.expect_redacted or not reachable,
            }
        )
    report.metrics.append(
        Metric("layer2", "denylist_keys", "coverage", denylist_hits, denylist_total)
    )
    report.metrics.append(
        Metric(
            "layer2",
            "denylist_keys",
            "reachable_via_extra",
            denylist_total,
            len(_DENYLISTED_LOG_KEYS),
        )
    )
    report.metrics.append(
        Metric("layer2", "control_keys", "survived_unchanged", control_survived, control_total)
    )
    report.tables["denylist_keys_unreachable"] = sorted(unreachable)
    report.disagreeing_case_ids += [r["id"] for r in key_records if not r["agrees_with_label"]]

    # (b) free-text routing of `message` (the `%`-interpolated result) over the whole corpus.
    message_outcomes = []
    for case in cases:
        payload = _format_record(formatter, filter_, msg="probe_case %s", args=(case.text,))
        emitted = str(payload.get("message", ""))
        redacted = case.text not in emitted
        message_outcomes.append(
            FreeTextOutcome(
                case_id=case.id,
                category=case.category,
                contract=case.contract,
                pii_class=case.pii_class,
                text=case.text,
                redacted_text=emitted,
                redacted=redacted,
                markers=_markers_in(emitted),
                contains_flag=contains_pii_pattern(case.text),
                agrees_with_label=redacted == case.expect_redacted,
            )
        )
    message_counts = confusion(message_outcomes)
    report.metrics += prf_metrics("layer2", "message_field", message_counts)

    # (c) free-text routing of `exc_info`.
    exc_outcomes = []
    for case in cases:
        payload = _format_record(formatter, filter_, msg="probe_exc", exc_info=_raised(case.text))
        emitted = str(payload.get("exc_info", ""))
        redacted = case.text not in emitted
        exc_outcomes.append(
            FreeTextOutcome(
                case_id=case.id,
                category=case.category,
                contract=case.contract,
                pii_class=case.pii_class,
                text=case.text,
                redacted_text=emitted[-160:],
                redacted=redacted,
                markers=_markers_in(emitted),
                contains_flag=contains_pii_pattern(case.text),
                agrees_with_label=redacted == case.expect_redacted,
            )
        )
    exc_counts = confusion(exc_outcomes)
    report.metrics += prf_metrics("layer2", "exc_info_field", exc_counts)

    # (d) the two documented gaps, quantified rather than described.
    #
    # `event` holds `record.msg` verbatim when it is a `str` - deliberately, because it is
    # the static template a caller groups by (D-394). A call site that passes an f-string
    # therefore puts free text into `event` unredacted. The AST sweep in D-394 found one such
    # call site; this measures what it would cost if the text were PII.
    in_contract = [c for c in cases if c.contract == "in_contract"]
    event_leaks = 0
    for case in in_contract:
        payload = _format_record(formatter, filter_, msg=f"tutor reply: {case.text}")
        if case.text in str(payload.get("event", "")):
            event_leaks += 1
    report.metrics.append(
        Metric("layer2", "gap_event_field_fstring", "leaked", event_leaks, len(in_contract))
    )

    # The filter checks top-level keys only (module docstring: "a call site that nests PII
    # inside a dict value under an innocuous key is not caught").
    nested_cases = [c for c in in_contract if c.pii_class in ("email", "phone", "url")][:40]
    nested_leaks = 0
    for case in nested_cases:
        payload = _format_record(
            formatter,
            filter_,
            msg="probe_nested",
            extra={"payload": {"email": case.text}},
        )
        # `ensure_ascii=False` or Korean text would come back as \uXXXX escapes and the
        # containment check would report a leak as a catch.
        if case.text in json.dumps(payload.get("payload"), default=str, ensure_ascii=False):
            nested_leaks += 1
    report.metrics.append(
        Metric("layer2", "gap_nested_extra_value", "leaked", nested_leaks, len(nested_cases))
    )

    report.tables["denylist_keys"] = key_records
    report.tables["message_confusion"] = message_counts
    report.tables["exc_info_confusion"] = exc_counts
    report.disagreeing_case_ids += [o.case_id for o in message_outcomes if not o.agrees_with_label]
    return report, key_records


# --------------------------------------------------------------------------------------
# Layer 3 - the span export redactor
# --------------------------------------------------------------------------------------


def layer3_report(span_cases: list[Any]) -> LayerReport:
    report = LayerReport(
        name="layer3_span_export_redactor",
        scope_statement=(
            "RedactingSpanExporter strips CREDENTIALS - token-bearing query parameters, bare "
            "JWTs, `Bearer` values - from span attributes, event names and event attributes "
            "at the export boundary (AUD-F-13, DRIFT-82). It is not a PII redactor and does "
            "not claim to be: student PII in a span passes through untouched, which is "
            "measured below rather than assumed."
        ),
    )
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(service_name="e6-1-pii-probe", span_exporter=exporter)
    tracer = provider.get_tracer("e6.1")
    for case in span_cases:
        with tracer.start_as_current_span(case.id) as span:
            if case.surface == "attribute":
                span.set_attribute(case.attribute_key, case.value)
            elif case.surface == "event_attribute":
                span.add_event("probe.event", {case.attribute_key: case.value})
            else:
                span.add_event(case.value)
    exported = {span.name: span for span in exporter.get_finished_spans()}
    provider.shutdown()

    records = []
    for case in span_cases:
        span = exported[case.id]
        if case.surface == "attribute":
            emitted = str((span.attributes or {}).get(case.attribute_key, ""))
        elif case.surface == "event_attribute":
            event = span.events[0]
            emitted = str((event.attributes or {}).get(case.attribute_key, ""))
        else:
            emitted = span.events[0].name
        redacted = emitted != case.value
        records.append(
            {
                "id": case.id,
                "category": case.category,
                "attribute_key": case.attribute_key,
                "surface": case.surface,
                "expect_redacted": case.expect_redacted,
                "redacted": redacted,
                "emitted": emitted,
                "agrees_with_label": redacted == case.expect_redacted,
            }
        )

    credential_cases = [
        r for r in records if r["expect_redacted"] and r["category"] != "span_pii_out_of_scope"
    ]
    clean_cases = [r for r in records if r["category"] == "span_clean"]
    pii_cases = [r for r in records if r["category"] == "span_pii_out_of_scope"]
    counts = {
        "tp": sum(1 for r in credential_cases if r["redacted"]),
        "fn": sum(1 for r in credential_cases if not r["redacted"]),
        "fp": sum(1 for r in clean_cases if r["redacted"]),
        "tn": sum(1 for r in clean_cases if not r["redacted"]),
    }
    report.metrics += prf_metrics("layer3", "credentials", counts)
    report.metrics.append(
        Metric(
            "layer3",
            "pii_out_of_scope",
            "redacted",
            sum(1 for r in pii_cases if r["redacted"]),
            len(pii_cases),
        )
    )
    per_category: dict[str, dict[str, int]] = {}
    for record in records:
        row = per_category.setdefault(record["category"], {"cases": 0, "redacted": 0})
        row["cases"] += 1
        row["redacted"] += int(bool(record["redacted"]))
    report.tables["per_category"] = per_category
    report.tables["records"] = records
    report.disagreeing_case_ids = [r["id"] for r in records if not r["agrees_with_label"]]
    return report


# --------------------------------------------------------------------------------------
# Positive controls - the scanner-style vacuity guard (scripts/scan_xray_pii.py)
# --------------------------------------------------------------------------------------


def positive_controls() -> dict[str, bool]:
    """Prove every pattern in every layer can fire before any clean result is trusted. A
    redactor whose patterns cannot fire scores a perfect precision, which is exactly the
    false negative AUD-F-12 recorded for a trace store that was silently empty.
    """
    controls = {
        "layer1_email": redact_free_text("ada.k@example.org") != "ada.k@example.org",
        "layer1_url": redact_free_text("https://example.org") != "https://example.org",
        "layer1_phone": redact_free_text("555-123-4567") != "555-123-4567",
        "layer1_contains": contains_pii_pattern("ada.k@example.org"),
    }
    formatter, filter_ = JsonLogFormatter(), PiiDenylistFilter()
    payload = _format_record(
        formatter, filter_, msg="control", extra={"email": "ada.k@example.org"}
    )
    controls["layer2_denylist"] = payload.get("email") == REDACTED_MARKER
    payload = _format_record(formatter, filter_, msg="control %s", args=("ada.k@example.org",))
    controls["layer2_message"] = "ada.k@example.org" not in str(payload.get("message"))
    payload = _format_record(
        formatter, filter_, msg="control", exc_info=_raised("ada.k@example.org")
    )
    controls["layer2_exc_info"] = "ada.k@example.org" not in str(payload.get("exc_info"))

    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(service_name="e6-1-control", span_exporter=exporter)
    tracer = provider.get_tracer("e6.1")
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    with tracer.start_as_current_span("control") as span:
        span.set_attribute("http.url", "https://example.org/s?token=abc123")
        span.set_attribute("jwt", jwt)
        span.set_attribute("auth", "Bearer abc123")
        span.add_event("probe.event", {"jwt": jwt})
    (exported,) = exporter.get_finished_spans()
    provider.shutdown()
    attributes = exported.attributes or {}
    controls["layer3_query_token"] = "abc123" not in str(attributes.get("http.url"))
    controls["layer3_jwt"] = attributes.get("jwt") == "REDACTED-JWT"
    controls["layer3_bearer"] = "abc123" not in str(attributes.get("auth"))
    controls["layer3_event"] = (exported.events[0].attributes or {}).get("jwt") == "REDACTED-JWT"
    return controls


# --------------------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------------------


@dataclass
class ProbeRun:
    git_sha: str
    generated_at: str
    environment: str
    controls: dict[str, bool]
    layer1: LayerReport
    layer2: LayerReport
    layer3: LayerReport
    layer1_outcomes: list[FreeTextOutcome]
    corpus_composition: dict[str, int]

    @property
    def metrics(self) -> list[Metric]:
        return [*self.layer1.metrics, *self.layer2.metrics, *self.layer3.metrics]

    def metric(self, layer: str, scope: str, name: str) -> Metric:
        for metric in self.metrics:
            if (metric.layer, metric.scope, metric.metric) == (layer, scope, name):
                return metric
        raise KeyError(f"{layer}/{scope}/{name}")


def git_sha() -> str:
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


def run_probe() -> ProbeRun:
    cases = corpus.CASES
    outcomes = run_layer1_cases(cases)
    layer2, _ = layer2_report(cases)
    composition = Counter(case.contract for case in cases)
    return ProbeRun(
        git_sha=git_sha(),
        generated_at=datetime.now(tz=UTC).isoformat(),
        environment=ENVIRONMENT,
        controls=positive_controls(),
        layer1=layer1_report(outcomes),
        layer2=layer2,
        layer3=layer3_report(corpus.SPAN_CASES),
        layer1_outcomes=outcomes,
        corpus_composition={
            "total": len(cases),
            "in_contract": composition["in_contract"],
            "out_of_contract": composition["out_of_contract"],
            "negative": composition["negative"],
            "span_cases": len(corpus.SPAN_CASES),
            "log_key_cases": len(corpus.build_log_key_cases(_DENYLISTED_LOG_KEYS)),
            "categories": len({case.category for case in cases}),
        },
    )


# --------------------------------------------------------------------------------------
# Artifacts
# --------------------------------------------------------------------------------------


def _layer_json(report: LayerReport) -> dict[str, Any]:
    return {
        "name": report.name,
        "scope_statement": report.scope_statement,
        "metrics": [{**metric.as_row(), "value_float": metric.value} for metric in report.metrics],
        "tables": report.tables,
        "disagreeing_case_ids": report.disagreeing_case_ids,
    }


def write_artifacts(run: ProbeRun, out_dir: pathlib.Path) -> dict[str, pathlib.Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "pii_probe_results.json"
    metrics_path = out_dir / "pii_probe_metrics.csv"
    report_path = out_dir / "E6_1_REPORT.md"

    results = {
        "experiment": "E6.1",
        "git_sha": run.git_sha,
        "generated_at": run.generated_at,
        "environment": run.environment,
        "cost": "$0 - no model call, no network, no database",
        "harness": "benchmarks/resume_evidence/06_eval_observability/pii_probe_harness.py",
        "corpus": "benchmarks/resume_evidence/06_eval_observability/pii_probe_corpus.py",
        "corpus_provenance": corpus.CORPUS_PROVENANCE,
        "corpus_composition": run.corpus_composition,
        "positive_controls": run.controls,
        "layers": [_layer_json(run.layer1), _layer_json(run.layer2), _layer_json(run.layer3)],
        "cases": [asdict(outcome) for outcome in run.layer1_outcomes],
    }
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    with metrics_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["layer", "scope", "metric", "numerator", "denominator", "value"]
        )
        writer.writeheader()
        for metric in run.metrics:
            writer.writerow(metric.as_row())

    report_path.write_text(build_report(run))
    return {"results": results_path, "metrics": metrics_path, "report": report_path}


def _pct(metric: Metric) -> str:
    value = metric.value
    if value is None:
        return f"n/a (0/{metric.denominator})"
    return f"{metric.numerator}/{metric.denominator} ({value:.1%})"


# Hand-written explanation for each category whose measured behaviour disagrees with its
# label. Keyed by category so the prose can never drift from the counts beside it.
FINDING_NOTES = {
    "email_exotic_syntax": (
        '**F-4 (low).** Quoted local parts (`"john doe"@…`), address literals '
        "(`ada.k@[192.0.2.14]`), a double `@`, and a TLD-less host (`ada.k@localhost`) are "
        "outside `[\\w.+-]+@[\\w-]+\\.[\\w.-]+`. Unlikely from a K-12 student typing into a "
        "chat box, and listed for completeness rather than as a priority."
    ),
    "url_uppercase_scheme": (
        "**F-1 (the one worth fixing).** `_URL_RE` is compiled without `re.IGNORECASE`, so "
        "`HTTP://`, `Https://` and `WWW.` are not matched at all. Scheme names are "
        "case-insensitive by RFC 3986, and a mobile keyboard's autocapitalisation produces "
        "`Https://` and `Www.` unprompted at the start of a message - which is exactly where "
        "a student pastes a link. One flag fixes it."
    ),
    "phone_parens_nospace": (
        "**F-3 (low).** `\\(?\\d{3}\\)?[-.\\s]` makes the separator after the area code "
        "mandatory, so `(555)123-4567` misses while `(555) 123-4567` matches. Same digits, "
        "same grouping, one space apart."
    ),
    "neg_phone_shaped_identifier": (
        "**Not a defect - the documented trade-off, priced.** These are SKUs, lot numbers and "
        "invoice numbers that genuinely carry a punctuated 3-3-4 grouping. A shape-only "
        "pattern cannot tell them from a phone number, and the module chose that direction "
        "deliberately: it redacts the phone-shaped string and keeps math content intact. The "
        "cost is bounded and visible here."
    ),
}


def build_report(run: ProbeRun) -> str:  # noqa: C901 - one long literal document
    lines: list[str] = []
    add = lines.append
    m = run.metric

    add("# E6.1 - PII-redaction precision/recall over a labeled synthetic probe corpus")
    add("")
    add("> Experiment: **E6.1** of `docs/resume_evidence/MEASUREMENT_PLAN.md` (Theme 6).")
    add(f"> Generated: **{run.generated_at}** at repository `{run.git_sha}`.")
    add(f"> Environment: **{run.environment}**.")
    add("> Cost of this measurement: **$0** - no model call, no network, no database, no AWS.")
    add("> Harness: `benchmarks/resume_evidence/06_eval_observability/pii_probe_harness.py`.")
    add("> Corpus: `benchmarks/resume_evidence/06_eval_observability/pii_probe_corpus.py`.")
    add("> Permanent lane: `packages/observability/tests/test_pii_probe_corpus.py`.")
    add("")

    add("## 1. What this measures, and what it does not")
    add("")
    add(
        "Before this run the repository had **no** labeled PII corpus, **no** negative corpus "
        "and **no** precision or recall number for redaction anywhere. The redactor had five "
        "direct unit tests (three positive, two negative) and `contains_pii_pattern` had "
        "none. The live scanners (`make scan-logs`, `make scan-traces`) carry 47 needles but "
        "are all-positive scans of a deployed store: they answer *is the store clean?*, never "
        "*how good is the redactor?*"
    )
    add("")
    add(
        "Three callable layers are driven offline over one labeled corpus. Each layer's scope "
        "is stated before its numbers, because the three do different jobs and the aggregate "
        "of a scope confusion is worse than no number at all."
    )
    add("")
    add("| layer | code under measurement | scope |")
    add("|---|---|---|")
    add(
        "| 1 | `intellichoice_shared.pii_redaction` | email, http(s)/`www.` URL, punctuated "
        "3-3-4 phone. **No name detection, by design.** |"
    )
    add(
        "| 2 | `intellichoice_observability.logging_config` | exact-match denylist over "
        "top-level `extra=` keys, plus D-394's free-text routing of `message`/`exc_info` "
        "through layer 1 |"
    )
    add(
        "| 3 | `intellichoice_observability.tracing.RedactingSpanExporter` | **credentials** "
        "(token query params, JWTs, `Bearer` values) on span attributes and events |"
    )
    add("")
    add(
        "**Names, addresses, birth dates and student IDs are not measured as recall here, and "
        "no number below should be read as covering them.** They are governed by a different "
        "mechanism - the structural payload allowlist, whose own evidence is the 59 "
        "reflection-driven payload-governance tests and the 47-needle live scanners - and by "
        "the absolute rule that Postgres stores no student PII at all (SPEC §5.30). This "
        "experiment does not re-measure that layer. It does measure how much such PII the "
        "regex layer catches anyway (§5), because the honest number there is not zero."
    )
    add("")

    add("## 2. The corpus")
    add("")
    composition = run.corpus_composition
    add(
        f"- **{composition['total']} labeled free-text cases** across "
        f"{composition['categories']} categories, every value synthetic."
    )
    add(
        f"- **{composition['in_contract']} in-contract positives** - real email/URL/3-3-4-phone "
        "forms the module documents itself as covering. The recall denominator."
    )
    add(
        f"- **{composition['out_of_contract']} out-of-contract positives** - real PII the module "
        "states it does not attempt. In neither denominator; reported in §5."
    )
    add(
        f"- **{composition['negative']} negatives** - no PII of any kind. The precision "
        "denominator."
    )
    add(
        f"- Plus **{composition['log_key_cases']} log-key cases** (layer 2) and "
        f"**{composition['span_cases']} span cases** (layer 3)."
    )
    add("")
    add(
        "Generation is deterministic: fixed value pools, fixed sentence templates, fixed "
        "order, no randomness and no I/O, so `build_corpus()` is byte-identical on any "
        "machine - which is what lets the pytest lane gate on an exact rate. Labels encode "
        "the module's *documented contract* and were fixed before the measurement ran; they "
        "are never derived from observed behaviour, or the experiment would score the "
        "implementation against itself and report 100% by construction."
    )
    add("")
    add(
        "**Disjoint from the live scanners on purpose.** `scan_logs_pii.py` and "
        "`scan_xray_pii.py` build their needles from `mysql_fixtures.py` - seeded display "
        "names, manager emails, branch addresses, branch coordinates. This corpus shares no "
        "value with that set. The two instruments answer different questions, and an "
        "overlapping corpus would let one instrument's blind spot hide inside the other's "
        "result."
    )
    add("")
    add("### 2.1 Why three labels rather than two")
    add("")
    add(
        "A two-way positive/negative split cannot describe this redactor honestly. Scoring a "
        "missed name as a recall failure would measure the module against a contract it "
        "never accepted; dropping names from the corpus would hide the residual risk the "
        "module explicitly documents. The third label - `out_of_contract` - keeps both "
        "visible: such cases are excluded from recall *and* from precision, and printed in "
        "their own table in §5."
    )
    add("")

    add("## 3. Positive controls")
    add("")
    fired = sum(1 for value in run.controls.values() if value)
    add(
        f"**{fired}/{len(run.controls)} controls fired.** Every pattern in every layer is "
        "proved able to fire before any clean result below is trusted - the "
        "`scripts/scan_xray_pii.py` convention, and the direct lesson of AUD-F-12, where an "
        'empty trace store certified "no PII" for an hour.'
    )
    add("")
    add("| control | fired |")
    add("|---|---|")
    for name, value in run.controls.items():
        add(f"| `{name}` | {'yes' if value else '**NO**'} |")
    add("")

    add("## 4. Layer 1 - the regex redactor")
    add("")
    add(f"> Scope: {run.layer1.scope_statement}")
    add("")
    add("| metric | n/N |")
    add("|---|---|")
    add(f"| **Precision** (negatives only) | {_pct(m('layer1', 'overall', 'precision'))} |")
    add(f"| **Recall** (in-contract positives only) | {_pct(m('layer1', 'overall', 'recall'))} |")
    add(f"| **F1** | {_pct(m('layer1', 'overall', 'f1'))} |")
    add(
        "| Precision excluding the adversarial negative subgroup | "
        f"{_pct(m('layer1', 'overall_excl_adversarial_negatives', 'precision'))} |"
    )
    add(
        "| False negatives | "
        f"{_pct(m('layer1', 'overall', 'false_negatives'))} of in-contract positives |"
    )
    add(f"| False positives | {_pct(m('layer1', 'overall', 'false_positives'))} of negatives |")
    add("")
    add("Per class:")
    add("")
    add("| class | recall (any pattern) | recall (own pattern) | precision |")
    add("|---|---|---|---|")
    for pii_class in ("email", "url", "phone"):
        scope = f"class:{pii_class}"
        add(
            f"| {pii_class} | {_pct(m('layer1', scope, 'recall'))} | "
            f"{_pct(m('layer1', scope, 'recall_by_own_pattern'))} | "
            f"{_pct(m('layer1', scope, 'precision'))} |"
        )
    add(
        f"| mixed (several classes in one message) | {_pct(m('layer1', 'class:mixed', 'recall'))} "
        "| - | - |"
    )
    add("")
    add(
        '"Own pattern" is stricter than "any pattern": a case counts only when its own '
        "class's marker fired, so a positive rescued by a *different* pattern shows as a miss "
        "for its own class instead of being silently credited. The two columns agree "
        "everywhere in this corpus, including the URLs carrying an address in their userinfo "
        "section (`https://ada.k@example.org/path`), where the email pattern runs first and "
        "the URL pattern then swallows its output - the URL marker is what survives, so the "
        "URL class is correctly credited."
    )
    add("")
    add("### 4.1 Before/after")
    add("")
    baseline = m("layer1", "baseline_identity", "positives_leaked")
    after = m("layer1", "with_redactor", "positives_leaked")
    add(
        f"Run through the identity function (no redaction), **{_pct(baseline)}** in-contract "
        f"positives leak. Through `redact_free_text`, **{_pct(after)}** leak. That is the "
        "before/after this experiment can measure directly; it says nothing about how often "
        "such text occurs in real traffic, which this corpus cannot and does not claim."
    )
    add("")
    add("### 4.2 API consistency")
    add("")
    consistency = m("layer1", "api_consistency", "contains_matches_redact")
    add(
        f"`contains_pii_pattern` agrees with `redact_free_text` on **{_pct(consistency)}** "
        "cases. They share the three compiled patterns, so any disagreement would be a defect "
        "rather than a measurement. `contains_pii_pattern` had no direct test before this run "
        "- it is the S25 memory-consolidation denylist screen, so a silent divergence there "
        "would let a model-generated fact carrying PII be stored."
    )
    add("")
    add("### 4.3 Per category")
    add("")
    add("| category | contract | cases | redacted | agrees with label |")
    add("|---|---|---:|---:|---|")
    for category, row in sorted(
        run.layer1.tables["per_category"].items(),
        key=lambda item: (item[1]["contract"], item[0]),
    ):
        cases_n = int(row["cases"])
        agree = int(row["agree"])
        add(
            f"| `{category}` | {row['contract']} | {cases_n} | {row['redacted']} | "
            f"{agree}/{cases_n} |"
        )
    add("")

    add("## 5. The out-of-scope table")
    add("")
    add(
        "Real PII the module states it does not attempt. **None of it is counted as a recall "
        "failure** - and where the regex catches some anyway, none of it is counted as a "
        "true positive either."
    )
    add("")
    caught = m("layer1", "out_of_scope", "caught_anyway")
    add(f"Caught anyway: **{_pct(caught)}**.")
    add("")
    add("| category | cases | caught anyway |")
    add("|---|---:|---:|")
    for category, row in sorted(run.layer1.tables["out_of_scope"].items()):
        add(f"| `{category}` | {row['cases']} | {row['caught_anyway']} |")
    add("")
    add(
        "The catches are incidental and worth naming so nobody reads them as coverage: "
        "Korean landline numbers with a three-digit area code (`031-123-4567`) happen to be "
        "3-3-4, and `mailto:` addresses are caught by the *email* pattern rather than by any "
        "URL handling. Korean **mobile** numbers - the format this product's actual users "
        "have - are 3-4-4 and are caught **0/8**."
    )
    add("")

    add("## 6. Layer 2 - the JSON log formatter and the denylist filter")
    add("")
    add(f"> Scope: {run.layer2.scope_statement}")
    add("")
    add("| measurement | n/N |")
    add("|---|---|")
    add(
        "| Denylisted `extra=` keys redacted (of those reachable) | "
        f"{_pct(m('layer2', 'denylist_keys', 'coverage'))} |"
    )
    add(
        "| Denylisted keys reachable through `extra=` at all | "
        f"{_pct(m('layer2', 'denylist_keys', 'reachable_via_extra'))} |"
    )
    add(
        "| Control keys surviving unchanged | "
        f"{_pct(m('layer2', 'control_keys', 'survived_unchanged'))} |"
    )
    add(f"| `message` field - recall | {_pct(m('layer2', 'message_field', 'recall'))} |")
    add(f"| `message` field - precision | {_pct(m('layer2', 'message_field', 'precision'))} |")
    add(f"| `exc_info` field - recall | {_pct(m('layer2', 'exc_info_field', 'recall'))} |")
    add(f"| `exc_info` field - precision | {_pct(m('layer2', 'exc_info_field', 'precision'))} |")
    add("")
    add(
        "The control-keys row exists so the denylist number cannot be gamed: a filter that "
        "redacted every field would score full coverage, so operationally necessary fields "
        "(`session_id`, `question_id`, `skill_name`, `model_id`, `latency_ms`, `cost_cents`, "
        "…) are measured for survival at the same time."
    )
    add("")
    add(
        "`message` and `exc_info` inherit layer 1's regexes exactly, so they inherit layer "
        "1's limits exactly - the rates match §4 case for case. That is the intended design "
        "(D-394 deliberately reuses one shared regex set rather than growing a second copy "
        "that would drift), and it means every finding in §8 applies to the log path too."
    )
    add("")
    unreachable = run.layer2.tables.get("denylist_keys_unreachable") or []
    if unreachable:
        add("### 6.1 A dead entry in the denylist")
        add("")
        add(
            "**F-5 (documentation-level, no leak).** "
            + ", ".join(f"`{key}`" for key in unreachable)
            + " is on the 37-key denylist but cannot be set through `extra=` at all: "
            "`Logger.makeRecord` raises "
            "`KeyError: \"Attempt to overwrite 'name' in LogRecord\"` for any standard record "
            "attribute, before the filter runs. So it neither leaks nor gets redacted through "
            "the ordinary call path, and the reachable denylist is "
            f"{m('layer2', 'denylist_keys', 'reachable_via_extra').numerator} keys, all of "
            "them covered. Nothing to fix in behaviour; worth knowing, because a reader of "
            "that list would reasonably believe a `name` field passed by a call site would be "
            "filtered, and the actual reason it is safe is that the standard library refuses "
            "the field, not that this filter catches it. (`student_name`, `parent_name`, "
            "`guardian_name`, `display_name`, `full_name`, `first_name` and `last_name` are "
            "all reachable and all covered.)"
        )
        add("")
    add("### 6.2 The two documented gaps, priced")
    add("")
    event_gap = m("layer2", "gap_event_field_fstring", "leaked")
    nested_gap = m("layer2", "gap_nested_extra_value", "leaked")
    add(
        f"- **`event` holds `record.msg` verbatim when it is a `str`**: {_pct(event_gap)} "
        "in-contract positives survive into the `event` field when a call site passes an "
        "f-string. This is deliberate - `event` is the static template an operator groups by, "
        "and interpolating it was D-394's *original* defect (unbounded cardinality plus free "
        "text). The exposure is real but is bounded by a call-site rule, and D-394's AST "
        "sweep found exactly one f-string call site."
    )
    add(
        f"- **The filter checks top-level keys only**: {_pct(nested_gap)} probed values nested "
        'one level deep under an innocuous key (`extra={"payload": {"email": …}}`) survive. '
        "The module docstring states this (D-011's exact-match precedent) and requires call "
        'sites to keep `extra=` flat. Measured here so "documented" is also "quantified".'
    )
    add("")

    add("## 7. Layer 3 - the span-export redactor")
    add("")
    add(f"> Scope: {run.layer3.scope_statement}")
    add("")
    add("| measurement | n/N |")
    add("|---|---|")
    add(f"| Credential recall | {_pct(m('layer3', 'credentials', 'recall'))} |")
    add(f"| Credential precision | {_pct(m('layer3', 'credentials', 'precision'))} |")
    add(
        "| Clean operational attributes altered | "
        f"{_pct(m('layer3', 'credentials', 'false_positives'))} |"
    )
    add(
        "| **Student PII redacted at this layer** | "
        f"{_pct(m('layer3', 'pii_out_of_scope', 'redacted'))} |"
    )
    add("")
    add("| category | cases | redacted |")
    add("|---|---:|---:|")
    for category, row in sorted(run.layer3.tables["per_category"].items()):
        add(f"| `{category}` | {row['cases']} | {row['redacted']} |")
    add("")
    add(
        "**The last row of the first table is the headline of this section, and it is a zero "
        "by design.** The span exporter is a credential redactor, not a PII redactor: an "
        "email address or a phone number set as a span attribute is exported verbatim. The "
        "control on that path is that PII must never be put in a span in the first place "
        "(SPEC §5.30 - no PII in logs, traces or LLM payloads, with no exemption), verified "
        "independently by `make scan-traces` against the deployed store. Stating it as a "
        "measured 0/8 rather than as an assumption is the point of including those cases."
    )
    add("")

    add("## 8. Findings")
    add("")
    add(
        "**No product code was changed by this experiment.** Every item below is reported, "
        "not fixed - fixing the redactor is a separate task with its own review."
    )
    add("")
    per_category = run.layer1.tables["per_category"]
    for category, note in FINDING_NOTES.items():
        row = per_category.get(category)
        if not row:
            continue
        cases_n = int(row["cases"])
        disagreeing = cases_n - int(row["agree"])
        add(f"### `{category}` - {disagreeing}/{cases_n} cases disagree with the label")
        add("")
        add(note)
        add("")
    span_gap = [
        record for record in run.layer3.tables["records"] if not record["agrees_with_label"]
    ]
    if span_gap:
        add(f"### Span-export credential gaps - {len(span_gap)} cases")
        add("")
        add(
            "**F-2 (medium).** Three credential shapes the span exporter's patterns do not "
            "name: `BEARER` uppercased (HTTP auth schemes are case-insensitive by RFC 7235), "
            "and `?refresh_token=` / `?id_token=` query parameters, which the *log* denylist "
            "does list as keys while the span redactor's query-parameter alternation "
            "(`token|access_token|api_key`) does not. A JWT-valued one is still caught by the "
            "JWT pattern; an opaque-valued one is not. The two layers' credential vocabularies "
            "having drifted apart is the finding, more than any single parameter name."
        )
        add("")
        add("| case | span attribute | exported verbatim |")
        add("|---|---|---|")
        for record in span_gap:
            add(f"| `{record['id']}` | `{record['attribute_key']}` | `{record['emitted']}` |")
        add("")
    add("### Over-capture (cosmetic, both directions worth knowing)")
    add("")
    add(
        "`_URL_RE`'s `\\S+` runs to the next whitespace, so a URL inside JSON takes the "
        'closing quote and brace with it: `{"url": "https://example.org/x"}` redacts to '
        '`{"url": "[redacted-url]` - valid text, invalid JSON. `_EMAIL_RE`\'s trailing '
        "`[\\w.-]+` likewise swallows a sentence-final period. Neither leaks anything; both "
        "would matter to anything that parses a redacted payload downstream."
    )
    add("")

    add("## 9. Limitations")
    add("")
    add(
        "1. **The regex layer detects email, URL and phone only.** Names, addresses, birth "
        "dates and student IDs are out of its contract and are governed by the structural "
        "payload-allowlist layer, which this experiment does not re-measure. No number here "
        'should be quoted as "PII detection" without that qualification.'
    )
    add(
        "2. **Aggregate rates depend on corpus composition.** 651 cases in chosen proportions "
        "are not a sample of production traffic; the per-category tables are the load-bearing "
        "result. No frequency or prevalence claim is made."
    )
    add(
        "3. **Synthetic only.** Every value is invented. That is a deliberate constraint (no "
        "real student data may enter this repository), and it means the corpus reflects "
        "*forms* that were anticipated. A form nobody thought of is invisible here - which is "
        "exactly why the live all-positive scanners over the deployed store remain a separate, "
        "independent instrument."
    )
    add(
        "4. **Local and offline.** These are pure functions and an in-memory exporter. Nothing "
        "here says what the deployed staging store contains; that is `make scan-logs` / "
        "`make scan-traces` (criterion 9) and E6.2."
    )
    add(
        "5. **Layer 2's `event`-field and nested-`extra` gaps are measured on probes, not on "
        "real call sites.** The counts say what would leak if a call site did those things, "
        "not that any call site does."
    )
    add("")

    add("## 10. Reproducing")
    add("")
    add("```")
    add("uv run python benchmarks/resume_evidence/06_eval_observability/pii_probe_harness.py")
    add("uv run pytest packages/observability/tests/test_pii_probe_corpus.py -q")
    add("```")
    add("")
    add(
        "The permanent lane runs in the default `make test` collection. Its gates are set AT "
        "the values measured above (the repository's measure-first-then-gate convention) and "
        "are one-directional: recall and precision may only improve. Because the corpus is "
        "deterministic, the tolerance is exactly zero - a single newly-missed case moves the "
        "rate and fails the gate. Adding cases to the corpus therefore requires re-running "
        "this harness and updating the recorded constants deliberately, which is the intended "
        "workflow: the constants are the recorded measurement, not a threshold someone guessed."
    )
    add("")
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="E6.1 PII redaction probe harness")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--no-write", action="store_true", help="print the summary only")
    args = parser.parse_args()

    run = run_probe()
    m = run.metric
    controls_fired = sum(1 for value in run.controls.values() if value)
    print(f"positive controls: {controls_fired}/{len(run.controls)} fired")
    if controls_fired != len(run.controls):
        silent = [name for name, value in run.controls.items() if not value]
        print(f"INVALID - these controls did not fire, so a clean result proves nothing: {silent}")
        return 2
    composition = run.corpus_composition
    print(
        f"corpus: {composition['total']} cases "
        f"({composition['in_contract']} in-contract, "
        f"{composition['out_of_contract']} out-of-contract, "
        f"{composition['negative']} negative) "
        f"+ {composition['log_key_cases']} log keys + {composition['span_cases']} spans"
    )
    print("")
    print("layer 1 (regex free text):")
    print(f"  precision {_pct(m('layer1', 'overall', 'precision'))}")
    print(f"  recall    {_pct(m('layer1', 'overall', 'recall'))}")
    print(f"  F1        {_pct(m('layer1', 'overall', 'f1'))}")
    for pii_class in ("email", "url", "phone"):
        print(
            f"  {pii_class:<6} recall {_pct(m('layer1', f'class:{pii_class}', 'recall'))}  "
            f"precision {_pct(m('layer1', f'class:{pii_class}', 'precision'))}"
        )
    print(f"  out-of-scope caught anyway {_pct(m('layer1', 'out_of_scope', 'caught_anyway'))}")
    print("layer 2 (json log formatter):")
    print(
        f"  denylist keys {_pct(m('layer2', 'denylist_keys', 'coverage'))}  "
        f"control keys survived {_pct(m('layer2', 'control_keys', 'survived_unchanged'))}"
    )
    print(
        f"  message recall {_pct(m('layer2', 'message_field', 'recall'))}  "
        f"exc_info recall {_pct(m('layer2', 'exc_info_field', 'recall'))}"
    )
    print("layer 3 (span export):")
    print(
        f"  credential recall {_pct(m('layer3', 'credentials', 'recall'))}  "
        f"precision {_pct(m('layer3', 'credentials', 'precision'))}"
    )
    print(
        f"  student PII redacted at this layer "
        f"{_pct(m('layer3', 'pii_out_of_scope', 'redacted'))} (by design)"
    )

    if args.no_write:
        return 0
    paths = write_artifacts(run, pathlib.Path(args.out_dir))
    print("")
    print("artifacts:")
    for name, path in paths.items():
        try:
            display = path.relative_to(REPO_ROOT)
        except ValueError:  # pragma: no cover - only when --out-dir is outside the repo
            display = path
        print(f"  {name:<10} {display}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
