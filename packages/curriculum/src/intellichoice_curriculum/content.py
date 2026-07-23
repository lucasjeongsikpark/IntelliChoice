"""Loads the internal curriculum taxonomy (SPEC §5.7.2) from repo-root `curriculum/`."""

from pathlib import Path

import yaml
from pydantic import BaseModel

# Repo root is four levels up from this file: src/intellichoice_curriculum/content.py
# -> intellichoice_curriculum -> src -> curriculum (package dir) -> packages -> repo root.
DEFAULT_CONTENT_ROOT = Path(__file__).resolve().parents[4] / "curriculum" / "internal_math"


class TopicDef(BaseModel):
    topic_id: str
    name: str
    grade_band: str
    description: str = ""


class SkillDef(BaseModel):
    skill_id: str
    topic_id: str
    name: str


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
