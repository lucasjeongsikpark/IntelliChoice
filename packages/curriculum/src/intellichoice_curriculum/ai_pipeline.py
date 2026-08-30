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
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Literal, NamedTuple

from intellichoice_db.models.questions import (
    VARIANT_ORIGIN_CANONICAL,
    QuestionTemplate,
    QuestionValidationRun,
    QuestionVariant,
)
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    AuthoredGeneratorPayload,
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    CircuitOpenError,
    EquationDesignPayload,
    EquationDesignResponse,
    QuestionJudgePayload,
    QuestionJudgeResponse,
    RepairContext,
    SolverPayload,
    SolverResponse,
    StructuredOutputError,
)
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_curriculum.authored_validation import (
    _is_whole_number,
    _option_matches,
    answer_leaked_beyond_the_question,
    arithmetic_identity,
    derive_answer,
    leak_phrase_present,
    route_answer,
    validate_authored_item,
)
from intellichoice_curriculum.content import (
    ANSWER_FAMILIES,
    DEFAULT_ANSWER_FAMILY,
    AnswerFamily,
    CurriculumContent,
    SkillDef,
    TopicDef,
    load_curriculum,
)

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

# topic_id -> skill_id -> the difficulty tiers that skill should carry content at, and
# skill_id -> the structure its equations must have.
#
# **Both are now DERIVED from the taxonomy rather than written here (D-274).** They used to
# be hand-maintained literals keyed by skill id, and that does not survive the full
# taxonomy: `generate_authored_candidate` raises `PipelineConfigError` for a skill missing
# from the tier map, so every new skill needed a Python edit before it could be generated
# at all. At 21 skills that was a nuisance; at 245 it is a second copy of the taxonomy that
# drifts from the first. `skills.yaml` already declares the topic/skill structure, so the
# tiers and the required equation shape now live next to the skill they describe.
#
# This is the same move D-232 made for `difficulty_anchors`, for the same stated reason: a
# rule kept next to the code that reads it is a rule nobody edits when they add content.
#
# The names are kept because they are the shape the planner and the tests already read, and
# because a *projection of one source* is not the duplication being removed. Callers that
# hold a `CurriculumContent` should prefer `curriculum.generation_plan()` and
# `SkillDef.structure`, which respect a caller-supplied taxonomy; these read the default one.
#
# Why the spans are not uniform, kept from D-186 because the reasoning still governs what
# goes in the YAML: `mastery_bootstrap` anchors `recommended_difficulty` on the modal
# assessed tier +/-1 and clamps to 1-5, so native-tier +/-1 is the entire range a skill can
# ever be recommended at - a fourth tier could not be selected by any student. Ladder ends
# stay single-tier because tier 1 has no neighbour below and tier 5 none above. And a span
# must be where the skill actually spans (D-223): claiming a range the skill does not have
# makes the tier decorative, and a decorative tier still routes a real student.
_DEFAULT_TAXONOMY = load_curriculum()

TOPIC_SKILL_DIFFICULTIES: dict[str, dict[str, list[int]]] = _DEFAULT_TAXONOMY.generation_plan()

SKILL_STRUCTURES: dict[str, str] = {
    skill.skill_id: skill.structure for skill in _DEFAULT_TAXONOMY.skills if skill.structure
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


# D-194 difficulty policy, changed in D-239 from reject-on-gap-2 to re-tier-and-flag.
#
# `_DIFFICULTY_FLAG_AT` is a real but survivable disagreement - the item is kept and a
# human is pointed at it. `_DIFFICULTY_RETIER_AT` is the gap at which the two readings stop
# being a judgement call: one of them is wrong about what the item demands.
#
# **What changed and why.** D-194 rejected at that gap. That threw away a question which
# had already passed the generator, both solvers and every judge flag, on the strength of
# one number being two away from the slot it happened to be generated for - and D-238
# measured what that number is worth. `place_value` items sat two tiers from where the
# judge read them because the *rubric* conflated two skills, not because the items were
# bad; the fix was to move tiers, and no item's content changed. The tier is the cheap
# thing to change and the item is the expensive one, so the gap now moves the item instead
# of discarding it - to the tier the judge read, held pending at `review_priority="high"`
# so a human still sees every one.
_DIFFICULTY_FLAG_AT = 1
_DIFFICULTY_RETIER_AT = 2

# D-231's dispersion control, and the reason a re-tier is not unconditional. A judge
# answering the same tier for everything produces small gaps on any bank centred near that
# tier and reads as excellent calibration; re-tiering on it would quietly restack a whole
# run onto one tier and report a high yield for having done so. So a move requires evidence
# that the instrument doing the moving is discriminating at all.
#
# **Dispersion, not distinctness** - D-231's first version fired only when the judge
# returned ONE tier for everything, and the first real run returned `{2: 20, 5: 1}`, which
# passed it while being a constant for every practical purpose.
_JUDGE_COLLAPSE_SHARE = 0.8
# Below this there is no histogram to speak of, and permitting a move would make re-tiering
# likeliest exactly where it is least supported - the first items of a run.
_MIN_JUDGE_OBSERVATIONS = 5


class JudgeDispersion:
    """The spread of the judge's own ratings so far in a run (D-231, D-239).

    Run-level evidence consumed by a per-item decision, so it is threaded through the run
    rather than recomputed: `run_plan` owns one instance and every candidate observes into
    it and asks it. That ordering has a property worth stating rather than discovering -
    **the first items in a run can never be re-tiered**, because the evidence that would
    justify moving them does not exist yet. A short run therefore moves nothing, which is
    the fail-closed direction (CLAUDE.md rule 5).

    Deliberately not persisted across runs. A histogram accumulated over months would let
    an instrument that has since drifted authorise today's moves.
    """

    def __init__(self) -> None:
        self._counts: dict[int, int] = {}

    def observe(self, reviewed: int) -> None:
        self._counts[reviewed] = self._counts.get(reviewed, 0) + 1

    @property
    def histogram(self) -> dict[int, int]:
        return dict(sorted(self._counts.items()))

    def permits_retier(self) -> bool:
        total = sum(self._counts.values())
        if total < _MIN_JUDGE_OBSERVATIONS:
            return False
        return max(self._counts.values()) / total < _JUDGE_COLLAPSE_SHARE


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
    decision: Literal["accepted", "flagged", "retiered", "rejected"]
    reasons: list[str]
    # The tier the item is actually stored at: `reviewed` when it moved, `requested`
    # otherwise. Computed here with the decision so the branch and the column cannot
    # disagree - the same reason the rest of this dataclass exists.
    effective_difficulty: int

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
            # The move itself, recorded rather than inferable. A reviewer opening this row
            # should not have to reconstruct which tier the row's own template ended up at
            # from two other fields and a rule about template ids.
            "stored_at_difficulty": self.effective_difficulty,
            "retiered_from": self.requested if self.decision == "retiered" else None,
        }


