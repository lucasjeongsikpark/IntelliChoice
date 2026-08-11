"""Targeted repair of a hint ladder and canonical solution from panel defects (D-260).

**Nothing calls this yet** - the loop that would (`review_loop.py`) has no pipeline caller
either. HINT_SOLUTION_REVIEW.md §4.6 is the design.

**Targeting is enforced by the schema, not by the prompt.** `HintSolutionRepairResponse`
contains only `hint_ladder` and `solution_steps` - the two things a `HintSolutionDefect` can
target - so a repair cannot move the stem, the options, the correct option or the equation
however the instruction is read. An earlier sketch returned a whole
`AuthoredGeneratedItemResponse` and asked the model to leave most of it alone; that version
could silently change the answer key, after which the panel would be reviewing a different
question from the one that was measured.

### The independence risk this channel creates, stated because it is real

`HintSolutionDefect.suggested_fix` is **the reviewer's own proposed wording**. If the repairer
adopts it verbatim, then reviewer B has authored the text that reviewer B is asked to approve
next round, and the two-reviewer independence D-256 measured (9 of 50 disagreements) leaks away
through the repair channel rather than through the panel.

Three responses were available and the choice is deliberate:

1. Withhold `suggested_fix` - loses the most actionable part of a defect.
2. Pass it and instruct the model that it is one option rather than replacement text - what
   this does, because the fix is genuinely useful and D-198 established that a rejection's
   content is the asset.
3. Guess at a mitigation and build it - refused. **It is instrumented instead:** the round
   history records `suggested_fix` beside the text that replaced it, so verbatim adoption is
   *countable* rather than argued about. If it turns out to be common, option 1 becomes a
   measured decision instead of a precaution.

This is the D-204 lesson applied before rather than after: do not change the roster on one good
argument without checking the property the role depends on.
"""

from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    BedrockGateway,
    BedrockGenerationResult,
    BedrockTask,
    HintSolutionDefect,
    HintSolutionRepairPayload,
    HintSolutionRepairResponse,
    SolutionStep,
)

_MAX_OUTPUT_TOKENS = 2000

_TARGETING = (
    "Change ONLY what the defects name. Every hint and every solution step the defects do "
    "not mention must come back word for word as you received it, **including its "
    "`common_mistake`** - that field records a misconception a student is likely to have at "
    "that step and dropping it silently removes feedback they would otherwise get. If you "
    "rewrite a step, carry its `common_mistake` across unless the rewrite makes it wrong. "
    "You are editing an item that is mostly correct, not writing a new one."
)

_SUGGESTIONS = (
    "Each defect carries a suggested fix. Treat it as one reviewer's opinion about what "
    "would help, not as replacement text to paste in. If you can see a better way to "
    "resolve the problem it names, take it - the defect's `problem` is what must be fixed, "
    "the suggestion is not."
)

_INVARIANTS = (
    "The question, the four options, the correct option and the final answer are fixed and "
    "are not yours to change. If a defect appears to ask you to change the answer, it is "
    "wrong - repair the hint or the step so that it leads to the answer given, and say so "
    "in your reasoning."
)

_STYLE = (
    "Keep the item's own voice. Do not rewrite hints that are merely phrased differently "
    "from how you would phrase them; there is no house style here."
)

SYSTEM_PROMPT = (
    "You repair the hint ladder and worked solution of a K-12 maths question that two "
    "independent reviewers have found defects in. Write `reasoning` first, naming each "
    "defect and what you changed for it.\n\n"
    f"{_TARGETING}\n\n{_SUGGESTIONS}\n\n{_INVARIANTS}\n\n{_STYLE}"
)


def render_defects(defects: list[HintSolutionDefect]) -> list[str]:
    """One flat line per defect, location first.

    Duplicates are preserved (D-259): if both reviewers named step 3, the repairer sees it
    twice, which is the only signal it gets that step 3 is where the agreement is.
    """
    return [
        f"{d.target}"
        + (f"[{d.index}]" if d.index is not None else " (overall)")
        + f": {d.problem} — suggested: {d.suggested_fix}"
        for d in defects
    ]


def build_payload(
    item: AuthoredGeneratedItemResponse,
    defects: list[HintSolutionDefect],
    *,
    skill_name: str,
    grade_band: str,
) -> HintSolutionRepairPayload:
    rendered_question = (
        f"{item.context_block}\n\n{item.stem}" if item.context_block else item.stem
    )
    return HintSolutionRepairPayload(
        rendered_question=rendered_question,
        option_a=item.option_a,
        option_b=item.option_b,
        option_c=item.option_c,
        option_d=item.option_d,
        correct_option=item.correct_option,
        hint_ladder=list(item.hint_ladder),
        # Passed through structurally, not rendered: the response must return this exact
        # shape, and D-263 measured a rendered form costing 4 of 10 repairs.
        solution_steps=list(item.canonical_solution.steps),
        solution_final_answer=item.canonical_solution.final_answer,
        skill_name=skill_name,
        grade_band=grade_band,
        defects=render_defects(defects),
    )


