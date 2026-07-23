"""Fast, no-DB tests for the Tutor Agent / Hint & Solution generators (SPEC §5.12,
§5.11.4-§5.11.5) - a fake `BedrockGateway` stands in for the real resilience wrapper
(already covered by `packages/adapters/tests/test_bedrock_gateway.py`), so these tests
focus purely on `learning_api.services.tutor`'s own fallback and verification logic.
"""

import asyncio

from intellichoice_shared.bedrock import (
    BedrockGatewayError,
    BedrockGenerationResult,
    BedrockTask,
    BedrockTutorPayload,
    EmbeddingResult,
    HintPersonalizationResponse,
    HintResponse,
    SolutionResponse,
    SolutionStep,
    TutorContext,
)
from learning_api.services import tutor
from pydantic import BaseModel


def _context() -> TutorContext:
    return TutorContext(
        grade="6",
        estimated_level="0.40",
        topic="Linear Equations",
        skill="Two-Step Equations",
        question="Solve for x: x + 3 = 7",
        selected_wrong_answer="3",
    )


class _FakeGateway:
    """Not class-generic like `ResilientBedrockGateway` isn't either - the Protocol's
    `generate_structured` is generic per-*call* (any `response_model` in, matching
    `BedrockGenerationResult[T]` out), so a fixed-payload double just returns whatever
    it was constructed with and lets each test's own assertions check the value.
    """

    def __init__(self, outcome: BedrockGenerationResult[BaseModel] | BedrockGatewayError) -> None:
        self._outcome = outcome

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
        if isinstance(self._outcome, BedrockGatewayError):
            raise self._outcome
        assert isinstance(self._outcome.value, response_model)
        return self._outcome  # type: ignore[return-value]

    async def create_embedding(
        self, *, texts: list[str], session_spend_cents: float
    ) -> EmbeddingResult:
        raise NotImplementedError("this fake never embeds - tutor service only generates")


def test_generate_hint_returns_validated_content_on_success() -> None:
    async def run() -> None:
        hint = HintResponse(
            hint_text="h", concept_reminder="c", next_step_prompt="n", difficulty=1
        )
        gateway = _FakeGateway(
            BedrockGenerationResult(
                value=hint,
                input_tokens=10,
                output_tokens=10,
                cost_cents=0.5,
                model_id="anthropic.claude-test",
                repaired=False,
            )
        )
        result, cost = await tutor.generate_hint(
            gateway=gateway, context=_context(), session_spend_cents=0.0
        )
        assert result is hint
        assert cost == 0.5

    asyncio.run(run())


def test_generate_hint_falls_back_on_gateway_error() -> None:
    async def run() -> None:
        gateway = _FakeGateway(BedrockGatewayError("boom", cost_cents=0.2))
        result, cost = await tutor.generate_hint(
            gateway=gateway, context=_context(), session_spend_cents=0.0
        )
        assert isinstance(result, HintResponse)
        assert result.answer_revealed is False
        assert cost == 0.2

    asyncio.run(run())


def test_generate_solution_accepts_a_correct_final_answer() -> None:
    async def run() -> None:
        solution = SolutionResponse(
            steps=[
                SolutionStep(step_number=1, explanation="e", expression="x=4"),
            ],
            final_answer="4",
        )
        gateway = _FakeGateway(
            BedrockGenerationResult(
                value=solution,
                input_tokens=10,
                output_tokens=10,
                cost_cents=0.5,
                model_id="anthropic.claude-test",
                repaired=False,
            )
        )
        result, cost = await tutor.generate_solution(
            gateway=gateway,
            context=_context(),
            correct_answer_text="4",
            session_spend_cents=0.0,
        )
        assert result is solution
        assert cost == 0.5

    asyncio.run(run())


def test_generate_solution_rejects_a_wrong_final_answer_and_falls_back() -> None:
    async def run() -> None:
        wrong_solution = SolutionResponse(
            steps=[SolutionStep(step_number=1, explanation="e", expression="x=99")],
            final_answer="99",
        )
        gateway = _FakeGateway(
            BedrockGenerationResult(
                value=wrong_solution,
                input_tokens=10,
                output_tokens=10,
                cost_cents=0.5,
                model_id="anthropic.claude-test",
                repaired=False,
            )
        )
        result, cost = await tutor.generate_solution(
            gateway=gateway,
            context=_context(),
            correct_answer_text="4",
            session_spend_cents=0.0,
        )
        assert result.final_answer == "4"  # deterministic fallback, verified correct
        assert result is not wrong_solution
        assert cost == 0.5  # the (wrong) call still cost real tokens

    asyncio.run(run())


def test_generate_solution_falls_back_on_gateway_error() -> None:
    async def run() -> None:
        gateway = _FakeGateway(BedrockGatewayError("boom", cost_cents=0.0))
        result, cost = await tutor.generate_solution(
            gateway=gateway,
            context=_context(),
            correct_answer_text="4",
            session_spend_cents=0.0,
        )
        assert result.final_answer == "4"
        assert cost == 0.0

    asyncio.run(run())


def test_generate_personalized_hint_returns_validated_content_on_success() -> None:
    async def run() -> None:
        personalized = HintPersonalizationResponse(
            hint_text="Since you added instead of subtracting, try the opposite operation.",
            concept_reminder="c",
            next_step_prompt="n",
            difficulty=1,
        )
        gateway = _FakeGateway(
            BedrockGenerationResult(
                value=personalized,
                input_tokens=10,
                output_tokens=10,
                cost_cents=0.5,
                model_id="anthropic.claude-test",
                repaired=False,
            )
        )
        result, cost, was_personalized = await tutor.generate_personalized_hint(
            gateway=gateway,
            context=_context(),
            canonical_hint_text="Try the opposite operation on both sides.",
            next_canonical_hint_text="Subtract 3 from both sides.",
            hint_level=1,
            attempt_count=1,
            misconception_tag="sign_error",
            previous_hint_summaries=[],
            correct_answer_text="4",
            session_spend_cents=0.0,
        )
        assert result is personalized
        assert cost == 0.5
        assert was_personalized is True

    asyncio.run(run())


