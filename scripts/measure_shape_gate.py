"""Score the two text checks in the §5.8.5 *shape* gate in both directions (D-223).

Run with (free - no AWS, no database, no paid call):

    uv run python scripts/measure_shape_gate.py
    uv run python scripts/measure_shape_gate.py --samples 400 --show-flagged

`validation.py` is the shape-variant half of the §5.8.5 gate and `authored_validation.py` is
the authored-item half. They carry near-duplicate text checks, and every fix the authored
half received - the boundary bug in `answer_text_leaked` (D-079, then D-195's mirror image)
and the word-boundary fix to the disallowed-wording list (D-191, which lost a question about
rolling a die) - was made on the authored copy only. This script exists because "the same
bug, still live in the other copy" is not visible from either file alone.

**Why it is worth measuring rather than just fixing.** `validate_variant` has two non-test
callers: `loader.py:115`, where a failure raises `CurriculumLoadError` and fails the staging
deploy's curriculum-load ops task (D-206), and `ai_pipeline.py:992`, where a failure returns
`PipelineOutcome(status="rejected", cost_cents=total_cost)` - i.e. the generator call has
already been paid for and the item is thrown away *before* the two solver calls. A false
positive here is a cost bug, not a cosmetic one.

**Four classes, deliberately opposite expectations** (D-221's rule: scoring only the direction
you are trying to improve rewards a check that stops firing):

  pipeline      variants drawn from `ai_pipeline.SHAPE_PARAMETER_BOUNDS` - the exact
                population the paid gate sees. Every flag costs a generator call.
  bank          variants drawn from the shipped hand-authored shape banks (`TEMPLATE_BANKS`),
                the population the loader sees. The loader validates one fixed seed per
                template (`seed=index`), so a flag here is latent until a bank edit re-rolls
                it - and then it fails a deploy.
  leak/unsafe   hand-labelled positive controls that MUST stay flagged.
  clean/safe    hand-labelled negative controls that MUST NOT be flagged.

The first two measure a *flag rate* against a population with no independent oracle - the
fixed check would be its own oracle, which proves nothing. They are only meaningful together
with `--show-flagged`, which prints every distinct flagged rendering so the claim "these are
false positives" is inspected rather than asserted. The labelled classes carry the ground
truth.
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass

from intellichoice_curriculum.ai_pipeline import SHAPE_PARAMETER_BOUNDS
from intellichoice_curriculum.generation import (
    GeneratedVariant,
    VariantGenerationError,
    generate_variant,
)
from intellichoice_curriculum.loader import TEMPLATE_BANKS
from intellichoice_curriculum.validation import (
    ValidationResult,
    check_age_appropriate_wording,
    check_no_answer_leakage,
)

_DISTRACTORS = ["distractor_sign_flip", "distractor_off_by_one", "distractor_scaled"]


@dataclass(frozen=True)
class LabelledCase:
    """A rendered question plus the answer text and what the gate must decide."""

    rendered_question: str
    correct_text: str
    should_flag: bool
    why: str


# Positive controls: the template bug this check exists for - the solved value rendered into
# the question itself. Includes the formats `format_integer` can actually produce (negative
# integers, and the `str(Fraction)` form) because that is where the boundary assertions bite.
LEAK_CASES = (
    LabelledCase("Solve for x: x + 3 = 10, x = 7", "7", True, "solved value appended"),
    LabelledCase("Solve for x: 2x = 14 (x=7)", "7", True, "no spaces around ="),
    LabelledCase("Solve for x: 2x = 14  (x  =  7)", "7", True, "extra spaces around ="),
    LabelledCase("Solve for x: 2x = -14, x = -7", "-7", True, "negative answer stated"),
    LabelledCase("Solve for x: 4x = 2, x = 1/2", "1/2", True, "fraction answer stated"),
    LabelledCase("Solve for x: x - 1 = 11, so x = 12.", "12", True, "sentence-final period"),
)

# Negative controls. Every one of these is a correct, servable question; a flag destroys it
# and, on the pipeline path, bins a paid generator call.
CLEAN_CASES = (
    LabelledCase("Solve for x: 10x = -60", "-6", False, "answer is a prefix of the RHS"),
    LabelledCase("Solve for x: 11x = -55", "-5", False, "the case D-222 found live"),
    LabelledCase("Solve for x: 5x = 55", "11", False, "answer nowhere in the stem"),
    LabelledCase("Solve for x: 2x = 70", "7", False, "answer is a prefix of the RHS"),
    LabelledCase("Solve for x: x + 5 = 12.5", "12", False, "answer is a decimal's integer part"),
    LabelledCase("Solve for x: 2x = 11/2", "11", False, "answer is a fraction's numerator"),
    LabelledCase("Solve for x: x + 7 = 14", "7", False, "answer equals a given coefficient"),
    LabelledCase("Solve for x: 5x = 25", "5", False, "the 'Solve for x:' prefix collision"),
)

# The wording check's controls. "die" is the word D-191 removed from the authored list after
# it destroyed a question about rolling a die; "skill" contains "kill" and "studies" contains
# "die", which is why substring matching cannot be used here either.
SAFE_WORDING = (
    "A number cube (die) is rolled and lands on 4. Solve for x: x + 4 = 11",
    "Maya studies for x hours a week. Solve for x: 3x = 12",
    "Her skill at chess improves by x points. Solve for x: x + 5 = 20",
    "The diet plan adds x grams. Solve for x: 2x = 8",
    "Solve for x: x + 3 = 10",
)
UNSAFE_WORDING = (
    "A soldier killed x enemies. Solve for x: x + 1 = 4",
    "That is a stupid way to solve for x: x + 1 = 4",
    "A dumb question. Solve for x: x + 1 = 4",
    "The character dies after x turns. Solve for x: x + 1 = 4",
)


def _variant_from(rendered_question: str, correct_text: str) -> GeneratedVariant:
    """The two checks under test read only `rendered_question` and the correct option's
    text, so a labelled case needs no shape, no schema and no solvable equation - which is
    the point: these are text checks and must be scored as text checks.
    """
    return GeneratedVariant(
        random_seed=0,
        rendered_question=rendered_question,
        option_a=correct_text,
        option_b=f"{correct_text} (b)",
        option_c=f"{correct_text} (c)",
        option_d=f"{correct_text} (d)",
        correct_option="a",
        parameter_values={},
    )


def _flags_leak(variant: GeneratedVariant) -> bool:
    result = ValidationResult()
    check_no_answer_leakage(variant, result)
    return not result.passed


def _flags_wording(rendered_question: str) -> bool:
    result = ValidationResult()
    check_age_appropriate_wording(_variant_from(rendered_question, "7"), result)
    return not result.passed


def _sample_pipeline(samples: int, rng: random.Random) -> list[GeneratedVariant]:
    """The population `ai_pipeline` puts through the gate: every registered shape under its
    own deterministic bounds, with the only registered correct-option generator.
    """
    variants = []
    for shape_key, schema in SHAPE_PARAMETER_BOUNDS.items():
        for _ in range(samples):
            try:
                variants.append(
                    generate_variant(
                        shape_key=shape_key,
                        parameter_schema=schema,
                        correct_option_generator="format_integer",
                        distractor_generator_keys=_DISTRACTORS,
                        seed=rng.randint(0, 10**6),
                    )
                )
            except VariantGenerationError:
                continue
    return variants


def _sample_bank(samples: int, rng: random.Random) -> list[GeneratedVariant]:
    """The population the loader puts through the gate: the shipped shape banks."""
    variants = []
    for templates in TEMPLATE_BANKS.values():
        for template in templates:
            for _ in range(samples):
                try:
                    variants.append(
                        generate_variant(
                            shape_key=template.solution_function,
                            parameter_schema=template.parameter_schema,
                            correct_option_generator=template.correct_option_generator,
                            distractor_generator_keys=template.distractor_generators,
                            seed=rng.randint(0, 10**6),
                        )
                    )
                except VariantGenerationError:
                    continue
    return variants


def _correct_text(variant: GeneratedVariant) -> str:
    return str(getattr(variant, f"option_{variant.correct_option}"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=200, help="variants per template/shape")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument(
        "--show-flagged",
        action="store_true",
        help="print every distinct flagged rendering, so a flag rate can be inspected",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    failures: list[str] = []

    print("== answer-leak check ==")
    for name, variants in (
        ("pipeline", _sample_pipeline(args.samples, rng)),
        ("bank", _sample_bank(args.samples, rng)),
    ):
        flagged = [v for v in variants if _flags_leak(v)]
        rate = 100 * len(flagged) / len(variants) if variants else 0.0
        print(f"  {name:<10} {len(flagged):>5} flagged / {len(variants):>6} sampled  ({rate:.2f}%)")
        if args.show_flagged and flagged:
            distinct = sorted({(v.rendered_question, _correct_text(v)) for v in flagged})
            for question, answer in distinct[:20]:
                print(f"      {question!r} answer={answer!r}")
            if len(distinct) > 20:
                print(f"      ... and {len(distinct) - 20} more distinct")

    for label, cases in (("leak (must flag)", LEAK_CASES), ("clean (must not)", CLEAN_CASES)):
        wrong = [
            c
            for c in cases
            if _flags_leak(_variant_from(c.rendered_question, c.correct_text)) != c.should_flag
        ]
        print(f"  {label:<18} {len(cases) - len(wrong)}/{len(cases)} correct")
        for case in wrong:
            print(
                f"      MISS {case.rendered_question!r} "
                f"answer={case.correct_text!r} ({case.why})"
            )
            failures.append(f"leak/{case.why}")

    print("== age-appropriate wording check ==")
    for label, texts, expected in (
        ("safe (must not)", SAFE_WORDING, False),
        ("unsafe (must flag)", UNSAFE_WORDING, True),
    ):
        wrong = [t for t in texts if _flags_wording(t) != expected]
        print(f"  {label:<18} {len(texts) - len(wrong)}/{len(texts)} correct")
        for text in wrong:
            print(f"      MISS {text!r}")
            failures.append(f"wording/{text[:40]}")

    if failures:
        print(f"\n{len(failures)} labelled case(s) wrong")
        return 1
    print("\nevery labelled case correct")
    return 0


if __name__ == "__main__":
    sys.exit(main())
