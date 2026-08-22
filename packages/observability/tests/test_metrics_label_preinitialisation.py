"""COST-22: a labelled metric with no pre-initialised series cannot be alarmed on before it fires.

**The gap was module-wide, not one metric.** Every one of the twenty-one `.labels(` call sites
lived inside a function or a handler and none at module scope, so each labelled counter's series
came into existence at the moment of its first event - `qa_service_degraded_total`, the metric
built so a Bedrock outage stops reading as a surge of off-topic questions, was absent from the
deployed namespace and could not be alarmed on until an outage created it.

Pre-initialisation is one line per metric and stays correct only while somebody remembers to add
it. This file is what remembers: a new labelled metric in `metrics.py` fails here unless it is
either given its label vocabulary or written into the exemption list, and the exemption is a
deliberate edit rather than a default. That is the same construction
`test_alarm_severity_routing.py` uses for the quiet SNS channel, and for the same reason - the
useful half of the assertion is the half that fires when someone *adds* something.

Both directions are asserted (D-221). The negative control matters more than usual here, because
every positive assertion in this file would still pass on a walk that found no metrics at all -
which is precisely how COST-22 stayed invisible while the suite was green.
"""

import pytest
from intellichoice_observability import metrics
from prometheus_client import CollectorRegistry, Counter
from prometheus_client.metrics import MetricWrapperBase


def _labelled_metrics(module: object) -> dict[str, MetricWrapperBase]:
    """Every labelled metric the module declares, attribute name -> metric.

    Module attributes rather than the default registry: the registry also holds
    `prometheus_client`'s own `python_gc_*` / `python_info` collectors and anything an importing
    app registered, and the property under test is about *this* module's declarations.
    """
    return {
        name: value
        for name, value in vars(module).items()
        if isinstance(value, MetricWrapperBase) and value._labelnames
    }


def _declared_label_values() -> dict[int, dict[str, tuple[str, ...]]]:
    """The pre-init table, keyed by metric identity."""
    return {
        id(metric): label_values for metric, label_values in metrics.PREINITIALISED_LABEL_VALUES
    }


def _undeclared(module: object) -> list[str]:
    exempt = {id(metric) for metric in metrics.UNBOUNDED_LABEL_EXEMPT}
    declared = _declared_label_values()
    return sorted(
        name
        for name, metric in _labelled_metrics(module).items()
        if id(metric) not in declared and id(metric) not in exempt
    )


def test_every_labelled_metric_is_pre_initialised_or_explicitly_exempt() -> None:
    """The guard itself. A new labelled counter fails here until it is classified."""
    assert _undeclared(metrics) == [], (
        "these labelled metrics have no pre-initialised label set and are not in "
        "UNBOUNDED_LABEL_EXEMPT, so each one is unalarmable until its first event (COST-22): "
        f"{_undeclared(metrics)}"
    )


def test_the_pre_init_table_covers_each_metrics_full_label_set() -> None:
    """A metric that grows a second label must grow a vocabulary for it too.

    Without this, adding `branch` to `qa_maps_calls_total` would leave the table pre-initialising
    a label set the metric no longer has - `.labels()` would raise at import, or worse, quietly
    pre-init a different series than the call sites use.
    """
    for metric, label_values in metrics.PREINITIALISED_LABEL_VALUES:
        assert tuple(label_values) == tuple(metric._labelnames), (
            f"{metric._name}: the pre-init table names {tuple(label_values)} but the metric "
            f"declares {tuple(metric._labelnames)}"
        )
        for label, values in label_values.items():
            assert values, f"{metric._name}.{label} has an empty value list"
            assert len(set(values)) == len(values), f"{metric._name}.{label} repeats a value"


def test_every_declared_combination_exists_at_import() -> None:
    """The observable end of it: the series is in the scrape output before anything happens.

    Presence, not value, is asserted - other tests in this package increment these counters and
    the registry is process-global, so a zero assertion would be an ordering trap. Presence is
    also the property that matters: CloudWatch cannot alarm on a series it has never seen.
    """
    exposition = metrics.render_metrics()[0].decode()

    for metric, label_values in metrics.PREINITIALISED_LABEL_VALUES:
        (label,) = tuple(label_values)  # every bounded metric here is single-labelled today
        for value in label_values[label]:
            assert (value,) in metric._metrics, (
                f"{metric._name}{{{label}={value}}} was not pre-initialised"
            )
            assert f'{metric._name}_total{{{label}="{value}"}}' in exposition, (
                f"{metric._name}{{{label}={value}}} is missing from /metrics, so nothing in "
                "CloudWatch can alarm on it before the first occurrence"
            )


def test_the_exemption_list_is_exactly_the_two_unbounded_infra_metrics() -> None:
    """The exemption is narrow on purpose, so nothing joins it by accident.

    `path` and `status` are bounded only by the route table and the HTTP status space; every
    other labelled metric in this module has a closed vocabulary and no excuse.
    """
    exempt_names = {metric._name for metric in metrics.UNBOUNDED_LABEL_EXEMPT}
    assert exempt_names == {"http_requests", "http_request_duration_seconds"}


def test_the_completeness_walk_is_not_vacuous(monkeypatch: pytest.MonkeyPatch) -> None:
    """The control, and the reason to trust the four tests above.

    A walk that found nothing - a renamed private attribute, a `prometheus_client` release that
    stops exposing `_labelnames` - would report a clean module while every metric stayed dark.
    So: the walk must find the metrics that exist, and it must *flag* a labelled metric that is
    neither pre-initialised nor exempt. The synthetic counter goes into a throwaway registry so
    it never reaches the real `/metrics`.
    """
    found = _labelled_metrics(metrics)
    assert len(found) >= 10, f"the module walk found only {sorted(found)}; it has drifted vacuous"
    assert "QA_SERVICE_DEGRADED" in found

    monkeypatch.setattr(
        metrics,
        "NEWLY_ADDED_COUNTER",
        Counter(
            "newly_added_total",
            "a labelled counter someone added without pre-initialising it",
            labelnames=("outcome",),
            registry=CollectorRegistry(),
        ),
        raising=False,
    )
    assert _undeclared(metrics) == ["NEWLY_ADDED_COUNTER"]
