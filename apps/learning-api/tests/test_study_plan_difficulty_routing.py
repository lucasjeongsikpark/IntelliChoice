"""AUD-L-12: `Mastery.recommended_difficulty` narrows template choice within the chosen
skill (SPEC §5.11.2 rules 2-3).

**Why these tests are synthetic, and why that is the honest form here.** The live bank is
1:1 skill<->difficulty - 5 approved skills, 10 templates each, one tier apiece - so
`_closest_to_recommended` provably returns the whole pool for *every* possible
recommendation, and no end-to-end test on real content can distinguish the wired
implementation from the unwired one. That masking is the finding. These tests therefore
build multi-tier templates by hand, which is the only way to exercise the mechanism before
real content has two tiers for one skill; the wiring itself (mastery row -> selector) is
asserted separately against the real flow in
`test_learning_flow.py::test_difficulty_recommendation_reaches_template_selection`.

No database: `_select_template` needs exactly one repository method, so a stub gives a
faster and stricter test than seeding rows would.
"""

import asyncio
import random

import pytest
from intellichoice_db.models.questions import QuestionTemplate
from learning_api.services.study_plan import (
    StudyPlanBuildError,
    _closest_to_recommended,
    _select_template,
)


def _template(template_id: str, difficulty: int) -> QuestionTemplate:
    """Only the two columns the selector reads. Never flushed, so the rest stay unset."""
    return QuestionTemplate(question_template_id=template_id, difficulty_label=difficulty)


class _StubQuestionRepo:
    def __init__(self, templates: list[QuestionTemplate]) -> None:
        self._templates = templates
        self.calls: list[str] = []

    async def get_active_questions_for_skill(self, skill_id: str) -> list[QuestionTemplate]:
        self.calls.append(skill_id)
        return list(self._templates)


def _select(
    templates: list[QuestionTemplate],
    recommended: int | None,
    used: set[str] | None = None,
) -> QuestionTemplate:
    repo = _StubQuestionRepo(templates)
    return asyncio.run(
        _select_template(
            repo,  # type: ignore[arg-type]  # stub implements the one method used
            "linear_two_step",
            used or set(),
            random.Random(7),
            recommended,
        )
    )


_MULTI_TIER = [_template("t1", 1), _template("t2", 2), _template("t3", 3), _template("t5", 5)]


def test_recommended_tier_is_preferred_exactly_when_available() -> None:
    """Rule 2: an exact tier match wins outright, not merely gets weighted."""
    assert _select(_MULTI_TIER, 3).question_template_id == "t3"
    assert _select(_MULTI_TIER, 1).question_template_id == "t1"


def test_widens_to_plus_or_minus_one_when_no_exact_match() -> None:
    """Rule 3: recommended 4 has no template; tiers 3 and 5 are both one away and tiers 1
    and 2 are excluded. Asserted on the *pool* rather than on the pick, because which of
    the two `rng` chooses is not the property under test - and a membership assertion on
    the pick would pass by luck against an unfiltered pool.
    """
    pool = _closest_to_recommended(_MULTI_TIER, 4)
    assert {t.question_template_id for t in pool} == {"t3", "t5"}
    assert _select(_MULTI_TIER, 4).question_template_id in {"t3", "t5"}


def test_falls_back_to_the_whole_pool_rather_than_serving_nothing() -> None:
    """A recommendation with nothing within +/-1 must not empty the pool - a skill with an
    unreachable recommendation still has to be servable.
    """
    only_tier_five = [_template("t5", 5), _template("t5b", 5)]
    assert _select(only_tier_five, 1).question_template_id in {"t5", "t5b"}


def test_no_recommendation_leaves_selection_untouched() -> None:
    """The remediation path passes `None` deliberately (see `flow._advance_study`); it must
    behave exactly as the pre-AUD-L-12 selector did.
    """
    assert _select(_MULTI_TIER, None).question_template_id in {"t1", "t2", "t3", "t5"}
    assert _closest_to_recommended(_MULTI_TIER, None) == _MULTI_TIER


def test_difficulty_outranks_the_unused_template_rule() -> None:
    """SPEC ranks rules 2-3 above rule 4, so a *used* template at the recommended tier beats
    an unused one two tiers away. This is the assertion that would fail if the unused-first
    filter were applied across the full pool instead of within the difficulty-matched one -
    the ordering bug that is easy to write and invisible on 1:1 content.
    """
    templates = [_template("exact-used", 3), _template("far-unused", 5)]
    chosen = _select(templates, 3, used={"exact-used"})
    assert chosen.question_template_id == "exact-used"


def test_unused_first_still_applies_within_the_matched_tier() -> None:
    """Rule 4 is not discarded, only subordinated: among templates at the recommended tier,
    an unused one is still preferred.
    """
    templates = [_template("tier3-used", 3), _template("tier3-unused", 3)]
    chosen = _select(templates, 3, used={"tier3-used"})
    assert chosen.question_template_id == "tier3-unused"


def test_selection_is_deterministic_under_a_seeded_rng() -> None:
    """Phase 10: identical inputs route identically. Narrowing the pool changes how much
    `rng` state a choice consumes, so this guards the property the narrowing could break.
    """
    first = _select(_MULTI_TIER, 4).question_template_id
    for _ in range(5):
        assert _select(_MULTI_TIER, 4).question_template_id == first


def test_no_approved_templates_still_raises_before_difficulty_is_considered() -> None:
    with pytest.raises(StudyPlanBuildError, match="no approved templates"):
        _select([], 3)


def test_the_live_bank_shape_makes_the_narrowing_inert() -> None:
    """Documents the masking as an executable claim rather than a comment: for a skill with
    a single tier, every recommendation - equal, adjacent, or far - yields the same full
    pool. If this test ever fails, real content has gained a second tier per skill and the
    other tests here have started describing production behaviour.
    """
    one_tier = [_template("a", 2), _template("b", 2), _template("c", 2)]
    for recommended in (None, 1, 2, 3, 5):
        assert _closest_to_recommended(one_tier, recommended) == one_tier
