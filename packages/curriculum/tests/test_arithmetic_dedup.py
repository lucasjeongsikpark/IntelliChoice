"""The dedup gap that 86% acceptance hid (D-273, C1 wave K-2).

The first generated wave produced 55 items at 86% acceptance, and every one read well on its
own. Counted by their *arithmetic* rather than their prose, 27 of the 55 shared a number set
with another item and four separate items were `9 + 9`. All of them passed dedup, because
dedup asked about the story twice - exact stem text, then stem-embedding distance - and about
the mathematics never.

Both directions, per D-246: the check must collide on the same sum told two ways, and must
NOT collide on genuinely different sums that happen to share digits.

Free: pure string and regex work, no model call, no database.
"""

import json
import pathlib
import re

import pytest
from intellichoice_curriculum.authored_validation import arithmetic_identity


@pytest.mark.parametrize(
    ("first", "second"),
    [
        # The exact collisions measured in the wave.
        ("Eq(x, 4 + 5)", "Eq(x, 5 + 4)"),
        ("Eq(x, 4 + 5)", "x = 5 + 4"),  # both written forms, one identity
        ("Eq(x, 9 + 9)", "x = 9 + 9"),
        ("Eq(x, 7 + 6)", "x = 7 + 6"),
        ("Eq(x, 35 + 24)", "Eq(x, 24 + 35)"),
        ("x = 2456 + 1378", "x = 2456 + 1378"),
        ("Eq(x, 9 - 7)", "Eq(x, 9 - 7)"),
    ],
)
def test_the_same_sum_told_two_ways_is_one_identity(first, second):
    assert arithmetic_identity(first) == arithmetic_identity(second)


@pytest.mark.parametrize(
    ("first", "second", "why"),
    [
        ("Eq(x, 9 + 9)", "Eq(x, 9 - 9)", "same numbers, different operation"),
        ("Eq(x, 4 + 5)", "Eq(x, 4 + 6)", "different operand"),
        ("Eq(x, 15 + 9 - 6)", "Eq(x, 15 + 9)", "an extra step is a different question"),
        ("Eq(x, 35 + 28)", "Eq(x, 3 + 5 + 28)", "different decomposition"),
        # The direction that matters most: a false collision costs a good candidate.
        ("Eq(x, 12 - 3 - 4)", "Eq(x, 12 - 34)", "digits regrouped is not the same sum"),
    ],
)
def test_different_calculations_do_not_collide(first, second, why):
    assert arithmetic_identity(first) != arithmetic_identity(second), why


def test_only_a_digitless_equation_returns_none():
    """Written asserting that a symbolic expression returns None, which was wrong: it was my
    assumption, not the code's behaviour. `(x - 3)*(x + 3)` contains the digits 3 and 3, so
    it has an identity like anything else.

    **The limit that mistake exposed, stated rather than hidden.** For `value` items the
    digits are the operands and the identity means what it says. For `symbolic` items they
    are coefficients, so two genuinely different expressions with the same coefficients and
    operators would collide - `Eq(x, 3*x + 3)` and a rearrangement of it, say. That is a
    false positive costing one candidate, which is the cheap direction, and no symbolic
    content exists yet (family B is grades 9-12, unseeded). Revisit when the 9-12 wave runs
    rather than pre-emptively weakening a check that is currently exact for what it guards.
    """
    assert arithmetic_identity("(x - 3)*(x + 3)") == (("3", "3"), ("*", "+", "-"))
    assert arithmetic_identity("") is None
    assert arithmetic_identity("Eq(a, b)") is None


def test_it_catches_what_the_measured_wave_actually_shipped():
    """The evidence this check was written from, pinned so a regression is visible.

    These are real `answer_expression` values from the wave, in the multiplicities they
    appeared. If the identity ever stops collapsing them, the 27-of-55 duplication returns.
    """
    wave = [
        "Eq(x, 4 + 5)",
        "Eq(x, 5 + 4)",
        "x = 5 + 4",
        "Eq(x, 9 + 9)",
        "Eq(x, 9 + 9)",
        "Eq(x, 9 + 9)",
        "x = 9 + 9",
    ]
    identities = {arithmetic_identity(equation) for equation in wave}
    # Seven items, two genuinely distinct calculations.
    assert len(identities) == 2


