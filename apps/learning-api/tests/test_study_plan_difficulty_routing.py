"""AUD-L-12: `Mastery.recommended_difficulty` narrows template choice within the chosen
skill (SPEC §5.11.2 rules 2-3).

**Why the first tests here are synthetic, and why that stopped being the whole story
(D-341).** When this file was written the live bank was 1:1 skill<->difficulty - 5 approved
skills, 10 templates each, one tier apiece - so `_closest_to_recommended` provably returned
the whole pool for *every* recommendation, and no test on real content could distinguish the
wired implementation from the unwired one. That masking was the finding, and hand-built
multi-tier templates were the only way to exercise the mechanism.

**That premise is now false, and the tests at the bottom of this file are the consequence.**
Measured 2026-08-15: 958 approved items, and **81 of 96 spanning skills hold templates at more
than one tier**. Real content can exercise this now. The synthetic tests stay - they pin the
branch behaviour precisely, which a real-content test cannot - but they are no longer the only
honest form. The wiring itself (mastery row -> selector) is asserted separately against the
real flow in `test_learning_flow.py::test_difficulty_recommendation_reaches_template_selection`.

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


def test_difficulty_yields_rather_than_repeating_a_used_template() -> None:
    """**This assertion was inverted on purpose (D-325), and the reason is measured.**

    It used to read: "SPEC ranks rules 2-3 above rule 4, so a *used* template at the
    recommended tier beats an unused one two tiers away." That is faithful to §5.11.2 and it
    was wrong in practice, because `used_template_ids` is seeded from the session's own
    pre-exam - so "prefer the used template at the right tier" meant serving the student the
    exact question they were about to be re-scored on. Dev database, before the change: **57
    of 201 study items repeated one of their own session's exam templates, 40 of them at the
    first study item**, driven by tiers holding as little as one approved template.

    **The concern this test was written to protect has not been dropped, only moved.** It
    guarded against applying unused-first across the *whole* pool unconditionally - an easy
    ordering bug, invisible on 1:1 content. That guard now lives in
    `test_the_exact_tier_still_wins_when_it_has_something_unused`, which fails if widening
    becomes the default rather than the fallback.
    """
    templates = [_template("exact-used", 3), _template("far-unused", 5)]
    chosen = _select(templates, 3, used={"exact-used"})
    assert chosen.question_template_id == "far-unused"


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


# --- D-325: the recommended tier yields rather than repeating the exam's question ---------
#
# `used_template_ids` is seeded from the session's own pre-exam, so "fall back to a used
# template" meant handing the student the exact question they were about to be re-scored on.
# Measured on the dev database before the change: **57 of 201 study items repeated one of
# their own session's exam templates, 40 at the very first study item.** The cause is pool
# size, not a missing filter - `g4_mult_by_one_digit` holds one approved template at tier 1.


def test_an_exhausted_recommended_tier_widens_instead_of_repeating() -> None:
    """**The defect, as a test.** One template at the recommended tier, and the exam already
    used it. The old code returned that same template because `pool = unused or matched` had
    narrowed `matched` to the exact tier; there is an unused template one tier away and it
    should be served instead."""
    templates = [_template("t-tier3-used", 3), _template("t-tier4-free", 4)]

    chosen = _select(templates, recommended=3, used={"t-tier3-used"})

    assert chosen.question_template_id == "t-tier4-free", (
        "the recommended tier had nothing unused, so a different question one tier away "
        "beats re-serving the question the student is scored on"
    )


def test_widening_picks_the_nearest_free_tier_not_merely_any_free_one() -> None:
    """A recommendation is still a preference, so giving it up should cost as little as the
    bank allows. Without the nearest-first sort this would be free to return tier 1."""
    templates = [
        _template("t-tier3-used", 3),
        _template("t-tier1-free", 1),
        _template("t-tier4-free", 4),
    ]

    chosen = _select(templates, recommended=3, used={"t-tier3-used"})

    assert chosen.question_template_id == "t-tier4-free"


def test_a_fully_used_skill_still_serves_rather_than_failing() -> None:
    """Fail-closed has a limit: when every approved template has been used there is no
    alternative to repeating, and serving nothing would be a 503 in the student's face. The
    repeat is logged instead (`study_template_repeat_unavoidable`) because at that point the
    fix is content, not code."""
    templates = [_template("only-one", 3)]

    chosen = _select(templates, recommended=3, used={"only-one"})

    assert chosen.question_template_id == "only-one"


def test_the_exact_tier_still_wins_when_it_has_something_unused() -> None:
    """The control. Widening must not become the default - SPEC §5.11.2 ranks the difficulty
    recommendation above novelty, and this change only lets it yield when the tier is empty.
    Without this a "fix" that always widened would pass the three tests above."""
    templates = [
        _template("t-tier3-used", 3),
        _template("t-tier3-free", 3),
        _template("t-tier4-free", 4),
    ]

    chosen = _select(templates, recommended=3, used={"t-tier3-used"})

    assert chosen.question_template_id == "t-tier3-free"


# ---------------------------------------------------------------------------------------
# D-341: the same function, against the REAL curriculum rather than hand-built templates.
#
# This file's header says the tests above are synthetic because "no end-to-end test on real
# content can distinguish the wired implementation from the unwired one". That was true of a
# 5-skill, one-tier-each bank. It is not true now: 81 of 96 spanning skills carry approved
# templates at more than one tier, so the branches select genuinely different pools.
#
# These two tests exist because of a *decision*, not just a growth in content. 15 spanning
# skills declare tiers the bank does not stock yet (`adv_vectors` declares [2, 4, 5] and holds
# only tier 2), and the user's ruling is that those declarations **stay** - the gaps close by
# generating content, not by narrowing the taxonomy. That makes the final fallback load-bearing
# rather than defensive, and a test that never asks whether a declared-but-unstocked tier is
# still servable would be missing the one thing the decision depends on.
# ---------------------------------------------------------------------------------------


def _real_curriculum_spanning_skills() -> list[tuple[str, list[int]]]:
    from intellichoice_curriculum.content import load_curriculum

    return [
        (s.skill_id, sorted(s.difficulty_tiers))
        for s in load_curriculum().skills
        if len(s.difficulty_tiers) > 1
    ]


def test_every_declared_tier_of_every_spanning_skill_is_servable() -> None:
    """**The property the taxonomy decision rests on.**

    For each spanning skill, and each tier it declares, `_closest_to_recommended` must return a
    non-empty pool from whatever that skill actually holds - including the 15 skills whose
    declared tiers are ahead of the bank. Empty means a student recommended that tier gets no
    question at all, which is how a declared-but-unstocked tier would become a dead end.

    Driven from the real declarations rather than a fixture list, so a taxonomy edit is covered
    the moment it lands instead of when someone remembers to update a constant.
    """
    spanning = _real_curriculum_spanning_skills()
    assert spanning, "the curriculum has no spanning skills - this test would be vacuous"

    for skill_id, declared in spanning:
        # The worst case the bank can present: a single stocked tier, as far from the
        # recommendation as this skill's declaration allows.
        for stocked_tier in {declared[0], declared[-1]}:
            pool = [_template(f"{skill_id}-only", stocked_tier)]
            for recommended in declared:
                got = _closest_to_recommended(pool, recommended)
                assert got, (
                    f"{skill_id} declares tier {recommended} but a bank holding only tier "
                    f"{stocked_tier} returned no candidates - that tier is a dead end"
                )


def test_an_exactly_matching_tier_still_wins_over_a_nearby_one() -> None:
    """The other half: the fallback must not have swallowed the preference.

    A function that always returned the whole pool would pass the test above trivially - it is
    satisfied by never being empty. This one fails unless the exact-match branch actually
    narrows, which is the behaviour AUD-L-12 found unwired and the reason the file exists.
    """
    pool = [_template("far", 1), _template("exact", 4), _template("near", 5)]
    assert [t.question_template_id for t in _closest_to_recommended(pool, 4)] == ["exact"]
