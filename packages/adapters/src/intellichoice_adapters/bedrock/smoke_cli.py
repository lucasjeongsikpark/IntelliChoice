"""Does this Bedrock model actually work through our structured-output path? (D-195)

Run with:
    uv run python -m intellichoice_adapters.bedrock.smoke_cli --model-id <id> [--contract solver]

Exists because the free discovery APIs do not answer the question. `get-foundation-model-
availability` returned a byte-identical `AVAILABLE / AUTHORIZED / AVAILABLE / AVAILABLE`
payload for Claude Haiku 4.5, which works on this account, and for Claude Sonnet 5, which
answers `AccessDeniedException: not available for this account`. Catalog presence says even
less. **A model is accessible only once a real invocation has succeeded**, so this makes the
smallest real invocation there is and reports exactly what came back.

Read-only by construction: it takes no session, opens no database connection, consumes no
question seed, and writes nothing. The only side effect is the model call itself.

Two things it checks, in order:

1. **Access and the structured-output contract**, with a tiny schema (`SmokeAnswer`) - can
   this model be invoked at all, does it honour a forced tool call, and does what it emits
   validate?
2. **The real response contracts** (`--contract`), against the actual pipeline schemas.
   Passing (1) and failing (2) is a real outcome: a model can support tool use and still be
   unable to satisfy a bounded integer, a `min_length` string or `extra="forbid"`.

Budget is a hard ceiling shared across every call in one process (`--budget-cents`,
default 20). Candidates are run one per invocation, deliberately - a loop that keeps going
after a definitive failure spends money to re-learn the same thing.
"""

import argparse
import asyncio
import json
import time
from typing import Any

from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    BedrockTask,
    CostBudgetExceededError,
    QuestionJudgeResponse,
    SolverResponse,
)
from pydantic import BaseModel, ConfigDict, Field

from .bedrock_runtime_provider import AnthropicBedrockProvider
from .gateway import ResilientBedrockGateway
from .titan_embedding_provider import TitanEmbeddingProvider

_SMOKE_MAX_OUTPUT_TOKENS = 2500


class SmokeAnswer(BaseModel):
    """The smallest schema that still exercises everything the pipeline depends on: a
    free-text field, a bounded integer, and `extra="forbid"`. `reasoning` comes first for
    the same reason it does on the real response models (D-193) - a model emits its fields
    in schema order, so a decision declared before the reasoning cannot be revised by it.
    """

    model_config = ConfigDict(extra="forbid")

    reasoning: str = Field(min_length=1)
    answer: int = Field(ge=0, le=10)


class SmokePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str


_CONTRACTS: dict[str, tuple[type[BaseModel], str, BaseModel]] = {
    "smoke": (
        SmokeAnswer,
        "Answer the arithmetic question. Put your working in `reasoning` first, then the "
        "number in `answer`.",
        SmokePayload(question="What is 2 + 2?"),
    ),
}


