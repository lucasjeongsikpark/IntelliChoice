"""RD-01/D-385: the nightly-job filter pattern must select the event the emitter actually writes.

**This is the test whose absence let a dead-man's switch ship broken.** The four heartbeat
alarms could never leave ALARM and could never enter OK, because `app_events.tf` built its
metric-filter patterns from the **hyphenated** terraform job keys
(`{ $.event = "session-consolidate_job_complete" }`) while `report_job_complete` rewrites the
hyphens and emits `session_consolidate_job_complete`. `JobCompletions` never published a single
datapoint, on any of the four `job` dimensions, over fourteen days - and every local test passed,
because no test in this repository crossed the two sides.
`test_alarm_severity_routing.py` asserts alarm *routing* and is structurally blind to it.

The two sides are asymmetric on purpose and both halves are asserted here:

  1. **The event name is underscored.** It is the log record's `event` field, which is what the
     filter pattern selects on.
  2. **The `job` field stays hyphenated**, verbatim from `locals.jobs`, because it is the alarm's
     `job` dimension. `scheduled_jobs.py:37-38` says so, and "fixing" it would break the
     dimension instead of the pattern.

Terraform is parsed rather than planned, following `test_deployed_route_admission_parity.py`'s
precedent (D-385): the property is about what the configuration *says*, no AWS credentials are
needed, and it runs in CI where `terraform plan` cannot.

The emitted record is **captured, not re-derived**. Both sides re-spelling the same expression is
how a parity test becomes vacuous, so the record goes through the real `report_job_complete` and
the real `JsonLogFormatter`, and the assertion is made against the parsed JSON an EMF/CloudWatch
filter would actually see.
"""

import io
import json
import logging
import re
from pathlib import Path

import pytest
from intellichoice_observability.logging_config import JsonLogFormatter
from intellichoice_observability.scheduled_jobs import report_job_complete

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STAGING_TF = _REPO_ROOT / "terraform" / "environments" / "staging" / "main.tf"
_APP_EVENTS_TF = _REPO_ROOT / "terraform" / "modules" / "observability" / "app_events.tf"

_NIGHTLY_JOB_EVENTS = re.compile(r"nightly_job_events\s*=\s*\[(?P<items>[^\]]*)\]", re.DOTALL)
_FILTER_BLOCK = re.compile(
    r'resource\s+"aws_cloudwatch_log_metric_filter"\s+"nightly_jobs"\s*\{(?P<body>.*?)\n\}',
    re.DOTALL,
)
_PATTERN_LINE = re.compile(r'^\s*pattern\s*=\s*"(?P<pattern>.*)"\s*$', re.MULTILINE)
_DIMENSIONS_LINE = re.compile(r"^\s*dimensions\s*=\s*\{(?P<body>[^}]*)\}\s*$", re.MULTILINE)
# `{ $.event = "some_event_name" }` - the only filter-pattern shape this test understands.
_JSON_SELECTOR = re.compile(r'^\{\s*(?P<selector>\$\.[\w.]+)\s*=\s*"(?P<value>[^"]*)"\s*\}$')


def _terraform_job_keys() -> list[str]:
    """The job keys staging passes into the observability module, in declaration order."""
    match = _NIGHTLY_JOB_EVENTS.search(_STAGING_TF.read_text())
    assert match is not None, f"nightly_job_events no longer parses out of {_STAGING_TF}"
    return re.findall(r'"([^"]+)"', match.group("items"))


def _filter_body() -> str:
    match = _FILTER_BLOCK.search(_APP_EVENTS_TF.read_text())
    assert match is not None, (
        f'the aws_cloudwatch_log_metric_filter "nightly_jobs" resource no longer parses '
        f"out of {_APP_EVENTS_TF}"
    )
    return match.group("body")


def _render_pattern(job_key: str) -> str:
    """Evaluate the `pattern` expression for one `each.key`, without a terraform binary.

    Exactly the two interpolations this resource has ever used are understood. Anything else
    fails loudly rather than being approximated: a pattern this test cannot evaluate is a
    pattern whose parity it cannot assert, and quietly passing would restore the blindness the
    file exists to remove.
    """
    match = _PATTERN_LINE.search(_filter_body())
    assert match is not None, "the nightly_jobs filter no longer has a single-line `pattern`"
    # Terraform-source escaping: `\"` in the .tf file is one `"` in the rendered pattern.
    pattern = match.group("pattern").replace('\\"', '"')

    def _interpolate(interpolation: re.Match[str]) -> str:
        expression = interpolation.group("expr").strip()
        if expression == "each.key":
            return job_key
        if re.fullmatch(r'replace\(\s*each\.key\s*,\s*"-"\s*,\s*"_"\s*\)', expression):
            return job_key.replace("-", "_")
        pytest.fail(
            f"unrecognised terraform interpolation `${{{expression}}}` in the nightly_jobs "
            "pattern; teach this test to evaluate it before changing the pattern"
        )

    return re.sub(r"\$\{(?P<expr>[^}]*)\}", _interpolate, pattern)


