"""DRIFT-54: `scan_logs_pii.py`'s three allowlist excuses, each scored in both directions.

**Why this test has to exist at all.** Every entry excuses a match the scanner would otherwise
report as PII, which is the one kind of change to a detector that makes it weaker. The list's own
comment says an allowlist that grows to cover a real leak is the failure mode it exists to slow
down - and a comment cannot fail. That is not hypothetical here: the comment above the list
previously claimed, from a 2,774-event window, that nothing needed excusing, and named
`shape:pii-field-name` as the exception it had expected and found unnecessary. Run over the 8-day
window the scheduled workflow uses (319,732 events, 2026-08-24) both claims were wrong.

The three false positives, measured and **enumerated rather than sampled** - reading the classes
off the three examples the scanner prints got the split wrong once already:

  - `branch-latitude:39.85`, 78 of its 86 hits, ISO-8601 timestamps
    (`2026-08-24T06:19:39.853559+00:00`). The fixture branch latitude is `39.8500` and the shared
    matcher's boundary guard was written against X-Ray's epoch floats, where the character before
    the seconds is a digit; in an ISO timestamp it is a `:`.
  - `shape:pii-field-name`, 45 hits, exactly one distinct line: the OTel collector sidecar's
    `Serving metrics {"address": "localhost:8888", "metrics level": "Normal"}`. The pattern fires
    on the field *name*.
  - `branch-latitude:39.85`, the other 8 hits, the access log's own `"duration_ms": 39.85`.

**Both directions for each, per D-221, and per constraint rather than per entry.** An excuse is
only safe if it still lets through the thing it resembles, so the negative controls are
first-class here. For the timestamp: a bare coordinate, a quoted coordinate and a coordinate pair
must all remain hits. For the bind address: a real street address, a `display_name` field and a
wildcard bind. For the duration: `{"latitude": 39.85}` must remain a hit **on both of its paths**,
which is the entire reason that excuse is path-keyed - see `LogExcuse`'s docstring. An allowlist
regex that quietly widened - dropping the timezone suffix, matching the field name instead of a
loopback value, or un-anchoring the duration path - would pass a one-directional test and blind
the scanner to the leak it exists to catch.

The scanner is loaded from its path rather than imported, because `scripts/` is not a package -
the same idiom as `apps/chat-api/tests/test_access_probe_harness_parity.py`. It lives in this
package's tests because that is where its imports are declared: `boto3` and
`intellichoice_adapters.seed.mysql_fixtures` (the needle source) are both `intellichoice-adapters`
dependencies, and reaching across a package seam on the shared venv is a defect this repository
names explicitly.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "scan_logs_pii.py"

# The exact shape measured in staging: a `logger`-prefixed access-log line, and the same value
# again as the JSON-walked `timestamp` field, which is why one log line produced two hits.
_REAL_TIMESTAMP_HITS = [
    '{"event": "http_request", "timestamp": "2026-08-24T06:19:39.853559+00:00", '
    '"logger": "intellichoice.access", "method": "GET", "status_code": 200}',
    "2026-08-24T06:19:39.853559+00:00",
    "2026-08-24T16:34:39.858919+00:00",
    "2026-08-24T16:34:39.85Z",
]

# What the pattern is actually for. None of these carries a `THH:MM:` prefix *and* a timezone
# suffix, so none of them may be excused.
_REAL_COORDINATE_HITS = [
    '{"latitude": 39.85}',
    '{"lat": "39.8500"}',
    "branch at 39.85, -89.69",
    '{"precise_location": "39.850012,-89.6900"}',
]

# The collector line as it appears in staging, tabs included - the only `shape:pii-field-name`
# excerpt the 8-day enumeration found.
_COLLECTOR_BIND_ADDRESS = (
    "2026-08-24T06:19:11.001Z\tinfo\tservice@v0.115.0/service.go:230\tStarting exporters..."
    '\ttelemetry/metrics.go:70\tServing metrics\t{"address": "localhost:8888", '
    '"metrics level": "Normal"}'
)

# A person's address, and two other `shape:pii-field-name` subjects. None of these has a loopback
# value, so none of them may be excused - the entry is narrow on the *value*, not the field name,
# because the field name is the whole reason the pattern exists.
_REAL_FIELD_NAME_HITS = [
    '{"address": "123 Main St, Springfield"}',
    '{"display_name": "Kim"}',
    '{"address": "0.0.0.0:8888"}',
]


# The access-log line the third excuse is for, and the shape a real leak of the same value takes.
_ACCESS_LOG_DURATION = '{"event": "http_request", "status_code": 200, "duration_ms": 39.85}'
_LEAKED_LATITUDE = '{"event": "http_request", "latitude": 39.85}'


@pytest.fixture(scope="module")
def scanner() -> Any:
    spec = importlib.util.spec_from_file_location("_log_pii_scanner", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered in `sys.modules` before execution, not after: the script declares `@dataclass`
    # under `from __future__ import annotations`, and `dataclasses` resolves those string
    # annotations through `sys.modules[cls.__module__]`. Without this the import fails inside
    # the decorator with an unrelated-looking `AttributeError` on `NoneType.__dict__`.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _hits(scanner: Any, text: str) -> list[Any]:
    """Run one string through the real matcher and the real allowlist, as `main()` does."""
    findings = scanner.Findings()
    patterns = scanner._fixture_patterns() + scanner.SHAPE_PATTERNS
    scanner._match(patterns, text, findings)
    return scanner._apply_log_allowlist(findings)


def test_the_allowlist_is_exactly_the_three_measured_entries(scanner: Any) -> None:
    """The list's size and subjects are pinned, so a fourth entry is a visible decision.

    Every entry here weakens the scanner by construction. Growth is allowed - the comment above
    the list states the rules - but it must arrive as a diff on this assertion rather than as one
    more tuple nobody reviews.
    """
    assert [
        (e.pattern, e.path is not None, e.excerpt is not None) for e in scanner.LOG_ALLOWLIST
    ] == [
        ("branch-latitude:39.85", False, True),
        ("shape:pii-field-name", False, True),
        ("branch-latitude:39.85", True, True),
    ]


def _excerpt_rule(scanner: Any, index: int) -> Any:
    """One excuse's excerpt constraint, by declaration index."""
    rule = scanner.LOG_ALLOWLIST[index].excerpt
    assert rule is not None
    return rule


