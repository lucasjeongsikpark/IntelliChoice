"""A structured-output failure has to say what broke (D-243).

D-240 measured the authored generator failing structured output on **41% of candidates** -
nine of twenty-two died before reaching any quality gate - and then could not say why.
Twenty-eight rows in `question_validation_runs` carry the identical constant string
`"structured output still invalid after one repair retry"`, and their `stage_results`
carry that same sentence again under `provider_error`. That is the whole record.

The cause is one `except ValidationError: return None` in `_try_validate`. Pydantic knows
exactly which field broke which rule; the gateway discards it and raises a message with
nowhere to put it. So the largest single loss in the pipeline is, by construction,
undiagnosable - and no amount of re-reading the code recovers evidence that was never
written down.

**Two things narrow what these failures can be, both established before this file existed.**
On the real path `bedrock_runtime_provider` returns `json.dumps(emitted["input"])`, so boto3
has already parsed the tool input and the text handed to `json.loads` is always well-formed;
and truncation raises `OutputTruncatedError`, a different type with a different message,
which those rows do not carry. All twenty-eight are therefore Pydantic validation failures
on valid JSON - exactly the case whose detail was thrown away.

**The digest is `field: rule` and deliberately nothing else.** Pydantic's `errors()` embeds
the offending `input` by default, which here is model-written curriculum prose - a whole
stem, four options, a hint ladder - and putting that into a database row, a log line and an
exception message is three copies of content this project keeps out of logs on principle
(SPEC §5.30). `loc` plus `type` is enough to act on: it groups in SQL, it names the rule,
and it cannot leak what the model wrote.
"""

import asyncio
import logging

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.provider import RawGeneration
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    AuthoredGeneratorPayload,
    BedrockTask,
    StructuredOutputError,
)

MODEL_ID = "anthropic.claude-test"

# A stem a human would recognise on sight, so a test can assert it never reaches the
# digest, the message or the log. Nonsense on purpose: if this string turns up anywhere
# it can only have come from the model's own output.
_TELLTALE = "A wombat named Persimmon buys 14 kazoos."


def _payload() -> AuthoredGeneratorPayload:
    return AuthoredGeneratorPayload(
        topic_name="Linear Equations",
        skill_name="Solve one-step linear equations",
        grade_band="6-7",
        target_difficulty=3,
        exemplars=[],
    )


class _OffContractProvider:
    """Returns the same off-contract body to both the first call and the repair, which is
    what a model that has misread the contract actually does - the repair prompt tells it
    the output was wrong, not which part, so it tends to reproduce the same mistake.
    """

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    async def raw_generate(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_message: str,
        json_schema: dict,
        max_output_tokens: int,
    ) -> RawGeneration:
        self.calls += 1
        return RawGeneration(text=self._text, input_tokens=10, output_tokens=10)


def _fails_with(text: str) -> StructuredOutputError:
    async def run() -> StructuredOutputError:
        gateway = ResilientBedrockGateway(
            provider=_OffContractProvider(text),
            model_registry={BedrockTask.AUTHORED_QUESTION_GENERATION: MODEL_ID},
        )
        with pytest.raises(StructuredOutputError) as caught:
            await gateway.generate_structured(
                task=BedrockTask.AUTHORED_QUESTION_GENERATION,
                system_prompt="s",
                payload=_payload(),
                response_model=AuthoredGeneratedItemResponse,
                max_output_tokens=2500,
                session_spend_cents=0.0,
            )
        return caught.value

    return asyncio.run(run())


def _item_json(*, extra: str = "", hints: int = 3, difficulty: int = 3) -> str:
    hint_list = ", ".join(f'"hint {n}"' for n in range(hints))
    return (
        "{"
        f'"stem": "{_TELLTALE}", '
        '"option_a": "1", "option_b": "2", "option_c": "3", "option_d": "4", '
        '"correct_option": "a", '
        f"\"hint_ladder\": [{hint_list}], "
        '"canonical_solution": {"steps": [{"step_number": 1, "explanation": "e", '
        '"expression": "x"}], "final_answer": "1"}, '
        '"estimated_time_seconds": 90, '
        f'"proposed_difficulty": {difficulty}, '
        '"difficulty_rationale": "one step, no distribution needed at all", '
        f'"reasoning": ""{extra}'
        "}"
    )


