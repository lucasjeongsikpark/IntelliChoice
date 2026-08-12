"""Loads the internal curriculum taxonomy (SPEC §5.7.2) from repo-root `curriculum/`."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

# Repo root is four levels up from this file: src/intellichoice_curriculum/content.py
# -> intellichoice_curriculum -> src -> curriculum (package dir) -> packages -> repo root.
DEFAULT_CONTENT_ROOT = Path(__file__).resolve().parents[4] / "curriculum" / "internal_math"


class TopicDef(BaseModel):
    topic_id: str
    name: str
    grade_band: str
    description: str = ""
    # The 1-5 difficulty rubric the judge rates this topic against (D-232). It lives here,
    # next to the topic it describes, rather than beside the judge prompt - because the
    # single global rubric that used to live there was written for `linear_equations`, was
    # correct for it, and silently became wrong for every topic added after (D-231: the
    # judge rated 20 of 21 `place_value` items "2", since none of them contain a negative
    # coefficient or a variable on both sides). A rubric kept next to the prompt is one
    # nobody edits when they add content; kept here, a topic without one is visible in the
    # same file the topic is declared in, and `test_every_topic_declares_difficulty_anchors`
    # makes it a failure rather than a silent fallback.
    difficulty_anchors: dict[int, str] = Field(default_factory=dict)


class AnswerFamily(BaseModel):
    """What kind of number a skill's answers are, and therefore which rules apply to them.

    **The problem this solves, measured (D-274).** `validate_equation_design` required every
    answer in the entire taxonomy to be a *positive whole number*, with the reasoning "a
    student cannot count a fraction of a thing". That is true of counting problems and false
    of the rest, and the constant had already outlived its scope: **26 of the 184 shipped
    items - the whole of `fraction_operations` - fail it**, so the pipeline could not
    regenerate 14% of its own bank. The docstring there said it would need to become a
    parameter "when such a topic exists"; `decimals`, `measurement` and the grade-5 word
    problems are that topic, three times over.

    A family is **not** a per-skill escape hatch. It names a genuinely different answer
    semantics, and the set stays small on purpose: two today, because two are what the
    content needs. A third belongs here when a topic needs it, not in anticipation - the
    same rule that kept `selection` out of the Phase-R router until something used it.

    Lives in the taxonomy rather than beside the validator for the reason D-232 gave when
    `difficulty_anchors` moved here: a rule kept next to the code that reads it is a rule
    nobody edits when they add content.
    """

    name: str
    whole_numbers_only: bool
    positive_only: bool
    # Handed to the designer verbatim when a proposal violates the family, so the retry
    # is told what to change rather than only that it was wrong (D-200's cheap-retry loop).
    guidance: str


ANSWER_FAMILIES: dict[str, AnswerFamily] = {
    "counting": AnswerFamily(
        name="counting",
        whole_numbers_only=True,
        positive_only=True,
        guidance=(
            "this skill counts discrete things, so the answer must be a positive whole "
            "number - change the quantities so the arithmetic comes out even"
        ),
    ),
    "rational": AnswerFamily(
        name="rational",
        whole_numbers_only=False,
        positive_only=True,
        guidance=(
            "this skill's answers are fractions, decimals, amounts of money or surds, so a "
            "non-whole answer is correct and expected - but it must still be positive"
        ),
    ),
    # D-277 adds the two the 6-8 and 9-12 bands need. Both were deliberately withheld in
    # D-274 - "a third belongs here when a topic needs it, not in anticipation" - and the
    # topics now exist: `prealg_negative_numbers` is *about* negative integers, and an
    # algebra or calculus answer is routinely negative, which `counting` and `rational` both
    # forbid. The four members are the two booleans crossed, and that is the whole space.
    "integer": AnswerFamily(
        name="integer",
        whole_numbers_only=True,
        positive_only=False,
        guidance=(
            "this skill's answers are whole numbers and may be negative - a negative answer "
            "is correct here, but a fraction is not"
        ),
    ),
    "signed": AnswerFamily(
        name="signed",
        whole_numbers_only=False,
        positive_only=False,
        guidance=(
            "this skill's answers may be negative and need not be whole - the value is "
            "whatever the mathematics gives, and no sign or roundness rule applies"
        ),
    ),
}

DEFAULT_ANSWER_FAMILY = "counting"


class SkillDef(BaseModel):
    skill_id: str
    topic_id: str
    name: str
    # The tiers this skill should carry content at (D-186), and the structure its equations
    # must have (D-200). Both used to be hand-written Python dicts in `ai_pipeline`, keyed
    # by skill id, which meant every new skill needed a source edit before it could be
    # generated at all - `TOPIC_SKILL_DIFFICULTIES` raises `PipelineConfigError` on a miss.
    # At 21 skills that was tolerable; the full taxonomy is 245 (D-274).
    #
    # Empty `difficulty_tiers` means "not authorable yet", which is a real state: a skill can
    # exist in the taxonomy for prerequisite edges and progress display before anyone has
    # decided where on the 1-5 ladder it lives.
    difficulty_tiers: list[int] = Field(default_factory=list)
    structure: str = ""
    answer_family: str = DEFAULT_ANSWER_FAMILY

    @field_validator("answer_family")
    @classmethod
    def _known_family(cls, value: str) -> str:
        if value not in ANSWER_FAMILIES:
            raise ValueError(
                f"unknown answer_family {value!r} "
                f"(known: {', '.join(sorted(ANSWER_FAMILIES))})"
            )
        return value

    @field_validator("difficulty_tiers")
    @classmethod
    def _tiers_on_the_scale(cls, value: list[int]) -> list[int]:
        outside = [t for t in value if t not in range(1, 6)]
        if outside:
            raise ValueError(f"difficulty tiers outside the 1-5 scale: {outside}")
        return sorted(set(value))

    @property
    def family(self) -> AnswerFamily:
        return ANSWER_FAMILIES[self.answer_family]


class PrerequisiteEdge(BaseModel):
    skill_id: str
    prerequisite_skill_id: str


class CurriculumContent(BaseModel):
    curriculum_version: str
    topics: list[TopicDef]
    skills: list[SkillDef]
    prerequisites: list[PrerequisiteEdge]
    grade_topic_candidates: dict[str, list[str]]

    def topic_ids(self) -> set[str]:
        return {t.topic_id for t in self.topics}

    def skill_ids(self) -> set[str]:
        return {s.skill_id for s in self.skills}

    def skills_for_topic(self, topic_id: str) -> list[SkillDef]:
        return [s for s in self.skills if s.topic_id == topic_id]

    def skill(self, skill_id: str) -> SkillDef | None:
        return next((s for s in self.skills if s.skill_id == skill_id), None)

    def generation_plan(self) -> dict[str, dict[str, list[int]]]:
        """topic_id -> skill_id -> the tiers that skill should carry content at.

        The authoring plan, derived from the taxonomy rather than hand-maintained beside the
        pipeline (D-274). Skills with no declared tiers are omitted, so "not authorable yet"
        and "authorable at no tier" stay the same thing they were when this was a Python
        dict: a topic or skill the planner does not know about.
        """
        plan: dict[str, dict[str, list[int]]] = {}
        for skill in self.skills:
            if not skill.difficulty_tiers:
                continue
            plan.setdefault(skill.topic_id, {})[skill.skill_id] = list(skill.difficulty_tiers)
        return plan

    def topics_for_grade(self, grade: str) -> list[str]:
        """The §5.7.3 candidate topic ids for a student's grade, or `[]` if none.

        `grade_topic_candidates` is keyed by *band* ("1-2", "6-7", and in the full §5.7.3
        table "K-1"), while a student's profile carries a single grade ("3"). Nothing
        resolved one to the other before D-187, which is why the map was loaded and never
        read - this is that resolution, kept here because the taxonomy owns both halves.

        Deliberately **not** a range comparison: bands are matched by explicit membership
        of their endpoints, so "K" needs no ordinal and a malformed key can only fail to
        match rather than silently swallow a neighbouring grade. A grade in no band (today:
        3, whose band 2-3 has no seeded topic) returns `[]` - the caller decides what that
        means, and no caller may treat "no candidates" as "no topics" (D-187).
        """
        wanted = grade.strip().upper()
        if not wanted:
            return []
        for band, candidates in self.grade_topic_candidates.items():
            if wanted in {part.strip().upper() for part in band.split("-")}:
                return list(candidates)
        return []

    def prerequisite_for(self, skill_id: str) -> str | None:
        """The immediate prerequisite skill for `skill_id`, or None if it has none.

        Used by the §5.11.7 retry ladder's 3rd step ("easier prerequisite problem"):
        an unresolved skill drops to a question from its prerequisite. The edges live in
        `prerequisites.yaml` and are read in-process (no Postgres table), so this
        remediation needs no schema (SPEC §5.7 / §5.11.2 rule 6).
        """
        for edge in self.prerequisites:
            if edge.skill_id == skill_id:
                return edge.prerequisite_skill_id
        return None


def _read_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def load_curriculum(content_root: Path = DEFAULT_CONTENT_ROOT) -> CurriculumContent:
    topics_doc = _read_yaml(content_root / "topics.yaml")
    skills_doc = _read_yaml(content_root / "skills.yaml")
    prerequisites_doc = _read_yaml(content_root / "prerequisites.yaml")
    grade_mapping_doc = _read_yaml(content_root / "grade_topic_mapping.yaml")

    return CurriculumContent(
        curriculum_version=topics_doc["curriculum_version"],
        topics=[TopicDef.model_validate(t) for t in topics_doc["topics"]],
        skills=[SkillDef.model_validate(s) for s in skills_doc["skills"]],
        prerequisites=[
            PrerequisiteEdge.model_validate(p) for p in prerequisites_doc["prerequisites"]
        ],
        grade_topic_candidates=grade_mapping_doc["grade_topic_candidates"],
    )
