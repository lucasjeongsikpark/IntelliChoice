from intellichoice_curriculum.content import CurriculumContent, load_curriculum


def test_loads_every_seeded_topic() -> None:
    """The exact set, not a count - a topic added without a decision should fail here.

    The four concept topics are the calibrated bank (D-222 through D-238). The six `g1_`/`g2_`
    topics are C1's K-2 wave (D-273), whose taxonomy is authored but whose items are not
    generated yet, so they will report `available=False` until the wave runs - which is a
    fact about the bank, not about this file (D-187 made availability a bank read).

    The seven added in D-274 are C1's 3-5 wave, and the twelve added in D-277 are the 6-8
    and 9-12 waves. Note what is *not* here: grade 3's addition, multiplication and division
    books, both grades' fraction rows, and grade 6's add/subtract fractions are covered by
    existing topics rather than by new ones - `skill_groups.yaml` records that mapping, and
    duplicating them would mean two topics teaching one thing.
    """
    content = load_curriculum()

    assert content.topic_ids() == {
        # the calibrated concept bank
        "linear_equations",
        "fraction_operations",
        "multiplication_division",
        "place_value",
        # C1 K-2 wave (D-273)
        "g1_addition",
        "g1_subtraction",
        "g1_word_problems",
        "g2_addition",
        "g2_subtraction",
        "g2_word_problems",
        # C1 3-5 wave (D-274/275)
        "g3_word_problems",
        "g4_multiplication_division",
        "g4_word_problems",
        "g5_word_problems",
        "decimals",
        "measurement",
        "number_sense",
        # C1 6-8 wave (D-277)
        "g6_fractions",
        "g6_word_problems",
        "g6_geometry_measurement",
        "pre_algebra",
        "algebra_foundations",
        "geometry_measures",
        "g68_word_problems",
        # C1 9-12 wave (D-277)
        "algebra_1",
        "algebra_2",
        "trigonometry",
        "calculus",
        "statistics_advanced",
        # C1 Phase 5 — family C (D-279). Authored deterministically by
        # `scripts/author_figure_items.py`, not generated: their skills carry no
        # `difficulty_tiers`, so no paid run can schedule them.
        "telling_time",
        "data_graphs",
        "plane_figures",
        "coordinate_geometry",
    }
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
    #
    # **Asserted as "both grades of a band resolve identically, and the band's lead topic
    # is first", not as a frozen list (D-277).** Every wave adds topics to bands, and a
    # frozen list turns "content was authored" into a test failure about recommendation
    # order. What must not drift is that a grade reaches its band at all.
    assert content.topics_for_grade("6") == content.topics_for_grade("7")
    assert content.topics_for_grade("6")[0] == "linear_equations"
    # D-228: a band may name more than one topic, and the order is the recommendation
    # order. C1's K-2 wave (D-273) put six topics into the two bands that already existed
    # rather than adding a "K-1" band, which would have matched grade 1 first and taken it
    # from `place_value` - the theft the next test guards. A grade-2 student's own year is
    # addition and subtraction, so those lead and the support skills follow.
    assert content.topics_for_grade("1") == content.topics_for_grade("2")
    assert content.topics_for_grade("1")[0] == "g1_addition"
    assert content.topics_for_grade("3")[0] == "g2_addition"
    # The support skill follows the year's own work rather than leading it.
    assert content.topics_for_grade("1")[-1] == "place_value"


def test_adding_a_band_never_steals_a_grade_from_an_existing_one() -> None:
    """§5.7.3's bands overlap, and `topics_for_grade` returns the *first* match.

    So band ordering is load-bearing, and the obvious way to add a topic for grade 3 - a
    new "3-4" band - would sit above "4-5" and silently take grade 4 away from
    `fraction_operations` (D-228 chose the already-populated "2-3" band for exactly this
    reason). Pinned per grade rather than per band, because the failure is a *grade*
    resolving to the wrong topic and a band-shaped assertion would not show it.
    """
    content = load_curriculum()

    # **The property, not a snapshot (D-277).** This asserted `topics_for_grade("4") ==
    # ["fraction_operations"]`, which broke the moment the 3-5 wave's topics were added to
    # the "4-5" band - a content addition failing a test whose subject is band *ordering*.
    # What theft actually looks like is a grade resolving to a band that does not contain
    # it, so that is what is checked: every grade lands in a band whose endpoints name it.
    for grade in [str(n) for n in range(1, 13)]:
        topics = content.topics_for_grade(grade)
        assert topics, f"grade {grade} resolves to no band"
        band = next(
            b for b, t in content.grade_topic_candidates.items() if t == topics
        )
        assert grade in {part.strip() for part in band.split("-")}, (
            f"grade {grade} resolved to band {band!r}, which does not name it"
        )

    # The specific theft D-228 guarded against, kept because it is the concrete case:
    # a "3-4" band placed above "4-5" would give grade 4 the grade-3 topics.
    assert "multiplication_division" not in content.topics_for_grade("4")
    assert "fraction_operations" not in content.topics_for_grade("3")
    assert "g4_multiplication_division" not in content.topics_for_grade("3")


def test_topics_for_grade_is_empty_for_a_grade_no_band_covers() -> None:
    content = load_curriculum()

    # D-227 populated grade 3's band (2-3 in the §5.7.3 table), so the real taxonomy no
    # longer has a covered-grade-with-no-candidates case. What is left here is the shape of
    # the answer for input no band can cover, which callers must not read as "no topics"
    # (see topic_availability). The populated-band cases are asserted above.
    # D-277: grades 1-12 are now all covered, so the uncovered case is input outside the
    # scale entirely. That is the case callers must not read as "no topics" - it means "we
    # cannot place this student", which is a different answer (see topic_availability).
    assert content.topics_for_grade("") == []
    assert content.topics_for_grade("not-a-grade") == []
    assert content.topics_for_grade("13") == []
    assert content.topics_for_grade("K") == []


def test_no_grade_is_stranded_between_two_populated_bands() -> None:
    """D-227: grade 3 sat between the populated `1-2` and `4-5` bands and got nothing.

    The failure mode is a *hole*, not an uncovered edge. A grade above or below everything
    we have authored honestly has no candidates - a grade-9 student is simply out of scope
    today. A grade **between** two populated bands is different: the student is inside the
    range this product serves and still gets "recommended nothing", which reads as an empty
    bank right up until the bank fills, and then reads as a defect.

    An earlier version of this test asserted every declared band's endpoints resolve. That
    passed against the broken mapping, because 3 was not an endpoint of any declared band -
    it guarded nothing. This one fails against it.

    It also indirectly pins the endpoint-matching trap: bands match by explicit endpoint
    membership, not by range, so "fixing" a hole by renaming `1-2` to `1-3` would strand
    grade 2 and fail here for the same reason.
    """
    content = load_curriculum()
    numeric = sorted(
        int(part)
        for band in content.grade_topic_candidates
        for part in band.split("-")
        if part.strip().isdigit()
    )
    stranded = [
        grade
        for grade in range(numeric[0], numeric[-1] + 1)
        if not content.topics_for_grade(str(grade))
    ]
    assert not stranded, (
        f"grades {stranded} sit inside the range this taxonomy serves "
        f"({numeric[0]}-{numeric[-1]}) and are recommended nothing"
    )


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