@pytest.mark.parametrize("text", _REAL_TIMESTAMP_HITS)
def test_an_iso_timestamp_second_is_excused_and_counted(scanner: Any, text: str) -> None:
    """The positive direction: the false positive is excused, and *counted* rather than dropped.

    `allowlisted` being incremented is half the point. The scanner prints that number, so an
    allowlist that starts absorbing hundreds of matches is visible in the run output instead of
    looking like a clean scan.
    """
    findings = scanner.Findings()
    patterns = scanner._fixture_patterns() + scanner.SHAPE_PATTERNS
    scanner._match(patterns, text, findings)
    assert findings.hits, f"the matcher no longer fires on {text!r} at all - this test is vacuous"

    kept = scanner._apply_log_allowlist(findings)
    assert [hit.pattern for hit in kept] == [], f"{text!r} was reported as PII"
    assert findings.allowlisted >= 1


@pytest.mark.parametrize("text", _REAL_COORDINATE_HITS)
def test_a_real_coordinate_is_still_a_hit(scanner: Any, text: str) -> None:
    """The negative direction (D-221): the leak this pattern exists for still exits 1.

    A coordinate never wears both halves of the excused shape - a `THH:MM:` prefix and a timezone
    suffix - which is the whole reason the entry can be this narrow. If a future edit drops either
    half to "simplify" the regex, this is what fails.
    """
    kept = _hits(scanner, text)
    assert any(hit.pattern.startswith("branch-latitude") for hit in kept), (
        f"{text!r} is a real coordinate leak and the allowlist swallowed it"
    )