def _contract_specs() -> dict[str, tuple[type[BaseModel], str, BaseModel]]:
    """The real pipeline schemas, built lazily so importing this module stays cheap.

    Payloads are minimal but *shaped like the real thing*, because the point is to learn
    whether the model can satisfy the actual response contract - a bounded 1-5 integer, a
    `min_length=20` rationale, `reasoning` before every verdict, and `extra="forbid"`.
    """
    from intellichoice_shared.bedrock import (
        AuthoredGeneratorPayload,
        HintSolutionRepairPayload,
        HintSolutionRepairResponse,
        HintSolutionReviewPayload,
        HintSolutionReviewResponse,
        QuestionJudgePayload,
        SolverPayload,
    )

    return {
        **_CONTRACTS,
        "generator": (
            AuthoredGeneratedItemResponse,
            "You are a K-12 math item writer. Write ONE original multiple-choice question "
            "for the given topic, skill, grade band and target difficulty: a scenario stem, "
            "four options with exactly one correct, a SymPy-parseable `equation`, a 3-level "
            "hint ladder, a worked solution whose final answer matches the correct option, "
            "a misconception tag per distractor, your own `proposed_difficulty` on a 1-5 "
            "scale, a `difficulty_rationale` naming the reasoning operations required, and "
            "`required_prerequisites`.",
            AuthoredGeneratorPayload(
                topic_name="Linear Equations",
                skill_name="Variables on Both Sides",
                grade_band="6-7",
                target_difficulty=4,
                exemplars=[],
            ),
        ),
        "solver": (
            SolverResponse,
            "You are an independent math solver. Work the question out in `reasoning` "
            "first, then select the letter of the option matching your answer. If your "
            "answer is not among the options set no_option_matches true; if the question "
            "admits more than one answer set is_unambiguous false and say why.",
            SolverPayload(
                rendered_question=(
                    "Two robots collect crystals. Robot A starts with 4 and collects 4 each "
                    "minute. Robot B starts with 16 and collects 2 each minute. After how "
                    "many minutes do they have the same number?"
                ),
                option_a="6 minutes",
                option_b="2 minutes",
                option_c="12 minutes",
                option_d="3 minutes",
            ),
        ),
        "judge": (
            QuestionJudgeResponse,
            "You are an independent judge. Write `reasoning` first and solve the question "
            "yourself, then set every boolean to match what you concluded. Rate "
            "`reviewed_difficulty` 1-5 from the question alone and explain it in "
            "`difficulty_reasoning` by naming the reasoning operations required. Score "
            "hint_quality_score 1-5. Do not use any other scale.",
            QuestionJudgePayload(
                rendered_question=(
                    "Two robots collect crystals. Robot A starts with 4 and collects 4 each "
                    "minute. Robot B starts with 16 and collects 2 each minute. After how "
                    "many minutes do they have the same number?"
                ),
                option_a="6 minutes",
                option_b="2 minutes",
                option_c="12 minutes",
                option_d="3 minutes",
                hint_ladder=[
                    "Write an expression for each robot's total after m minutes.",
                    "Robot A has 4 + 4m and Robot B has 16 + 2m; set them equal.",
                    "Collect the m terms on one side, then divide.",
                ],
                canonical_solution="6 minutes",
                topic_name="Linear Equations",
                skill_name="Variables on Both Sides",
                grade_band="6-7",
            ),
        ),
        # D-255 reviewer C. The contract's two hard parts are both here on purpose: a
        # `Literal` verdict (the mock cannot stand in for this - `"mock-verdict"` fails
        # validation, which is why `_generic_json` was not reusable in D-251), and the
        # model validator that rejects a blocking verdict carrying no located defect. A
        # model that emits a bare `"repair"` with an empty `defects` list fails here, and
        # that is the whole point: D-204 measured smoke-pass-contract-fail as a real and
        # common outcome.
        #
        # **Do not read the verdict as a quality signal.** The first version of this
        # comment claimed the fixture "carries a genuine defect - hint 3 states the answer
        # outright - so a working reviewer should return `repair`". That was wrong about
        # this project's own design. An answer stated verbatim in a hint is owned by the
        # *deterministic* gate D-246 restored, and the shipped system prompt tells the
        # reviewer so explicitly - so `pass` is the correct answer here, not a miss.
        # Measured: gpt-oss-120b, qwen3-32b and Haiku 4.5 all returned `pass`, and Haiku is
        # the reviewer D-254 falsified. Three models agreeing is what sent me back to read
        # the prompt.
        #
        # This contract answers "can the model emit the schema", which is all the smoke CLI
        # has ever claimed to answer.
        # D-260's repairer. The hard part is not the four fields - it is `solution_steps`,
        # a list of *nested* SolutionStep objects. A model that emits flat schemas happily
        # can still fail a nested list, and D-204 measured smoke-pass-contract-fail as a
        # real and common outcome, so this is probed rather than assumed.
        "hint_solution_repair": (
            HintSolutionRepairResponse,
            "You repair the hint ladder and worked solution of a K-12 maths question. Write "
            "`reasoning` first. Change ONLY what the defects name; return every other hint "
            "and step word for word. The question, options and final answer are fixed.",
            HintSolutionRepairPayload(
                rendered_question=(
                    "Two robots collect crystals. Robot A starts with 4 and collects 4 each "
                    "minute. Robot B starts with 16 and collects 2 each minute. After how "
                    "many minutes do they have the same number?"
                ),
                option_a="6 minutes",
                option_b="2 minutes",
                option_c="12 minutes",
                option_d="3 minutes",
                correct_option="a",
                hint_ladder=[
                    "Write an expression for each robot's total after m minutes.",
                    "Robot A has 4 + 4m and Robot B has 16 + 2m; set them equal.",
                    "Collect the m terms on one side, then divide.",
                ],
                solution_steps=[
                    "1. Set the two totals equal [4 + 4m = 16 + 2m]",
                    "2. Collect the m terms [2m = 12]",
                    "3. Divide by 2 [2m / 2]",
                ],
                solution_final_answer="6 minutes",
                skill_name="Variables on Both Sides",
                grade_band="6-7",
                defects=[
                    "canonical_solution[3]: the step says to divide but shows the division "
                    "unevaluated, so it never states the answer - suggested: show the result"
                ],
            ),
        ),
        "hint_solution_review": (
            HintSolutionReviewResponse,
            # Written here rather than imported from
            # `intellichoice_curriculum.hint_solution_review`: `adapters` is the lower
            # layer and importing upward would invert the dependency for a probe. Every
            # other contract in this file inlines its prompt for the same reason. The
            # consequence is honest and worth stating - **this measures whether the model
            # can emit the contract, not how the shipped reviewer behaves.** The shipped
            # prompt is longer and says more; a pass here is a capability result only.
            "You review a K-12 math question's hint ladder and worked solution. Write "
            "`reasoning` first. Then return `verdict`: `pass` if both are sound, `repair` "
            "if a located fix would make them sound, `reject` if not. Every `repair` or "
            "`reject` MUST carry at least one entry in `defects`, each naming its `target` "
            "(`hint_ladder` or `canonical_solution`), a 1-based `index` where one applies, "
            "the `problem`, and a `suggested_fix`. Set `uncertainty` to low, medium or "
            "high. Correctness of the answer key and the options is already verified "
            "deterministically - do not re-check it.",
            HintSolutionReviewPayload(
                rendered_question=(
                    "Two robots collect crystals. Robot A starts with 4 and collects 4 each "
                    "minute. Robot B starts with 16 and collects 2 each minute. After how "
                    "many minutes do they have the same number?"
                ),
                option_a="6 minutes",
                option_b="2 minutes",
                option_c="12 minutes",
                option_d="3 minutes",
                correct_option="a",
                hint_ladder=[
                    "Write an expression for each robot's total after m minutes.",
                    "Robot A has 4 + 4m and Robot B has 16 + 2m; set them equal.",
                    "The answer is 6 minutes.",
                ],
                solution_steps=[
                    "1. Set the two totals equal [4 + 4m = 16 + 2m]",
                    "2. Collect the m terms [2m = 12]",
                    "3. Divide by 2 [m = 6]",
                ],
                solution_final_answer="6 minutes",
                skill_name="Variables on Both Sides",
                grade_band="6-7",
            ),
        ),
    }