# --- R3b: the frozen E5.2 / E5.3 corpora, now that the check is wired -------------------------
#
# `arithmetic_identity` was written for D-273 and left **unwired** for four waves, on the
# argument recorded in `ai_pipeline` §2b: the cause had been fixed upstream by
# `avoid_equations`, so the backstop was not worth four failing test fixtures. E5.2 supplied
# the number that argument was missing, and R3b wired it into the dedup stage. These two tests
# pin what the frozen corpora say it does - and, equally, what they say it does not.

_CORPUS_PATH = (
    pathlib.Path(__file__).resolve().parents[3]
    / "docs"
    / "resume_evidence"
    / "05_content_generation"
    / "defect_corpus.jsonl"
)
_E5_3_SCORES = (
    pathlib.Path(__file__).resolve().parents[3]
    / "docs"
    / "resume_evidence"
    / "05_content_generation"
    / "e5_3"
    / "validated_arm_scores.jsonl"
)


def _jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("record") != "header":
                rows.append(record)
    return rows


@pytest.mark.skipif(not _CORPUS_PATH.exists(), reason="corpus artifact not built")
def test_every_e5_2_near_duplicate_mutant_collides_with_its_source():
    """17/17, at every cosmetic severity, where the paid embedding check managed 8/17.

    The corpus clones a clean control and edits it cosmetically at three graded severities -
    typography only, protagonist renamed, protagonist **and** story object renamed. The
    embedding check at `NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD = 0.05` scores 6/6, 2/6 and
    **0/5** across those tiers, because a renamed story is not a near-verbatim copy. The
    arithmetic is preserved by construction in all three, so the identity is unmoved - and
    the third tier is the shape D-273 actually measured in production output.

    Scored the way the pipeline scopes it: against the reference set **of the same topic**,
    never against itself.
    """
    records = _jsonl(_CORPUS_PATH)
    reference: dict[str, dict[tuple, str]] = {}
    for record in records:
        if record["label"] != "clean":
            continue
        item = record["item"]
        identity = arithmetic_identity(item.get("answer_expression") or "")
        if identity is not None:
            reference.setdefault(item["topic_id"], {})[identity] = record["corpus_id"]

    mutants = [r for r in records if r["defect_class"] == "near_duplicate"]
    assert len(mutants) == 17
    caught = []
    for record in mutants:
        identity = arithmetic_identity(record["item"].get("answer_expression") or "")
        if identity is None:
            continue
        if reference.get(record["item"]["topic_id"], {}).get(identity):
            caught.append(record["corpus_id"])
    assert len(caught) == 17


@pytest.mark.skipif(not _E5_3_SCORES.exists(), reason="E5.3 artifact not present")
def test_the_e5_3_residual_is_a_class_this_check_provably_cannot_catch():
    """A negative result, recorded because R3's own task spec asserted the opposite.

    E5.3's whole validated-arm residual is 8 of 174 machine-accepted items carrying
    `duplicate scenario (skeleton collision)` - **the same sentence with different numbers**
    (`E5_3_REPORT.md` §5.1). Different numbers mean a different identity by construction, so
    the fingerprint cannot see them, and this asserts that rather than leaving it to be
    rediscovered: all four same-topic groups among the eight survivors have two distinct
    identities, e.g. `Eq(x, 120/6)` beside `Eq(x, 56/8)`.

    What would catch them is a *skeleton* check scoped within a topic - D-286's
    `stem_skeleton_exists_in_another_topic` with its cross-topic scoping dropped. That is a
    separate instrument with a separate cost: the approved bank contains 8 same-topic skeleton
    groups covering 35 items, and at least 22 of those are legitimate by design
    (`place_value_compare`'s "Which of these numbers is the largest?" twelve times,
    `time_read_clock`'s "What time does this clock show?" ten times), which is precisely the
    reason D-286's docstring gives for scoping its check across topics only. So E5.3's
    residual stays open, and this test is where that is written down.
    """
    rows = [r for r in _jsonl(_E5_3_SCORES) if r["defect_families"]]
    assert len(rows) == 8
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        skeleton = re.sub(r"[0-9]+(\.[0-9]+)?", "#", row["stem"].lower())
        groups.setdefault((row["topic_id"], skeleton), []).append(row)
    assert len(groups) == 4
    for members in groups.values():
        identities = {arithmetic_identity(m["equation"]) for m in members}
        assert len(identities) == len(members), (
            "if this ever fails the fingerprint has started catching E5.3's class and the "
            "R3 report's residual analysis is stale"
        )
