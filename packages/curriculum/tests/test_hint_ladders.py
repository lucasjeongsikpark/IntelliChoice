"""S21: pure-data validation of the hand-authored canonical hint ladders for the
shape-based template bank - no DB, no LLM. Reuses the same leak-phrase and
monotonicity checks S20's authored-item validation runs (`authored_validation.py`),
generalized to plain `list[str]` so both callers share one implementation.
"""

from intellichoice_curriculum.authored_validation import (
    hint_ladder_monotonicity_violations,
    leak_phrase_present,
)
from intellichoice_curriculum.hint_ladders import SHAPE_HINT_LADDERS
from intellichoice_curriculum.templates.registry import SHAPES

_REQUIRED_HINT_LEVELS = 3


def test_every_registered_shape_has_a_canonical_ladder() -> None:
    assert set(SHAPE_HINT_LADDERS) == set(SHAPES)


def test_every_ladder_has_exactly_three_levels() -> None:
    for key, ladder in SHAPE_HINT_LADDERS.items():
        assert len(ladder) == _REQUIRED_HINT_LEVELS, key


def test_no_ladder_level_is_empty() -> None:
    for key, ladder in SHAPE_HINT_LADDERS.items():
        assert all(level.strip() for level in ladder), key


def test_no_ladder_level_contains_a_leak_phrase() -> None:
    for key, ladder in SHAPE_HINT_LADDERS.items():
        for level in ladder:
            assert not leak_phrase_present(level), (key, level)


def test_no_ladder_has_a_monotonicity_violation() -> None:
    for key, ladder in SHAPE_HINT_LADDERS.items():
        assert hint_ladder_monotonicity_violations(ladder) == [], key


def test_ladder_levels_are_distinct() -> None:
    for key, ladder in SHAPE_HINT_LADDERS.items():
        assert len(set(ladder)) == len(ladder), key