def classify_failure(detail: str) -> str:
    """Which *kind* of failure this was, from the error text.

    The distinction is the whole point of the exercise: "we cannot call this model at all"
    and "we can call it but it will not emit our schema" lead to completely different
    decisions, and both arrive as a string from boto3.
    """
    lowered = detail.lower()
    if "accessdenied" in lowered or "not available for this account" in lowered:
        return "ACCESS DENIED - the account cannot invoke this model"
    if "toolchoice" in lowered or "tool choice" in lowered:
        return "UNSUPPORTED TOOL CHOICE - the model will not accept a forced tool call"
    if "toolconfig" in lowered or "tool use" in lowered or "tools" in lowered:
        return "UNSUPPORTED TOOL USE - the model does not support toolConfig on Converse"
    if "does not support" in lowered and "system" in lowered:
        return "UNSUPPORTED SYSTEM PROMPT - the model rejects a system block on Converse"
    if "validationexception" in lowered and "schema" in lowered:
        return "SCHEMA COMPILATION FAILURE - the model rejected our JSON Schema"
    if "validationexception" in lowered:
        return "UNSUPPORTED API SHAPE - Converse rejected the request"
    if "did not return a tool_use block" in lowered:
        return "PARSER INCOMPATIBILITY - no toolUse block in the response"
    if "throttl" in lowered:
        return "THROTTLED - not a capability signal, retry later"
    # Both of the gateway's own structured-output messages, matched on the words they
    # share rather than on either full sentence - the first version of this checked for
    # "structured output invalid" and missed "structured output *still* invalid after one
    # repair retry", which is precisely the string `openai.gpt-oss-120b-1:0` produced, so
    # a definitive contract failure was reported as "OTHER".
    if "structured output" in lowered:
        return "VALID CALL, INVALID SCHEMA - the model answered but not in our shape"
    if "validation" in lowered:
        return "VALID CALL, INVALID SCHEMA - the model answered but not in our shape"
    return "OTHER"


