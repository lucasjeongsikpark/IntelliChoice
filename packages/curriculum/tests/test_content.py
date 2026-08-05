from intellichoice_curriculum.content import CurriculumContent, load_curriculum


def test_loads_three_seeded_topics() -> None:
    content = load_curriculum()

    assert content.topic_ids() == {"linear_equations", "fraction_operations", "place_value"}
    assert content.curriculum_version


def test_every_skill_references_a_known_topic() -> None:
    content = load_curriculum()
    topic_ids = content.topic_ids()

    for skill in content.skills:
        assert skill.topic_id in topic_ids


def test_linear_equations_has_five_skill_ladder() -> None:
    content = load_curriculum()
    linear_skills = {s.skill_id for s in content.skills_for_topic("linear_equations")}

    assert linear_skills == {
        "linear_one_step",
        "linear_two_step",
        "linear_neg_frac_coeff",
        "linear_both_sides",
        "linear_distribute",
    }


def test_every_prerequisite_edge_references_known_skills() -> None:
    content = load_curriculum()
    skill_ids = content.skill_ids()

    for edge in content.prerequisites:
        assert edge.skill_id in skill_ids
        assert edge.prerequisite_skill_id in skill_ids
        assert edge.skill_id != edge.prerequisite_skill_id


def test_prerequisite_for_returns_edge_or_none() -> None:
    content = load_curriculum()
    # `linear_two_step`'s prerequisite is `linear_one_step` (used by the §5.11.7 ladder's
    # easier-prerequisite step); the base skill `linear_one_step` has none.
    assert content.prerequisite_for("linear_two_step") == "linear_one_step"
    assert content.prerequisite_for("linear_one_step") is None
    assert content.prerequisite_for("no_such_skill") is None


def test_topics_for_grade_resolves_a_single_grade_through_its_band() -> None:
    content = load_curriculum()

    # The profile carries "6" or "7"; the map is keyed "6-7". Resolving the two is the
    # whole reason D-187 could read a map that had been loaded and ignored since S3.
    assert content.topics_for_grade("6") == ["linear_equations"]
    assert content.topics_for_grade("7") == ["linear_equations"]
    assert content.topics_for_grade("2") == ["place_value"]


def test_topics_for_grade_is_empty_for_a_grade_no_band_covers() -> None:
    content = load_curriculum()

    # Grade 3's band (2-3 in the §5.7.3 table) has no seeded topic, so the honest answer is
    # "no candidates" - which callers must not read as "no topics" (see topic_availability).
    assert content.topics_for_grade("3") == []
    assert content.topics_for_grade("") == []
    assert content.topics_for_grade("not-a-grade") == []


def test_topics_for_grade_matches_band_endpoints_rather_than_substrings() -> None:
    content = CurriculumContent(
        curriculum_version="test",
        topics=[],
        skills=[],
        prerequisites=[],
        grade_topic_candidates={"K-1": ["kindergarten_topic"], "11-12": ["algebra_2"]},
    )

    # "K" needs no ordinal, and "1" must not be swallowed by the "11-12" band.
    assert content.topics_for_grade("K") == ["kindergarten_topic"]
    assert content.topics_for_grade("k") == ["kindergarten_topic"]
    assert content.topics_for_grade("1") == ["kindergarten_topic"]
    assert content.topics_for_grade("12") == ["algebra_2"]
    assert content.topics_for_grade("2") == []


def test_grade_topic_candidates_reference_known_topics() -> None:
    content = load_curriculum()
    topic_ids = content.topic_ids()

    assert content.grade_topic_candidates
    for candidates in content.grade_topic_candidates.values():
        for topic_id in candidates:
            assert topic_id in topic_ids
