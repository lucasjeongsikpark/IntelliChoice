"""Every mock branch must satisfy the schema it stands in for (D-238).

`MockBedrockProvider` dispatches on `json_schema["title"]`, which is a *string* match
against a Pydantic model's name. Nothing connects the two, so renaming a field - or the
model - leaves the branch compiling, passing every existing test, and returning JSON that
fails validation the moment anyone actually runs that task.

That is not hypothetical. D-194 renamed `difficulty_label` to `reviewed_difficulty` on
`QuestionJudgeResponse` and added a required `difficulty_reasoning`; the mock kept emitting
the old shape and reading `proposed_difficulty`, a payload field the same decision deleted.
The same rename broke `AuthoredGeneratedItemResponse`'s branch. Both went unnoticed for
long enough that a later session recorded "QUESTION_JUDGE has no branch in mock_provider"
as a fact and planned around it - the branch was there, it just could not produce a valid
response, and the two failures are indistinguishable from the caller's side.

**Why this matters more than a missing mock normally would.** A task with no working mock
can only be exercised by paying for real Bedrock, so its report assembly, its thresholds
and its gating arithmetic go untested by default - and the judge path is exactly where
this project keeps finding gates that never fired (D-193's unbounded score, D-223's
one-copy fixes).
"""

import asyncio
import inspect
import json
from typing import Any

import intellichoice_shared.bedrock as bedrock_module
import pytest
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from pydantic import BaseModel

# Payloads for the branches that read their input. `{}` is the default and is the honest
# case for most: a mock that needs a well-formed payload to emit a valid response is a
# mock that fails closed in a test, which is the wrong direction for a test double.
_PAYLOADS: dict[str, dict[str, Any]] = {
    "LlmJudgeResponse": {"dimensions": ["accuracy", "tone"]},
    "RerankResponse": {"candidates": [{"chunk_id": "c1", "text": "t"}]},
}


def _response_models() -> list[type[BaseModel]]:
    return sorted(
        (
            obj
            for name, obj in vars(bedrock_module).items()
            if inspect.isclass(obj) and issubclass(obj, BaseModel) and name.endswith("Response")
        ),
        key=lambda cls: cls.__name__,
    )


def test_there_are_response_models_to_check() -> None:
    """Guards the guard: `_response_models` finding nothing would make every parametrised
    case below vanish silently, and a suite that shrinks to zero cases reports green."""
    assert len(_response_models()) >= 15


@pytest.mark.parametrize("model", _response_models(), ids=lambda cls: cls.__name__)
def test_the_mock_branch_produces_a_valid_response(model: type[BaseModel]) -> None:
    """The mock's output for this schema validates against the model that named it.

    Models with no dedicated branch fall through to `_generic_json`, which builds from the
    schema itself and therefore satisfies it by construction. So a failure here always
    means a *hand-written* branch has drifted from its model - the case string dispatch
    cannot catch.
    """
    payload = _PAYLOADS.get(model.__name__, {})
    model.model_validate(json.loads(_generate(model, payload)))


def _generate(model: type[BaseModel], payload: dict[str, Any]) -> str:
    return asyncio.run(
        MockBedrockProvider().raw_generate(
            model_id="mock",
            system_prompt="",
            user_message=json.dumps(payload),
            json_schema=model.model_json_schema(),
            max_output_tokens=1024,
        )
    ).text


def test_the_mock_judge_is_stable_and_spreads_across_the_scale() -> None:
    """Two properties the audit's report paths depend on, and a constant has neither.

    Stability, because a test double that varies run to run turns any comparison built on
    it into noise. Spread, because the `gap >= 2` arithmetic, the tier histogram and
    `partition_findings`' four arms only execute when the judged tiers actually differ from
    the declared ones - a mock that answers 1 to everything runs the reporting code but
    exercises one branch of it.
    """
    stems = [f"A shop sells {n} apples in {n % 7 + 2} boxes. How many per box?" for n in range(40)]
    tiers = [
        json.loads(_generate(bedrock_module.QuestionJudgeResponse, {"rendered_question": s}))[
            "reviewed_difficulty"
        ]
        for s in stems
    ]

    repeat = json.loads(
        _generate(bedrock_module.QuestionJudgeResponse, {"rendered_question": stems[0]})
    )["reviewed_difficulty"]
    assert repeat == tiers[0]
    assert set(tiers) == {1, 2, 3, 4, 5}


def test_the_mock_judge_cannot_see_the_declared_tier() -> None:
    """D-194's blindness rule, enforced on the double as well as on the real call.

    The branch this replaced read `proposed_difficulty` straight out of the payload and
    echoed it back, so under the mock the judge "agreed" with whatever it was handed. That
    is the exact failure D-194 removed the field to prevent, surviving in the test double
    after being fixed in production - so a mock-driven check of the calibration gate would
    have shown perfect agreement and meant nothing.
    """
    same_stem = {"rendered_question": "Leo has 12 marbles shared into 3 bags. How many per bag?"}
    baseline = json.loads(_generate(bedrock_module.QuestionJudgeResponse, same_stem))

    for declared in (1, 2, 3, 4, 5):
        smuggled = json.loads(
            _generate(
                bedrock_module.QuestionJudgeResponse,
                {**same_stem, "proposed_difficulty": declared, "difficulty_label": declared},
            )
        )
        assert smuggled["reviewed_difficulty"] == baseline["reviewed_difficulty"]


def test_the_mock_accepts_every_argument_the_real_provider_does() -> None:
    """Signature parity, and the drift it exists to catch was live (D-244).

    D-202 widened `AnthropicBedrockProvider.raw_generate` with `tools`/`tool_executor`/
    `max_tool_rounds` so the model could call a calculator while designing an equation.
    `MockBedrockProvider` was never widened with it, so **every call passing `tools` raised
    `TypeError` at the provider boundary** - which the gateway catches as a provider
    failure, indistinguishable from Bedrock being down. The consequence was quiet and
    expensive: the equation-design stage could not run under the mock at all, so the only
    way to exercise it was to pay for it.

    This is the same lesson as this file's own subject, one level up. There the mock's
    *output* had drifted from the schema it stood in for; here its *interface* had drifted
    from the provider it stands in for. Both were invisible because the failure mode of a
    test double is to look like the thing it replaces failing.

    Compared as a set of parameter names rather than an exact signature: the mock is free
    to accept more than the real provider (a test-only hook would be legitimate), but never
    less, because less is what turns a free path into a paid one.
    """
    from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider

    real = set(inspect.signature(AnthropicBedrockProvider.raw_generate).parameters)
    mock = set(inspect.signature(MockBedrockProvider.raw_generate).parameters)
    assert real <= mock, f"the mock cannot accept: {sorted(real - mock)}"
