"""Which topics may be offered to a student, and which its grade suggests (D-187).

Before this, availability had two disagreeing sources and neither was the bank:
`apps/learning-web/src/topics.ts` hard-coded `available: true/false` per topic, and
`grade_topic_candidates` (SPEC §5.7.3) was loaded by `content.load_curriculum` and never
read at runtime at all. A grade-based picker built on the second would have offered topics
with no questions behind them; the first had to be hand-edited every time content landed.

Both are answered here from the one fact that actually decides it - whether
`assessment_builder.build_pre_exam` could build an exam for the topic *right now*. The
threshold is imported from that module rather than restated, so the offer and the build
cannot drift: a topic this service calls available and the builder then refuses is exactly
the 503 this exists to prevent.
"""

from intellichoice_curriculum.content import CurriculumContent
from pydantic import BaseModel

from learning_api.services.assessment_builder import DIFFICULTIES, QUESTIONS_PER_DIFFICULTY


class TopicOption(BaseModel):
    """One row of the topic picker. No skill ids, no per-difficulty counts, no
    "needs 1 more template at difficulty 3" - the audience is a K-12 student, and internal
    curriculum structure stays internal (SPEC §5.10.3). The operator-facing detail is in
    the pipeline's own tooling, not in a student's response body.
    """

    topic_id: str
    name: str
    grade_band: str
    available: bool
    recommended_for_grade: bool


def build_topic_options(
    *,
    curriculum: CurriculumContent,
    active_counts: dict[str, dict[int, int]],
    grade: str | None,
) -> list[TopicOption]:
    """Every taxonomy topic, in taxonomy order, annotated rather than filtered.

    **Never filters.** Today's seeded students are grades 2-5 and the only topic with
    content is `linear_equations` (band 6-7), so a picker that showed only grade candidates
    would show most students an empty screen, and one that showed grade candidates
    *unfiltered by content* would offer `place_value` to a second-grader and 503 on the
    click. Showing everything, disabling what has no content, and marking what the grade
    suggests is the only combination that misleads nobody.

    `recommended_for_grade` is therefore conjunctive with `available` on purpose: the grade
    map may never surface a topic the bank cannot serve. `test_topic_availability.py` pins
    that, because it is the invariant the whole reconciliation rests on.
    """
    candidates = set(curriculum.topics_for_grade(grade)) if grade else set()
    options: list[TopicOption] = []
    for topic in curriculum.topics:
        available = _is_available(active_counts.get(topic.topic_id, {}))
        options.append(
            TopicOption(
                topic_id=topic.topic_id,
                name=topic.name,
                grade_band=topic.grade_band,
                available=available,
                recommended_for_grade=available and topic.topic_id in candidates,
            )
        )
    return options


def _is_available(counts_by_difficulty: dict[int, int]) -> bool:
    """`build_pre_exam`'s precondition, asked without building anything: every difficulty
    the exam spans needs at least as many approved templates as it samples.
    """
    return all(
        counts_by_difficulty.get(difficulty, 0) >= QUESTIONS_PER_DIFFICULTY
        for difficulty in DIFFICULTIES
    )
