"""SPEC §5.8.3 AI question-generation pipeline (S9), offline only - never called from a
runtime request path (CLAUDE.md non-negotiable #2, "no runtime NL2SQL" - by extension, no
runtime LLM authoring of graded content either).

```
Curriculum Topic -> Generator Agent -> Structured Question Template
  -> Solver Agent A -> Solver Agent B
  -> Difficulty Reviewer -> Ambiguity Reviewer -> Curriculum Alignment Reviewer
  -> Deterministic/Executable Validation -> Deduplication -> Activate or Quarantine
```

Design choices worth knowing before reading the code (see DECISIONS.md D-026):

- The Generator Agent picks a *shape key* from an explicit, difficulty-scoped allowlist
  (`DIFFICULTY_SHAPES`) - it never invents solving logic (D-015). Numeric parameter
  bounds are NOT requested from the model at all; `SHAPE_PARAMETER_BOUNDS` supplies them
  deterministically by shape, keeping magnitude a code-owned property (§5.8.4 lists
  "numerical magnitude" as one of several *deterministic complexity features*, not
  something an LLM should choose freely).
- Every model-proposed string (shape_key, correct_option_generator,
  distractor_generator_keys) is re-validated against the same registry the deterministic
  loader uses before it's trusted - a bad/hallucinated key rejects the candidate, it is
  never passed through to `generate_variant`.
- Solver A/B agreement is checked as *selected option letter*, not free-text answer
  matching - avoids formatting ambiguity, mirrors §5.8.4's "independent solver
  agreement" and this project's existing `generate_solution` answer-verification pattern
  (`learning_api/services/tutor.py`).
- A candidate that passes every automated check lands at `validation_status="pending"`,
  never auto-`"approved"` - see `QuestionRepository.activate_template` for why.
- Currently only `linear_equations` has registered shapes (D-003/D-015); calling this for
  any other topic_id raises `PipelineConfigError` rather than silently doing nothing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

from intellichoice_db.models.questions import (
    VARIANT_ORIGIN_CANONICAL,
    QuestionTemplate,
    QuestionValidationRun,
    QuestionVariant,
)
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.bedrock import (
    AlignmentReviewPayload,
    AlignmentReviewResponse,
    AmbiguityReviewPayload,
    AmbiguityReviewResponse,
    AuthoredGeneratedItemResponse,
    AuthoredGeneratorPayload,
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    DifficultyReviewPayload,
    DifficultyReviewResponse,
    GeneratedTemplateResponse,
    GeneratorPayload,
    QuestionJudgePayload,
    QuestionJudgeResponse,
    SolverPayload,
    SolverResponse,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_curriculum.authored_validation import validate_authored_item
from intellichoice_curriculum.content import CurriculumContent
from intellichoice_curriculum.generation import VariantGenerationError, generate_variant
from intellichoice_curriculum.templates.model import QuestionTemplateDef
from intellichoice_curriculum.templates.registry import (
    CORRECT_OPTION_GENERATORS,
    DISTRACTOR_GENERATORS,
)
from intellichoice_curriculum.validation import validate_variant

# topic_id -> difficulty_label -> skill_id. Deterministic, not LLM-chosen: this topic's
# skill ladder tracks difficulty 1:1 (matches the S4 hand-authored bank exactly - see
# curriculum/internal_math/skills.yaml's comment and templates/linear_equations.py).
TOPIC_DIFFICULTY_SKILLS: dict[str, dict[int, str]] = {
    "linear_equations": {
        1: "linear_one_step",
        2: "linear_two_step",
        3: "linear_neg_frac_coeff",
        4: "linear_both_sides",
        5: "linear_distribute",
    }
}

# topic_id -> skill_id -> the difficulty tiers that skill should carry content at.
#
# D-186: the authoring plan, and the reason it is a *second* map rather than an inversion
# of the one above. `TOPIC_DIFFICULTY_SKILLS` stays the **native** ladder - each skill's
# home tier, the default when no skill is named, and still 1:1. This map says which tiers
# each skill should additionally be authored at, and it is deliberately not uniform:
#
#   - The three middle skills carry their native tier ±1. `mastery_bootstrap` anchors
#     `recommended_difficulty` on the modal assessed tier ±1 and clamps to 1-5, so T±1 is
#     the entire range a skill can ever be recommended at - a fourth tier could not be
#     selected by any student.
#   - The ladder ends (`linear_one_step` at 1, `linear_distribute` at 5) stay single-tier.
#     The clamp means tier 1's neighbour below and tier 5's neighbour above do not exist,
#     and the user's call was multi-tier "for the middle skills".
#
# **Authored mode only.** The shape pipeline picks from `DIFFICULTY_SHAPES`, which is keyed
# by tier alone, so a skill generated at an off-native tier would be handed another skill's
# math forms (`linear_two_step` at tier 3 would get `frac_coeff`/`neg_coeff`). Authored mode
# has no shape allowlist - it generates a real stem from the skill and tier - which is why
# multi-tier lives there and `run_pipeline` is untouched.
TOPIC_SKILL_DIFFICULTIES: dict[str, dict[str, list[int]]] = {
    "linear_equations": {
        "linear_one_step": [1],
        "linear_two_step": [1, 2, 3],
        "linear_neg_frac_coeff": [2, 3, 4],
        "linear_both_sides": [3, 4, 5],
        "linear_distribute": [5],
    }
}

# topic_id -> difficulty_label -> shape keys the Generator Agent may choose among.
DIFFICULTY_SHAPES: dict[str, dict[int, list[str]]] = {
    "linear_equations": {
        1: ["one_step_add", "one_step_sub", "one_step_mul"],
        2: ["two_step", "two_step_sub_b"],
        3: ["frac_coeff", "neg_coeff"],
        4: ["both_sides", "both_sides_alt"],
        5: ["distribute_simple", "distribute_combine"],
    }
}


def _bounds(min_: int, max_: int, exclude: list[int] | None = None) -> dict:
    spec: dict = {"min": min_, "max": max_}
    if exclude:
        spec["exclude"] = exclude
    return spec


# Deterministic per-shape parameter bounds (see module docstring) - one safe default per
# shape, grade-appropriate magnitude, guaranteed by construction to avoid the zero
# coefficients each shape's `solve` divides by.
SHAPE_PARAMETER_BOUNDS: dict[str, dict] = {
    "one_step_add": {"b": _bounds(1, 20), "x": _bounds(1, 20, [0])},
    "one_step_sub": {"b": _bounds(1, 20), "x": _bounds(1, 20, [0])},
    "one_step_mul": {"a": _bounds(2, 12, [0, 1]), "x": _bounds(1, 20, [0])},
    "two_step": {"a": _bounds(2, 12, [0]), "b": _bounds(1, 20), "x": _bounds(-9, 9, [0])},
    "two_step_sub_b": {"a": _bounds(2, 12, [0]), "b": _bounds(1, 20), "x": _bounds(-9, 9, [0])},
    "frac_coeff": {
        "d": _bounds(2, 6, [0, 1]),
        "b": _bounds(1, 20),
        "x_over_d": _bounds(-9, 9, [0]),
    },
    "neg_coeff": {"a": _bounds(2, 6, [0]), "b": _bounds(1, 20), "x": _bounds(-9, 9, [0])},
    "both_sides": {
        "a": _bounds(2, 10, [0]),
        "d": _bounds(2, 10, [0]),
        "b": _bounds(1, 20),
        "x": _bounds(-9, 9, [0]),
    },
    "both_sides_alt": {
        "a": _bounds(2, 10, [0]),
        "d": _bounds(2, 10, [0]),
        "b": _bounds(1, 20),
        "x": _bounds(-9, 9, [0]),
    },
    "distribute_simple": {
        "a": _bounds(2, 10, [0, 1]),
        "b": _bounds(1, 15),
        "x": _bounds(-9, 9, [0]),
    },
    "distribute_combine": {
        "a": _bounds(2, 8, [0]),
        "d": _bounds(-8, 8, [0]),
        "b": _bounds(1, 15),
        "x": _bounds(-9, 9, [0]),
    },
}

_REQUIRED_DISTRACTOR_COUNT = 3  # 4 options total: 1 correct + 3 distractors.

_GENERATOR_SYSTEM_PROMPT = (
    "You are a math question generator for a K-12 curriculum. Given a topic, skill, "
    "grade band, and target difficulty, choose ONE equation shape and metadata from the "
    "allowed lists provided. Never propose a shape, generator, or distractor key that "
    "isn't in the allowed lists."
)
_SOLVER_SYSTEM_PROMPT = (
    "You are an independent math solver. Work the question out in `reasoning` first, "
    "then select the letter of the one option that matches the answer you reached. "
    # Without this the solver's only move is to name one of four options, so a question
    # whose real answer is missing produces a confident wrong pick - and two solvers doing
    # that independently land on the same wrong pick and are recorded as agreeing (D-193).
    "Do not work backwards from the options. If the answer you reached is not among "
    "them, set no_option_matches to true and select the closest option anyway. If the "
    "question admits more than one defensible answer, set is_unambiguous to false and "
    "say why in ambiguity_reasons."
)


# D-194 difficulty policy. `_DIFFICULTY_REJECT_AT` is the gap at which two independent
# readings of the same item stop being a judgement call and start being a contradiction:
# one of them is wrong about what the item demands, and neither the pipeline nor a
# reviewer can tell which. `_DIFFICULTY_FLAG_AT` is a real but survivable disagreement -
# the item is kept and a human is pointed at it.
_DIFFICULTY_FLAG_AT = 1
_DIFFICULTY_REJECT_AT = 2


@dataclass(frozen=True)
class DifficultyVerdict:
    """The whole difficulty decision as data, so the evidence written to
    `question_validation_runs` and the branch taken by the pipeline cannot disagree -
    they are computed once, here, from the same fields.
    """

    proposed: int
    proposed_rationale: str
    reviewed: int
    reviewed_rationale: str
    requested: int
    proposal_gap: int
    slot_gap: int
    decision: Literal["accepted", "flagged", "rejected"]
    reasons: list[str]

    def as_evidence(self) -> dict:
        return {
            "generator_proposed_difficulty": self.proposed,
            "generator_difficulty_rationale": self.proposed_rationale,
            "judge_reviewed_difficulty": self.reviewed,
            "judge_difficulty_reasoning": self.reviewed_rationale,
            "requested_difficulty": self.requested,
            "proposal_vs_review_difference": self.proposal_gap,
            "review_vs_requested_difference": self.slot_gap,
            "decision": self.decision,
        }


def judge_difficulty(
    *,
    proposed: int,
    proposed_rationale: str,
    reviewed: int,
    reviewed_rationale: str,
    requested: int,
) -> DifficultyVerdict:
    """Compare the Generator's difficulty claim with the judge's independent one.

    Three numbers are in play and they answer different questions, which is why one gate
    cannot cover them:

    - `requested` is the tier the *slot* asked for. It is an instruction, not an opinion,
      and it decides where the item is stored and what its template id says.
    - `proposed` is the Generator's claim. It saw `requested`, so it is anchored - the
      number is weak evidence and the rationale beside it is the part worth reading.
    - `reviewed` is the judge's, reached without seeing either of the others
      (`QuestionJudgePayload` no longer carries them). This is the only independent one.

    So `proposal_gap` asks "do two readers agree about this item?" and `slot_gap` asks
    "does this item belong in the slot it was generated for?". Both reject at 2. An item
    the judge calls tier 1 stored in the tier-5 slot would be selected for students who
    have earned tier 5, which is a worse failure than a wasted candidate.

    Acceptability is decided here rather than asked of the model, deliberately. A judge
    blind to the proposal *cannot* say whether it is acceptable, and a judge shown the
    proposal is no longer independent - so the question the instruction asks for is only
    answerable by arithmetic on two numbers, which is also the answer that cannot be
    argued out of (CLAUDE.md rule 2, deterministic core).
    """
    proposal_gap = abs(proposed - reviewed)
    slot_gap = abs(reviewed - requested)
    reasons: list[str] = []
    if proposal_gap >= _DIFFICULTY_REJECT_AT:
        reasons.append(
            f"difficulty disagreement: generator proposed {proposed} "
            f"({proposed_rationale}), judge independently rated {reviewed} "
            f"({reviewed_rationale})"
        )
    if slot_gap >= _DIFFICULTY_REJECT_AT:
        reasons.append(
            f"judge rated difficulty {reviewed} ({reviewed_rationale}), too far from the "
            f"requested tier {requested} this candidate would be stored at"
        )
    if reasons:
        decision: Literal["accepted", "flagged", "rejected"] = "rejected"
    elif proposal_gap >= _DIFFICULTY_FLAG_AT or slot_gap >= _DIFFICULTY_FLAG_AT:
        decision = "flagged"
    else:
        decision = "accepted"
    return DifficultyVerdict(
        proposed=proposed,
        proposed_rationale=proposed_rationale,
        reviewed=reviewed,
        reviewed_rationale=reviewed_rationale,
        requested=requested,
        proposal_gap=proposal_gap,
        slot_gap=slot_gap,
        decision=decision,
        reasons=reasons,
    )


def solver_objections(
    solver_a: SolverResponse, solver_b: SolverResponse, *, declared: str
) -> list[str]:
    """Everything the two solvers can object to, in one place so both pipelines gate the
    same way. Empty list means the stage passed.

    Agreement was the whole check before D-193, and it is the weakest of the three: two
    solvers reading the same broken question fail the same way, and the closed
    `selected_option` literal forced them to express that failure as a *vote*. So a
    missing correct answer and a genuine ambiguity are now their own rejections, checked
    before agreement - an item where the solvers agree on an option neither of them
    believes should not be reported as "solvers agreed".

    Either solver objecting is enough. These are the fail-closed direction (CLAUDE.md
    rule 5), and requiring both to independently notice the same defect would put the
    threshold above what one careful reader catches.
    """
    reasons: list[str] = []
    for name, solver in (("solver_a", solver_a), ("solver_b", solver_b)):
        if solver.no_option_matches:
            reasons.append(
                f"{name} reached an answer that is not among the options "
                f"(closest={solver.selected_option!r}): {solver.reasoning}"
            )
        if not solver.is_unambiguous:
            reasons.append(f"{name} flagged ambiguity: {'; '.join(solver.ambiguity_reasons)}")
    if not (solver_a.selected_option == solver_b.selected_option == declared):
        reasons.append(
            "independent solver disagreement: "
            f"solver_a={solver_a.selected_option!r} solver_b={solver_b.selected_option!r} "
            f"declared={declared!r}"
        )
    return reasons


_DIFFICULTY_SYSTEM_PROMPT = (
    "You are an independent difficulty reviewer for a K-12 math question bank. Rate the "
    "question's difficulty from 1 (easiest) to 5 (hardest), independent of the proposed "
    "label."
)
_AMBIGUITY_SYSTEM_PROMPT = (
    "You are reviewing a multiple-choice math question for ambiguity - wording that "
    "could reasonably support more than one option, or that is unclear to a K-12 "
    "student."
)
_ALIGNMENT_SYSTEM_PROMPT = (
    "You are reviewing whether a math question is correctly aligned to its stated "
    "topic and skill for a K-12 curriculum."
)

_MAX_TOKENS = 400

# S20 authored mode's responses are far larger than S9's shape-mode ones, and the single
# shared ceiling above made authored generation *impossible* rather than merely tight -
# silently, because nothing exercised it under a real model until now. Measured against
# real Bedrock (Haiku 4.5, 2026-08-05): a complete `AuthoredGeneratedItemResponse` runs
# 631 output tokens at tier 1 and 954 at tier 5, so 400 truncated every candidate at the
# generator stage, before the deterministic gate ever ran. Sized with headroom above the
# measured worst case rather than at it - the ceiling is a runaway guard, not a budget,
# since output tokens bill by actual use.
# Raised from 1600 after the first scenario run hit it (D-191). The 1600 was measured
# against bare "Solve for x" output, where the worst case was 954 tokens; a question that
# sets up a situation, four unit-bearing options and a worked solution is simply longer, so
# the old ceiling was calibrated on content the pipeline no longer produces. Still a
# runaway guard rather than a budget - output tokens bill by actual use.
_AUTHORED_ITEM_MAX_TOKENS = 2500
# Solver and judge responses are a few small fields plus a free-text `reasoning` (the
# generator's ran ~660 characters at tier 5, i.e. well inside 400 on its own). Not observed
# truncating, but a judge truncated by this ceiling discards a candidate that has already
# paid for four calls, so they get modest headroom for the same reason.
# Raised from 800 once the questions became scenarios: a solver reading a *story* has to
# model it before it can answer, and one ran out of tokens mid-reasoning on the first run.
# The judge shares this ceiling and writes considerably more now that it also checks the
# scenario's own constraints - and more again since D-193 made `reasoning` the field it
# writes first, which is the point of that change, so the headroom is load-bearing.
_AUTHORED_REVIEW_MAX_TOKENS = 1200

# --- S20 authored generation mode (plan §7) -----------------------------------------

_AUTHORED_GENERATOR_SYSTEM_PROMPT = (
    "You are an expert K-12 math item writer. Given a topic, skill, grade band, and "
    "target difficulty, write ONE original multiple-choice question: a clear stem, four "
    "distinct options with exactly one correct, a SymPy-parseable `equation` that models "
    "the question, a 3-level hint ladder that progressively guides "
    "without ever stating the final answer, a worked canonical solution whose final "
    "answer matches the correct option exactly, and a misconception tag per distractor. "
    "Never leak the answer in the stem or any hint. "
    # The pipeline's first real output was five items, every one of them a bare
    # "Solve for x: ..." with no context block at all - the field was documented as
    # "optional ... if it helps" and the model took the cheap path every time. Nothing
    # rejected a richer question; none was ever generated. Hence the requirement rather
    # than the invitation (D-191).
    "WRITE A SITUATION, NOT AN EXERCISE. The stem must place the mathematics in a "
    "concrete scenario a student can picture - characters, objects, a goal, a question "
    "worth answering. A bare symbolic prompt such as 'Solve for x: 7x + 3 = 4x + 4' is "
    "NOT acceptable; the same mathematics presented as two robots collecting crystals at "
    "different rates from different starting amounts IS. Only when the skill is explicitly "
    "about symbolic manipulation for its own sake may the stem be purely symbolic. "
    "Vary the setting between items - do not write two questions in the same world. "
    "Keep every sentence under 30 words and the reading level inside the grade band; a "
    "scenario that is hard to read is a reading test, not a math question. "
    "The answer may carry a unit ('12 minutes', '40 cm') when the scenario implies one - "
    "write the unit in the option text; the equation stays purely numeric. "
    # The deterministic gate solves `equation` and compares the derived value to the
    # options' own text, so an option that does not parse as a value cannot be confirmed
    # correct. The first real run lost six of eleven candidates to exactly this - correct
    # answers written as "x = 7" or with a typographic minus - so the format is stated
    # rather than left implied. `_normalize_math_text` now also repairs both cases at the
    # parse site; asking here as well keeps the item text itself clean, since the stored
    # option text is what students and downstream text checks actually see.
    "Write each option as a bare value with no variable "
    "and no equals sign ('7', not 'x = 7'), and use the ASCII hyphen '-' for negatives, "
    "never a typographic minus. "
    # D-191 measured the alternative: six passing items in a row whose correct answer was
    # option b, i.e. a bank a student could score 100% on by answering "always b". The fix
    # is `shuffle_options`, in code and seeded; this sentence only stops the model from
    # *also* trying, which would compose with the shuffle into a fresh bias rather than
    # cancelling it.
    "Do not try to control which option letter is correct - vary it naturally and ignore "
    "the position; a deterministic shuffle reorders the options afterwards. "
    # The distractors are what make an MCQ diagnostic rather than a coin flip. Generic
    # wrong numbers tell a teacher nothing; a distractor that is the answer a specific
    # mistake produces turns the response data into evidence about *which* mistake.
    "Each distractor must be the value a specific, likely student mistake produces - "
    "dropping a sign, adding where the equation subtracts, solving for the wrong "
    "quantity, stopping one step early - and its misconception tag must name that "
    "mistake. Never pad with a value no plausible reasoning reaches. Exactly one option "
    "may be defensible: if a second reading of your own stem makes another option "
    "arguable, rewrite the stem. "
    # D-194. The tier is supplied as a target, so `proposed_difficulty` is anchored by it
    # and is not evidence on its own - the independent number comes from the judge, which
    # never sees either. What this field genuinely buys is the rationale: a model that has
    # to name the operations an item demands writes a different item than one that does
    # not, and the rationale is what a human reviewer reads next to the judge's.
    "Set `proposed_difficulty` to the tier YOU judge the item to be, on a 1-5 scale, even "
    "when that differs from the target you were given - a disagreement recorded is worth "
    "more than a number echoed. In `difficulty_rationale`, name the reasoning operations "
    "the item actually demands: 'the equation is not given, so the student must translate "
    "two rates and two starting amounts into one', 'the variable appears on both sides', "
    "'distribution is required before like terms can be combined', 'the coefficient is a "
    "negative fraction', 'two distinct reasoning steps with no intermediate prompt'. Do "
    "NOT restate the label ('this is difficulty 3', 'moderately difficult', 'appropriate "
    "for the grade') - that is not a rationale. "
    "List in `required_prerequisites` the curriculum concepts a student must already hold "
    "for this item to be fair, in plain words ('integer arithmetic with negatives', "
    "'solving one-step equations')."
)
_JUDGE_SYSTEM_PROMPT = (
    "You are an independent judge reviewing one authored K-12 math question for "
    "difficulty fit, ambiguity, curriculum alignment, age-appropriateness, and the "
    "quality of its hint ladder. Be strict: a genuinely ambiguous, misaligned, or "
    "unsafe question must be flagged. "
    # The first scenario run produced "A video game has three levels ... how many levels
    # did she complete?" with the answer 4. The equation was solved correctly and the
    # story was impossible; solvers and judge all passed it, because nothing had asked
    # anyone to compare the answer against the scenario's own stated facts (D-191).
    "Check the answer against the situation the question describes, not only against "
    "its arithmetic. If the story states a limit or a quantity and the answer exceeds "
    "or contradicts it - a three-level game whose answer is four levels, a person "
    "buying more items than are for sale, a negative number of minutes - the question "
    "is not internally consistent, however correct the algebra is. "
    # Left unstated until 2026-08-05, when the first real run showed the judge inventing a
    # 1-10 scale and scoring 8-9 on every item - which sits above both thresholds below,
    # so the hint-quality gate silently never fired. The schema now bounds the field too;
    # this states the same contract in the place the model is most likely to follow it.
    "Score hint_quality_score on a scale of 1 to 5, where 1 is a ladder that misleads or "
    "gives the answer away, 3 is usable but shallow, and 5 is a genuinely progressive "
    "ladder that guides without revealing. Do not use any other scale. "
    # The schema now puts `reasoning` first (D-193) so this instruction is followable;
    # stated here as well because the judge that missed a wrong answer had *found* it in
    # prose and still emitted the passing boolean. Naming the dependency explicitly is
    # cheap next to another item reaching a student.
    "Write `reasoning` first and work the question out there in full, including solving "
    "it yourself. Then set every boolean to match what you concluded. If your reasoning "
    "finds the stated answer wrong, `is_internally_consistent` must be false. "
    # D-194. The judge is not told the tier that was requested or the tier the generator
    # claimed, so this is genuinely its own reading - which is the only reason comparing
    # the two numbers means anything. Saying "you have not been told" out loud discourages
    # the model from guessing at an intended answer.
    "Rate `reviewed_difficulty` on the same 1-5 scale from the question alone. You have "
    "NOT been told what tier this item was written for, and you should not try to infer "
    "one from the request - judge what the item demands. In `difficulty_reasoning`, name "
    "the reasoning operations required (translating a scenario into an equation, a "
    "variable on both sides, distribution before combining like terms, negative or "
    "fractional coefficients, the number of distinct steps), not how hard it feels."
)

# Small, fixed set of hand-written few-shot exemplars (this project has no pre-authored
# hint/solution content to draw from - hints are otherwise only ever LLM-generated at
# request time, §5.11.4) describing the expected stem/hint-ladder/solution style. Not
# topic-specific by design so the same list works across every authored difficulty.
_AUTHORED_FEW_SHOT_EXEMPLARS: list[str] = [
    # Every exemplar is a scenario, deliberately. The previous pair was one word problem
    # and one bare "Solve for x", and the model copied the bare one five times out of five
    # - an exemplar set is a menu, and half of that menu was the thing to avoid.
    #
    # Each is now complete rather than illustrative of the stem alone (D-194): options with
    # the mistake each one encodes, a three-level ladder, the final answer, a difficulty
    # rationale naming reasoning operations, and prerequisites. A field demonstrated in
    # every exemplar is filled far more consistently than one only described in the prompt,
    # and `difficulty_rationale` is exactly the field a model will otherwise satisfy with
    # "moderately difficult". The three settings and the three tiers are unlike each other
    # so variety is shown, not just asked for.
    (
        "stem: 'Two robots are collecting energy crystals. Robot A starts with 4 crystals "
        "and collects 4 crystals each minute. Robot B starts with 16 crystals and collects "
        "2 crystals each minute. After how many minutes will the robots have the same "
        "number of crystals?' | options: '6 minutes' (correct), '2 minutes' (added the two "
        "rates instead of subtracting), '12 minutes' (stopped at 2m = 12 without dividing), "
        "'3 minutes' (ignored Robot B's rate) | misconception_tags: ['added_rates', "
        "'skipped_final_division', 'ignored_second_rate'] | hint_ladder: ['Write an "
        "expression for each robot's total after m minutes.', 'Robot A has 4 + 4m and Robot "
        "B has 16 + 2m. The question asks when those are equal.', 'Collect the m terms on "
        "one side, then divide by what is left.'] | canonical_solution final_answer: "
        "'6 minutes' | equation: 'Eq(4 + 4*m, 16 + 2*m)' | proposed_difficulty: 4 | "
        "difficulty_rationale: 'The equation is not given, so the student must turn two "
        "starting amounts and two rates into one equation; the variable then appears on "
        "both sides and has to be collected before dividing.' | required_prerequisites: "
        "['writing a linear expression from a starting amount and a rate', 'solving "
        "two-step equations']"
    ),
    (
        "stem: 'Mia is saving for a bike. She already has $18 and saves $6 each week. The "
        "bike costs $60. How many weeks until she can buy it?' | options: '7 weeks' "
        "(correct), '13 weeks' (added the $18 instead of subtracting it), '10 weeks' "
        "(ignored the money already saved), '42 weeks' (stopped at 6w = 42) | "
        "misconception_tags: ['added_instead_of_subtracted', 'ignored_starting_amount', "
        "'skipped_final_division'] | hint_ladder: ['What will Mia have saved after w "
        "weeks?', 'Her savings are 18 + 6w, and she needs that to reach 60.', 'Subtract "
        "what she already has, then divide by her weekly amount.'] | canonical_solution "
        "final_answer: '7 weeks' | equation: 'Eq(18 + 6*w, 60)' | proposed_difficulty: 2 | "
        "difficulty_rationale: 'Two steps - undo the starting amount, then undo the weekly "
        "rate - with the variable on one side only and no negative or fractional "
        "coefficient.' | required_prerequisites: ['whole-number division', 'writing an "
        "expression from a starting amount and a constant rate']"
    ),
    (
        "stem: 'A bakery packs gift boxes. Each box holds the same number of cookies plus "
        "2 chocolates, and there are 5 boxes. The bakery also packs 12 loose cookies. "
        "Altogether there are 42 items. How many cookies are in each box?' | options: "
        "'4 cookies' (correct), '5 cookies' (multiplied 5 by the cookies but not by the 2 "
        "chocolates), '6 cookies' (folded the 2 into the coefficient and solved 7x = 42), "
        "'32 cookies' (stopped at 8x = 32) | misconception_tags: "
        "['distributed_only_the_first_term', 'combined_constant_into_coefficient', "
        "'skipped_final_division'] | hint_ladder: ['How many items are in one box, if a box "
        "holds c cookies?', 'Five boxes hold 5(c + 2) items, and 12 loose cookies are added "
        "to that.', 'Multiply out the bracket first, then gather the c terms.'] | "
        "canonical_solution final_answer: '4 cookies' | equation: 'Eq(5*(c + 2) + 12, 42)' "
        "| proposed_difficulty: 5 | difficulty_rationale: 'The bracket has to be "
        "distributed before like terms can be combined, and the student must first decide "
        "that a box is c + 2 items rather than c.' | required_prerequisites: ['the "
        "distributive property', 'combining like terms', 'solving two-step equations']"
    ),
]

# Cosine-*distance* ceiling for the SPEC §5.8.5 authored near-duplicate check (0 =
# identical, 2 = opposite) - a placeholder pending real-embedding calibration, same
# "never exercised against real AWS" caveat as D-025/D-035/D-046: `MockBedrockProvider`'s
# hash-based vectors are high-dimensional and effectively random for unrelated text, so
# only a near-exact-text stem collides this tightly in tests.
NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD = 0.05

# SPEC §5.8.5/plan §7 judge thresholds: a genuinely low hint-quality score rejects; a
# borderline one (or a 1-off difficulty disagreement) doesn't reject but does route the
# candidate to human review first (`review_priority="high"`) rather than the ordinary
# queue. `hint_quality_score` is judged on a 1 (poor) - 5 (excellent) scale.
_HINT_QUALITY_REJECT_BELOW = 2
_HINT_QUALITY_BORDERLINE_AT = 3


# Mirrors `authored_validation._OPTION_LABELS`; kept local rather than importing a
# private name across modules.
_OPTION_LABELS = ("a", "b", "c", "d")


def shuffle_options(
    item: AuthoredGeneratedItemResponse, *, seed: int
) -> AuthoredGeneratedItemResponse:
    """Deterministically permute the four options, keeping `correct_option` pointing at
    the same text.

    The first scenario run produced six passing items whose correct answer was option
    **b** every single time (D-191). A student answering "always b" would have scored 100%.
    Two solver agents and the judge passed all six without noticing, and no deterministic
    check looked at the distribution - it is not a property of any single item, so nothing
    examining one item could see it.

    Fixed here rather than in the prompt on purpose: "vary which option is correct" is
    exactly the kind of instruction a model follows unreliably and unverifiably, while a
    seeded permutation is free, exact, and reproducible. Seeded from the candidate's own
    seed so a re-run at the same seed rebuilds the identical item (D-013's determinism
    posture).

    Applied *before* validation and before the solvers, so every downstream stage sees the
    item as a student would. Positions are tracked by index rather than by text, so an item
    with duplicate options - which `check_unique_options` rejects a moment later - cannot
    mislabel which option is correct on the way there.
    """
    texts = [item.option_a, item.option_b, item.option_c, item.option_d]
    correct_index = _OPTION_LABELS.index(item.correct_option)
    order = list(range(len(texts)))
    random.Random(seed).shuffle(order)
    shuffled = [texts[old_index] for old_index in order]
    return item.model_copy(
        update={
            "option_a": shuffled[0],
            "option_b": shuffled[1],
            "option_c": shuffled[2],
            "option_d": shuffled[3],
            "correct_option": _OPTION_LABELS[order.index(correct_index)],
        }
    )


class PipelineConfigError(Exception):
    """The pipeline was asked to generate for a topic/difficulty it has no registered
    shapes or skill for - a configuration gap, not a per-candidate rejection.
    """


# Which stage ended the candidate. Recorded rather than inferred from the reason strings,
# because a run's headline number is only interpretable if "the solvers disagreed" and "we
# ran out of money before calling anything" are different rows (D-192).
RejectionStage = Literal[
    "generator",
    "validation",
    "dedup",
    "solver",
    "judge",
    # D-194: split out of "judge" because it is a different finding. A judge rejection
    # says the question is bad; a difficulty rejection says the question may be fine and
    # the two independent readings of how hard it is cannot both be right. Merging them
    # would make the run summary's largest bucket uninterpretable.
    "difficulty",
    "budget",
    "unsupported_shape",
]


@dataclass
class PipelineOutcome:
    status: Literal["pending", "rejected"]
    reasons: list[str] = field(default_factory=list)
    rejected_at: RejectionStage | None = None
    question_template_id: str | None = None
    question_variant_id: str | None = None
    cost_cents: float = 0.0


async def _call(
    gateway: BedrockGateway,
    *,
    task: BedrockTask,
    system_prompt: str,
    payload: BaseModel,
    response_model: type[BaseModel],
    session_spend_cents: float,
    max_output_tokens: int = _MAX_TOKENS,
) -> tuple[BaseModel | None, float, str | None]:
    """Thin wrapper: returns (value, cost_cents, error) instead of raising, so the
    pipeline can record *why* a candidate was rejected instead of crashing the batch run
    (SPEC §5.29-style failure handling, applied to an offline pipeline instead of a
    request path).

    `max_output_tokens` is per call site rather than per `BedrockTask` on purpose: the
    authored solvers deliberately reuse the shape pipeline's `QUESTION_GENERATION` and
    `QUESTION_REVIEW` task slots so they resolve to two different models, so the task
    alone cannot say how large a response to expect. The default keeps every shape-mode
    call at the value it has always used.
    """
    try:
        result = await gateway.generate_structured(
            task=task,
            system_prompt=system_prompt,
            payload=payload,
            response_model=response_model,
            max_output_tokens=max_output_tokens,
            session_spend_cents=session_spend_cents,
        )
    except BedrockGatewayError as exc:
        return None, exc.cost_cents, str(exc)
    return result.value, result.cost_cents, None


async def generate_candidate(
    *,
    session: AsyncSession,
    gateway: BedrockGateway,
    curriculum: CurriculumContent,
    topic_id: str,
    difficulty_label: int,
    seed: int,
    session_spend_cents: float,
) -> PipelineOutcome:
    """Runs one candidate template through the full pipeline and persists the result
    (as `pending` or `rejected` - see module docstring). Returns the outcome plus the
    real cost incurred, so a caller running many candidates can track cumulative spend
    across calls (the gateway itself only guards a single call against the budget it's
    told about - see `ResilientBedrockGateway.generate_structured`).
    """
    difficulty_shapes = DIFFICULTY_SHAPES.get(topic_id, {}).get(difficulty_label)
    skill_id = TOPIC_DIFFICULTY_SKILLS.get(topic_id, {}).get(difficulty_label)
    if not difficulty_shapes or skill_id is None:
        raise PipelineConfigError(
            f"no registered shapes/skill for topic_id={topic_id!r} "
            f"difficulty_label={difficulty_label!r}"
        )
    topic = next((t for t in curriculum.topics if t.topic_id == topic_id), None)
    skill = next((s for s in curriculum.skills if s.skill_id == skill_id), None)
    if topic is None or skill is None:
        raise PipelineConfigError(f"topic/skill not in curriculum taxonomy: {topic_id}/{skill_id}")

    spend = session_spend_cents
    total_cost = 0.0

    def _spend(cost: float) -> None:
        nonlocal spend, total_cost
        spend += cost
        total_cost += cost

    # --- 1. Generator Agent -----------------------------------------------------
    gen_payload = GeneratorPayload(
        topic_name=topic.name,
        skill_name=skill.name,
        grade_band=topic.grade_band,
        difficulty_label=difficulty_label,
        allowed_shape_keys=difficulty_shapes,
        allowed_correct_option_generators=list(CORRECT_OPTION_GENERATORS),
        allowed_distractor_generator_keys=list(DISTRACTOR_GENERATORS),
    )
    proposal, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_GENERATION,
        system_prompt=_GENERATOR_SYSTEM_PROMPT,
        payload=gen_payload,
        response_model=GeneratedTemplateResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None or proposal is None:
        return PipelineOutcome(
            status="rejected", reasons=[f"generator call failed: {error}"], cost_cents=total_cost
        )
    assert isinstance(proposal, GeneratedTemplateResponse)

    reasons: list[str] = []
    if proposal.shape_key not in difficulty_shapes:
        reasons.append(
            f"generator proposed unregistered/off-difficulty shape {proposal.shape_key!r}"
        )
    if proposal.correct_option_generator not in CORRECT_OPTION_GENERATORS:
        reasons.append(
            f"generator proposed unregistered correct_option_generator "
            f"{proposal.correct_option_generator!r}"
        )
    distractor_keys = proposal.distractor_generator_keys
    if len(distractor_keys) != _REQUIRED_DISTRACTOR_COUNT or any(
        key not in DISTRACTOR_GENERATORS for key in distractor_keys
    ):
        reasons.append(
            f"generator proposed invalid distractor_generator_keys {distractor_keys!r} "
            f"(need exactly {_REQUIRED_DISTRACTOR_COUNT} registered keys)"
        )
    if reasons:
        return PipelineOutcome(status="rejected", reasons=reasons, cost_cents=total_cost)

    parameter_schema = SHAPE_PARAMETER_BOUNDS[proposal.shape_key]
    template_def = QuestionTemplateDef(
        topic_id=topic_id,
        skill_id=skill_id,
        grade_band=topic.grade_band,
        difficulty_label=difficulty_label,
        question_type="multiple_choice",
        parameter_schema=parameter_schema,
        solution_function=proposal.shape_key,
        correct_option_generator=proposal.correct_option_generator,
        distractor_generators=distractor_keys,
        common_error_tags=proposal.common_error_tags,
        estimated_time_seconds=proposal.estimated_time_seconds,
        generator_model="bedrock-question-generation",
        review_model_versions={},
    )

    # --- 2. Deterministic variant generation + §5.8.5 executable validation -----
    try:
        variant = generate_variant(
            shape_key=proposal.shape_key,
            parameter_schema=parameter_schema,
            correct_option_generator=proposal.correct_option_generator,
            distractor_generator_keys=distractor_keys,
            seed=seed,
        )
    except VariantGenerationError as exc:
        return PipelineOutcome(
            status="rejected",
            reasons=[f"variant generation failed: {exc}"],
            cost_cents=total_cost,
        )

    if await QuestionRepository(session).rendered_question_exists(variant.rendered_question):
        return PipelineOutcome(
            status="rejected", reasons=["duplicate rendered_question"], cost_cents=total_cost
        )

    validation = validate_variant(template_def, variant, curriculum)
    if not validation.passed:
        return PipelineOutcome(
            status="rejected", reasons=validation.failures, cost_cents=total_cost
        )

    # --- 3. Independent Solver Agents A and B ------------------------------------
    solver_payload = SolverPayload(
        rendered_question=variant.rendered_question,
        option_a=variant.option_a,
        option_b=variant.option_b,
        option_c=variant.option_c,
        option_d=variant.option_d,
    )
    solver_a, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_GENERATION,
        system_prompt=_SOLVER_SYSTEM_PROMPT,
        payload=solver_payload,
        response_model=SolverResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None:
        return PipelineOutcome(
            status="rejected", reasons=[f"solver A call failed: {error}"], cost_cents=total_cost
        )
    solver_b, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_GENERATION,
        system_prompt=_SOLVER_SYSTEM_PROMPT,
        payload=solver_payload,
        response_model=SolverResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None:
        return PipelineOutcome(
            status="rejected", reasons=[f"solver B call failed: {error}"], cost_cents=total_cost
        )
    assert isinstance(solver_a, SolverResponse) and isinstance(solver_b, SolverResponse)

    objections = solver_objections(solver_a, solver_b, declared=variant.correct_option)
    if objections:
        return PipelineOutcome(status="rejected", reasons=objections, cost_cents=total_cost)

    # --- 4. Difficulty / Ambiguity / Curriculum-Alignment reviewers -------------
    difficulty_review, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_REVIEW,
        system_prompt=_DIFFICULTY_SYSTEM_PROMPT,
        payload=DifficultyReviewPayload(
            rendered_question=variant.rendered_question,
            option_a=variant.option_a,
            option_b=variant.option_b,
            option_c=variant.option_c,
            option_d=variant.option_d,
            skill_name=skill.name,
            proposed_difficulty=difficulty_label,
        ),
        response_model=DifficultyReviewResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None:
        return PipelineOutcome(
            status="rejected",
            reasons=[f"difficulty review failed: {error}"],
            cost_cents=total_cost,
        )
    assert isinstance(difficulty_review, DifficultyReviewResponse)
    if abs(difficulty_review.difficulty_label - difficulty_label) > 1:
        return PipelineOutcome(
            status="rejected",
            reasons=[
                f"difficulty reviewer rated {difficulty_review.difficulty_label}, too far "
                f"from proposed {difficulty_label}"
            ],
            cost_cents=total_cost,
        )

    ambiguity_review, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_REVIEW,
        system_prompt=_AMBIGUITY_SYSTEM_PROMPT,
        payload=AmbiguityReviewPayload(
            rendered_question=variant.rendered_question,
            option_a=variant.option_a,
            option_b=variant.option_b,
            option_c=variant.option_c,
            option_d=variant.option_d,
        ),
        response_model=AmbiguityReviewResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None:
        return PipelineOutcome(
            status="rejected", reasons=[f"ambiguity review failed: {error}"], cost_cents=total_cost
        )
    assert isinstance(ambiguity_review, AmbiguityReviewResponse)
    if ambiguity_review.is_ambiguous:
        return PipelineOutcome(
            status="rejected",
            reasons=[f"ambiguity reviewer flagged the question: {ambiguity_review.reasoning}"],
            cost_cents=total_cost,
        )

    alignment_review, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_REVIEW,
        system_prompt=_ALIGNMENT_SYSTEM_PROMPT,
        payload=AlignmentReviewPayload(
            rendered_question=variant.rendered_question,
            topic_name=topic.name,
            skill_name=skill.name,
        ),
        response_model=AlignmentReviewResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None:
        return PipelineOutcome(
            status="rejected", reasons=[f"alignment review failed: {error}"], cost_cents=total_cost
        )
    assert isinstance(alignment_review, AlignmentReviewResponse)
    if not alignment_review.is_aligned:
        return PipelineOutcome(
            status="rejected",
            reasons=[f"alignment reviewer flagged the question: {alignment_review.reasoning}"],
            cost_cents=total_cost,
        )

    # --- 5. Persist as pending (never auto-approved - see module docstring) -----
    repo = QuestionRepository(session)
    template_id = f"ai-{topic_id}-d{difficulty_label}-{seed}"
    template = await repo.create_template(
        QuestionTemplate(
            question_template_id=template_id,
            curriculum_version=curriculum.curriculum_version,
            topic_id=topic_id,
            skill_id=skill_id,
            grade_band=topic.grade_band,
            difficulty_label=difficulty_label,
            difficulty_confidence=1.0
            if difficulty_review.difficulty_label == difficulty_label
            else 0.5,
            question_type="multiple_choice",
            parameter_schema=parameter_schema,
            solution_function=proposal.shape_key,
            correct_option_generator=proposal.correct_option_generator,
            distractor_generators=distractor_keys,
            common_error_tags=proposal.common_error_tags,
            estimated_time_seconds=proposal.estimated_time_seconds,
            generator_model="bedrock-question-generation",
            review_model_versions={
                "difficulty": "bedrock-question-review",
                "ambiguity": "bedrock-question-review",
                "alignment": "bedrock-question-review",
            },
            validation_status="pending",
            active_status="active",
        )
    )
    persisted_variant = await repo.create_variant(
        QuestionVariant(
            # The newly authored template's defining rendering (D-106).
            origin=VARIANT_ORIGIN_CANONICAL,
            question_template_id=template.question_template_id,
            random_seed=variant.random_seed,
            rendered_question=variant.rendered_question,
            option_a=variant.option_a,
            option_b=variant.option_b,
            option_c=variant.option_c,
            option_d=variant.option_d,
            correct_option=variant.correct_option,
            parameter_values=variant.parameter_values,
        )
    )

    return PipelineOutcome(
        status="pending",
        question_template_id=template.question_template_id,
        question_variant_id=persisted_variant.question_variant_id,
        cost_cents=total_cost,
    )


async def _generate_authored_item(
    gateway: BedrockGateway,
    *,
    topic: object,
    skill: object,
    difficulty_label: int,
    spend: float,
) -> tuple[BaseModel | None, float, str | None]:
    """Stage 1 of authored mode: the one call that invents the question."""
    payload = AuthoredGeneratorPayload(
        topic_name=topic.name,  # type: ignore[attr-defined]
        skill_name=skill.name,  # type: ignore[attr-defined]
        grade_band=topic.grade_band,  # type: ignore[attr-defined]
        target_difficulty=difficulty_label,
        exemplars=_AUTHORED_FEW_SHOT_EXEMPLARS,
    )
    return await _call(
        gateway,
        task=BedrockTask.AUTHORED_QUESTION_GENERATION,
        system_prompt=_AUTHORED_GENERATOR_SYSTEM_PROMPT,
        payload=payload,
        response_model=AuthoredGeneratedItemResponse,
        session_spend_cents=spend,
        max_output_tokens=_AUTHORED_ITEM_MAX_TOKENS,
    )


async def generate_authored_candidate(
    *,
    session: AsyncSession,
    gateway: BedrockGateway,
    curriculum: CurriculumContent,
    topic_id: str,
    difficulty_label: int,
    seed: int,
    session_spend_cents: float,
    version: int = 1,
    skill_id: str | None = None,
) -> PipelineOutcome:
    """Runs one candidate through the S20 *authored* pipeline (plan §7): a real
    hand-quality stem/hint-ladder/solution instead of a parameterized shape (see this
    module's docstring for the two modes' relationship). Reuses the same
    `TOPIC_DIFFICULTY_SKILLS` topic/skill map the shape pipeline above uses (same scope
    limit - other topics raise `PipelineConfigError`, D-003/D-016). `version` lets
    `review_cli.py`'s edit-and-rerun action persist a new template that supersedes an
    existing one (plan §7 "Versioning/audit").

    Every rejection - even one before a `QuestionTemplate` row exists - is persisted as
    its own `question_validation_runs` row (`question_template_id=None` in that case;
    see the model's own docstring for why), satisfying ROADMAP S20's "rejected with
    persisted reasons" done-when criterion.
    """
    # D-186: an explicit `skill_id` is how a skill gets authored at an off-native tier.
    # Deriving from the tier is still the default and still correct for the 1:1 ladder, but
    # it *cannot* express multi-tier - once two skills share a tier the derivation has no
    # way to know which was meant, so the caller has to say. Validated against the authoring
    # plan rather than accepted verbatim: an unplanned (skill, tier) pair is a config error,
    # not a licence to generate content nothing will ever select.
    if skill_id is None:
        skill_id = TOPIC_DIFFICULTY_SKILLS.get(topic_id, {}).get(difficulty_label)
        if skill_id is None:
            raise PipelineConfigError(
                f"no registered skill for topic_id={topic_id!r} "
                f"difficulty_label={difficulty_label!r}"
            )
    else:
        planned = TOPIC_SKILL_DIFFICULTIES.get(topic_id, {}).get(skill_id)
        if planned is None:
            raise PipelineConfigError(
                f"no registered skill for topic_id={topic_id!r} skill_id={skill_id!r}"
            )
        if difficulty_label not in planned:
            raise PipelineConfigError(
                f"skill_id={skill_id!r} is not planned at difficulty_label="
                f"{difficulty_label!r} (planned: {planned})"
            )
    topic = next((t for t in curriculum.topics if t.topic_id == topic_id), None)
    skill = next((s for s in curriculum.skills if s.skill_id == skill_id), None)
    if topic is None or skill is None:
        raise PipelineConfigError(f"topic/skill not in curriculum taxonomy: {topic_id}/{skill_id}")

    spend = session_spend_cents
    total_cost = 0.0

    def _spend(cost: float) -> None:
        nonlocal spend, total_cost
        spend += cost
        total_cost += cost

    repo = QuestionRepository(session)

    async def _reject(
        reasons: list[str], stage_results: dict, stage: RejectionStage
    ) -> PipelineOutcome:
        await repo.create_validation_run(
            QuestionValidationRun(
                question_template_id=None,
                outcome="rejected",
                stage_results=stage_results,
                reasons=reasons,
                cost_cents=total_cost,
            )
        )
        return PipelineOutcome(
            status="rejected", reasons=reasons, cost_cents=total_cost, rejected_at=stage
        )

    # --- 1. Authored Generator Agent --------------------------------------------
    item, cost, error = await _generate_authored_item(
        gateway, topic=topic, skill=skill, difficulty_label=difficulty_label, spend=spend
    )
    _spend(cost)
    if error is not None or item is None:
        return await _reject([f"authored generator call failed: {error}"], {}, "generator")
    assert isinstance(item, AuthoredGeneratedItemResponse)
    item = shuffle_options(item, seed=seed)  # D-191's position-bias fix.

    rendered_question = f"{item.context_block}\n\n{item.stem}" if item.context_block else item.stem

    # --- 2. Deterministic gate (schema/markdown safety, SymPy solve, exactly-one- --
    # --- correct, leakage, hint-ladder monotonicity, hint/solution/answer          -
    # --- agreement, wordlist/readability - see authored_validation.py) ------------
    gate = validate_authored_item(difficulty_label, item)
    stage_results: dict = {"deterministic_gate": {"passed": gate.passed, "failures": gate.failures}}
    if not gate.passed:
        return await _reject(gate.failures, stage_results, "validation")

    if await repo.rendered_question_exists(rendered_question):
        stage_results["deduplication"] = {"passed": False, "reason": "exact text duplicate"}
        return await _reject(
            ["duplicate rendered_question (exact text match)"], stage_results, "dedup"
        )

    # --- 3. Near-duplicate check: embed the stem, cosine-compare against every ---
    # --- other authored template's stem in this topic -----------------------------
    try:
        embed_result = await gateway.create_embedding(texts=[item.stem], session_spend_cents=spend)
    except BedrockGatewayError as exc:
        stage_results["deduplication"] = {"passed": False, "error": str(exc)}
        return await _reject([f"stem embedding call failed: {exc}"], stage_results, "dedup")
    _spend(embed_result.cost_cents)
    stem_embedding = embed_result.vectors[0]
    if await repo.stem_near_duplicate_exists(
        topic_id, stem_embedding, threshold=NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD
    ):
        stage_results["deduplication"] = {
            "passed": False,
            "reason": "near-duplicate stem embedding",
        }
        return await _reject(
            ["near-duplicate stem (embedding cosine distance below threshold)"],
            stage_results,
            "dedup",
        )
    stage_results["deduplication"] = {"passed": True}

    # --- 4. Independent Solver Agents A and B, routed through two already- -------
    # --- distinct task/model slots so they resolve to different models -----------
    solver_payload = SolverPayload(
        rendered_question=item.stem,
        option_a=item.option_a,
        option_b=item.option_b,
        option_c=item.option_c,
        option_d=item.option_d,
    )
    solver_a, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_GENERATION,
        system_prompt=_SOLVER_SYSTEM_PROMPT,
        payload=solver_payload,
        response_model=SolverResponse,
        session_spend_cents=spend,
        max_output_tokens=_AUTHORED_REVIEW_MAX_TOKENS,
    )
    _spend(cost)
    if error is not None:
        return await _reject([f"solver A call failed: {error}"], stage_results, "solver")
    solver_b, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_REVIEW,
        system_prompt=_SOLVER_SYSTEM_PROMPT,
        payload=solver_payload,
        response_model=SolverResponse,
        session_spend_cents=spend,
        max_output_tokens=_AUTHORED_REVIEW_MAX_TOKENS,
    )
    _spend(cost)
    if error is not None:
        return await _reject([f"solver B call failed: {error}"], stage_results, "solver")
    assert isinstance(solver_a, SolverResponse) and isinstance(solver_b, SolverResponse)
    # The objection flags are recorded, not only the pick: a reviewer reading the evidence
    # for an accepted item should be able to see that both solvers found the answer and
    # found it unambiguous, rather than inferring it from the absence of a rejection.
    for name, solver in (("solver_a", solver_a), ("solver_b", solver_b)):
        stage_results[name] = {
            "selected_option": solver.selected_option,
            "no_option_matches": solver.no_option_matches,
            "is_unambiguous": solver.is_unambiguous,
        }

    objections = solver_objections(solver_a, solver_b, declared=item.correct_option)
    if objections:
        return await _reject(objections, stage_results, "solver")

    # --- 5. Judge: difficulty fit, ambiguity, alignment, age-appropriateness, ----
    # --- hint quality, all from one independent model call -----------------------
    judge_payload = QuestionJudgePayload(
        rendered_question=item.stem,
        option_a=item.option_a,
        option_b=item.option_b,
        option_c=item.option_c,
        option_d=item.option_d,
        hint_ladder=item.hint_ladder,
        canonical_solution=item.canonical_solution.final_answer,
        topic_name=topic.name,
        skill_name=skill.name,
        grade_band=topic.grade_band,
    )
    judge, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_JUDGE,
        system_prompt=_JUDGE_SYSTEM_PROMPT,
        payload=judge_payload,
        response_model=QuestionJudgeResponse,
        session_spend_cents=spend,
        max_output_tokens=_AUTHORED_REVIEW_MAX_TOKENS,
    )
    _spend(cost)
    if error is not None:
        return await _reject([f"judge call failed: {error}"], stage_results, "judge")
    assert isinstance(judge, QuestionJudgeResponse)
    stage_results["judge"] = judge.model_dump()

    judge_reasons: list[str] = []
    if judge.is_ambiguous:
        judge_reasons.append(f"judge flagged ambiguity: {judge.reasoning}")
    if not judge.is_aligned:
        judge_reasons.append(f"judge flagged misalignment: {judge.reasoning}")
    if not judge.is_age_appropriate:
        judge_reasons.append(f"judge flagged age-inappropriate content: {judge.reasoning}")
    if not judge.is_internally_consistent:
        judge_reasons.append(
            f"judge flagged the answer as impossible in the situation described: {judge.reasoning}"
        )
    if judge.hint_quality_score < _HINT_QUALITY_REJECT_BELOW:
        judge_reasons.append(f"judge rated hint quality {judge.hint_quality_score}, too low")
    if judge_reasons:
        return await _reject(judge_reasons, stage_results, "judge")

    # Difficulty is its own stage from here (D-194) rather than one more judge flag. Both
    # numbers and both rationales are persisted whatever the outcome, so a reviewer reading
    # a rejection can see the two readings that disagreed instead of a verdict.
    difficulty = judge_difficulty(
        proposed=item.proposed_difficulty,
        proposed_rationale=item.difficulty_rationale,
        reviewed=judge.reviewed_difficulty,
        reviewed_rationale=judge.difficulty_reasoning,
        requested=difficulty_label,
    )
    stage_results["difficulty"] = difficulty.as_evidence()
    stage_results["prerequisites"] = item.required_prerequisites
    if difficulty.decision == "rejected":
        return await _reject(difficulty.reasons, stage_results, "difficulty")

    review_priority = "normal"
    if judge.hint_quality_score <= _HINT_QUALITY_BORDERLINE_AT or difficulty.decision == "flagged":
        review_priority = "high"

    # --- 6. Persist as pending (never auto-approved - see module docstring) -----
    template_id = f"authored-{topic_id}-d{difficulty_label}-{seed}"
    template = await repo.create_template(
        QuestionTemplate(
            question_template_id=template_id,
            curriculum_version=curriculum.curriculum_version,
            topic_id=topic_id,
            skill_id=skill_id,
            grade_band=topic.grade_band,
            difficulty_label=difficulty_label,
            # Two independent readings agreeing is the only thing here worth calling
            # confidence; the requested tier is an instruction, not a second opinion.
            difficulty_confidence=1.0 if difficulty.decision == "accepted" else 0.5,
            question_type="multiple_choice",
            parameter_schema={},
            solution_function="authored",
            correct_option_generator="authored",
            distractor_generators=[],
            common_error_tags=item.misconception_tags,
            estimated_time_seconds=item.estimated_time_seconds,
            generator_model="bedrock-authored-question-generation",
            review_model_versions={
                "solver_a": "bedrock-question-generation",
                "solver_b": "bedrock-question-review",
                "judge": "bedrock-question-judge",
            },
            validation_status="pending",
            active_status="active",
            authoring_mode="authored",
            stem=item.stem,
            context_block=item.context_block,
            # The response field is `equation` (D-191); the column keeps its
            # original name, so the mapping is stated here rather than implied.
            answer_expression=item.equation,
            hint_ladder=item.hint_ladder,
            canonical_solution=item.canonical_solution.model_dump(),
            stem_embedding=stem_embedding,
            review_priority=review_priority,
            version=version,
        )
    )
    persisted_variant = await repo.create_variant(
        QuestionVariant(
            # The newly authored template's defining rendering (D-106), declared
            # explicitly rather than left to the column default, which is "runtime".
            # It used to be true that such a template "never gains runtime ones"; D-189
            # made it servable, so it now gains one row per showing and this flag is what
            # separates the reviewed content from an arbitrary student's rendering.
            origin=VARIANT_ORIGIN_CANONICAL,
            question_template_id=template.question_template_id,
            random_seed=seed,
            rendered_question=rendered_question,
            option_a=item.option_a,
            option_b=item.option_b,
            option_c=item.option_c,
            option_d=item.option_d,
            correct_option=item.correct_option,
            parameter_values={},
        )
    )
    await repo.create_validation_run(
        QuestionValidationRun(
            question_template_id=template.question_template_id,
            outcome="pending",
            stage_results=stage_results,
            reasons=[],
            cost_cents=total_cost,
        )
    )

    return PipelineOutcome(
        status="pending",
        question_template_id=template.question_template_id,
        question_variant_id=persisted_variant.question_variant_id,
        cost_cents=total_cost,
    )
