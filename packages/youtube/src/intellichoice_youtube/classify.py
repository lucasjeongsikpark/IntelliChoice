"""SPEC §5.18: classifies a video's topic/skill/difficulty coverage from its
title+description via a Bedrock structured-output call, then re-validates every
proposed name against the real curriculum registry before trusting it (D-038/D-026's
"model proposes, code re-derives" pattern, applied here to catalog labels instead of
citations/shape keys) - an invented or misspelled name is silently dropped, never
stored as a `topic_id`/`skill_id`.
"""

from dataclasses import dataclass

from intellichoice_curriculum.content import CurriculumContent
from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    VideoClassificationPayload,
    VideoClassificationResponse,
)

# Safe defaults when classification can't run at all (Bedrock unavailable). An
# unclassified video simply never matches any skill-scoped `search_catalog` call
# (empty topic_ids/skill_ids), so it can't surface an incorrect recommendation - it
# isn't dropped from the catalog outright, since a later re-sync may classify it.
_FALLBACK_GRADE_BAND = "3-5"
_FALLBACK_DIFFICULTY_MIN = 1
_FALLBACK_DIFFICULTY_MAX = 5


@dataclass(frozen=True)
class VideoClassification:
    topic_ids: list[str]
    skill_ids: list[str]
    grade_band: str
    difficulty_min: int
    difficulty_max: int


async def classify_video(
    gateway: BedrockGateway,
    curriculum: CurriculumContent,
    *,
    title: str,
    description: str,
    session_spend_cents: float,
) -> tuple[VideoClassification, float]:
    topic_by_name = {t.name: t.topic_id for t in curriculum.topics}
    skill_by_name = {s.name: s.skill_id for s in curriculum.skills}

    try:
        result = await gateway.generate_structured(
            task=BedrockTask.VIDEO_CLASSIFICATION,
            system_prompt=(
                "Classify which of the given known topics and skills this educational "
                "video covers, based only on its title and description. Only choose "
                "names from the given lists - never invent a new one."
            ),
            payload=VideoClassificationPayload(
                title=title,
                description=description,
                known_topic_names=list(topic_by_name),
                known_skill_names=list(skill_by_name),
            ),
            response_model=VideoClassificationResponse,
            max_output_tokens=512,
            session_spend_cents=session_spend_cents,
        )
    except BedrockGatewayError as exc:
        return (
            VideoClassification(
                topic_ids=[],
                skill_ids=[],
                grade_band=_FALLBACK_GRADE_BAND,
                difficulty_min=_FALLBACK_DIFFICULTY_MIN,
                difficulty_max=_FALLBACK_DIFFICULTY_MAX,
            ),
            exc.cost_cents,
        )

    response: VideoClassificationResponse = result.value
    topic_ids = [topic_by_name[name] for name in response.topic_names if name in topic_by_name]
    skill_ids = [skill_by_name[name] for name in response.skill_names if name in skill_by_name]

    return (
        VideoClassification(
            topic_ids=topic_ids,
            skill_ids=skill_ids,
            grade_band=response.grade_band,
            difficulty_min=response.difficulty_min,
            difficulty_max=response.difficulty_max,
        ),
        result.cost_cents,
    )
