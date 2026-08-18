"""D-236: recorded human verdicts, and the ways one must stop applying.

A suppression list is a dangerous thing to add to an audit - it is the mechanism by which
a finding stops being reported, so every test here is about the record *failing* to
suppress rather than succeeding at it. The one that matters most is
`test_the_shipped_record_is_live`: a file of stale fingerprints suppresses nothing, looks
completely healthy, and would leave the audit exactly as noisy as it was before.
"""

from pathlib import Path

import pytest
import yaml
from intellichoice_curriculum.adjudications import (
    Adjudication,
    Findings,
    JudgedItem,
    classify,
    fingerprint,
    judge_inputs,
    load_adjudications,
    partition_findings,
)
from intellichoice_curriculum.authored_bank import load_authored_bank
from intellichoice_curriculum.content import load_curriculum
from intellichoice_shared.bedrock import QuestionJudgePayload


def _payload(**overrides: object) -> QuestionJudgePayload:
    base: dict[str, object] = dict(
        rendered_question="Solve for x: x + 3 = 7",
        option_a="4",
        option_b="5",
        option_c="10",
        option_d="3",
        correct_option="a",
        hint_ladder=["What undoes adding 3?"],
        canonical_solution="4",
        topic_name="Linear Equations",
        skill_name="Solve one-step linear equations",
        grade_band="6-7",
    )
    base.update(overrides)
    return QuestionJudgePayload(**base)  # type: ignore[arg-type]


def _verdict(**overrides: object) -> Adjudication:
    base: dict[str, object] = dict(
        question_template_id="authored-test-d5-1",
        decision="upheld",
        decided_on="2026-08-09",
        decided_in="D-235",
        declared_difficulty=5,
        judge_difficulty=2,
        fingerprint="abc123",
        rationale="because",
    )
    base.update(overrides)
    return Adjudication(**base)  # type: ignore[arg-type]


ANCHORS = {1: "one step", 5: "distribution required"}


def test_the_fingerprint_hashes_what_the_claim_actually_depends_on() -> None:
    """D-237: scope by verdict type, because over-hashing is not the safe direction.

    An `upheld` verdict is a claim about a specific instrument, so the prompt is in scope and
    a prompt change must lapse it. A `retiered` verdict is a human reading of content against
    a rubric, so the prompt is not an input - hashing it in made one shipped sentence lapse
    16 verdicts it had no bearing on, and a lapse that happens for no reason is one people
    learn to clear without reading.
    """
    payload, prompt = _payload(), "system prompt v1"
    instrument = fingerprint(payload, ANCHORS, prompt)
    content = fingerprint(payload, ANCHORS)

    assert fingerprint(payload, ANCHORS, prompt) == instrument, "stable for identical inputs"
    assert content != instrument, "the two scopes must not collide"

    # Both scopes move with the item and with the rubric it was judged against.
    for scope in (lambda p, a: fingerprint(p, a), lambda p, a: fingerprint(p, a, prompt)):
        base = scope(payload, ANCHORS)
        assert scope(_payload(option_b="6"), ANCHORS) != base, "an option changed"
        assert scope(_payload(hint_ladder=["x"]), ANCHORS) != base, "a hint changed"
        assert scope(payload, {1: "one step", 5: "REWORDED"}) != base, "the rubric changed"

    # Only the instrument scope moves with the prompt. This is the D-237 correction.
    assert fingerprint(payload, ANCHORS, "system prompt v2") != instrument
    assert fingerprint(payload, ANCHORS) == content


def test_a_verdict_stops_applying_when_its_item_or_its_instrument_moves() -> None:
    """Every way a record must lapse, one assertion each."""
    live = _verdict(fingerprint="fp-1", declared_difficulty=5)
    common: dict[str, object] = dict(current_fingerprint="fp-1", disagrees=True)

    assert classify(adjudication=live, declared_difficulty=5, **common) == "known"  # type: ignore[arg-type]
    assert classify(adjudication=None, declared_difficulty=5, **common) == "new"  # type: ignore[arg-type]
    # The tier moved, so whatever was decided was decided about a different claim.
    assert classify(adjudication=live, declared_difficulty=4, **common) == "lapsed_tier"  # type: ignore[arg-type]
    # The item, its anchors or the judge prompt changed.
    assert (
        classify(
            adjudication=live,
            declared_difficulty=5,
            current_fingerprint="fp-2",
            disagrees=True,
        )
        == "lapsed_content"
    )


