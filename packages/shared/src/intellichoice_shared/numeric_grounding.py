"""Numeric-grounding check for generated narrative text (S26, plan §18-L7).

Every number a model writes into a student-facing narrative must already exist in the
deterministic evidence JSON assembled *before* the call - the model is never trusted to
compute or invent a number itself (same "model proposes, code verifies" split as
`RagAnswerResponse`'s citation-quote check, D-038). `stage_narrative` (S26) is the first
caller; S28's report interpretation is planned to reuse this same module (plan §18-L9)
rather than a second bespoke check.

Matching allows rounding to the nearest integer or one decimal place, since a model may
reasonably phrase `2.6666...` as "about 2.7" or "67%" for `0.6666...` when the evidence
also carries a percent-scaled field - exact-only matching would reject ordinary rounding
as if it were an invented number. `bool` is excluded from evidence value collection even
though Python's `bool` is an `int` subclass, since a stray `True`/`False` should never be
treated as groundable numeric content.
"""

import re

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def extract_numbers(text: str) -> list[float]:
    return [float(match) for match in _NUMBER_RE.findall(text)]


def _collect_evidence_numbers(value: object) -> list[float]:
    numbers: list[float] = []
    if isinstance(value, bool):
        return numbers
    if isinstance(value, (int, float)):
        numbers.append(float(value))
    elif isinstance(value, dict):
        for item in value.values():
            numbers.extend(_collect_evidence_numbers(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            numbers.extend(_collect_evidence_numbers(item))
    return numbers


def _matches(extracted: float, evidence_value: float) -> bool:
    if extracted == evidence_value:
        return True
    if round(extracted) == round(evidence_value):
        return True
    return round(extracted, 1) == round(evidence_value, 1)


def is_grounded(narrative_text: str, evidence: dict) -> bool:
    """False if `narrative_text` contains any number that doesn't correspond (exactly,
    or within nearest-integer/one-decimal rounding) to a numeric value found anywhere in
    `evidence`. A narrative with no numbers at all is trivially grounded.
    """
    evidence_numbers = _collect_evidence_numbers(evidence)
    for extracted in extract_numbers(narrative_text):
        if not any(_matches(extracted, value) for value in evidence_numbers):
            return False
    return True