def test_generate_personalized_hint_falls_back_on_gateway_error() -> None:
    async def run() -> None:
        gateway = _FakeGateway(BedrockGatewayError("boom", cost_cents=0.2))
        result, cost, was_personalized = await tutor.generate_personalized_hint(
            gateway=gateway,
            context=_context(),
            canonical_hint_text="Try the opposite operation on both sides.",
            next_canonical_hint_text=None,
            hint_level=1,
            attempt_count=1,
            misconception_tag=None,
            previous_hint_summaries=[],
            correct_answer_text="4",
            session_spend_cents=0.0,
        )
        assert result.hint_text == "Try the opposite operation on both sides."
        assert cost == 0.2
        assert was_personalized is False

    asyncio.run(run())


def test_generate_personalized_hint_falls_back_on_leaked_answer() -> None:
    async def run() -> None:
        leaking = HintPersonalizationResponse(
            hint_text="The answer is 4, since x + 3 = 7 means x = 4.",
            concept_reminder="c",
            next_step_prompt="n",
            difficulty=1,
        )
        gateway = _FakeGateway(
            BedrockGenerationResult(
                value=leaking,
                input_tokens=10,
                output_tokens=10,
                cost_cents=0.5,
                model_id="anthropic.claude-test",
                repaired=False,
            )
        )
        result, cost, was_personalized = await tutor.generate_personalized_hint(
            gateway=gateway,
            context=_context(),
            canonical_hint_text="Try the opposite operation on both sides.",
            next_canonical_hint_text=None,
            hint_level=3,
            attempt_count=2,
            misconception_tag="sign_error",
            previous_hint_summaries=["an earlier hint"],
            correct_answer_text="4",
            session_spend_cents=0.0,
        )
        assert result.hint_text == "Try the opposite operation on both sides."
        assert cost == 0.5  # the (rejected) call still cost real tokens
        assert was_personalized is False

    asyncio.run(run())


def test_generate_personalized_hint_falls_back_on_monotonicity_violation() -> None:
    async def run() -> None:
        revealing_next_level = HintPersonalizationResponse(
            hint_text="Here's a big hint: subtract 3 from both sides.",
            concept_reminder="c",
            next_step_prompt="n",
            difficulty=1,
        )
        gateway = _FakeGateway(
            BedrockGenerationResult(
                value=revealing_next_level,
                input_tokens=10,
                output_tokens=10,
                cost_cents=0.5,
                model_id="anthropic.claude-test",
                repaired=False,
            )
        )
        result, cost, was_personalized = await tutor.generate_personalized_hint(
            gateway=gateway,
            context=_context(),
            canonical_hint_text="Try the opposite operation on both sides.",
            next_canonical_hint_text="subtract 3 from both sides",
            hint_level=1,
            attempt_count=1,
            misconception_tag=None,
            previous_hint_summaries=[],
            correct_answer_text="4",
            session_spend_cents=0.0,
        )
        assert result.hint_text == "Try the opposite operation on both sides."
        assert was_personalized is False

    asyncio.run(run())


def test_payload_from_context_never_carries_common_error_tag_or_previous_hints() -> None:
    context = TutorContext(
        grade="6",
        estimated_level="0.40",
        topic="Linear Equations",
        skill="Two-Step Equations",
        question="Solve for x: x + 3 = 7",
        selected_wrong_answer="3",
        common_error_tag="sign_error",
        previous_hints=["an earlier hint"],
    )
    payload = tutor._payload_from_context(context, None)
    assert isinstance(payload, BedrockTutorPayload)
    assert not hasattr(payload, "common_error_tag")
    assert not hasattr(payload, "previous_hints")


class _CapturingGateway:
    """S25 read-path proof: records the exact payload it was called with, so a test can
    assert `relevant_learning_fact` actually reached the wire payload - not just that
    `generate_hint`/`generate_solution` accept the parameter.
    """

    def __init__(self, value: BaseModel) -> None:
        self._value = value
        self.last_payload: BaseModel | None = None

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
        self.last_payload = payload
        assert isinstance(self._value, response_model)
        return BedrockGenerationResult(
            value=self._value,
            input_tokens=10,
            output_tokens=10,
            cost_cents=0.1,
            model_id="anthropic.claude-test",
            repaired=False,
        )

    async def create_embedding(self, *, texts: list[str], session_spend_cents: float):
        raise NotImplementedError


def test_generate_hint_forwards_relevant_learning_fact_to_the_wire_payload() -> None:
    async def run() -> None:
        hint = HintResponse(
            hint_text="h", concept_reminder="c", next_step_prompt="n", difficulty=1
        )
        gateway = _CapturingGateway(hint)
        await tutor.generate_hint(
            gateway=gateway,
            context=_context(),
            session_spend_cents=0.0,
            relevant_learning_fact="Struggles with negative signs when distributing.",
        )
        assert isinstance(gateway.last_payload, BedrockTutorPayload)
        assert (
            gateway.last_payload.relevant_learning_fact
            == "Struggles with negative signs when distributing."
        )

    asyncio.run(run())