def _selector_and_value(pattern: str) -> tuple[str, str]:
    match = _JSON_SELECTOR.match(pattern)
    assert match is not None, (
        f'the filter pattern {pattern!r} is no longer a plain `{{ $.field = "value" }}` '
        "equality; this test's matcher would silently over-approximate it"
    )
    selector, value = match.group("selector"), match.group("value")
    assert "*" not in value, (
        f"the filter pattern {pattern!r} uses a wildcard; a wildcard can match an event name "
        "the emitter does not produce, which is exactly the parity this test asserts"
    )
    return selector, value


def _matches(pattern: str, record: dict[str, object]) -> bool:
    """Whether a CloudWatch JSON filter pattern selects a record. Equality shapes only."""
    selector, value = _selector_and_value(pattern)
    field = selector.removeprefix("$.")
    return record.get(field) == value


def _emitted_record(job_key: str) -> dict[str, object]:
    """The real record `report_job_complete` writes, formatted by the real formatter.

    The handler is attached to the emitter's own logger rather than to root, because
    `configure_logging` - which `report_job_complete` calls - clears root's handlers.
    """
    stream = io.StringIO()
    logger = logging.getLogger("intellichoice_observability.scheduled_jobs")
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    try:
        report_job_complete(job_key, deleted=0)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
    written = stream.getvalue().strip()
    assert written, f"report_job_complete({job_key!r}) emitted nothing at all"
    return json.loads(written)


def test_every_nightly_job_filter_pattern_selects_the_emitted_event() -> None:
    """RD-01 itself. One assertion per job key, so the failure names the job that is dark."""
    job_keys = _terraform_job_keys()
    assert len(job_keys) >= 4, (
        f"parser found only {job_keys} nightly job keys; the regex or the environment has drifted"
    )

    for job_key in job_keys:
        pattern = _render_pattern(job_key)
        record = _emitted_record(job_key)
        assert _matches(pattern, record), (
            f"{job_key}: the metric filter searches for "
            f"{_selector_and_value(pattern)[1]!r} but the emitter writes "
            f"{record['event']!r} - JobCompletions can never publish a datapoint for this job, "
            "and its heartbeat alarm can never leave ALARM"
        )


def test_the_job_dimension_stays_the_hyphenated_terraform_key() -> None:
    """The other half, and the reason the fix went on the terraform side.

    The alarm's `job` dimension reads `$.job` out of the same record. Making the event name
    match by teaching the emitter to stop rewriting hyphens would have fixed the pattern and
    broken the dimension, so this pins the field the pattern must *not* be reconciled against.
    """
    dimensions = _DIMENSIONS_LINE.search(_filter_body())
    assert dimensions is not None, "the nightly_jobs metric_transformation lost its `dimensions`"
    assert '"$.job"' in dimensions.group("body"), (
        f"the `job` dimension no longer reads `$.job`: {dimensions.group('body').strip()!r}"
    )

    for job_key in _terraform_job_keys():
        assert _emitted_record(job_key)["job"] == job_key, (
            f"{job_key}: the record's `job` field no longer matches the terraform key verbatim, "
            "so the heartbeat alarm's dimension has nothing to match"
        )


def test_the_parity_matcher_rejects_a_mismatched_event_name() -> None:
    """The non-vacuity control (D-221), scoring the negative direction too.

    A matcher that returned `True` unconditionally would make the test above pass while the
    alarms stayed dark - which is the *original* defect's shape, not a hypothetical. So:
    one job's pattern must not select another job's record, and it must not select the
    hyphenated spelling the broken configuration searched for.
    """
    job_keys = _terraform_job_keys()
    pattern = _render_pattern(job_keys[0])
    assert not _matches(pattern, _emitted_record(job_keys[1]))
    assert not _matches(pattern, {"event": f"{job_keys[0]}_job_complete"})
