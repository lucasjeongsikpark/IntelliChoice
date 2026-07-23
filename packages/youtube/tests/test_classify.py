"""SPEC §5.18 classification re-validation (D-038/D-026-style "model proposes, code
re-derives"): a proposed topic/skill name only ever becomes a stored `topic_id`/
`skill_id` if it's a real, exact match against the curriculum registry the model was
given as its menu. Uses a scripted gateway (mirrors `apps/chat-api/tests/
test_qa_service.py::_FakeGateway`) so the test controls exactly what the model
"proposed", including a name outside the real menu.
"""

import asyncio

from intellichoice_curriculum.content import load_curriculum
from intellichoice_shared.bedrock import (
    BedrockGatewayError,
    BedrockGenerationResult,
    BedrockTask,
    EmbeddingResult,
    VideoClassificationResponse,
)
from intellichoice_youtube.classify import classify_video
from pydantic import BaseModel


class _ScriptedGateway:
    """Mirrors `apps/chat-api/tests/test_qa_service.py::_FakeGateway` - returns a fixed
    outcome regardless of what it's called with.
    """

    def __init__(self, response: VideoClassificationResponse) -> None:
        self._response = response

    async def generate_structured[T: BaseModel](
        self,
        *,
        task: BedrockTask,
        system_prompt: str,
        payload: BaseModel,
        response_model: type[T],
        max_output_tokens: int,
        session_spend_cents: float,
    ) -> BedrockGenerationResult[T]:
        assert isinstance(self._response, response_model)
        return BedrockGenerationResult(
            value=self._response,
            input_tokens=10,
            output_tokens=10,
            cost_cents=0.05,
            model_id="test-model",
            repaired=False,
        )  # type: ignore[return-value]

    async def create_embedding(
        self, *, texts: list[str], session_spend_cents: float
    ) -> EmbeddingResult:
        raise NotImplementedError


class _FailingGateway:
    async def generate_structured[T: BaseModel](
        self,
        *,
        task: BedrockTask,
        system_prompt: str,
        payload: BaseModel,
        response_model: type[T],
        max_output_tokens: int,
        session_spend_cents: float,
    ) -> BedrockGenerationResult[T]:
        raise BedrockGatewayError("boom", cost_cents=0.02)

    async def create_embedding(
        self, *, texts: list[str], session_spend_cents: float
    ) -> EmbeddingResult:
        raise NotImplementedError


def test_invented_name_outside_the_real_menu_is_dropped() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        gateway = _ScriptedGateway(
            VideoClassificationResponse(
                topic_names=["Linear Equations", "Quantum Mechanics"],
                skill_names=["Solve one-step linear equations", "Time Travel"],
                grade_band="3-5",
                difficulty_min=1,
                difficulty_max=3,
            )
        )
        classification, cost = await classify_video(
            gateway,
            curriculum,
            title="Solve one-step linear equations",
            description="An introduction video.",
            session_spend_cents=0.0,
        )
        assert classification.topic_ids == ["linear_equations"]
        assert classification.skill_ids == ["linear_one_step"]
        assert cost == 0.05

    asyncio.run(run())


def test_gateway_failure_falls_back_to_safe_unclassified_defaults() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        classification, cost = await classify_video(
            _FailingGateway(),
            curriculum,
            title="Anything",
            description="Anything.",
            session_spend_cents=0.0,
        )
        assert classification.topic_ids == []
        assert classification.skill_ids == []
        assert cost == 0.02

    asyncio.run(run())