def test_the_excused_timestamp_shape_requires_both_halves(scanner: Any) -> None:
    """The regex itself, scored against near-misses of its own shape.

    Neither half alone may excuse anything: a time-of-day with no timezone could be free text a
    caller supplied, and a bare `39.85` followed by an offset-looking suffix is not a timestamp.
    """
    excuse = _excerpt_rule(scanner, 0)
    assert excuse.search("2026-08-24T06:19:39.853559+00:00")
    assert excuse.search("2026-08-24T06:19:39.85Z")
    assert not excuse.search("06:19:39.853559")  # no `T` prefix, no timezone
    assert not excuse.search("T06:19:39.853559")  # no timezone suffix
    assert not excuse.search("39.85+00:00")  # no time-of-day context at all


def test_the_collector_bind_address_is_excused_and_counted(scanner: Any) -> None:
    """The positive direction for the second entry, on the real staging line."""
    findings = scanner.Findings()
    patterns = scanner._fixture_patterns() + scanner.SHAPE_PATTERNS
    scanner._match(patterns, _COLLECTOR_BIND_ADDRESS, findings)
    assert any(hit.pattern == "shape:pii-field-name" for hit in findings.hits), (
        "the matcher no longer fires on the collector's bind address - this test is vacuous"
    )

    kept = scanner._apply_log_allowlist(findings)
    assert [hit.pattern for hit in kept] == [], "the collector's bind address was reported as PII"
    assert findings.allowlisted >= 1


@pytest.mark.parametrize("text", _REAL_FIELD_NAME_HITS)
def test_a_real_pii_field_name_is_still_a_hit(scanner: Any, text: str) -> None:
    """The negative direction for the second entry (D-221).

    The entry is narrow on the *value* being loopback, never on the field name and never on the
    collector's log prose. `0.0.0.0:8888` is in this list on purpose: a collector that started
    binding a wildcard address would turn this workflow red, and that is the intended direction -
    a third entry then gets considered by a human rather than inherited.
    """
    kept = _hits(scanner, text)
    assert any(hit.pattern == "shape:pii-field-name" for hit in kept), (
        f"{text!r} must still be reported and the allowlist swallowed it"
    )


def test_the_excused_bind_address_shape_requires_a_loopback_value(scanner: Any) -> None:
    """The second regex itself, scored against near-misses.

    The field name alone must never excuse anything - that is the pattern's whole subject - and
    neither may a loopback mentioned anywhere else on the line.
    """
    excuse = _excerpt_rule(scanner, 1)
    assert excuse.search('{"address": "localhost:8888"}')
    assert excuse.search('{"address": "localhost:4318", "x": 1}')
    assert not excuse.search('{"address": "0.0.0.0:8888"}')  # wildcard bind, not loopback
    assert not excuse.search('{"address": "123 Main St"}')  # a person's address
    assert not excuse.search('"host": "localhost:8888"')  # some other field entirely


def test_a_suffixed_field_name_was_never_a_hit_and_this_allowlist_did_not_change_that(
    scanner: Any,
) -> None:
    """Measured while building the negative controls above, and recorded so it is not misread.

    `{"branch_address": "1 Elm St"}` produces **no** `shape:pii-field-name` hit, and it never did:
    the shared pattern is `\b(...|address|...)\b` and the `_` in `branch_address` is a word
    character, so the leading `\b` cannot match. That is a property of the shared matcher in
    `scan_xray_pii.py`, not of the allowlist added here - a future reader finding this line
    unreported must not conclude the allowlist swallowed it.

    Left as an observation rather than fixed: the shared matcher is criterion 9's *trace* evidence
    too, and widening it is a decision with its own blast radius. It is real coverage the
    field-name shape does not have, and the fixture-derived `branch-address:<value>` pattern
    covers this project's actual branch addresses by exact value regardless.
    """
    assert not [hit for hit in _hits(scanner, '{"branch_address": "1 Elm St"}')]
    # The prefix-free spelling is a hit, which is what makes the above a `\b` effect and not a
    # claim that the scanner ignores addresses.
    assert any(
        hit.pattern == "shape:pii-field-name" for hit in _hits(scanner, '{"address": "1 Elm St"}')
    )


