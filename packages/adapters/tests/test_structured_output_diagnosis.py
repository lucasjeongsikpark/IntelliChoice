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
import json
import logging

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.provider import RawGeneration
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    AuthoredGeneratorPayload,
    BedrockTask,
    SolverResponse,
    StructuredOutputError,
)
from pydantic import BaseModel

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
        f'"hint_ladder": [{hint_list}], '
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


def test_the_bound_cannot_crowd_out_the_rule_that_explains_the_failure() -> None:
    """Written after the bound hid the answer in this session's own paid run (D-243).

    The generator's real failure mode is to wrap the whole item in a key of its own
    invention. Pydantic reports that as *every required field missing* plus **one**
    `extra_forbidden` naming the wrapper - and it emits `missing` first, so a first-eight
    bound returned eight identical `missing` entries and dropped the single entry that
    says what the model actually sent. Six failures, six identical digests, and the
    diagnosis one layer further down than the instrument could reach.

    So the bound keeps *rule diversity* rather than the first N: every distinct rule gets
    one entry before any rule gets a second. A uniform failure can no longer crowd out the
    rare entry, which is the only kind of entry worth the space.
    """
    exc = _fails_with('{"generated_question": ' + _item_json() + "}")
    assert "generated_question: extra_forbidden" in exc.schema_errors
    assert len(exc.schema_errors) <= 8
    assert any(entry.endswith(": missing") for entry in exc.schema_errors), (
        "the missing-field evidence must survive too - it is half the picture"
    )


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


class _SchemaRecordingProvider:
    """Records the `json_schema` of every call, so a test can assert what the model was
    actually shown rather than what the response model declares.
    """

    def __init__(self) -> None:
        self.schemas: list[dict] = []

    async def raw_generate(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_message: str,
        json_schema: dict,
        max_output_tokens: int,
    ) -> RawGeneration:
        self.schemas.append(json_schema)
        return RawGeneration(text=_item_json(), input_tokens=10, output_tokens=10)


def _schema_sent_for(model: type[BaseModel]) -> dict:
    async def run() -> dict:
        provider = _SchemaRecordingProvider()
        gateway = ResilientBedrockGateway(
            provider=provider,
            model_registry={BedrockTask.AUTHORED_QUESTION_GENERATION: MODEL_ID},
        )
        try:
            await gateway.generate_structured(
                task=BedrockTask.AUTHORED_QUESTION_GENERATION,
                system_prompt="s",
                payload=_payload(),
                response_model=model,
                max_output_tokens=2500,
                session_spend_cents=0.0,
            )
        except StructuredOutputError:
            pass  # only the schema that was sent matters here
        return provider.schemas[0]

    return asyncio.run(run())


def test_the_schema_sent_to_the_model_carries_no_ref_indirection() -> None:
    """The measured cause of D-240's 41%, and this session's largest finding.

    `AuthoredGeneratedItemResponse` is the only response model in this project with a
    nested one inside it, so it is the only schema Pydantic emits with a `$defs` block and
    a `$ref` pointing into it - and it is the schema that fails. Measured on Haiku 4.5,
    twelve calls with the `$ref` form returned an object containing **exactly one key,
    `canonical_solution`** - the one field that is a `$ref` - and nothing else. Four calls
    with the same schema dereferenced returned three valid items.

    So the model appears to read the `$ref` target as *the* schema rather than as one
    field's type. Nothing is loosened to fix it: an inlined schema is the same schema,
    which is why this is a representation change at one seam and not a contract change.

    `0/12` against `3/4` is the whole evidence base, and it is small. It is reported as
    what it is - one model, one topic, one prompt - rather than as a general claim about
    `$ref` in tool schemas.
    """
    schema = _schema_sent_for(AuthoredGeneratedItemResponse)
    rendered = json.dumps(schema)
    assert "$ref" not in rendered
    assert "$defs" not in rendered
    # Inlined, not dropped: the nested shape must still be described, or the model is
    # simply being told less and the "same schema" claim above is false.
    nested = schema["properties"]["canonical_solution"]
    assert nested["type"] == "object"
    assert set(nested["required"]) == {"steps", "final_answer"}
    assert nested["properties"]["steps"]["items"]["properties"]["step_number"]


def test_a_flat_schema_is_handed_over_untouched() -> None:
    """Most response models have no `$defs` at all, and the fix must be a no-op for them -
    otherwise a change aimed at one schema quietly rewrites what every task sends.
    """
    assert _schema_sent_for(SolverResponse) == SolverResponse.model_json_schema()


def test_a_self_referential_schema_is_declined_rather_than_half_inlined() -> None:
    """No model in this project is recursive today, so this is a guard rather than a fix
    for an observed bug - but the failure it prevents is an infinite loop inside a paid
    call path, which is the one class of defect not worth discovering in production.

    Declining outright, rather than inlining to some depth and leaving a dangling `$ref`
    behind: a schema that references a `$defs` block we just deleted is worse than the
    one we started with, and "we could not inline this" is a true statement the original
    schema already makes.
    """

    class Node(BaseModel):
        label: str
        child: "Node | None" = None

    sent = _schema_sent_for(Node)
    # The gateway adds a `title` afterwards, so compare on the part the inliner owns:
    # the `$defs` block and the reference into it both survive intact.
    assert sent["$defs"] == Node.model_json_schema()["$defs"]
    assert sent["$ref"] == "#/$defs/Node"


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
