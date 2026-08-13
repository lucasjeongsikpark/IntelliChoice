"""D-187: the topic picker's availability, and the invariant tying it to the grade map."""

from intellichoice_curriculum.content import CurriculumContent, TopicDef, load_curriculum
from learning_api.services.assessment_builder import (
    DIFFICULTIES,
    EXAM_QUESTION_COUNT,
    QUESTIONS_PER_DIFFICULTY,
)
from learning_api.services.topic_availability import build_topic_options


def _content() -> CurriculumContent:
    """Two topics and a grade map, independent of the real taxonomy so a future content
    change cannot make these tests pass or fail for the wrong reason.
    """
    return CurriculumContent(
        curriculum_version="test",
        topics=[
            TopicDef(topic_id="stocked", name="Stocked", grade_band="6-7"),
            TopicDef(topic_id="empty", name="Empty", grade_band="1-2"),
        ],
        skills=[],
        prerequisites=[],
        grade_topic_candidates={"6-7": ["stocked"], "1-2": ["empty"]},
    )


def _full_bank() -> dict[int, int]:
    return {difficulty: QUESTIONS_PER_DIFFICULTY for difficulty in DIFFICULTIES}


def test_a_topic_with_a_full_bank_is_available_and_an_empty_one_is_not() -> None:
    options = {
        o.topic_id: o
        for o in build_topic_options(
            curriculum=_content(),
            active_counts={"stocked": _full_bank()},
            grade=None,
        )
    }

    assert options["stocked"].available is True
    assert options["empty"].available is False


def test_one_short_difficulty_no_longer_closes_a_topic_that_can_still_fill_an_exam() -> None:
    """**Inverted in D-302, and the two halves have to move together.**

    This used to assert that a gap at any single tier closed the whole topic, because the
    exam sampled `QUESTIONS_PER_DIFFICULTY` from each of five tiers and a short tier was a
    build failure rather than a smaller exam. D-302 stores the judge's tier on a `flagged`
    verdict, which moved 214 items down against 116 up and emptied the top tiers: under the
    old rule openable topics would have gone 26 -> 12. Measured under this one: 33 -> 33.

    So the rule is now "can this topic fill one exam", and a topic short at d3 but holding a
    surplus elsewhere is available - it serves a tier-skewed exam, which is the uneven and
    biased distribution the user accepted in exchange for filling the question count.
    """
    bank = _full_bank()
    bank[3] = QUESTIONS_PER_DIFFICULTY - 1
    bank[2] += 1  # the surplus pass 2 tops up from
    assert sum(bank.values()) == EXAM_QUESTION_COUNT
    options = {
        o.topic_id: o
        for o in build_topic_options(
            curriculum=_content(), active_counts={"stocked": bank}, grade=None
        )
    }

    assert options["stocked"].available is True


def test_a_topic_that_cannot_fill_one_exam_is_still_unavailable() -> None:
    """The floor did not disappear, it moved. A topic one item short of an exam must stay
    closed, because `build_pre_exam` raises on exactly this shape and an available topic the
    builder refuses is the 503 this module exists to prevent.
    """
    bank = _full_bank()
    bank[3] = QUESTIONS_PER_DIFFICULTY - 1
    assert sum(bank.values()) == EXAM_QUESTION_COUNT - 1
    options = {
        o.topic_id: o
        for o in build_topic_options(
            curriculum=_content(), active_counts={"stocked": bank}, grade=None
        )
    }

    assert options["stocked"].available is False


def test_the_grade_map_can_never_recommend_a_topic_the_bank_cannot_serve() -> None:
    """The invariant the whole reconciliation rests on. A grade-2 student's candidate
    topic is `empty`; recommending it would produce a click that 503s.
    """
    options = {
        o.topic_id: o
        for o in build_topic_options(
            curriculum=_content(),
            active_counts={"stocked": _full_bank()},
            grade="2",
        )
    }

    assert options["empty"].available is False
    assert options["empty"].recommended_for_grade is False
    for option in options.values():
        assert not (option.recommended_for_grade and not option.available)


def test_a_grade_inside_the_band_is_recommended_its_stocked_topic() -> None:
    options = {
        o.topic_id: o
        for o in build_topic_options(
            curriculum=_content(),
            active_counts={"stocked": _full_bank()},
            grade="7",
        )
    }

    assert options["stocked"].recommended_for_grade is True


def test_an_unknown_grade_annotates_nothing_but_still_offers_every_topic() -> None:
    """Grade 3 is in no seeded band today, and "no candidates" must never collapse into
    "no topics" - the picker is the student's only way in.
    """
    options = build_topic_options(
        curriculum=_content(), active_counts={"stocked": _full_bank()}, grade="3"
    )

    assert [o.topic_id for o in options] == ["stocked", "empty"]
    assert not any(o.recommended_for_grade for o in options)
    assert any(o.available for o in options)


def test_a_missing_profile_costs_the_hint_and_nothing_else() -> None:
    options = build_topic_options(
        curriculum=_content(), active_counts={"stocked": _full_bank()}, grade=None
    )

    assert [o.available for o in options] == [True, False]
    assert not any(o.recommended_for_grade for o in options)


def test_the_real_taxonomy_names_only_topics_the_picker_can_render() -> None:
    """Guards the seam the frontend used to own: every topic in a grade band must exist in
    the taxonomy, or the picker would annotate a row it never renders.
    """
    curriculum = load_curriculum()
    topic_ids = curriculum.topic_ids()

    options = build_topic_options(curriculum=curriculum, active_counts={}, grade=None)
    assert {o.topic_id for o in options} == topic_ids
    for band in curriculum.grade_topic_candidates:
        for candidate in curriculum.grade_topic_candidates[band]:
            assert candidate in topic_ids