def test_the_access_log_duration_is_excused_on_both_of_its_paths(scanner: Any) -> None:
    """The positive direction for the third excuse, on the real access-log line.

    One log line produces two hits here - the raw message (`$`) and the JSON-walked field
    (`$<json>.duration_ms`) - and they carry different evidence, so the excuse has to cover both.
    Asserting the paths explicitly is what keeps this test honest about *why* it passes.
    """
    findings = scanner.Findings()
    patterns = scanner._fixture_patterns() + scanner.SHAPE_PATTERNS
    scanner._match(patterns, _ACCESS_LOG_DURATION, findings)
    raw = [hit for hit in findings.hits if hit.pattern == "branch-latitude:39.85"]
    assert {hit.path for hit in raw} == {"$", "$<json>.duration_ms"}, (
        f"the matcher no longer produces both paths for this line: {[h.path for h in raw]}"
    )

    kept = scanner._apply_log_allowlist(findings)
    assert [hit for hit in kept if hit.pattern == "branch-latitude:39.85"] == []
    assert findings.allowlisted >= 2


def test_a_leaked_latitude_is_still_a_hit_on_both_paths(scanner: Any) -> None:
    """The negative control the path-aware mechanism exists for (D-221).

    `{"latitude": 39.85}`'s JSON-walked hit has the excerpt `39.85` - character for character what
    `"duration_ms": 39.85` produces on that path. That is why the duration excuse is keyed on the
    *path* and why the path regex is anchored: `\\.duration_ms$` cannot reach `$<json>.latitude`.
    An un-anchored or field-name-agnostic rule would silently excuse this line, which is the leak
    this whole scanner exists to catch.
    """
    kept = _hits(scanner, _LEAKED_LATITUDE)
    latitude_hits = [hit for hit in kept if hit.pattern == "branch-latitude:39.85"]
    assert {hit.path for hit in latitude_hits} == {"$", "$<json>.latitude"}, (
        f"a leaked latitude was partly or wholly excused: {[h.path for h in latitude_hits]}"
    )


def test_the_duration_excuse_is_anchored_to_one_field(scanner: Any) -> None:
    """The third excuse's two constraints, each scored on its own.

    `excuses()` treats them as alternatives, so each has to be narrow by itself - a loose path
    rule would be enough to excuse a coordinate even with a perfect excerpt rule beside it.
    """
    excuse = scanner.LOG_ALLOWLIST[2]
    assert excuse.path is not None and excuse.excerpt is not None

    assert excuse.path.search("$<json>.duration_ms")
    assert not excuse.path.search("$<json>.latitude")
    assert not excuse.path.search("$<json>.longitude")
    # Anchored, so a field that merely *starts* with the name cannot inherit the excuse.
    assert not excuse.path.search("$<json>.duration_ms_bucket")
    assert not excuse.path.search("$")

    assert excuse.excerpt.search('"duration_ms": 39.85}')
    assert excuse.excerpt.search('"duration_ms": 39.8512}')
    assert not excuse.excerpt.search('"latitude": 39.85}')
    assert not excuse.excerpt.search("39.85")  # the bare JSON-walked value, path's job not this


def test_an_excuse_with_no_constraint_at_all_excuses_nothing(scanner: Any) -> None:
    """The mechanism's own floor: `LogExcuse(pattern)` alone must never match.

    `excuses()` returns True on the first constraint that matches, so a future entry written with
    neither constraint filled in would be the widest possible rule if the default were `True`.
    Pinned here rather than trusted, because that entry would look harmless in review.
    """
    empty = scanner.LogExcuse("branch-latitude:39.85")
    hit = scanner.Hit("branch-latitude:39.85", "$<json>.latitude", "39.85")
    assert not empty.excuses(hit)
