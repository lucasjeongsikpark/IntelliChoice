"""A taxonomy skill with zero items must never become a study target (D-288).

Measured live before it was code: the calculus band walk's exam finalize returned 503 on
some runs and not others. `build_study_plan` ranks the *taxonomy's* skill list weakest
first, and `calc_differential_equations` - in the taxonomy, zero bank items - has no
mastery row, so after a graded exam it is the only skill scoring 0.0, ranks weakest, is
served FIRST, and `_select_template` finds nothing. The intermittency was the tie-break:
on runs where every stocked skill also scored 0.0, curriculum order pushed the empty skill
last and nothing fired.

Five topics carry such skills today (algebra_1 x2, algebra_2, calculus, g68_word_problems,
g6_fractions). Only calculus is currently servable, which is why only calculus 503'd - the
other four would arm the moment Phase 3 unblocks them.

Stub repositories, real curriculum: the topic under test is the real `calculus`, so the
test breaks if the taxonomy stops carrying the empty skill it exists to guard against -
at which point it should be updated to another, or to a synthetic taxonomy.
"""

import asyncio
import random
from dataclasses import dataclass, field

import pytest
from intellichoice_db.models.mastery import StudySession
from learning_api.services import study_plan
from learning_api.services.study_plan import StudyPlanBuildError, build_study_plan

TOPIC = "calculus"
EMPTY_SKILL = "calc_differential_equations"
STOCKED = {"calc_limits", "calc_derivatives", "calc_integrals"}


@dataclass
class _Mastery:
    weighted_score: float
    recommended_difficulty: int | None = None


class _StubQuestions:
    def __init__(self, stocked: set[str]) -> None:
        self._stocked = stocked

    async def skill_ids_with_servable_items(self, skill_ids):
        return {skill_id for skill_id in skill_ids if skill_id in self._stocked}


class _StubMastery:
    """The firing configuration: every stocked skill has a row (the exam just graded
    them), the empty skill has none - so unfiltered, the empty skill ranks weakest."""

    async def get_mastery(self, student_external_id, skill_id):
        return _Mastery(weighted_score=0.4) if skill_id in STOCKED else None


@dataclass
class _StubStudy:
    sessions: list[StudySession] = field(default_factory=list)

    async def create_study_session(self, session: StudySession) -> StudySession:
        session.study_session_id = "study-1"
        self.sessions.append(session)
        return session


def _build(monkeypatch: pytest.MonkeyPatch, *, stocked: set[str]) -> StudySession:
    created: list[str] = []

    @dataclass
    class _FakeItem:
        difficulty: int = 2  # build_study_plan records the served tier from the item

    async def _fake_create_study_item(**kwargs):
        created.append(kwargs["skill_id"])
        return _FakeItem()

    # Selection is what changed; item creation is covered by the flow tests and needs a
    # rendered variant, which selection does not.
    monkeypatch.setattr(study_plan, "create_study_item", _fake_create_study_item)
    study = _StubStudy()
    session = asyncio.run(
        build_study_plan(
            question_repo=_StubQuestions(stocked),  # type: ignore[arg-type]
            mastery_repo=_StubMastery(),  # type: ignore[arg-type]
            study_repo=study,  # type: ignore[arg-type]
            student_external_id="student-ext-test",
            topic_id=TOPIC,
            used_template_ids=set(),
            rng=random.Random(7),
        )
    )
    assert created, "the plan never served a first item"
    assert created[0] == session.target_skill_ids[0]
    return session


def test_an_empty_taxonomy_skill_is_never_a_study_target(monkeypatch) -> None:
    session = _build(monkeypatch, stocked=STOCKED)
    assert EMPTY_SKILL not in session.target_skill_ids, session.target_skill_ids
    # The stocked skills all still made the plan - filtering removed the unservable one,
    # not the ranking.
    assert set(session.target_skill_ids) == STOCKED


def test_the_empty_skill_would_have_ranked_first(monkeypatch) -> None:
    """Pins WHY this mattered: with no mastery row the empty skill scores 0.0 against the
    stocked skills' 0.4, so unfiltered it wins selection and is served first - the exact
    503 the calculus walk measured. If this assertion ever fails, the firing configuration
    has drifted and the first test is no longer testing the dangerous case."""
    session = _build(monkeypatch, stocked=STOCKED | {EMPTY_SKILL})
    assert session.target_skill_ids[0] == EMPTY_SKILL


def test_a_topic_with_no_servable_skill_still_fails_closed(monkeypatch) -> None:
    with pytest.raises(StudyPlanBuildError):
        _build(monkeypatch, stocked=set())