def collateral_edits(
    item: AuthoredGeneratedItemResponse,
    repair: HintSolutionRepairResponse,
    defects: list[HintSolutionDefect],
) -> list[str]:
    """Positions the repair changed that no defect named (D-261).

    **This is an exact invariant, which is why it is deterministic** (§3's bar): a hint or a
    step at a position nobody objected to either came back character for character or it did
    not. No judgement, no threshold.

    It exists because targeting turned out to be a *model property* rather than a guaranteed
    one. Measured at n=4 on the same fixture: Haiku rewrote nothing (4/4 clean), qwen3-32b
    rewrote an unobjected step once in four, and `mistral-large-3` rewrote **every** solution
    step **every** time while still fixing the defect it was asked about. A prompt clause
    cannot be relied on for this; a comparison can.

    **Compares the whole step, not selected fields (D-268).** It used to compare `explanation`
    and `expression` and ignore `common_mistake`, which is the third. The repairer does not
    return that field, so every repaired step silently lost its misconception note - 67 of them
    across 25 items, caught in a diff review rather than by this function, which is what it
    exists for. A targeting check that inspects a subset of a record is not a targeting check.

    Two deliberate limits:

    - A defect with `index=None` puts its whole target in scope, so nothing in that target is
      collateral. That is what "this is about the ladder as a whole" means.
    - A length change is **not** reported. Adding a step can be a legitimate repair, and once
      the lengths differ, positions no longer align, so any comparison would be inventing a
      correspondence rather than checking one. The caller sees the length change itself.
    """
    named: dict[str, set[int]] = {"hint_ladder": set(), "canonical_solution": set()}
    whole: set[str] = set()
    for defect in defects:
        if defect.index is None:
            whole.add(defect.target)
        else:
            named[defect.target].add(defect.index)

    edits: list[str] = []
    if "hint_ladder" not in whole and len(repair.hint_ladder) == len(item.hint_ladder):
        edits.extend(
            f"hint_ladder[{position}] changed but no defect named it"
            for position, (before, after) in enumerate(
                zip(item.hint_ladder, repair.hint_ladder, strict=True), start=1
            )
            if position not in named["hint_ladder"] and before != after
        )
    original_steps = item.canonical_solution.steps
    if "canonical_solution" not in whole and len(repair.solution_steps) == len(original_steps):
        edits.extend(
            f"canonical_solution[{position}] changed but no defect named it"
            for position, (before, after) in enumerate(
                zip(original_steps, repair.solution_steps, strict=True), start=1
            )
            if position not in named["canonical_solution"] and before != after
        )
    return edits


def carry_misconception_notes(
    original: list[SolutionStep], repaired: list[SolutionStep]
) -> list[SolutionStep]:
    """`repaired`, with any `common_mistake` the repair dropped restored from `original`.

    Public and separate because two callers need it and D-223 is this project's entry about
    what happens when one rule gets two implementations: `apply_repair` uses it live, and
    `scripts/apply_solution_repairs.py` needs it for dumps produced before it existed.

    A note the repair supplied itself always wins - carrying across is a floor, not an
    override, because a repair that rewrote a step knows more about that step than the
    original did.
    """
    if len(repaired) != len(original):
        # Position stops identifying "the same step" once a repair restructures the
        # solution, and a misconception note on the wrong step is worse than none.
        return list(repaired)
    return [
        step
        if step.common_mistake or not before.common_mistake
        else step.model_copy(update={"common_mistake": before.common_mistake})
        for step, before in zip(repaired, original, strict=True)
    ]


def apply_repair(
    item: AuthoredGeneratedItemResponse, repair: HintSolutionRepairResponse
) -> AuthoredGeneratedItemResponse:
    """The repaired item, with everything outside the ladder and the solution untouched.

    Built by copy rather than by constructor so that the day a field is added to
    `AuthoredGeneratedItemResponse` is not the day this silently drops it - **but revalidated**
    (D-267). `model_copy(update=...)` does **not** run validators, so before this a repair
    could produce an item that violates its own schema and the loop would carry it to the end
    without noticing. It happened: two four-rung hint ladders against a `max_length=3` field,
    accepted by both reviewers, caught only when the bank loader refused the file.

    Raises `ValidationError` if the repair does not produce a legal item. That is the right
    shape - the caller already treats a failing repair as a discard, and an item that cannot
    be constructed is not a repair.

    ### `common_mistake` is carried across, not requested (D-269)

    It is an optional field, models omit optional fields, and asking nicely was measured at
    **0 of 52 preserved** across 29 repaired items - a total loss, on every item, despite an
    explicit prompt clause. `collateral_edits` did not catch it either: it skips a target
    entirely when any defect for it carries `index=None` ("this is about the solution as a
    whole"), which reviewers file constantly, so the escape hatch swallowed the check.

    So the field stops being the model's to lose. Where the repair leaves it empty and the
    original step at that position had one, the original is restored. **Only when the step
    counts match** - once a repair restructures the solution, position no longer identifies
    "the same step", and attaching a misconception note to the wrong step is worse than
    having none.
    """
    steps = carry_misconception_notes(item.canonical_solution.steps, repair.solution_steps)
    return AuthoredGeneratedItemResponse.model_validate(
        item.model_copy(
            update={
                "hint_ladder": list(repair.hint_ladder),
                "canonical_solution": item.canonical_solution.model_copy(
                    update={"steps": steps, "final_answer": repair.solution_final_answer}
                ),
            }
        ).model_dump()
    )


async def repair_hints_and_solution(
    gateway: BedrockGateway,
    item: AuthoredGeneratedItemResponse,
    defects: list[HintSolutionDefect],
    *,
    skill_name: str,
    grade_band: str,
    session_spend_cents: float,
) -> BedrockGenerationResult[HintSolutionRepairResponse]:
    """One repair attempt. Decides nothing - re-reading the result is the loop's job.

    Returns the whole result for the reason `review_hints_and_solution` does: the loop's
    per-item cent cap needs the price, and a repair is the expensive call of the pair.
    """
    result = await gateway.generate_structured(
        task=BedrockTask.HINT_SOLUTION_REPAIR,
        system_prompt=SYSTEM_PROMPT,
        payload=build_payload(item, defects, skill_name=skill_name, grade_band=grade_band),
        response_model=HintSolutionRepairResponse,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        session_spend_cents=session_spend_cents,
    )
    return result
