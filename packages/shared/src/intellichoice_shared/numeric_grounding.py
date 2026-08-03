"""Numeric-grounding check for generated narrative text (S26, plan §18-L7).

Every number a model writes into a student-facing narrative must already exist in the
deterministic evidence JSON assembled *before* the call - the model is never trusted to
compute or invent a number itself (same "model proposes, code verifies" split as
`RagAnswerResponse`'s citation-quote check, D-038). `stage_narrative` (S26) is the first
caller; S28's report interpretation reuses this same module (plan §18-L9) rather than a
second bespoke check.

Matching allows rounding to the nearest integer or one decimal place, since a model may
reasonably phrase `2.6666...` as "about 2.7" - exact-only matching would reject ordinary
rounding as if it were an invented number. `bool` is excluded from evidence value
collection even though Python's `bool` is an `int` subclass, since a stray `True`/`False`
should never be treated as groundable numeric content.

## D-163: three false-rejection classes, each measured before it was fixed

`scripts/measure_report_grounding.py` ran the real deployed model 15 times across three
payload shapes and **every single generation was rejected** - so the parent-report
narrative had never once shipped under a real model, on any data. 85 of the 94 rejected
numbers came from one cause, and none of the three was the model inventing anything:

1. **Percent rendering.** Evidence carries `mastery_by_skill: 0.8333`; any competent
   parent-facing writer renders that as "83%". Nothing here understood scale, so the
   single most natural phrasing of a proportion was treated as fabrication. `_matches`
   now accepts a whole-percent rendering of an evidence value **that is itself a
   proportion in [0, 1]** - the bound is what keeps this from being a 100x fail-open:
   `raw_gain: 3.0` still does not ground the claim "improved 300%".
2. **Thousands separators.** `"1,284 hints"` tokenized as `1` and `284`, neither of which
   is in evidence, so a correctly-quoted number failed. That was a tokenizer bug, not a
   policy question - `1,284` *is* the number 1284.
3. **Numbers inside evidence strings.** `date_range_label` ("2026-07-01 to 2026-07-31")
   and `weak_skill_window_label` (which interpolates "70%") are evidence the model is
   shown and the prompt explicitly tells it to cite - but only `int`/`float` *values*
   were collected, so quoting the window it was told to name was ungrounded. Strings are
   now walked too. This is a false-negative fix, not a loosening: a number in an evidence
   string does exist in the evidence.

**What deliberately still fails**, verified in the same measurement: a model writing
"accuracy improved from 40% to 70%, a gain of 30 percentage points" over evidence that
contains no such trend is still rejected, because 0.30 is nowhere in the payload. The
check kept catching real inventions across the re-measurement; what it stopped doing was
rejecting faithful prose. `tests/test_numeric_grounding.py` pairs every widened rule with
a control asserting the invented-number case still fails.
"""

import re

# Ordered alternation: the grouped form is tried first so "1,284" is read whole rather
# than as "1" then "284". The lookbehind stops a grouped match from starting mid-number -
# without it "In 2026, 317 solutions" would match "026,317" and invent 26317.
_GROUPED = r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?"
_PLAIN = r"-?\d+(?:\.\d+)?"
_NUMBER_RE = re.compile(rf"(?<![\d.,])(?:{_GROUPED}|{_PLAIN})")

# Half a percentage point: what "rounded to the nearest whole percent" actually means.
# Deliberately an absolute tolerance rather than `round()`, because Python rounds halves
# to even - `round(62.5)` is 62, so a model writing the equally correct "63%" for an
# evidence value of 0.625 would have been rejected by a round-based rule.
_PERCENT_TOLERANCE = 0.5


def extract_numbers(text: str) -> list[float]:
    return [float(match.replace(",", "")) for match in _NUMBER_RE.findall(text)]


def _collect_evidence_numbers(value: object) -> list[float]:
    numbers: list[float] = []
    if isinstance(value, bool):
        return numbers
    if isinstance(value, (int, float)):
        numbers.append(float(value))
    elif isinstance(value, str):
        # D-163 cause 3. Dict keys are walked as well as values below: the model is shown
        # the whole serialized payload, so a number in a skill name or a window label is
        # as much a part of the evidence as one in a numeric field.
        numbers.extend(extract_numbers(value))
    elif isinstance(value, dict):
        for key, item in value.items():
            numbers.extend(_collect_evidence_numbers(key))
            numbers.extend(_collect_evidence_numbers(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            numbers.extend(_collect_evidence_numbers(item))
    return numbers


def _matches_at_same_scale(extracted: float, evidence_value: float) -> bool:
    if extracted == evidence_value:
        return True
    if round(extracted) == round(evidence_value):
        return True
    return round(extracted, 1) == round(evidence_value, 1)


def _matches(extracted: float, evidence_value: float) -> bool:
    if _matches_at_same_scale(extracted, evidence_value):
        return True
    # D-163 cause 1, bounded to proportions. An evidence value outside [0, 1] is not a
    # rate, so reading the narrative's number as a percentage of it would ground claims
    # like "300%" against `raw_gain: 3.0`.
    if 0.0 <= evidence_value <= 1.0:
        return abs(extracted - evidence_value * 100.0) <= _PERCENT_TOLERANCE
    return False


def is_grounded(narrative_text: str, evidence: dict) -> bool:
    """False if `narrative_text` contains any number that doesn't correspond to a numeric
    value found anywhere in `evidence` - exactly, within nearest-integer/one-decimal
    rounding, or as a whole-percent rendering of an evidence value that is a proportion in
    [0, 1]. Numbers written inside evidence *strings* count as evidence. A narrative with
    no numbers at all is trivially grounded.
    """
    evidence_numbers = _collect_evidence_numbers(evidence)
    for extracted in extract_numbers(narrative_text):
        if not any(_matches(extracted, value) for value in evidence_numbers):
            return False
    return True