def test_a_retiered_item_suppresses_nothing() -> None:
    """It was changed to match the judge, so agreement is now the expectation.

    Recording it and then suppressing on it would hide the one outcome worth knowing: that
    a re-tier did not take, either because the tier is still wrong or because the judge is
    reading the item differently than the anchors say.
    """
    retiered = _verdict(decision="retiered", fingerprint="fp-1", declared_difficulty=4)
    assert (
        classify(
            adjudication=retiered,
            declared_difficulty=4,
            current_fingerprint="fp-1",
            disagrees=True,
        )
        == "new"
    )


def test_an_upheld_verdict_the_judge_now_agrees_with_is_reported_as_spent() -> None:
    """The instrument moving is the finding, and it produces no flag to notice it by.

    An `upheld` verdict says the judge is wrong. The day it starts agreeing, the item is
    clean, nothing is flagged, and the only trace is a suppression that quietly stopped
    being needed. `moot` exists so that shows up in the report instead.
    """
    upheld = _verdict(fingerprint="fp-1", declared_difficulty=5)
    assert (
        classify(
            adjudication=upheld,
            declared_difficulty=5,
            current_fingerprint="fp-1",
            disagrees=False,
        )
        == "moot"
    )


def test_two_verdicts_for_one_item_is_an_error(tmp_path: Path) -> None:
    """A second verdict must replace the first, not sit beside it - otherwise which one
    applies depends on file order, and the record silently means whatever it was written in.
    """
    doc = {
        "version": 1,
        "adjudications": [
            _verdict().model_dump(),
            _verdict(rationale="a different reason").model_dump(),
        ],
    }
    path = tmp_path / "adjudications.yaml"
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError, match="two adjudications"):
        load_adjudications(path)


def test_a_missing_file_is_empty_rather_than_an_error(tmp_path: Path) -> None:
    """The state every environment was in before D-236, and every new topic starts in."""
    assert load_adjudications(tmp_path / "nothing-here.yaml") == {}


def test_every_verdict_points_at_an_item_that_still_exists() -> None:
    """A verdict about a deleted or retired item is dead weight that reads as coverage."""
    banks = load_authored_bank()
    known_ids = {t.question_template_id for ts in banks.values() for t in ts}
    orphans = sorted(set(load_adjudications()) - known_ids)
    assert not orphans, f"adjudications for items no longer in the bank: {orphans}"


def test_an_upheld_verdict_suppresses_something_that_would_have_been_flagged() -> None:
    """`upheld` only earns its keep on a gap the audit would actually report.

    The §5.8.5 gap threshold is 2. A verdict recorded on a gap of 1 suppresses nothing,
    because nothing would have been flagged - it would sit in the file looking like a
    decision while doing no work at all.
    """
    thin = [
        f"{a.question_template_id} (declared {a.declared_difficulty}, judge {a.judge_difficulty})"
        for a in load_adjudications().values()
        if a.decision == "upheld"
        and a.judge_difficulty is not None
        and abs(a.declared_difficulty - a.judge_difficulty) < 2
    ]
    assert not thin, f"upheld verdicts on a gap the audit would not flag anyway: {thin}"


