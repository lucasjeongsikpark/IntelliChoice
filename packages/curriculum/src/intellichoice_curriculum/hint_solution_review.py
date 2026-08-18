"""D-251 hint & solution review - `BedrockTask.HINT_SOLUTION_REVIEW`.

The design, its rationale and the checks that gate it are in docs/HINT_SOLUTION_REVIEW.md.
This module is the thin task-specific wrapper over `generate_structured`, same shape as
every other task service function here.

**Nothing calls this in the pipeline yet, and that is deliberate.** The plan's step 4 is a
falsification run (reproducibility + false-rejection against the approved bank) and the
instrument does not get wired into a decision until it survives it. An unvalidated reviewer
wired to a gate is exactly what D-249 found already shipped.
"""

from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    BedrockGateway,
    BedrockGenerationResult,
    BedrockTask,
    HintSolutionReviewPayload,
    HintSolutionReviewResponse,
)

_MAX_OUTPUT_TOKENS = 1500

# The instrument judges *pedagogy*. Everything below is already decided exactly and for free
# by `authored_validation`, so saying so keeps the model from spending output re-deriving it
# and from reporting a "defect" that is really a deterministic check's job (D-223).
_ALREADY_CHECKED = (
    "A separate deterministic check already guarantees, before you see this item, that: no "
    "hint states the correct answer verbatim; the solution's final answer matches the "
    "declared correct option; and the arithmetic is machine-verified. Do not re-check these "
    "and do not report them as defects. Judge only what a rule cannot: whether the hints "
    "actually help, whether each rung adds something the one before it did not, whether the "
    "solution can be followed by a student who did not already know the answer, and whether "
    "the language fits the grade band."
)

_VERDICTS = (
    'Return exactly one verdict. "pass": a student would be helped by this; it may be plain '
    'or unpolished, which is not a defect. "repair": something concrete is wrong and you can '
    'say what would fix it - this is the verdict for a recoverable item. "reject": the hints '
    "or solution would mislead a student, or the item would need rewriting rather than "
    'fixing. Every "repair" and "reject" must carry at least one located defect; a verdict '
    "with nothing to act on is not usable."
)

# Diversity is a first-class constraint (HINT_SOLUTION_REVIEW.md §2). Without this the
# reviewer's implicit reference is "the hint ladder I would have written", and repairing
# every item toward one voice is a worse outcome than the mediocre ladders being repaired.
_DIVERSITY = (
    "There is no house style and no reference item. Do not mark an item down for being "
    "phrased differently from how you would phrase it, for using a different pedagogical "
    "approach than you would choose, or for being terse. Vary is not the same as wrong: only "
    "report a defect you can state as a concrete problem for a specific student reading it."
)

_UNCERTAINTY = (
    'Set uncertainty to "low" when the same reader would reach this verdict again, "medium" '
    'when the item sits near the boundary between two verdicts, and "high" when you are '
    "guessing. This routes borderline items for a second reading; it is not a confidence "
    "score and does not affect how seriously your verdict is taken."
)

SYSTEM_PROMPT = (
    "You are reviewing the hint ladder and worked solution of a multiple-choice question for "
    "a K-12 student, on behalf of a teacher who will not read every item themselves.\n\n"
    f"{_ALREADY_CHECKED}\n\n{_VERDICTS}\n\n{_DIVERSITY}\n\n{_UNCERTAINTY}\n\n"
    "Never restate the correct answer in your reasoning or in a suggested fix - you are told "
    "it so you can judge whether the hints lead there, not so you can repeat it."
)


def build_payload(
    item: AuthoredGeneratedItemResponse, *, skill_name: str, grade_band: str
) -> HintSolutionReviewPayload:
    """Flattens the item into what the reviewer sees.

    `rendered_question` is context block + stem for D-196's reason: judging the stem alone
    means judging text no student is served.
    """
    rendered_question = f"{item.context_block}\n\n{item.stem}" if item.context_block else item.stem
    return HintSolutionReviewPayload(
        rendered_question=rendered_question,
        option_a=item.option_a,
        option_b=item.option_b,
        option_c=item.option_c,
        option_d=item.option_d,
        correct_option=item.correct_option,
        hint_ladder=list(item.hint_ladder),
        solution_steps=[
            f"{step.step_number}. {step.explanation} [{step.expression}]"
            for step in item.canonical_solution.steps
        ],
        solution_final_answer=item.canonical_solution.final_answer,
        skill_name=skill_name,
        grade_band=grade_band,
    )


def out_of_range_defects(
    response: HintSolutionReviewResponse, item: AuthoredGeneratedItemResponse
) -> list[str]:
    """Defect indices that point at a rung or step the item does not have.

    The schema bounds `index` below at 1 because the upper bound is the item's own length,
    which only the caller knows. A defect pointing at `hint_ladder[7]` of a three-rung ladder
    is not actionable and must not reach a repair prompt as if it were: repairing against a
    hallucinated location is how a good item gets damaged.
    """
    lengths = {
        "hint_ladder": len(item.hint_ladder),
        "canonical_solution": len(item.canonical_solution.steps),
    }
    return [
        f"{defect.target}[{defect.index}] does not exist "
        f"({defect.target} has {lengths[defect.target]} entries)"
        for defect in response.defects
        if defect.index is not None and defect.index > lengths[defect.target]
    ]


async def review_hints_and_solution(
    gateway: BedrockGateway,
    item: AuthoredGeneratedItemResponse,
    *,
    skill_name: str,
    grade_band: str,
    session_spend_cents: float,
) -> BedrockGenerationResult[HintSolutionReviewResponse]:
    """One independent review of `item`'s hint ladder and canonical solution.

    Returns the verdict as given. It does **not** decide anything - routing, second readings
    and repair belong to the caller, and no caller exists until the falsification run passes
    (docs/HINT_SOLUTION_REVIEW.md §5).

    **The whole result rather than `.value`, because cost is information the caller needs**
    (D-260). `review_loop` enforces a per-item cent cap alongside the round limit - §7: a
    round limit is not a spend limit - and it cannot do that against a wrapper that throws
    the price away. The first draft of that loop checked a running total nothing incremented.
    """
    result = await gateway.generate_structured(
        task=BedrockTask.HINT_SOLUTION_REVIEW,
        system_prompt=SYSTEM_PROMPT,
        payload=build_payload(item, skill_name=skill_name, grade_band=grade_band),
        response_model=HintSolutionReviewResponse,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        session_spend_cents=session_spend_cents,
    )
    return result