async def run_one(
    *,
    model_id: str,
    contract: str,
    region: str,
    budget_cents: float,
    already_spent: float,
) -> dict[str, Any]:
    """One model, one contract, one call. Returns a report dict; raises nothing."""
    specs = _contract_specs()
    response_model, system_prompt, payload = specs[contract]

    provider = AnthropicBedrockProvider(aws_region=region)
    gateway = ResilientBedrockGateway(
        provider=provider,
        embedding_provider=TitanEmbeddingProvider(aws_region=region),
        # One task slot, pointed at whichever model is under test. Using the real gateway
        # rather than the provider directly is deliberate: retry, repair, truncation
        # handling and cost accounting are all part of "does this work for us".
        model_registry={BedrockTask.AUTHORED_QUESTION_GENERATION: model_id},
        session_budget_cents=budget_cents,
        # Deliberately no retries here. A capability failure is not transient, and paying
        # three times to learn it once is the thing this command exists to avoid.
        max_retries=0,
    )

    report: dict[str, Any] = {
        "model_id": model_id,
        "contract": contract,
        "api": "bedrock-runtime Converse + toolConfig (forced toolChoice)",
        "region": region,
    }
    started = time.monotonic()
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.AUTHORED_QUESTION_GENERATION,
            system_prompt=system_prompt,
            payload=payload,
            response_model=response_model,  # type: ignore[arg-type]
            max_output_tokens=_SMOKE_MAX_OUTPUT_TOKENS,
            session_spend_cents=already_spent,
        )
    except CostBudgetExceededError as exc:
        report.update(
            success=False,
            failure="BUDGET CEILING REACHED",
            detail=str(exc),
            cost_cents=0.0,
        )
        return report
    except Exception as exc:  # noqa: BLE001 - the classification below is the whole point
        detail = str(exc)
        report.update(
            success=False,
            failure=classify_failure(detail),
            detail=detail,
            # A failed call may still have billed input tokens; the gateway only reports
            # cost on success, so this is recorded as unknown rather than as zero.
            cost_cents=None,
        )
        return report

    report.update(
        success=True,
        failure=None,
        parsed=result.value.model_dump(),
        stop_reason=result.stop_reason or "(empty)",
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_cents=result.cost_cents,
        repaired=result.repaired,
        duration_s=round(time.monotonic() - started, 2),
    )
    return report


def render(report: dict[str, Any]) -> str:
    lines = [
        f"model:        {report['model_id']}",
        f"contract:     {report['contract']}",
        f"api:          {report['api']}  ({report['region']})",
    ]
    if report["success"]:
        parsed = json.dumps(report["parsed"], ensure_ascii=False)
        lines += [
            "invocation:   SUCCESS",
            f"stop reason:  {report['stop_reason']}",
            f"tokens:       in={report['input_tokens']} out={report['output_tokens']}",
            f"cost:         {report['cost_cents']:.4f} cents"
            + ("  (rate table has no entry - default rate used)" if report["cost_cents"] else ""),
            f"repaired:     {report['repaired']}",
            f"duration:     {report['duration_s']}s",
            # Truncated for a human reading one result. **Use `--json` for anything that
            # analyses the output** - a script parsing this line gets a JSON syntax error the
            # moment a response exceeds 900 characters, which is most of them, and the calls
            # are already paid for by the time it fails.
            f"parsed:       {parsed[:900]}{' ...' if len(parsed) > 900 else ''}",
        ]
    else:
        lines += [
            "invocation:   FAILED",
            f"failure:      {report['failure']}",
            f"cost:         {'0.0000 cents' if report['cost_cents'] == 0.0 else 'unknown'}",
            f"error:        {report['detail'][:600]}",
        ]
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prove whether a Bedrock model works through our structured-output path"
    )
    parser.add_argument("--model-id", required=True, help="Exact invocable Bedrock model id")
    parser.add_argument(
        "--contract",
        default="smoke",
        # Derived from the registry, not restated. The literal list here had gone stale the
        # first time a contract was added (D-255's `hint_solution_review`): the spec built
        # fine and argparse refused the name, which is a harmless failure only because it
        # happens before the model call rather than after it.
        choices=sorted(_contract_specs()),
        help="'smoke' is a tiny schema (access + tool-use contract). The others are the "
        "real pipeline response models - a model can pass 'smoke' and fail these",
    )
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument(
        "--budget-cents",
        type=float,
        default=20.0,
        help="Hard ceiling for this process. The gateway refuses a call that could cross it",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the full report as JSON instead of the human summary - the parsed "
        "response is complete here, where the summary truncates it at 900 characters",
    )
    parser.add_argument(
        "--already-spent",
        type=float,
        default=0.0,
        help="Cents already spent by earlier smoke invocations, so the ceiling is shared "
        "across a sequence of separate runs",
    )
    args = parser.parse_args()

    report = await run_one(
        model_id=args.model_id,
        contract=args.contract,
        region=args.region,
        budget_cents=args.budget_cents,
        already_spent=args.already_spent,
    )
    print(json.dumps(report, ensure_ascii=False) if args.json else render(report))
    raise SystemExit(0 if report["success"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