def test_the_shipped_record_is_live() -> None:
    """The failure mode a suppression list hides best: every fingerprint stale.

    Nothing would look wrong. The file parses, the ids resolve, the audit runs - and not one
    verdict applies, so the report is exactly as noisy as it was before the file existed.

    **A lapse is legitimate, so read the failure before "fixing" it.** Editing an item, a
    topic's `difficulty_anchors` or the judge system prompt all lapse verdicts on purpose,
    because a verdict is a claim about a specific instrument. The remedy is one of two
    deliberate acts, never a re-generated hash: re-run `audit_authored_bank.py --judge` and
    decide again on what it now reports, or delete the entries whose subject no longer
    exists. Refreshing the fingerprint without re-deciding re-asserts a judgement nobody
    made.
    """
    curriculum = load_curriculum()
    topics = {t.topic_id: t for t in curriculum.topics}
    by_id = {t.question_template_id: t for ts in load_authored_bank().values() for t in ts}
    stale = []
    for template_id, verdict in load_adjudications().items():
        item = by_id[template_id]
        payload, anchors, prompt = judge_inputs(item)
        current = (
            fingerprint(payload, anchors)
            if verdict.decision == "retiered"
            else fingerprint(payload, anchors, prompt)
        )
        if verdict.fingerprint != current:
            stale.append(template_id)
        elif verdict.declared_difficulty != item.difficulty_label:
            stale.append(f"{template_id} (tier {item.difficulty_label})")
    assert not stale, (
        f"{len(stale)} of {len(load_adjudications())} verdicts no longer apply to their "
        f"item under the current judge prompt and anchors: {stale}"
    )
    assert topics, "sanity: the taxonomy loaded"


def test_partition_reports_new_and_lapsed_and_suppresses_only_known() -> None:
    """The whole report shape in one pass, on the logic that decides what a human never sees.

    Written when `--judge` could only be run by paying, which is why the partition is a pure
    function here rather than a loop inside the script. **D-238 found that diagnosis wrong in
    its details:** the mock provider did have a `QUESTION_JUDGE` branch, but D-194's field
    rename had left it emitting a response that failed validation, so it was indistinguishable
    from no branch at all. Both are fixed and `--judge` now runs free end to end.

    This test stays as it is. The end-to-end run exercises the arms the *bank* happens to
    produce; these cases pin each arm deliberately, including the ones a real bank rarely
    reaches - and a hash-driven mock is not a stable enough oracle to assert a partition on.
    """
    verdicts = {
        "known-1": _verdict(
            question_template_id="known-1", fingerprint="fp", declared_difficulty=5
        ),
        "lapsed-1": _verdict(
            question_template_id="lapsed-1", fingerprint="OLD", declared_difficulty=5
        ),
        "retiered-1": _verdict(
            question_template_id="retiered-1",
            decision="retiered",
            fingerprint="content",
            declared_difficulty=4,
        ),
        "moot-1": _verdict(question_template_id="moot-1", fingerprint="fp", declared_difficulty=5),
    }
    judged = [
        JudgedItem("known-1", 5, 2, True, "content", "fp"),
        JudgedItem("lapsed-1", 5, 2, True, "content", "fp"),
        JudgedItem("retiered-1", 4, 2, True, "content", "fp"),
        JudgedItem("moot-1", 5, 5, False, "content", "fp"),
        JudgedItem("never-seen", 3, 1, True, "content", "fp"),
        JudgedItem("clean", 2, 2, False, "content", "fp"),
    ]

    findings = partition_findings(judged, verdicts)

    assert [i.question_template_id for i in findings.new] == ["retiered-1", "never-seen"]
    assert [i.question_template_id for i in findings.known] == ["known-1"]
    assert [i.question_template_id for i in findings.lapsed] == ["lapsed-1"]
    assert [i.question_template_id for i in findings.moot] == ["moot-1"]
    # A clean item with no verdict is in no bucket at all - it is not a finding.
    assert "clean" not in {
        i.question_template_id
        for b in (findings.new, findings.known, findings.lapsed, findings.moot)
        for i in b
    }


def test_an_empty_record_reports_every_finding_as_new() -> None:
    """The pre-D-236 behaviour must be exactly what an empty file produces.

    If adding the mechanism changed what a bank with no verdicts reports, the mechanism
    would be doing something other than filtering.
    """
    judged = [JudgedItem(f"item-{n}", 5, 2, True, "content", "fp") for n in range(3)]
    findings = partition_findings(judged, {})
    assert len(findings.new) == 3
    assert (findings.known, findings.lapsed, findings.moot) == ([], [], [])
    assert isinstance(findings, Findings)
