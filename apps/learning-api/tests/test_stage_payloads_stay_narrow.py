"""AUD-L-09/D-098 mitigation 2: each stage narrative sees only its own stage's evidence.

The finding is that numeric grounding checks a number's *provenance*, not its
*attribution* - so every number in a narrative's evidence is a number that narrative can
misattribute. `numeric_grounding` now rejects one attribution error (the pre/post pair
stated in reverse); this file pins the other half of D-098's disposition, which is
structural rather than algorithmic: **give each stage fewer numbers to confuse.**

That property already held when the finding was fixed - `study_outro` carries usage counts
and no scores, `pre_intro` carries no numbers at all - so there was nothing to implement,
and a fix with nothing to implement is exactly the kind that silently regresses. Adding
`pre_raw_score` to a `study_step` payload would be a one-line change that widens what that
stage's prose can get wrong, passes every behavioural test, and shows up nowhere.

**Source-level rather than behavioural, and deliberately so.** The property is "this call
site does not pass that field", and the payloads are built inside graph nodes from resolved
DB state - a behavioural test would need a full pre->study->post cycle per stage to observe
a *negative* (a field that is not there), which is both slow and weaker: it would pass just
as happily if the field were present and merely None. Same reasoning, and the same AST
shape, as `packages/db/tests/test_standalone_clis_use_the_env_fallback.py`.

The anti-vacuity control matters here more than usual (D-171 §2): a test that finds zero
construction sites - because the class was renamed, or a site moved to a file not listed
below - would pass while checking nothing. `test_every_stage_is_constructed_somewhere`
fails in that case.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Every module that builds a `StageNarrativePayload` for a real request. Kept as an
# explicit list rather than a tree walk so that a *new* construction site in a new file is
# a deliberate addition here, not an untested one.
_CONSTRUCTION_SITES = [
    "apps/learning-api/src/learning_api/graph/nodes.py",
    "apps/learning-api/src/learning_api/routers/stream.py",
]

# What each stage is allowed to carry, and nothing more. `stage` and `grade` are on every
# payload: `grade` reaches the prompt for age-appropriate wording (SPEC §5.10.3) and holds
# no figure a narrative could get wrong.
_ALWAYS_ALLOWED = {"stage", "grade"}

_ALLOWED_BY_STAGE: dict[str, set[str]] = {
    # Fires before any question is answered, so there is no result to describe yet.
    "pre_intro": {"attendance_status"},
    # Names the skills to work on. Scores exist by now and are deliberately not passed:
    # the pre-exam number belongs to the post-exam comparison, not to this transition.
    "pre_outro": {"weak_skill_names", "target_skill_name"},
    # A move between two skills. Two names, no counts.
    "study_step": {"completed_skill_name", "target_skill_name"},
    # Usage counts for the study phase. No scores: the post-exam has not run.
    "study_outro": {"hint_count", "solution_count", "video_count"},
    # The one stage that legitimately compares two scores, and therefore the only one where
    # the directional check in `numeric_grounding` can fire at all.
    "post_outro": {
        "weak_skill_names",
        "pre_raw_score",
        "post_raw_score",
        "raw_gain",
        "normalized_gain",
        "independent_correct_rate",
        "relevant_learning_facts",
    },
}


def _payload_constructions() -> list[tuple[str, int, str, set[str]]]:
    """(file, line, stage, keyword names) for every `StageNarrativePayload(...)` call whose
    `stage=` is a literal string. A call with a computed stage would be invisible to this
    test, so it is reported as a failure instead of skipped.
    """
    found: list[tuple[str, int, str, set[str]]] = []
    unresolved: list[str] = []
    for relative in _CONSTRUCTION_SITES:
        path = _REPO_ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "StageNarrativePayload":
                continue
            keywords = {kw.arg for kw in node.keywords if kw.arg is not None}
            stage_values = [
                kw.value.value
                for kw in node.keywords
                if kw.arg == "stage"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ]
            if len(stage_values) != 1:
                unresolved.append(f"{relative}:{node.lineno}")
                continue
            found.append((relative, node.lineno, stage_values[0], keywords))
    assert not unresolved, (
        "a StageNarrativePayload is built with a non-literal `stage`, so this test cannot "
        f"tell which stage's fields to check: {unresolved}"
    )
    return found


def test_every_stage_is_constructed_somewhere() -> None:
    """The control. Without it, a rename of the class or a move to an unlisted module makes
    every assertion below pass over an empty list.
    """
    constructions = _payload_constructions()
    assert constructions, "no StageNarrativePayload construction found - is the class renamed?"
    stages = {stage for _, _, stage, _ in constructions}
    assert stages == set(_ALLOWED_BY_STAGE), (
        "the set of stages built in production code no longer matches this test's table: "
        f"built={sorted(stages)} expected={sorted(_ALLOWED_BY_STAGE)}"
    )


@pytest.mark.parametrize("relative,line,stage,keywords", _payload_constructions())
def test_a_stage_payload_carries_only_its_own_stages_fields(
    relative: str, line: int, stage: str, keywords: set[str]
) -> None:
    allowed = _ALWAYS_ALLOWED | _ALLOWED_BY_STAGE[stage]
    extra = keywords - allowed
    assert not extra, (
        f"{relative}:{line} passes {sorted(extra)} to a `{stage}` narrative. Every number in "
        "a payload is a number that stage's prose can misattribute (AUD-L-09), and numeric "
        "grounding cannot catch a wrong claim about a number the evidence really contains. "
        "If the stage genuinely needs the field, widen the table above and say why."
    )


def test_only_the_post_exam_stage_sees_both_scores() -> None:
    """Stated as its own assertion because it is the property the directional check depends
    on: `_known_score_pair` needs both scores present, so if a second stage started carrying
    them, that stage's narrative would come under a rule written for the post-exam comparison.
    """
    with_both = {
        stage
        for stage, allowed in _ALLOWED_BY_STAGE.items()
        if {"pre_raw_score", "post_raw_score"} <= allowed
    }
    assert with_both == {"post_outro"}