def judge_difficulty(
    *,
    proposed: int,
    proposed_rationale: str,
    reviewed: int,
    reviewed_rationale: str,
    requested: int,
    may_retier: bool = False,
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
    "does this item belong in the slot it was generated for?". An item the judge calls tier
    1 stored in the tier-5 slot would be selected for students who have earned tier 5 - but
    the answer to that is to store it at tier 1, which is what `slot_gap >= 2` now does when
    `may_retier` says the judge is discriminating (D-239).

    **`proposal_gap` no longer rejects, and the measurement is why (D-239).** Over all 41
    pipeline candidates that carry a difficulty stage, `requested == proposed` in **30** -
    the Generator is anchored, exactly as the note above predicts - and `proposal_gap`
    rejected independently of `slot_gap` **zero** times. Kept as a rejection it would have
    fired on the same items the re-tier exists to save, silently restoring the old
    behaviour for precisely those candidates. It still contributes to `flagged` and both
    numbers stay in the evidence, because `proposed`'s value was never the number: it is
    the *rationale* beside it, which is what a reviewer reads when the two readings differ.

    Acceptability is decided here rather than asked of the model, deliberately. A judge
    blind to the proposal *cannot* say whether it is acceptable, and a judge shown the
    proposal is no longer independent - so the question the instruction asks for is only
    answerable by arithmetic on two numbers, which is also the answer that cannot be
    argued out of (CLAUDE.md rule 2, deterministic core).
    """
    proposal_gap = abs(proposed - reviewed)
    slot_gap = abs(reviewed - requested)
    reasons: list[str] = []
    decision: Literal["accepted", "flagged", "retiered", "rejected"]
    effective = requested

    if slot_gap >= _DIFFICULTY_RETIER_AT:
        if may_retier:
            decision = "retiered"
            effective = reviewed
        else:
            decision = "rejected"
            reasons.append(
                f"judge rated difficulty {reviewed} ({reviewed_rationale}), too far from "
                f"the requested tier {requested} this candidate would be stored at, and "
                f"the judge's own ratings in this run are too collapsed to re-tier on"
            )
    elif proposal_gap >= _DIFFICULTY_FLAG_AT or slot_gap >= _DIFFICULTY_FLAG_AT:
        decision = "flagged"
        # D-302: the judge's tier is stored here too, not only on a re-tier. It used to keep
        # `requested`, which is what D-300 found: 10 of 16 sampled bank items carried the
        # *slot's* tier over a recorded judge disagreement, so "the judge does not reproduce
        # its own labels" was largely the judge being scored against a label it never
        # assigned. Bank-wide, 327 of 759 serving items were labelled this way (D-301).
        #
        # The user's decision, after seeing both measurements: follow the judge, accept that
        # the resulting tier distribution is uneven and biased, and fill the question count
        # instead. That last clause is load-bearing - storing the judge's tier moves 204 items
        # down against 104 up, which empties the top tiers, so it is only safe together with
        # `EXAM_QUESTION_COUNT` replacing the per-tier serving floor.
        effective = reviewed
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
        effective_difficulty=effective,
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
# The design call emits a sketch, an equation and a number - it does not need the item's
# budget, and keeping it small is most of why retrying here is affordable (D-200).
_EQUATION_DESIGN_MAX_TOKENS = 700
# A solver response is a few small fields plus a free-text `reasoning` (the generator's ran
# ~660 characters at tier 5, i.e. well inside 400 on its own). Raised from 800 once the
# questions became scenarios: a solver reading a *story* has to model it before it can
# answer, and one ran out of tokens mid-reasoning on the first run.
_AUTHORED_SOLVER_MAX_TOKENS = 1200

# **The judge no longer shares that ceiling (D-231), because it had outgrown it.** The
# comment here used to say the headroom was load-bearing and predicted exactly this: the
# judge writes two prose fields (`reasoning` first since D-193, then `difficulty_reasoning`)
# and checks the scenario's own constraints, so it writes far more than a solver.
#
# Measured with a 4000-token ceiling on one item from each topic: **1847, 2108 and 1822
# output tokens**. Against 1200 that is every judge call truncating, and a truncated judge
# is not a slow judge - `raw_generate` refuses to retry under the same ceiling, so the
# candidate is rejected *after* paying for equation design, generation and two solvers.
# Found by D-229's audit, which could not judge a single item; the same failure was live in
# the pipeline itself and had no symptom short of running it.
#
# Same class as D-195's shared 400-token ceiling, which made authored generation impossible
# for the same reason: one constant serving two stages whose output sizes differ by ~2x.
_AUTHORED_JUDGE_MAX_TOKENS = 4000

# D-233. The judge's two limits are coupled: raising the token ceiling makes the response
# longer, which makes the call slower, which is how D-231's fix turned a deterministic
# truncation into an intermittent timeout. Both were measured together, one item per topic
# under a 6000-token ceiling:
#
#   linear_equations         1922 tokens  15.0s
#   multiplication_division  1985 tokens  15.2s
#   fraction_operations      2407 tokens  18.8s
#   place_value              4370 tokens  34.3s
#
# `place_value` is the outlier because its items are short and its rubric is the least
# equation-like, so the judge writes more prose to justify a tier. 5000 tokens clears the
# worst observed by ~15%, and 90s clears the worst latency by ~2.5x - deliberately generous,
# because the failure mode is silent (empty error string) and the call is offline.
_AUTHORED_JUDGE_TIMEOUT_S = 90.0

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
    # Everything from here to the difficulty block was written against the first
    # four-candidate pilot's measured output (D-195), one sentence per observed failure.
    # The rules were all implicit before, and each was broken anyway - the gate caught
    # every one, but only after the item had been generated and paid for.
    #
    # Candidate 1 emitted four hints where the contract says three. The schema now bounds
    # the field, so this sentence is the same rule told to the model in words as well.
    "Write EXACTLY three hints - not two, not four. "
    # Candidate 2's third hint contained the answer verbatim. "Never leak the answer" was
    # already stated above and was still read as applying only to the stem, so the hint
    # ladder is spelled out here as its own progression with an explicit final level.
    "No hint may contain the final answer, the correct option's letter, or a value equal "
    "to the answer - not even the last one. Hint 1 orients the student in the situation, "
    "hint 2 names the relationship to write down, hint 3 sets up the equation and stops "
    "there. The third hint ends where the arithmetic begins. "
    # Candidate 2's stem contained "The question is adjusted to ask for the number of
    # rides after...". A deterministic check now rejects the blatant forms; this stops it
    # being written at all, which is cheaper than rejecting the whole candidate for it.
    "Student-facing text - stem, context, options, hints, solution steps - must read as a "
    "finished question written directly to a student. Never mention the question's own "
    "construction: no 'the question was adjusted', 'this version asks', 'as requested', "
    "no notes to a reviewer, no description of your own process. Explain your choices in "
    "`difficulty_rationale` and `reasoning`, which the student never sees. "
    # Candidate 4 described two people saving money without ever giving their starting
    # amounts or rates. Both solvers reported the item unanswerable and one set
    # `no_option_matches`. No deterministic check can catch this - a stem with a missing
    # premise is well-formed text - so the requirement is stated where it can still help.
    "The situation must contain EVERY number needed to reach one unique answer. Before "
    "you finish, reread the stem alone, as a student who cannot see your solution: if any "
    "starting amount, rate, or total is missing, the item is unanswerable - add it. "
    # Candidate 2's `equation` was `Eq((20 - 3) / 2, (25 - 7) / 2)`: no unknown, and false
    # besides (8.5 != 9). The gate rejects both, and the substitution check below is the
    # habit that prevents them.
    "The equation must model the story and contain EXACTLY ONE unknown, written as a "
    "letter. It is the relationship the scenario describes, never a restatement of the "
    "answer: `Eq(8 + 2*m, 18 + m)` is an equation, `Eq(17, 17)` and `Eq((20-3)/2, 9)` are "
    "not - they contain no unknown to solve for. Then verify: substitute your final "
    "answer back into the equation and confirm both sides are genuinely equal. If they "
    "are not, your item is wrong - fix it before emitting it. Confirm too that the answer "
    "appears exactly once among the four options. "
    # Nothing rejected the pilot's 8 cm by 18 cm "garden" - the judge was asked about
    # internal consistency and correctly said there was none to violate. Plausibility is
    # not deterministically checkable, so the only place to ask for it is here.
    "Use quantities and units a person would actually encounter: a garden is measured in "
    "metres, a pencil in centimetres, a journey in kilometres or minutes. An 8 cm by 18 cm "
    "'garden' is a seed tray - check that your numbers make sense at the scale of the "
    "thing you named. "
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
    "'solving one-step equations'). "
    # D-198. Stated as "fix the item", never "make the check pass" - the difference is the
    # whole point. A model told to satisfy a checker will satisfy the checker; the defect
    # list describes what is wrong with the *question*, and the instruction is to correct
    # the question. The commonest defect measured (D-197: 4 of 10 items) is an answer the
    # item's own equation does not produce, and the tempting cheap fix - relabel the
    # correct option to whatever the equation happens to give - is called out explicitly,
    # because it converts a wrong answer into a wrong *question* that passes the gate.
    # D-200. The instruction is deliberately absolute: the numbers arriving here have
    # already been solved deterministically, so any "improvement" to them is a regression
    # to the defect the stage was added to remove.
    "IF a `verified_design` block is present, its equation and answer have ALREADY been "
    "checked by an automatic solver. Build the question around them EXACTLY: use that "
    "equation, make `correct_option` the option whose text is that answer, and put that "
    "answer in `canonical_solution.final_answer`. Do NOT change the numbers, do NOT "
    "'improve' the arithmetic, and do NOT round anything. Your job is the writing - the "
    "scenario, the four options with a real mistake behind each distractor, the three "
    "hints, the worked solution, and the difficulty rationale. "
    "IF a `repair` block is present, you are correcting a specific earlier attempt, not "
    "writing a new question. Keep whatever was sound about it - the scenario, the "
    "characters, the shape of the mathematics - and fix exactly what the defects "
    "describe. Do not start over with an unrelated topic. "
    "If a `verified_design` is also present during a repair, its equation and answer are "
    "NOT the defect and must not change - fix only what the defect list describes. "
    "When a defect says your answer does not match your equation, the fix is to decide "
    "which one is right and correct the other, then recheck by substitution. Do NOT simply "
    "relabel the correct option to whatever the equation produces: if that value is a "
    "fraction, or negative, or impossible in your scenario, the *scenario's numbers* are "
    "what needs changing so the answer comes out whole and sensible. "
    "Re-verify everything before emitting, not only the part that was flagged - a repair "
    "that fixes one defect and introduces another is a wasted attempt."
)
# The 1-5 tier scale, stated once and used by BOTH the equation designer and the judge
# (D-200). One definition on purpose: before this, the judge rated on an implicit absolute
# scale (15 of 17 items scored "2") while the generator aimed at the requested tier, so the
# two were measuring different things and every tier-4/5 item was rejected by arithmetic.
# Handing the same anchors to the stage that *builds* the equation and the stage that
# *rates* it is what makes the comparison mean anything.
#
# Anchored on the structure of the equation, not the wrapping: every item here is a word
# problem (D-191 made the scenario mandatory), so "it is a word problem" is a constant, and
# a constant cannot discriminate. A first draft that used it rated a one-step item 3.
# These mirror the skill ladder in `TOPIC_DIFFICULTY_SKILLS`, which is where the tiers came
# from in the first place.


def judge_system_prompt(topic: TopicDef) -> str:
    """The judge prompt for one topic, whose 1-5 rubric comes from the topic itself.

    D-232 made this a function. It was a module constant carrying a single global
    `DIFFICULTY_ANCHORS` table written for `linear_equations` - correct for that topic, and
    applied unchanged to three topics that contain no equations, where it collapsed the
    judge onto a constant 2 (D-231 measured 20 of 21). The anchors now live in topics.yaml
    next to the topic they describe.
    """
    return (
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
        # D-202: taken over from a deterministic check that could not distinguish a stated
        # answer from a coincidence of digits. The instruction is about *function*, not about
        # characters, which is exactly what a rule could not express.
        "Set `hint_reveals_answer` true only if a hint actually GIVES the student the answer - "
        "states it, or reduces the problem to reading it off. A hint that repeats a number "
        "already printed in the question does NOT reveal anything: if the question says a "
        "4-pack and the answer happens to be 4, a hint mentioning the 4-pack is fine, because "
        "the student is already looking at that number. Judge what the hint does for a student "
        "who has read the question, not which digits appear in it. Explain your call in "
        "`hint_reveals_answer_reason`. "
        "Score hint_quality_score on a scale of 1 to 5, where 1 is a ladder that misleads or "
        "gives the answer away, 3 is usable but shallow, and 5 is a genuinely progressive "
        "ladder that guides without revealing. Do not use any other scale. "
        # The schema now puts `reasoning` first (D-193) so this instruction is followable;
        # stated here as well because the judge that missed a wrong answer had *found* it in
        # prose and still emitted the passing boolean. Naming the dependency explicitly is
        # cheap next to another item reaching a student.
        # D-233/D-234: the length bound is load-bearing, not style. Without it the judge's
        # `reasoning` expanded to fill whatever ceiling it was given - the same items
        # produced 1847, 2263, 4370 and then over 5000 tokens as the ceiling was raised
        # from 1200 - so every raise bought one more round of truncation at a higher price.
        #
        # **250 was measured, not chosen.** Three bounds over the same 25 `place_value`
        # items - the topic where the judge writes most, because its rubric is the least
        # equation-like:
        #
        #   unbounded   4 failures  37.4c  tiers {1:1,2:8,3:7,4:4,5:1}  exact 10/21
        #   250 words   1 failure   16.8c  tiers {1:6,2:10,3:4,4:3,5:1} exact 10/24
        #   150 words   0 failures  14.5c  tiers {1:8,2:12,3:2,4:3}     exact  8/25
        #
        # Cutting the reasoning cuts the discrimination (D-193's finding again): at 150 the
        # judge loses a tier entirely and collapses back toward 2. 250 keeps the full
        # five-tier spread at 45% of the unbounded cost. The one remaining failure is the
        # price of not paying 2x for the other three.
        "Keep `reasoning` under about 250 words and `difficulty_reasoning` under about 80. "
        "Working out the answer does not require narrating every step in prose. "
        "Write `reasoning` first and work the question out there, including solving "
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
        "fractional coefficients, the number of distinct steps), not how hard it feels. "
        # D-200, and the highest-leverage sentence in this prompt. Measured across six paid
        # runs: `reviewed_difficulty` was 2 in **15 of 17** items - distribution {1:1, 2:15,
        # 3:1} - while the generator's proposals spanned 1-5 and tracked the request sensibly.
        # A rater told to use a 1-5 scale and never told what the numbers *mean* falls back on
        # an absolute "how hard is mathematics" reading, and on that reading all of grade 6-7
        # linear algebra is a 2. The consequence was arithmetic, not a tendency: requested
        # tier 4 gives |4 - 2| = 2 and tier 5 gives 3, both at or over the rejection
        # threshold, so **no tier-4 or tier-5 item could ever pass, however good it was**. Six
        # runs, zero survivors above tier 2.
        #
        # The fix is a scale, not a hint: the anchors below describe structural features
        # visible in the item, and the judge is still never told which tier was requested, so
        # the reading stays independent (D-194) - it is now independent *and* calibrated
        # rather than independent and constant.
        "The 1-5 scale is RELATIVE TO THE GRADE BAND YOU ARE GIVEN, not to mathematics as a "
        "whole. A 2 does not mean 'easy for an adult'; it means 'the second-easiest thing a "
        "student at this grade band is asked to do'. Almost every item you see will be routine "
        "for you and that tells you nothing - rate the work the item demands of a student in "
        "that band, using these anchors: "
        # Anchored on the STRUCTURE OF THE EQUATION, deliberately. The first draft of this
        # rubric made tier 3 "the student must build the equation from the situation", and the
        # judge promptly rated a one-step item 3 - correctly, by that wording. Every item in
        # this bank is a word problem (D-191 made the scenario mandatory), so "it is a word
        # problem" is a constant and a constant cannot discriminate. These anchors mirror the
        # skill ladder in `TOPIC_DIFFICULTY_SKILLS` - one-step, two-step, negative/fractional
        # coefficients, variables on both sides, distribution - which is the ladder the tiers
        # were defined by in the first place.
        "Rate the EQUATION the student must solve, not the wrapping. Every item here is set in "
        "a story; that is the house style and it does NOT by itself raise the tier. A short "
        "preliminary calculation to get a number out of the scenario does not either. "
        + " ".join(f"{tier} = {text}." for tier, text in sorted(topic.difficulty_anchors.items()))
        + " "
        "Use the whole range. If an item genuinely sits between two anchors, choose the higher "
        "one when the extra step is structural and the lower one when it is only arithmetic. "
        # D-237, and the mirror image of D-200 above. D-200 defended the *bottom* of the scale
        # ("a 2 does not mean easy for an adult") and left the top undefended, so the judge
        # kept refusing it: measured over every tier-5 item in the bank, it returned
        # {2: 4, 3: 4, 4: 9} - **zero fives out of seventeen**. Four of those items require
        # distribution in the same algebraic form as tier 5's own worked example.
        #
        # It is not general miscalibration. The same run scored 13/16 exact on the d1/d2
        # control with tiers {1: 6, 2: 9, 3: 1}, so the scale is well anchored at the bottom
        # and specifically will not use its top. An anchored 1-5 whose 5 is never returned is
        # a four-point scale, and the loss is invisible in an aggregate agreement figure.
        "The top of the scale is ordinary, not exceptional. A 5 is simply the hardest "
        "structure a student in this grade band is asked for - it is not a distinction "
        "reserved for remarkable items, and a well-built bank has a meaningful share of them. "
        "If an item matches the tier-5 anchor, rate it 5. That the mathematics is routine for "
        "you is not a reason to withhold the top of the scale, and neither is a harder "
        "question you can imagine but are not looking at."
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

# SPEC §5.8.5/plan §7 judge thresholds on the 1 (poor) - 5 (excellent) hint-quality scale.
# The two do different jobs and only one of them decides anything:
#
# `_HINT_QUALITY_REJECT_BELOW` **rejects** the candidate (see the gate below). **D-252
# measured it and it has never fired**: 102 in-scale judge readings on real generated
# candidates (`question_validation_runs.stage_results->'judge'`, 2026-08-06 -> 08-10) plus
# D-249's 24 readings on the approved bank - 126 readings, **minimum observed 2, zero below
# it**. So the floor sits below the distribution's observed support. It is kept anyway, for
# D-240's reason: a live, correct, never-firing gate costs nothing and is the guard against a
# model regression. Zero in 126 is a ~2% upper bound, not a proof that a 1 is impossible.
#
# `_HINT_QUALITY_BORDERLINE_AT` **no longer routes anything.** It used to mean
# `review_priority="high"`, and this comment still said so for three sessions after **D-249
# removed that** - the score fires on 46% of human-approved bank items, so ordering by it
# told a reviewer nothing. Its only live consumer is `review_cli._review_flags`, which
# *prints* "at or below the borderline" next to the item. Display, not a decision.
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
    # D-200: the cheap pre-stage could not produce an equation that solves to a positive
    # whole number. Its own bucket because it is the one rejection that costs almost
    # nothing - conflating it with `generator` would hide the fact that the run failed
    # early and cheaply rather than late and expensively.
    "design",
    "budget",
    # D-199: the circuit breaker refused the call, so no model ever saw this candidate.
    # Its own bucket for the same reason "budget" has one - it is a *skip*, not a verdict
    # on a question. Measured cost of not having it: a run reported `generator=11` when
    # two candidates had actually been attempted and nine were refused after the breaker
    # opened, and the run read as "the model cannot produce anything" when it meant "the
    # model failed twice and the breaker did its job".
    "circuit_open",
    "unsupported_shape",
]


@dataclass
class PipelineOutcome:
    # `retiered` is a pending candidate that was stored at the tier the judge read rather
    # than the one its slot asked for (D-239). Its own status rather than a flag on
    # `pending`, because the run summary must be able to report it without the two
    # collapsing into one number - D-192's lesson, applied to a new bucket.
    status: Literal["pending", "retiered", "rejected"]
    reasons: list[str] = field(default_factory=list)
    rejected_at: RejectionStage | None = None
    question_template_id: str | None = None
    question_variant_id: str | None = None
    cost_cents: float = 0.0
    # The same evidence written to `question_validation_runs.stage_results`, carried back
    # to the caller (D-198). The repair loop needs two things from a rejection - which
    # qualitative objections were raised, and what the item said - and both already live
    # here. Returning them beats re-reading the row that was just written, and beats
    # widening the return type of a function with ten early exits.
    stage_results: dict = field(default_factory=dict)
    # How many Generator calls this slot consumed. 1 unless a repair attempt ran.
    attempts: int = 1
    # The equation the design stage settled on, whatever became of the candidate (D-273).
    # The runner feeds it to the next candidate of the same slot as `avoid_equations`, and a
    # rejected candidate's numbers are as used up as an accepted one's - so this is set on
    # every path that got as far as a design, not only on the ones that survived.
    equation: str | None = None
    # Recorded for the same reason as `equation`: the caller accumulates it to keep the
    # next candidate for this skill from reusing the setting (D-275).
    scenario_sketch: str | None = None


async def _call(
    gateway: BedrockGateway,
    *,
    task: BedrockTask,
    system_prompt: str,
    payload: BaseModel,
    response_model: type[BaseModel],
    session_spend_cents: float,
    max_output_tokens: int = _MAX_TOKENS,
    tools: list[dict] | None = None,
    timeout_s: float | None = None,
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
    # Forwarded only when asked for, so the `BedrockGateway` Protocol stays as narrow as it
    # was and every scripted test double keeps working unchanged (D-202).
    extra: dict = {"tools": tools, "tool_executor": execute_pipeline_tool} if tools else {}
    # Same reason, same shape (D-233): only the judge needs a longer timeout, so a caller
    # that does not ask keeps the gateway's own value and the Protocol keeps its narrow
    # signature.
    if timeout_s is not None:
        extra["timeout_s"] = timeout_s
    try:
        result = await gateway.generate_structured(
            task=task,
            system_prompt=system_prompt,
            payload=payload,
            response_model=response_model,
            max_output_tokens=max_output_tokens,
            session_spend_cents=session_spend_cents,
            **extra,
        )
    except BedrockGatewayError as exc:
        return None, exc.cost_cents, str(exc)
    return result.value, result.cost_cents, None


# D-202: the SymPy check the deterministic gate used to run *after* generation, offered to
# the model *during* it instead. Same solver, same `derive_answer`, different moment - the
# author can now ask "what does this equation actually come to?" while it still has the
# option to change the numbers, rather than being told afterwards that a candidate it had
# already finished writing was wrong.
SOLVE_EQUATION_TOOL: dict = {
    "toolSpec": {
        "name": "solve_equation",
        "description": (
            "Solve a one-unknown equation exactly, with SymPy. Use this to check your own "
            "arithmetic before you commit to an answer, and to check that each distractor "
            "is the value a specific mistake really produces. Returns the exact solution, "
            "whether it is a whole number, and any error."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "equation": {
                        "type": "string",
                        "description": (
                            "One equation with exactly one unknown letter, e.g. "
                            "'Eq(8 + 2*m, 18 + m)' or '8 + 2*m = 18 + m'."
                        ),
                    }
                },
                "required": ["equation"],
            }
        },
    }
}


def execute_pipeline_tool(name: str, arguments: dict) -> dict:
    """Run a tool the model asked for, here in our process (D-202).

    Deliberately tiny and total: it never raises, because a tool error is information the
    model should get back and reason about, not an exception that kills a paid call
    mid-conversation.
    """
    if name != "solve_equation":
        return {"error": f"unknown tool {name!r}"}
    equation = str(arguments.get("equation", ""))
    solved, error = derive_answer(equation)
    if solved is None:
        return {"equation": equation, "error": error or "could not be solved"}
    return {
        "equation": equation,
        "solution": str(solved),
        "is_whole_number": bool(solved.is_Integer),
        "is_positive": solved.is_positive is True,
    }


_EQUATION_DESIGN_SYSTEM_PROMPT = (
    "You are choosing the mathematics for ONE K-12 word problem, before anyone writes it "
    "up. Output only the skeleton: a one-sentence scenario sketch, what the unknown "
    "stands for, the equation that models it, and the answer. "
    "The equation must match the difficulty anchor and the skill structure you are given - "
    "they describe the STRUCTURE the equation must have, and an equation of the wrong "
    "structure is the wrong answer to this task however neat it is. "
    # D-304, and the shape is this session's recurring one: two parts of the system asking
    # for incompatible things, with the failure charged to the model. D-277 widened
    # `validate_equation_design` from "one equation, one unknown, one solution" to the full
    # router - a quadratic, an inequality, a system, a factorisation and a surd are all
    # designable - and left this prompt still demanding the first of those, in capitals.
    #
    # Measured on the C1 re-run: **12 of 21 failed design attempts** were the model trying to
    # express a derivative as `f(x) = 4*x**3 + ...` or `y = 15*x**2 + ...` and being told it
    # had "2 unknowns, expected exactly one". `calc_derivatives.structure` already said "a
    # bare EXPRESSION that is the derivative ... the answer is an expression, not a number";
    # the skill was right, the prompt overrode it, and `design=7 of 18` was the result.
    "MOST skills have a single unknown and a numeric answer, and the rules below are about "
    "those. But read the skill structure first: when it says the answer is an EXPRESSION "
    "rather than a number - a derivative, a factorisation, an integral - then the equation "
    "IS that bare expression, `final_answer` states the expression, and the numeric rules "
    "below do not apply to it. Follow the worked example the structure gives you. "
    # The measured defect this whole stage exists for. Across six paid runs the commonest
    # failure by far was a declared answer the item's own equation does not produce -
    # 21/5, 62/7, 12/5, -10/3, 50/13, 8/3 - i.e. the model picked numbers that do not
    # divide and then wrote down the answer it wanted instead of the one it had built.
    "WHEN THE ANSWER IS A NUMBER: choose numbers that come out even. Solve your own equation "
    "before you answer, and if the solution is a fraction, a negative, or zero, CHANGE YOUR "
    "NUMBERS and solve again - unless the skill's answer family says otherwise, the answer "
    "must be a positive whole number, because it will be counted in a real situation: trips "
    "to a shop, weeks of saving, cards swapped. Nobody makes 2.4 trips. "
    "Work the arithmetic in `reasoning` first, then state `final_answer` as a bare number "
    "with no units and no variable ('7', never 'x = 7' or '7 weeks'); put any unit in "
    "`answer_units`. "
    "If you are shown previous attempts, they FAILED the automatic solver for the reason "
    "given. Do not repeat those numbers - change the quantities so the arithmetic divides."
)


class EquationDesignError(Exception):
    """The design stage could not produce a usable equation within its attempt budget."""


class DuplicateTemplateIdError(IntegrityError):
    """A flush-time duplicate template id, carrying what the dropped candidate had spent.

    The collision surfaces inside `QuestionRepository.create_template`, which flushes, so
    it is raised while the candidate is still being built - *after* the design, generator,
    embedding, solver and judge calls have all been paid for. The caller's `outcome` is
    therefore never assigned, and before this type existed the cost was simply trapped in
    this module's locals when the exception escaped: `run_plan`'s duplicate branch had
    nothing to add to the run total or to the spend its budget check reads, so a duplicate
    silently bought a candidate the operator had not authorised (COST-06).

    A subclass of `IntegrityError` rather than a new exception hierarchy, so every existing
    `except IntegrityError` - `pipeline_cli.run_plan`'s branch, `_settle`'s commit-time one
    (D-193), any caller that never asked about cost - keeps catching it unchanged. The
    positional signature is the parent's, which is what `StatementError.__reduce__` passes.
    """

    def __init__(
        self,
        statement: str | None,
        params: object,
        # `StatementError` stores both as optional and `__reduce__` hands them straight
        # back, so the signature has to accept what the parent can produce.
        orig: BaseException | None,
        hide_parameters: bool = False,
        connection_invalidated: bool = False,
        code: str | None = None,
        ismulti: bool | None = None,
        *,
        cost_cents: float = 0.0,
    ) -> None:
        super().__init__(
            statement,
            params,  # type: ignore[arg-type]
            orig,  # type: ignore[arg-type]
            hide_parameters,
            connection_invalidated,
            code,
            ismulti,
        )
        self.cost_cents = cost_cents

    @classmethod
    def wrapping(cls, cause: IntegrityError, *, cost_cents: float) -> DuplicateTemplateIdError:
        """The same error, re-raised with the money attached and the message unchanged."""
        return cls(
            cause.statement,
            cause.params,
            cause.orig,
            cause.hide_parameters,
            cause.connection_invalidated,
            cause.code,
            cause.ismulti,
            cost_cents=cost_cents,
        )


def validate_equation_design(
    design: EquationDesignResponse,
    *,
    target_difficulty: int,
    family: AnswerFamily = ANSWER_FAMILIES[DEFAULT_ANSWER_FAMILY],
) -> list[str]:
    """Deterministic gate on the skeleton, before anything is written around it (D-200).

    This is the same `derive_answer` check the full item already faces, moved to where it
    is cheap. Measured across six runs: it was rejecting roughly half of all candidates
    *after* a ~2500-token authoring call had been paid for, and the design call it now
    guards is ~150 tokens. Nothing is weakened - the full item still faces every gate,
    including this one.

    **The number rules come from the skill's answer family (D-274), not from here.** They
    were a constant, with the note that a topic needing continuous answers would have to
    turn it into a parameter. That claim was already false when it was written: the shipped
    `fraction_operations` items answer `5/8`, and **26 of the 184 items in the bank fail the
    constant** - the pipeline could not regenerate 14% of its own content. `decimals`,
    `measurement` and the grade-5 word problems make it false three more times.

    The default keeps every existing caller's behaviour exactly: `counting` is
    whole-and-positive, which is what the constant said.

    **The answer MODEL comes from the router, not from `derive_answer` (D-277).** This gate
    used to require one equation, one unknown, one solution - the pre-Phase-R contract - while
    the item gate it claims to duplicate had already been widened to a router. Measured before
    the 6-8/9-12 taxonomy was written: **all five B-family forms are rejected here**, so a
    quadratic, an inequality, a system, a factorisation and a surd could each pass the item
    gate and none could ever be *designed*. That is the same defect as D-274's number rule -
    a rule scoped to one answer model, installed as universal - one dimension over.

    The number rules apply only to the `value` model, because they are claims about a number:
    an interval is not "positive", a factorisation is not "whole". For every other model the
    family is silent by construction, which is why no `symbolic` family is needed.
    """
    derivation, error = route_answer(design.equation)
    if derivation is None:
        return [error or f"equation {design.equation!r} could not be solved"]

    failures: list[str] = []
    # The same predicate the item gate uses, rather than a second comparison that would drift
    # from it (D-223). It reads `'3 or -3'` as a root set and `'(6, 4)'` as a tuple, which a
    # bare `_sympify` cannot.
    # **D-312: the second reading belongs here too, and leaving it out cost a whole skill.**
    # D-297/D-298/D-309 taught the *item* gate to read the notation D-288 requires of
    # student-facing text (`x²`, `7√2`, `3e^(4t)`) - and this call, which claims to be "the same
    # predicate the item gate uses", was left consulting the first reading only. Measured the
    # moment D-312's refusal fix got the model writing the right equation form:
    #
    #   equation '2*exp(3*t)' rejected: derives the symbolic answer 2*exp(3*t), but
    #   final_answer says '2e^(3t)' - they must state the same thing
    #
    # Both state the same thing. `2e^(3t)` is what D-288 *requires* the answer be written as, so
    # the design stage refused every correct exponential design in `calc_differential_equations`
    # - 8 of 10 candidates, after three other levers had each moved the failure one layer
    # deeper. Same ordering rule as `matching_options`: the first reading wins outright, and the
    # student reading is consulted only when it matched nothing, so this can turn a rejection
    # into a pass and never one pass into a different one (D-281).
    if not _option_matches(derivation, design.final_answer) and not _option_matches(
        derivation, design.final_answer, student_notation=True
    ):
        return [
            f"equation derives the {derivation.model} answer {derivation.payload}, but "
            f"final_answer says {design.final_answer!r} - they must state the same thing"
        ]

    if derivation.model != "value":
        return failures

    (solved,) = derivation.payload  # type: ignore[misc]
    if family.whole_numbers_only and not _is_whole_number(solved):
        failures.append(
            f"equation solves to {solved}, which is not a whole number - {family.guidance}"
        )
    elif family.positive_only and solved.is_positive is not True:
        failures.append(f"equation solves to {solved}, which is not positive - {family.guidance}")
    return failures


async def _design_equation(
    gateway: BedrockGateway,
    *,
    topic: TopicDef,
    skill: SkillDef,
    difficulty_label: int,
    spend: float,
    max_attempts: int,
    avoid_equations: Sequence[str] = (),
    avoid_scenarios: Sequence[str] = (),
) -> tuple[EquationDesignResponse | None, float, list[str]]:
    """Cheap loop: propose a skeleton, check it deterministically, retry with the reason.

    Retrying *here* is the point. The same retry after a full authoring call costs an order
    of magnitude more, which is why the pipeline previously threw the whole candidate away
    instead.

    `skill` was typed `object` and read through `getattr`, which is what a side table keyed
    by skill id costs at the call site. Now that the structure and the answer family live on
    the skill, the real type says what this needs (D-274).
    """
    total = 0.0
    previous: list[str] = []
    # Skill first, tier second: the skill fixes the shape of the equation and the tier says
    # how demanding the numbers inside it should be. Handing over only the tier is what
    # produced two different skills with one identical equation.
    #
    # `SKILL_STRUCTURES` is consulted only as a fallback, for a caller that passed a
    # taxonomy whose skills predate the field - the module-level view is built from the
    # default taxonomy and would otherwise disagree with a caller-supplied one.
    structure = skill.structure or SKILL_STRUCTURES.get(skill.skill_id, "")
    tier_anchor = topic.difficulty_anchors.get(difficulty_label, "")
    anchor = (
        f"REQUIRED STRUCTURE for this skill: {structure}. "
        f"For reference, tier {difficulty_label} on the shared 1-5 scale means: {tier_anchor}. "
        f"If the two ever seem to disagree, the required structure wins - it is what this "
        f"slot exists to teach - and the tier tells you only how demanding to make the "
        f"numbers within that structure."
        if structure
        else tier_anchor
    )
    if avoid_equations:
        # Stated in the anchor rather than left to `avoid_equations` alone, because a field
        # the prompt never mentions is a field the model can ignore - D-252 measured a
        # prompt clause protecting one field at 0 of 52 preserved, and the lesson there was
        # that structure beats asking. Here the structure *is* the sentence: the field
        # carries the data and this makes it an instruction rather than context.
        anchor = (
            f"{anchor} Another variant of this skill already uses "
            f"{', '.join(avoid_equations)}. Choose DIFFERENT numbers - a variant that "
            f"repeats the same calculation with a new story is the same question."
        )
    if avoid_scenarios:
        # The second half of the same lesson. Naming the numbers to avoid without naming
        # the settings produced 11 of 17 stems about cutting ribbon (D-275): the model
        # varied exactly what it was asked to vary and held everything else fixed.
        anchor = (
            f"{anchor} These settings are already used by this skill: "
            f"{'; '.join(avoid_scenarios)}. Choose a DIFFERENT everyday setting - renaming "
            f"the character while keeping the situation is the same story."
        )
    for _ in range(max_attempts):
        payload = EquationDesignPayload(
            topic_name=topic.name,  # type: ignore[attr-defined]
            skill_name=skill.name,  # type: ignore[attr-defined]
            grade_band=topic.grade_band,  # type: ignore[attr-defined]
            target_difficulty=difficulty_label,
            difficulty_anchor=anchor,
            previous_attempts=previous,
            avoid_equations=list(avoid_equations or ()),
            avoid_scenarios=list(avoid_scenarios or ()),
        )
        value, cost, error = await _call(
            gateway,
            task=BedrockTask.EQUATION_DESIGN,
            system_prompt=_EQUATION_DESIGN_SYSTEM_PROMPT,
            payload=payload,
            response_model=EquationDesignResponse,
            session_spend_cents=spend + total,
            max_output_tokens=_EQUATION_DESIGN_MAX_TOKENS,
            # D-205: the calculator belongs here, not on the authoring call. Probed 6 of 6
            # valid and 6 of 6 passing the deterministic gate on this six-field schema,
            # against 9 of 11 structured-output failures when the same model authored the
            # fifteen-field one. Arithmetic is this stage's whole job.
            tools=[SOLVE_EQUATION_TOOL],
        )
        total += cost
        if error is not None or value is None:
            # A provider failure is not a design failure. Recorded with the marker so the
            # caller can tell "the model proposed equations that would not divide" from
            # "the model was unreachable" - D-199 learned this on the generator stage, and
            # an AWS `ServiceUnavailableException` outage promptly proved the design stage
            # needed it too by reporting `design=8` when nothing had been designed.
            previous.append(f"{_CIRCUIT_OPEN_MARKER}: call failed: {error}")
            continue
        assert isinstance(value, EquationDesignResponse)
        failures = validate_equation_design(
            value, target_difficulty=difficulty_label, family=skill.family
        )
        if not failures:
            return value, total, []
        previous.append(f"equation {value.equation!r} rejected: {'; '.join(failures)}")
    return None, total, previous


# Prefix on the error string a circuit-open generator failure carries, so the one place
# that classifies the rejection does not have to match on the breaker's wording (D-199).
_CIRCUIT_OPEN_MARKER = "circuit_open"


class _GeneratorAttempt(NamedTuple):
    """One call's outcome. A `NamedTuple` rather than a fifth positional element because
    D-243's `schema_errors` was the point at which the tuple stopped being readable at the
    call site - `item, cost, error, model_id, digest = ...` is four chances to mis-order.
    """

    item: AuthoredGeneratedItemResponse | None
    cost_cents: float
    error: str | None
    model_id: str
    # Which fields broke which rules, when `error` is a structured-output failure (D-243).
    # Empty for every other kind of failure, which is what makes its presence meaningful:
    # a non-empty digest says the model answered and answered off-contract.
    schema_errors: list[str] = []


async def _generate_authored_item(
    gateway: BedrockGateway,
    *,
    topic: object,
    skill: object,
    difficulty_label: int,
    spend: float,
    repair: RepairContext | None = None,
    verified_design: EquationDesignResponse | None = None,
) -> _GeneratorAttempt:
    """Stage 1 of authored mode: the one call that invents the question.

    Returns the model id as a fourth element rather than going through `_call`, which
    discards it. It is wanted for the rejection evidence (D-195): "which model wrote this"
    is the first question asked of a rejected candidate, and with several models now
    configurable per role it cannot be inferred from the code. Empty string on failure -
    the `BedrockGateway` Protocol has no way to name the model for a call that never
    succeeded, and inventing one would be worse than admitting it is unknown.
    """
    payload = AuthoredGeneratorPayload(
        topic_name=topic.name,  # type: ignore[attr-defined]
        skill_name=skill.name,  # type: ignore[attr-defined]
        grade_band=topic.grade_band,  # type: ignore[attr-defined]
        target_difficulty=difficulty_label,
        exemplars=_AUTHORED_FEW_SHOT_EXEMPLARS,
        repair=repair,
        verified_design=verified_design,
    )
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.AUTHORED_QUESTION_GENERATION,
            system_prompt=_AUTHORED_GENERATOR_SYSTEM_PROMPT,
            payload=payload,
            response_model=AuthoredGeneratedItemResponse,
            max_output_tokens=_AUTHORED_ITEM_MAX_TOKENS,
            session_spend_cents=spend,
        )
    except CircuitOpenError as exc:
        # Distinguished from every other gateway failure before it is flattened to a
        # string: the caller has to tell "we asked and it went wrong" from "we never
        # asked", and by the time it is a message that distinction is a substring match.
        return _GeneratorAttempt(None, exc.cost_cents, f"{_CIRCUIT_OPEN_MARKER}: {exc}", "")
    except StructuredOutputError as exc:
        # The 41% case (D-240), carried structurally rather than only inside the message
        # so it groups in SQL. `OutputTruncatedError` is a subclass and lands here too,
        # correctly: its digest is empty, which is how "ran out of tokens" stays visibly
        # different from "answered off-contract".
        return _GeneratorAttempt(None, exc.cost_cents, str(exc), "", list(exc.schema_errors))
    except BedrockGatewayError as exc:
        return _GeneratorAttempt(None, exc.cost_cents, str(exc), "")
    return _GeneratorAttempt(result.value, result.cost_cents, None, result.model_id)


# Stages a repair attempt is allowed to act on (D-198). The exclusions carry the whole
# soundness argument, so they are stated rather than implied:
#
#   `difficulty` is **terminal**. The only feedback that would help is the judge's tier,
#   and handing that back is not repair - it is relabeling, and it destroys the blind
#   review D-194 built (the judge is unaware of the proposal precisely so its number is
#   independent). It is terminal for a measured reason too: D-197 found
#   `linear_both_sides` proposed-4/judged-2 four times across three sessions. That slot's
#   *authoring plan* is miscalibrated, not its items, so repairing them burns money on a
#   disagreement no rewrite resolves.
#
#   `dedup` is terminal because the defect is not in the item - it already exists.
#   `generator` is terminal because there is no item to repair.
_REPAIRABLE_STAGES: frozenset[str] = frozenset({"validation", "solver", "judge"})


def repair_feedback(
    *, stage: RejectionStage, reasons: list[str], stage_results: dict
) -> list[str] | None:
    """What a rejected candidate may tell the Generator about why it failed (D-198).

    Returns `None` when the stage is not repairable at all, so the caller stops rather
    than paying for an attempt that cannot help.

    **This is the trust boundary.** The raw `reasons` are written for a human reading an
    audit row and contain the independent checks' verdicts verbatim - `"independent solver
    disagreement: solver_a='b' solver_b='a' declared='a'"`, `"judge rated difficulty 2"`.
    Feeding those back would make the checks into targets: the cheapest resolution of the
    first is to change the declared answer to `b`, and of the second to relabel the tier.
    Neither fixes the item, both satisfy the gate, and the gate stops meaning anything.

    So the filter is by *kind of statement*, not by string matching:

    - Deterministic-gate failures pass through verbatim. They are mechanical facts about
      the item ("your equation solves to 21/5, you declared 7"), carry no verdict, and are
      the defects most worth repairing.
    - Solver and judge objections are re-stated qualitatively - *that* a solver could not
      find the answer, *why* it read as ambiguous - with every option letter and every
      difficulty number dropped.
    """
    if stage not in _REPAIRABLE_STAGES:
        return None

    if stage == "validation":
        # `reasons` here is `gate.failures`, which is exactly the deterministic output.
        return list(reasons)

    defects: list[str] = []
    if stage == "solver":
        # Read from the recorded flags rather than the reason strings, which is what keeps
        # the option letters out: `solver_objections` formats them into its messages, and
        # a filter that had to strip them back out would be one regex away from leaking.
        for name in ("solver_a", "solver_b"):
            result = stage_results.get(name) or {}
            if result.get("no_option_matches"):
                defects.append(
                    "An independent solver worked your question and could not find its "
                    "answer among your four options. Either your options do not contain "
                    "the answer your own scenario leads to, or the scenario does not lead "
                    "to a single answer."
                )
            if result.get("is_unambiguous") is False:
                defects.append(
                    "An independent solver found your question ambiguous - it could be "
                    "read in more than one way, or it did not contain everything needed "
                    "to reach one answer."
                )
        if not defects:
            # Reached when the solvers simply disagreed. Deliberately says nothing about
            # what either chose.
            defects.append(
                "Two independent solvers did not reach the same answer to your question. "
                "Re-read your stem as a student who cannot see your solution: it must "
                "lead to exactly one defensible answer."
            )
        return defects

    judge = stage_results.get("judge") or {}
    if judge.get("is_ambiguous"):
        defects.append("An independent reviewer found the question ambiguous.")
    if judge.get("is_aligned") is False:
        defects.append(
            "An independent reviewer found the question does not test the skill it was written for."
        )
    if judge.get("is_age_appropriate") is False:
        defects.append("An independent reviewer found the content unsuitable for the grade band.")
    if judge.get("is_internally_consistent") is False:
        defects.append(
            "An independent reviewer found the answer impossible in the situation you "
            "described - the arithmetic may be right while the scenario cannot produce "
            "that result."
        )
    if not defects:
        # The remaining judge rejection is a low hint-quality score. The number is the
        # verdict, so the defect is described instead.
        defects.append(
            "An independent reviewer rated your hint ladder too weak to guide a student. "
            "Each hint must add one genuinely new step toward setting up the equation."
        )
    return defects


def candidate_snapshot(
    item: AuthoredGeneratedItemResponse,
    *,
    topic_id: str,
    skill_id: str,
    requested_difficulty: int,
    seed: int,
    generator_model_id: str,
    planned_template_id: str,
    attempt: int = 1,
    repaired_defects: list[str] | None = None,
) -> dict:
    """The complete generated candidate, recorded as authoring evidence (D-195).

    A rejected candidate never becomes a `QuestionTemplate` row, so before this its content
    existed only inside the function that rejected it. The first four-candidate pilot made
    the cost concrete: four rejections, and afterwards the stems, options, hints and
    solutions could not be read back at all - the reasons said *that* a hint leaked the
    answer, never *which* hint or *what* answer. A pilot whose whole purpose is manual
    content review cannot discard the content.

    Deliberately a plain dict in the existing `stage_results` JSON column rather than a new
    table: the shape is authoring evidence read by a human, not something queried by
    column, and one nullable JSON key is a far smaller commitment than a schema migration
    for data whose fields will move as the Generator contract does.

    Taken **after** `shuffle_options` on purpose, so it is the item the gates actually
    judged - snapshotting the pre-shuffle order would record option labels that disagree
    with the solvers' recorded picks, which is exactly the confusion this exists to end.

    This is evidence, never content: nothing reads it back into a candidate, and the served
    YAML bank is exported from approved `QuestionTemplate` rows, which this never becomes.
    """
    return {
        "planned_template_id": planned_template_id,
        "attempt": attempt,
        "repaired_defects": list(repaired_defects or []),
        "topic_id": topic_id,
        "skill_id": skill_id,
        "requested_difficulty": requested_difficulty,
        "seed": seed,
        "generator_model_id": generator_model_id,
        "stem": item.stem,
        "context_block": item.context_block,
        "option_a": item.option_a,
        "option_b": item.option_b,
        "option_c": item.option_c,
        "option_d": item.option_d,
        "correct_option": item.correct_option,
        "equation": item.equation,
        "hint_ladder": list(item.hint_ladder),
        "canonical_solution": item.canonical_solution.model_dump(),
        "proposed_difficulty": item.proposed_difficulty,
        "difficulty_rationale": item.difficulty_rationale,
        "required_prerequisites": list(item.required_prerequisites),
        "misconception_tags": list(item.misconception_tags),
        "estimated_time_seconds": item.estimated_time_seconds,
    }


async def _attempt_authored_candidate(
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
    attempt: int = 1,
    repair: RepairContext | None = None,
    design: EquationDesignResponse | None = None,
    dispersion: JudgeDispersion | None = None,
    # D-294. The design call is made by the caller, once per slot, *before* this function
    # runs - so its cost was reaching `RunSummary` (via the caller's running total) and no
    # `question_validation_runs` row at all. Measured: a design attempt costs a median
    # 1.26c against an accepted row's 2.67c, so every accepted row understated its slot by
    # about a third, and the two spend numbers this project keeps disagreed by exactly that.
    #
    # Passed in for the *row* only, never added to the returned `PipelineOutcome` - the
    # caller already holds the design cost in its own running total, and adding it here too
    # would double-count it. The caller passes it on attempt 1 and zero afterwards, so a
    # repaired slot records the design once across its rows and `sum(rows) == the slot's
    # contribution to the run summary` holds either way.
    design_cost_cents: float = 0.0,
    # D-295: threaded through rather than derived, so every row a run writes carries the
    # run that wrote it. `None` for callers outside a batch (review_cli's edit-and-rerun),
    # which is a real state and not a gap.
    pipeline_run_id: str | None = None,
    # NOTE: this function does not read `avoid_equations`/`avoid_scenarios` and never
    # did - the design is handed to it already built, so both belong on
    # `generate_authored_candidate`, which is where the design call lives. The dead
    # `avoid_equations` parameter is removed here rather than joined by a second one.
) -> PipelineOutcome:
    """One pass: generate an item and run it through every gate (D-198 split this out of
    `generate_authored_candidate`, which is now the bounded repair loop around it).

    A repair attempt is a *fresh* pass, not a patch - every gate runs again on the new
    item, including the ones the previous attempt passed. Re-running only the failed gate
    would let a repair fix its reported defect while breaking something already verified,
    and that is exactly the failure a one-shot fixer produces.

    Runs one candidate through the S20 *authored* pipeline (plan §7): a real
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

    def _row_cost() -> float:
        """What this attempt's row should say the slot has spent so far (D-294).

        Distinct from `total_cost`, which is what the *caller* is told: the caller adds
        this attempt to a slot total it already owns, and the design cost is already in
        there. Only the row needs the sum, because a row is the only place a reader can
        see what a candidate cost after the run has ended.
        """
        return total_cost + design_cost_cents

    def _design_evidence() -> dict:
        """The design stage as row evidence, so a row explains its own cost (D-294).

        Without this the accepted rows carried design *money* and no design *record*,
        which is the state that made the 31% gap look like a mystery instead of an
        arithmetic error: 67 rows named the stage (the design failures, which return
        before this function) and 1,117 did not.
        """
        if design_cost_cents <= 0.0:
            return {}
        return {
            "equation_design": {
                "passed": True,
                "cost_cents": round(design_cost_cents, 4),
            }
        }

    repo = QuestionRepository(session)
    template_id = f"authored-{topic_id}-d{difficulty_label}-{seed}"

    # Set once the Generator has returned an item, and read by every later `_reject`
    # (D-195). Threading it through ten call sites would have meant ten chances to forget
    # it on the one path that mattered; a closure variable makes "every rejection after the
    # Generator succeeded carries the candidate" true by construction rather than by
    # discipline.
    snapshot: dict | None = None

    async def _reject(
        reasons: list[str], stage_results: dict, stage: RejectionStage
    ) -> PipelineOutcome:
        # Copied, then added to: the snapshot is one more key beside the stage evidence,
        # never a replacement for it. A reviewer needs both the content and the readings
        # that rejected it.
        evidence = dict(stage_results)
        evidence.update(_design_evidence())
        if snapshot is not None:
            evidence["candidate_snapshot"] = snapshot
        await repo.create_validation_run(
            QuestionValidationRun(
                question_template_id=None,
                outcome="rejected",
                stage_results=evidence,
                reasons=reasons,
                cost_cents=_row_cost(),
                pipeline_run_id=pipeline_run_id,
            )
        )
        return PipelineOutcome(
            status="rejected",
            reasons=reasons,
            cost_cents=total_cost,
            rejected_at=stage,
            stage_results=evidence,
        )

    # --- 1. Authored Generator Agent --------------------------------------------
    item, cost, error, generator_model_id, schema_errors = await _generate_authored_item(
        gateway,
        topic=topic,
        skill=skill,
        difficulty_label=difficulty_label,
        spend=spend,
        repair=repair,
        verified_design=design,
    )
    _spend(cost)
    if error is not None or item is None:
        # No item exists, so there is nothing to snapshot and nothing is invented. What is
        # persisted instead is the request that failed and the provider's exact words -
        # enough to tell "the model refused us" from "the model answered off-contract",
        # which are the same string to the caller and opposite problems (D-195).
        return await _reject(
            [f"authored generator call failed: {error}"],
            {
                "generator_request": {
                    "planned_template_id": template_id,
                    "topic_id": topic_id,
                    "skill_id": skill_id,
                    "requested_difficulty": difficulty_label,
                    "seed": seed,
                    "task": BedrockTask.AUTHORED_QUESTION_GENERATION.value,
                    "max_output_tokens": _AUTHORED_ITEM_MAX_TOKENS,
                    "provider_error": error,
                    # D-243. Its own key rather than only inside `provider_error`, because
                    # the question this exists to answer - *which* fields does the
                    # generator get wrong, across a whole run - is a `GROUP BY`, and a
                    # sentence with the digest glued on the end does not group.
                    "schema_errors": schema_errors,
                }
            },
            "circuit_open" if (error or "").startswith(_CIRCUIT_OPEN_MARKER) else "generator",
        )
    item = shuffle_options(item, seed=seed)  # D-191's position-bias fix.
    snapshot = candidate_snapshot(
        item,
        topic_id=topic_id,
        skill_id=skill_id,
        requested_difficulty=difficulty_label,
        seed=seed,
        generator_model_id=generator_model_id,
        planned_template_id=template_id,
        attempt=attempt,
        repaired_defects=list(repair.defects) if repair is not None else None,
    )

    rendered_question = f"{item.context_block}\n\n{item.stem}" if item.context_block else item.stem

    # --- 2. Deterministic gate (schema/markdown safety, SymPy solve, exactly-one- --
    # --- correct, leakage, hint-ladder monotonicity, hint/solution/answer          -
    # --- agreement, wordlist/readability - see authored_validation.py) ------------
    # D-202: the deterministic gate is gone. It ran here, between generation and the
    # solvers, and its checks now live in two better places - the SymPy solve is a tool the
    # author can call *while writing* (`SOLVE_EQUATION_TOOL`), and the content judgements
    # are the solvers' and judge's, which read the item as a student would.
    #
    # Recorded plainly because it is a real reduction in coverage, taken deliberately: the
    # solvers see only stem and options, so nothing mechanical now checks hint-ladder
    # length, hint monotonicity, whether the worked solution agrees with the answer key, or
    # sentence length. The judge sees the hints and the final answer and is asked about all
    # of it, but it is a model reading prose, not a rule. If items start reaching review
    # with four hints or a contradictory solution, this is the reason.
    # D-246 restores exactly one check of the gate D-202 removed, and no more.
    #
    # D-202's argument - that content judgements belong to the solvers and the judge, who
    # read the item as a student would - holds for ambiguity, alignment and difficulty. It
    # does not hold for "is the answer printed in the hint", which is a string fact with an
    # exact test that costs nothing and gives the same answer every call.
    #
    # **Measured, which is why it is back.** D-245 found the judge's `hint_reveals_answer`
    # sets true on 4 of 8 items a human had already approved, and answers *both ways* on 3
    # of them across identical calls. D-246 found it catches an outright stated answer
    # 32/32. So it is an excellent detector and a coin flip as a gate - and it was the
    # *only* thing looking, because `review_cli.approve` calls `activate_template` straight
    # on the database row and never re-runs the loader's copy of this check.
    #
    # `answer_text_leaked` is imported rather than reimplemented (D-223's rule). It already
    # carries two measured false-positive fixes in its lookarounds - a negative answer that
    # `\b` could never match, and a single digit inside a decimal - that a second copy here
    # would silently lack.
    # Two checks, run separately and unconditionally, exactly as `check_no_answer_leakage`
    # runs them in the loader. **D-249 correction:** D-246 merged them into a new
    # `hint_leaks_answer` helper, which was a duplicate - `answer_leaked_beyond_the_question`
    # has existed since **D-201**, with the same visibility rule and a docstring recording
    # that the naive check "destroyed four correct items before this existed". So D-246's
    # "finding" that the naive check rejects `1609201` was a rediscovery of D-201's, and its
    # fix was a second implementation of D-201's - in the same change that cited D-223 as the
    # reason to import rather than reimplement. Deleted; these are the originals.
    #
    # `rendered_question` is stem + context block and never the options, which the D-201
    # helper's docstring calls out: passing the options disables the check entirely, because
    # the correct option's text *is* the answer.
    answer_text = getattr(item, f"option_{item.correct_option}")
    hint_leaks = [
        f"hint_ladder[{n}] leaks the correct answer text verbatim"
        for n, hint in enumerate(item.hint_ladder)
        if leak_phrase_present(hint)
        or answer_leaked_beyond_the_question(
            hint_text=hint,
            correct_answer_text=answer_text,
            question_text=rendered_question,
        )
    ]
    if hint_leaks:
        stage_results: dict = {"deterministic_gate": {"passed": False, "failures": hint_leaks}}
        return await _reject(hint_leaks, stage_results, "validation")

    # **D-202's removal of the deterministic gate is reversed here, and D-276 is the
    # measurement that reversed it.** D-275 had restored one *presence* check on D-246's
    # narrow argument. Exporting the 3-5 wave showed the narrow version was not enough:
    # **7 of 344 bank items fail this gate, and 5 of them are wrong answer keys** -
    # an equation deriving `6*x - 48` for an item keyed "8 pencils", two options both
    # matching the derived 8848, options that are not unique, and two items whose derived
    # value cannot match a *label* option ("Museum B", "Odd").
    #
    # D-202 argued content judgements belong to the solvers and the judge, who read the item
    # as a student would. That holds for ambiguity and alignment. It does not hold for "does
    # the equation solve to the option you marked correct", which is arithmetic: it costs
    # nothing, gives the same answer every call, and the two solvers and the judge passed all
    # five of those items.
    #
    # The decisive argument is not coverage though - it is that `loader.py` runs exactly this
    # gate, so an item failing it **cannot be in the bank at all**. A pipeline applying a
    # weaker gate than the bank does not produce more content, it produces content that is
    # rejected later, after being paid for, reviewed, approved and exported. Two gates that
    # disagree about what a valid item is are worse than either alone; this makes them one
    # gate, called from both places (D-223's rule: share the predicate, not the intent).
    #
    # `check_difficulty_rubric_compliance` is included and does not fight the re-tier flow -
    # it asserts only that the tier is on the 1-5 scale and the time estimate is positive.
    #
    # Placed before the solvers deliberately: an item that cannot enter the bank should not
    # be paid for three more times first.
    gate = validate_authored_item(
        difficulty_label, item, answer_form=curriculum.answer_form(skill_id)
    )
    if not gate.passed:
        stage_results: dict = {"deterministic_gate": {"passed": False, "failures": gate.failures}}
        return await _reject(list(gate.failures), stage_results, "validation")

    stage_results: dict = {
        "deterministic_gate": {"passed": True, "checks": ["validate_authored_item"]}
    }

    if await repo.rendered_question_exists(rendered_question):
        stage_results["deduplication"] = {"passed": False, "reason": "exact text duplicate"}
        return await _reject(
            ["duplicate rendered_question (exact text match)"], stage_results, "dedup"
        )

    # D-286: the same sentence with different numbers, in a *different topic*. Free - one
    # indexed-scan query, no embedding call - and placed before the paid embedding below
    # for that reason. It closes the gap between the exact check above (global, but needs
    # the digits to match) and the cosine check below (fuzzy, but scoped to one topic),
    # which is precisely where three collisions landed in the shipped bank: "Liam has 9
    # stickers in his album..." reached both `g1_addition` and `g2_word_problems`.
    if duplicate_id := await repo.stem_skeleton_exists_in_another_topic(
        topic_id=topic_id, rendered_question=rendered_question
    ):
        stage_results["deduplication"] = {
            "passed": False,
            "reason": "same stem skeleton in another topic",
            "existing_question_template_id": duplicate_id,
        }
        return await _reject(
            [
                f"the same question with different numbers already exists in another topic "
                f"({duplicate_id}) - change the setting, not just the digits"
            ],
            stage_results,
            "dedup",
        )

    # --- 2b. Same calculation, different story (D-273) - WIRED ---------------------
    #
    # **The cause was fixed upstream first; this is the backstop, and it is now wired.** The
    # first wave produced 27 of 55 items sharing a number set, and every duplicate group was
    # a *same-slot pair* - seeds 6200/6201 both `6 + 7`, 6400/6401 both `9 + 9`.
    # `candidates_per_slot` is 2 and both candidates were receiving an identical design
    # payload, so the model had no reason to choose different numbers and did not.
    # `avoid_equations` tells each candidate what its slot-mate used, which removes the
    # reason rather than rejecting the result after paying for it. What it cannot remove is
    # a repeat **across slots or across runs**, which is what this catches.
    #
    # **The measurement that wired it (E5.2).** Over 102 labeled defects and 102 clean
    # controls, `arithmetic_identity` caught **17/17** near-duplicates at every cosmetic
    # severity, where the paid embedding check managed 8/17 - 6/6 on typography-only edits,
    # 2/6 once the protagonist is renamed, and **0/5** once the protagonist and the story
    # object are both renamed, which is the shape D-273 actually measured in production
    # output. It flagged 4 of the 102 clean controls, and all four were read by hand and are
    # real: two genuine duplicate pairs already in the approved bank, `Eq(x, 9 + 9)` and
    # `Eq(x, 30 + 40)`. Against its actual claim - "this arithmetic already exists in this
    # topic" - it made 0 false positives in 102, for one regex over an equation string.
    #
    # Free, and placed with the other free predicates before the paid embedding call for
    # that reason: a candidate that repeats a topic's arithmetic should not be embedded
    # first. The comparison is in Python rather than SQL because `arithmetic_identity` is
    # the predicate the E5.2 harness measured and a SQL re-implementation would be a second
    # copy of it (D-223).
    #
    # **Scoped to the topic**, like the embedding check beneath it and unlike the exact-text
    # check above. Two topics legitimately teach the same arithmetic - that is the
    # curriculum spiral, and D-286's docstring records the same argument for the skeleton
    # check - so a global identity check would reject correct content by design.
    #
    # Reported honestly: on the full 958-item approved bank this predicate finds 58
    # same-topic identity groups covering 133 items. That is a *content* finding about
    # already-approved material, not a regression, and it changes nothing at load time -
    # the loader's re-gate runs `validate_authored_item` and no dedup stage at all, so this
    # check is on the generation path only and cannot fail an existing bank item.
    if candidate_identity := arithmetic_identity(item.equation or ""):
        for existing_id, existing_equation in await repo.authored_equations_in_topic(topic_id):
            if arithmetic_identity(existing_equation) != candidate_identity:
                continue
            stage_results["deduplication"] = {
                "passed": False,
                "reason": "same arithmetic identity in this topic",
                "existing_question_template_id": existing_id,
                "arithmetic_identity": [list(part) for part in candidate_identity],
            }
            return await _reject(
                [
                    f"the same calculation already exists in this topic ({existing_id}) - "
                    f"same numbers, same operators, different story"
                ],
                stage_results,
                "dedup",
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
        # `rendered_question`, not `item.stem` (D-196). These were the stem alone, while
        # the student is served `context_block + stem` - so a generator that puts the
        # numbers in the context block and asks the question in the stem gave the solvers
        # an unanswerable fragment. Measured: the barrel item, whose stem is "After how
        # many hours will both barrels contain the same amount of water?" and whose 50 L /
        # 3 L-per-hour / 30 L / 5 L-per-hour all live in the context. Solver A reported
        # "the problem statement is incomplete" and was right about what it was shown; the
        # item itself is correct. The value was already computed above for exactly this
        # text and simply was not used here.
        rendered_question=rendered_question,
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
        max_output_tokens=_AUTHORED_SOLVER_MAX_TOKENS,
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
        max_output_tokens=_AUTHORED_SOLVER_MAX_TOKENS,
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
        # Same fix as the solvers, and the more serious half of it (D-196). The judge is
        # the gate that clears content for a student on ambiguity, alignment and
        # age-appropriateness - so judging the stem alone meant those verdicts were reached
        # about text that is not what gets served. An item could be approved on a fragment
        # and served with a context block the judge never read.
        rendered_question=rendered_question,
        option_a=item.option_a,
        option_b=item.option_b,
        option_c=item.option_c,
        option_d=item.option_d,
        correct_option=item.correct_option,
        hint_ladder=item.hint_ladder,
        canonical_solution=item.canonical_solution.final_answer,
        topic_name=topic.name,
        skill_name=skill.name,
        grade_band=topic.grade_band,
    )
    judge, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_JUDGE,
        system_prompt=judge_system_prompt(topic),
        payload=judge_payload,
        response_model=QuestionJudgeResponse,
        session_spend_cents=spend,
        max_output_tokens=_AUTHORED_JUDGE_MAX_TOKENS,
        timeout_s=_AUTHORED_JUDGE_TIMEOUT_S,
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
    # D-246: **not** a rejection any more. Measured at n=4 on 8 items a human had already
    # approved, this flag was true for 4 of them at least once and answered both ways on 3
    # - so rejecting on one call discards roughly half of paid, otherwise-passing content
    # on a coin flip. It stays a first-class signal and travels to the reviewer instead
    # (`review_priority="high"` below), which is D-239's move applied to a second gate that
    # turned out to be an excellent detector and a poor discriminator.
    #
    # Safe only because the deterministic check above now runs: an answer stated verbatim
    # is rejected before this point without asking a model. Restoring that was the
    # precondition for this line, not a separate improvement.
    if judge.hint_quality_score < _HINT_QUALITY_REJECT_BELOW:
        judge_reasons.append(f"judge rated hint quality {judge.hint_quality_score}, too low")
    if judge_reasons:
        return await _reject(judge_reasons, stage_results, "judge")

    # Difficulty is its own stage from here (D-194) rather than one more judge flag. Both
    # numbers and both rationales are persisted whatever the outcome, so a reviewer reading
    # a rejection can see the two readings that disagreed instead of a verdict.
    # The judge's rating joins this run's histogram BEFORE the gate reads it, so an item
    # contributes to the evidence that governs it. Excluding it would make the control
    # depend on arrival order for no gain: one observation cannot rescue a collapsed
    # histogram, and cannot collapse a dispersed one.
    if dispersion is not None:
        dispersion.observe(judge.reviewed_difficulty)
    difficulty = judge_difficulty(
        proposed=item.proposed_difficulty,
        proposed_rationale=item.difficulty_rationale,
        reviewed=judge.reviewed_difficulty,
        reviewed_rationale=judge.difficulty_reasoning,
        requested=difficulty_label,
        may_retier=dispersion is not None and dispersion.permits_retier(),
    )
    stage_results["difficulty"] = difficulty.as_evidence()
    stage_results["prerequisites"] = item.required_prerequisites
    if difficulty.decision == "rejected":
        return await _reject(difficulty.reasons, stage_results, "difficulty")

    # A re-tier is a disagreement a human still has to look at - the judge decided where
    # the item goes, and nobody has confirmed it belongs there.
    review_priority = review_priority_for(
        judge={
            "hint_reveals_answer": judge.hint_reveals_answer,
            "hint_quality_score": judge.hint_quality_score,
        },
        difficulty={"decision": difficulty.decision},
    )

    # --- 6. Persist as pending (never auto-approved - see module docstring) -----
    # `template_id` is computed once at the top of the function: the rejection evidence
    # needs the id the plan reserved for this candidate, and a second identical f-string
    # here would be two places to change the id format.
    pending_template = QuestionTemplate(
        question_template_id=template_id,
        curriculum_version=curriculum.curriculum_version,
        topic_id=topic_id,
        skill_id=skill_id,
        grade_band=topic.grade_band,
        # Where the judge read it when it moved, where the slot asked otherwise
        # (D-239). The `d{n}` in `template_id` still names the tier it was AUTHORED
        # at - D-235's rule, and the reason this column is the one to read.
        difficulty_label=difficulty.effective_difficulty,
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
    # `create_template` flushes, so a duplicate id is raised HERE - with every paid call of
    # this attempt already behind it - rather than at commit. Re-raised carrying that spend
    # because the caller never gets an `outcome` on this path: the cost used to stay in
    # these locals, so `run_plan`'s duplicate branch added nothing to the run total or to
    # the spend its budget check reads, and a collision quietly bought an unauthorised
    # candidate (COST-06). `_settle` still catches the same error arriving at commit time,
    # where an `outcome` does exist (D-193).
    try:
        template = await repo.create_template(pending_template)
    except IntegrityError as exc:
        raise DuplicateTemplateIdError.wrapping(exc, cost_cents=total_cost) from exc
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
    stage_results.update(_design_evidence())
    await repo.create_validation_run(
        QuestionValidationRun(
            question_template_id=template.question_template_id,
            outcome="pending",
            stage_results=stage_results,
            reasons=[],
            cost_cents=_row_cost(),
            pipeline_run_id=pipeline_run_id,
        )
    )

    return PipelineOutcome(
        # A re-tiered candidate is pending too - it is the *slot* that changed, not the
        # approval state - but the run has to be able to say how many moved (D-239).
        status="retiered" if difficulty.decision == "retiered" else "pending",
        question_template_id=template.question_template_id,
        question_variant_id=persisted_variant.question_variant_id,
        cost_cents=total_cost,
        stage_results=stage_results,
        attempts=attempt,
    )


# Repair is off unless asked for, so every existing caller keeps one-shot behaviour and
# turning it on is a deliberate, costed act (D-198).
DEFAULT_MAX_REPAIR_ATTEMPTS = 0
# D-200: on by default, unlike repair. Repair adds cost to buy a second chance; the design
# stage adds a ~150-token call that *removes* the ~2500-token calls that were being thrown
# away - roughly half of them, measured. Turning it off is the deliberate act here.
DEFAULT_DESIGN_ATTEMPTS = 3


def review_priority_for(*, judge: dict, difficulty: dict) -> str:
    """Where this candidate goes in the review queue (D-248).

    A pure function on the two evidence dicts, so the rule is testable without a gateway or
    a database - and so `review_cli`'s prose flags and this ordering cannot drift into
    disagreeing about what matters.

    **The bar is "could this reach a student and mislead them", not "did anything fire".**
    D-247 measured the previous rule at `high` on 26 of 29 pending candidates, and this
    field's only consumer is a sort (`list_pending_authored_templates` orders by
    `(review_priority == "high").desc()`), so it was putting 26 items ahead of 3 and telling
    a reviewer nothing.

    Difficulty disagreement drove 13 of those 29 on its own, and D-238 settled what it is
    worth: **the tier is a label; the item is the work.** An item whose two readings differ
    is a correct item that may be filed in the wrong place. It belongs in the queue with its
    reason printed (D-247's `_review_flags`), not at the front of it.

    **`retiered` is deliberately kept at `high`, and that is not a judgement of mine.** It
    was an explicit instruction in D-239: a candidate whose judged tier sits >= 2 from its
    slot's persists at the judge's tier, `review_priority="high"`. That is a different claim
    from `flagged` - the tier actually *moved*, on evidence strong enough to overrule the
    plan - and nothing measured here bears on it. (It has also never fired: D-240 found the
    re-tier live but untriggered, and the pending queue holds 19 `flagged` and 0 `retiered`.)
    """
    if difficulty.get("decision") == "retiered":
        return "high"
    if judge.get("hint_reveals_answer"):
        return "high"
    # D-249: `hint_quality_score <= 3` is NOT here, and its removal is measured rather than
    # argued. D-248 kept it and left `high` on 13 of 29. Judging an unbiased sample of the
    # hand-authored bank then put **46%** of human-written, human-reviewed, shipped items at
    # `<= 3` - against the pending queue's 45%. The two populations are indistinguishable on
    # this number, so it says nothing about the candidate; it says where this judge sits.
    #
    # It is still *shown* - `review_cli._review_flags` prints "hint quality N, at or below
    # the borderline" on every item that has it. What it no longer does is decide reading
    # order, because ordering by a signal that fires equally on approved content is the same
    # saturation D-247 found, one level down.
    return "normal"


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
    max_repair_attempts: int = DEFAULT_MAX_REPAIR_ATTEMPTS,
    budget_ceiling_cents: float | None = None,
    design_attempts: int = DEFAULT_DESIGN_ATTEMPTS,
    # Defaults to None - "no re-tiering" - so every existing caller keeps D-194's
    # behaviour unless a run explicitly opts in by owning a histogram (D-239).
    dispersion: JudgeDispersion | None = None,
    # Equations a sibling candidate of this same slot already used (D-273). Empty for the
    # first candidate of a slot, and for every caller that generates one item at a time.
    avoid_equations: Sequence[str] = (),
    avoid_scenarios: Sequence[str] = (),
    # D-295: one id per `run_plan` invocation, recorded on every row the run writes so
    # per-run dispersion, yield and spend stop needing reconstruction from timestamps.
    pipeline_run_id: str | None = None,
) -> PipelineOutcome:
    """One slot, with a bounded repair loop: when a candidate is rejected for something a
    rewrite could fix, the Generator is told what was wrong and tries again (D-198).

    **The slot keeps one template id across every attempt.** That is why the loop lives
    here rather than in `pipeline_cli.run_plan` - retrying at the plan level would need a
    fresh seed per attempt, and the seed *is* the id, so a repair would claim a slot the
    plan had already promised to another candidate.

    **Each attempt is fully gated and fully recorded.** A failed repair writes its own
    `question_validation_runs` row with its own snapshot and `attempt` number, so
    `make question-review-rejected` shows the whole history rather than only the last try.
    Only an attempt that clears every gate persists a template, and it persists as
    `pending` exactly as before - repair never approves anything.

    **What the Generator is told is filtered, not forwarded** - see `repair_feedback`. A
    stage with no safe feedback (`difficulty`, `dedup`, `generator`) ends the loop rather
    than paying for an attempt that cannot help.

    `budget_ceiling_cents` bounds the whole slot, repairs included: an attempt only starts
    if spend so far is still under it. Without it, per-slot cost is unbounded in a way the
    run budget - checked *between* slots - would not catch until after the money was gone.
    """
    attempt = 1
    spent = 0.0
    repair: RepairContext | None = None
    design: EquationDesignResponse | None = None
    # Hoisted out of the block below so the loop can hand it to the first attempt's row
    # (D-294). Stays 0.0 when the design stage is off or never reached a model, which is
    # exactly when there is no design cost to record.
    design_cost = 0.0

    if design_attempts > 0:
        topic = next((t for t in curriculum.topics if t.topic_id == topic_id), None)
        resolved_skill = skill_id or TOPIC_DIFFICULTY_SKILLS.get(topic_id, {}).get(difficulty_label)
        skill = next((s for s in curriculum.skills if s.skill_id == resolved_skill), None)
        if topic is not None and skill is not None:
            design, design_cost, design_failures = await _design_equation(
                gateway,
                topic=topic,
                skill=skill,
                difficulty_label=difficulty_label,
                spend=session_spend_cents,
                max_attempts=design_attempts,
                avoid_equations=avoid_equations,
                avoid_scenarios=avoid_scenarios,
            )
            spent += design_cost
            provider_only = all(
                f.startswith(_CIRCUIT_OPEN_MARKER) for f in design_failures
            ) and bool(design_failures)
            if design is None:
                # Cheap failure, and it stays cheap: nothing was authored around a
                # skeleton that could not be made to divide evenly, and no repair is
                # attempted because there is no item to repair.
                run = QuestionValidationRun(
                    question_template_id=None,
                    outcome="rejected",
                    stage_results={
                        "equation_design": {"passed": False, "attempts": design_failures}
                    },
                    reasons=[
                        "equation design never reached a model: " + "; ".join(design_failures[-1:])
                        if provider_only
                        else f"equation design failed after {design_attempts} attempts"
                    ],
                    cost_cents=spent,
                    pipeline_run_id=pipeline_run_id,
                )
                await QuestionRepository(session).create_validation_run(run)
                return PipelineOutcome(
                    status="rejected",
                    reasons=list(run.reasons),
                    cost_cents=spent,
                    rejected_at="circuit_open" if provider_only else "design",
                    stage_results=dict(run.stage_results),
                )

    # Set on every outcome below, so the runner learns what this slot's design chose even
    # when the candidate is later rejected (D-273). `design` is in scope from the block
    # above; it is None only on paths that returned before reaching this loop.
    designed_equation = design.equation if design is not None else None
    designed_scenario = design.scenario_sketch if design is not None else None

    while True:
        try:
            outcome = await _attempt_authored_candidate(
                session=session,
                gateway=gateway,
                curriculum=curriculum,
                topic_id=topic_id,
                difficulty_label=difficulty_label,
                seed=seed,
                session_spend_cents=session_spend_cents + spent,
                version=version,
                skill_id=skill_id,
                attempt=attempt,
                repair=repair,
                # Designed once, before the loop: the skeleton was already verified, so
                # re-designing per repair would pay again for the same check *and* hand the
                # repair a different equation - contradicting "keep what was sound and fix
                # the defect", which is the whole instruction a repair is given.
                design=design,
                dispersion=dispersion,
                # Attempt 1 only: the design was paid for once, so recording it on every
                # attempt's row would make a repaired slot look like it designed twice
                # (D-294).
                design_cost_cents=design_cost if attempt == 1 else 0.0,
                pipeline_run_id=pipeline_run_id,
            )
        except DuplicateTemplateIdError as exc:
            # The one exit from this loop that returns no outcome, so it is also the one
            # place `spent += outcome.cost_cents` below never runs. What the attempt itself
            # cost travels on the exception; what the slot spent before it - the design
            # call, and any earlier repair attempt - is only known here, so the caller is
            # told the whole figure rather than the last attempt's share (COST-06).
            exc.cost_cents += spent
            raise
        outcome.equation = designed_equation
        outcome.scenario_sketch = designed_scenario
        spent += outcome.cost_cents
        # Every attempt's spend counts, including the failed ones: the caller is paying for
        # the slot, not for its last try.
        outcome = replace(outcome, cost_cents=spent, attempts=attempt)

        # `retiered` is a success and must not fall into the repair loop: there is nothing
        # to repair - the item was accepted and the tier moved to meet it. Testing for
        # "pending" alone here would have paid for a rewrite of a candidate that had just
        # passed every gate.
        if outcome.status in ("pending", "retiered") or attempt > max_repair_attempts:
            return outcome

        defects = repair_feedback(
            stage=outcome.rejected_at or "generator",
            reasons=outcome.reasons,
            stage_results=outcome.stage_results,
        )
        if not defects:
            return outcome

        previous = outcome.stage_results.get("candidate_snapshot")
        if not previous:
            # Only reachable if the Generator itself failed, which `repair_feedback`
            # already refuses - but a repair with nothing to repair would silently become a
            # plain re-roll, and that should not depend on two checks agreeing.
            return outcome

        if budget_ceiling_cents is not None and session_spend_cents + spent >= budget_ceiling_cents:
            return replace(
                outcome,
                reasons=[
                    *outcome.reasons,
                    f"repair attempt {attempt + 1} not started: slot budget ceiling of "
                    f"{budget_ceiling_cents} cents reached",
                ],
            )

        repair = RepairContext(
            attempt=attempt,
            previous_stem=previous.get("stem", ""),
            previous_context_block=previous.get("context_block"),
            previous_equation=previous.get("equation"),
            previous_final_answer=(previous.get("canonical_solution") or {}).get(
                "final_answer", ""
            ),
            defects=defects,
        )
        attempt += 1