def test_a_schema_failure_names_the_field_and_the_rule_that_broke() -> None:
    """The single assertion this whole file exists for.

    Three violations at once, because a real off-contract response usually carries more
    than one and a digest that reports only the first would send a reader to fix one
    quarter of the problem.
    """
    exc = _fails_with(
        _item_json(extra=', "teacher_notes": "remember to praise effort"', hints=4, difficulty=9)
    )
    assert set(exc.schema_errors) == {
        "hint_ladder: too_long",
        "proposed_difficulty: less_than_equal",
        "teacher_notes: extra_forbidden",
    }


def test_the_digest_never_carries_the_model_s_own_words() -> None:
    """`ValidationError.errors()` includes `input` unless told not to, and `input` here is
    the item the model just wrote. This is the assertion that keeps the fix from turning a
    diagnostic improvement into three new copies of generated content in the logs.
    """
    exc = _fails_with(_item_json(hints=4))
    assert _TELLTALE not in str(exc)
    assert not any(_TELLTALE in entry for entry in exc.schema_errors)
    assert "hint_ladder: too_long" in exc.schema_errors


def test_a_response_that_is_not_json_at_all_is_distinguished_from_an_off_contract_one() -> None:
    """Opposite problems that reach the caller as the same sentence today.

    Prose back from the model means the tool was never called - a parser or model-choice
    problem (`smoke_cli` already classifies it as `PARSER INCOMPATIBILITY`). Valid JSON of
    the wrong shape means the contract is being read and missed. One is fixed by changing
    models, the other by changing the schema or the prompt, and an empty digest for both
    would read as "no detail available" for the case where the detail is the whole point.
    """
    exc = _fails_with("I'm sorry, I can't write questions about wombats.")
    assert exc.schema_errors == ["<response>: not_json"]


def test_the_digest_is_bounded() -> None:
    """A model that has lost the contract entirely emits dozens of extra keys, and an
    unbounded digest would write all of them into a JSON column and a log line. The bound
    is small on purpose: past the first handful the reader has already learned the answer.
    """
    extras = "".join(f', "junk_{n}": {n}' for n in range(40))
    exc = _fails_with(_item_json(extra=extras))
    assert 0 < len(exc.schema_errors) <= 8


def test_the_flattened_message_carries_the_digest_too() -> None:
    """`ai_pipeline` persists `str(exc)` as `provider_error`, and every caller that only
    logs the message would otherwise still see the pre-D-243 sentence. Carrying it in both
    places costs one f-string and means no caller has to be updated to benefit.
    """
    exc = _fails_with(_item_json(hints=4))
    assert "still invalid after one repair retry" in str(exc)
    assert "hint_ladder: too_long" in str(exc)


def test_the_failure_log_record_carries_the_digest(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`_log_failure` is what a production run leaves behind - the pipeline's database row
    exists only for the authoring path, and the serving apps have nothing else.
    """
    with caplog.at_level(logging.WARNING):
        _fails_with(_item_json(hints=4))
    records = [r for r in caplog.records if getattr(r, "reason", "") == "schema_invalid"]
    assert records, "a schema failure must log a schema_invalid failure record"
    assert "hint_ladder: too_long" in getattr(records[0], "detail", "")
    assert _TELLTALE not in getattr(records[0], "detail", "")


def test_a_repair_that_succeeds_reports_no_errors_at_all() -> None:
    """The digest must not become a thing that is populated on the happy path. A field
    that is always non-empty stops being read, and this one is only meaningful when the
    candidate actually died.
    """

    class _RepairsOnSecondCall:
        def __init__(self) -> None:
            self.calls = 0

        async def raw_generate(
            self,
            *,
            model_id: str,
            system_prompt: str,
            user_message: str,
            json_schema: dict,
            max_output_tokens: int,
        ) -> RawGeneration:
            self.calls += 1
            text = _item_json(hints=4) if self.calls == 1 else _item_json()
            return RawGeneration(text=text, input_tokens=10, output_tokens=10)

    async def run() -> None:
        gateway = ResilientBedrockGateway(
            provider=_RepairsOnSecondCall(),
            model_registry={BedrockTask.AUTHORED_QUESTION_GENERATION: MODEL_ID},
        )
        result = await gateway.generate_structured(
            task=BedrockTask.AUTHORED_QUESTION_GENERATION,
            system_prompt="s",
            payload=_payload(),
            response_model=AuthoredGeneratedItemResponse,
            max_output_tokens=2500,
            session_spend_cents=0.0,
        )
        assert result.repaired is True
        assert result.value.stem == _TELLTALE

    asyncio.run(run())
