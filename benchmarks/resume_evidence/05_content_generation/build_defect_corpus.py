"""E5.2 - build the labeled mutation corpus the defect-detection benchmark is scored on.

    uv run python benchmarks/resume_evidence/05_content_generation/build_defect_corpus.py \
      --out docs/resume_evidence/05_content_generation/defect_corpus.jsonl

Free: reads `curriculum/internal_math/authored/*.yaml`, calls no model, touches no database,
and writes exactly one JSONL file plus an optional summary JSON. **Nothing here writes to the
bank or to any question table** - every mutated item exists only in memory and in the corpus
artifact.

## What the corpus is for

The recorded negative control for the authoring pipeline is `audit_authored_bank.py
--self-test`: it moves every declared answer to a wrong option and counts how many the solver
panel objects to. That produced 12/12 (D-229) and is real evidence, but it measures **one
defect class, in one direction, at n=12**. It cannot produce a precision number at all,
because it never shows the detectors an item that is fine.

This builds the missing half and widens the first: six labeled defect classes plus an
equal-size clean control set, drawn from the same approved bank, so every detector can be
scored both ways (D-221: score the direction you are not trying to prove, and treat the
negative controls as a first-class number rather than decoration).

## The six classes, and why each one is a defect worth measuring

Each class is chosen because a *different* stage of the pipeline is the only thing that can
catch it. A benchmark whose defects all die at the same check measures that check twice.

- `wrong_numeric_answer` - the declared `correct_option` is re-pointed at a distractor. The
  continuity anchor: this is exactly D-229's class and exactly what `--self-test` seeds, so
  the solver-panel recall reported here is comparable with the recorded 12/12. SymPy
  re-derivation also catches it, which is the D-276 finding (with the deterministic gate off,
  five items of this class passed both blind solvers *and* the judge).
- `no_correct_option` - every option's first numeral is shifted by one delta, so the derived
  answer is absent from all four. Distinct from the above: a solver that works the question
  out honestly cannot express "none of these" as a vote, which is why `SolverResponse` grew
  `no_option_matches` (D-193). This class is what that field exists for.
- `mismatched_solution` - `canonical_solution` is replaced wholesale by another item's. The
  deterministic gate's `check_hint_solution_answer_agreement` is the only thing that looks at
  it; the solver panel is never shown the solution, so its recall here should be ~0 by
  construction, and measuring that is the point.
- `mismatched_hint_ladder` - `hint_ladder` is replaced by another item's, chosen so its
  numerals do not occur in this item's question or equation. **Nothing in the deterministic
  gate ties a hint to its stem** (`hint_ladder_monotonicity_violations` is verbatim
  containment and says so in its own docstring), and the solver panel is not shown hints
  either. This class is here to measure a hole, not to be caught.
- `contradictory_constraints` - one numeral in the stem is shifted, leaving the equation,
  options and answer key untouched, so the story now states a quantity the declared equation
  does not model. This is the class SymPy *structurally cannot* catch - the equation still
  derives its declared answer - and it is the one `check_sympy_independent_solve`'s own
  docstring warns about ("it verifies equation -> answer, never situation -> equation"). The
  blind solver panel reads the stem and is the only detector that can see it.
- `near_duplicate` - a clean control cloned with cosmetic edits at three graded severities
  (typography only / person-name swap / name + story-object swap, the last being the shape
  D-273 measured at 27 of 55 items sharing a number set). Neither the gate nor the solvers
  can see this: a near-duplicate is a *valid* item, and the defect is relational. Only the
  embedding-distance check can, which is why the severities are graded - the interesting
  number is where `NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD = 0.05` stops firing.

Deliberately **not** included: hint answer leakage. D-246 already measured that class at
32/32 against this same gate, the gate check is free and unchanged, and re-buying solver
calls for a class with recorded evidence would spend this experiment's budget on the least
uncertain thing in it.

## What makes a mutation trustworthy

Every mutation is verified against the real gate before it is admitted to the corpus, not
asserted by construction:

- a class whose defect the gate *must* see is admitted only if `validate_authored_item`
  actually fails, and only if the failure names the intended check;
- `contradictory_constraints` carries a **shadow equation** - the declared equation with the
  same numeral shifted - and is admitted only if that shadow derives a *different* answer.
  Without it, "perturbed the stem" could mean "perturbed it into an equivalent problem", and
  the item would be scored as an undetected defect while not being a defect at all;
- `near_duplicate` is admitted only if the clone still *passes* the gate, because a
  near-duplicate that fails the gate would be counted as a gate catch for the wrong reason;
- every source item is itself gate-clean before mutation, so a failure after mutation is
  attributable to the mutation.

Sources are sampled stratified over (topic, difficulty) from the 918 bank items where the
deterministic checks apply, and the clean-control block is **disjoint** from every mutation
source. That disjointness is load-bearing for the dedup detector: the clean controls are the
reference set standing in for "the approved bank", so a mutated item whose source were also a
control would register as a duplicate of itself.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from intellichoice_curriculum.authored_bank import AuthoredTemplateDef, load_authored_bank
from intellichoice_curriculum.authored_validation import (
    AuthoredValidationResult,
    DerivedAnswer,
    arithmetic_identity,
    resolved_matches,
    route_answer,
    validate_authored_item,
)
from intellichoice_curriculum.content import CurriculumContent, load_curriculum

# --- corpus shape -------------------------------------------------------------------------

DEFECT_CLASSES: tuple[str, ...] = (
    "wrong_numeric_answer",
    "no_correct_option",
    "mismatched_solution",
    "mismatched_hint_ladder",
    "contradictory_constraints",
    "near_duplicate",
)

# 17 x 6 = 102 defects and 102 clean controls: the measurement plan's n >= 100 on both sides
# with the smallest margin that clears it, because every corpus item is two paid solver calls.
DEFAULT_PER_CLASS = 17

# The one seed the whole corpus derives from. Every per-item seed is `CORPUS_SEED + index`,
# so a class's items are reproducible independently of how many other classes were built.
CORPUS_SEED = 520_000

# Graded cosmetic severities for `near_duplicate`, in the order they are assigned round-robin.
NEAR_DUPLICATE_TIERS: tuple[str, ...] = (
    "typography_only",
    "name_swap",
    "name_and_noun_swap",
)

# Deltas tried in order when a numeral has to be shifted off the derived answer. Odd and
# mostly prime, so a shift is unlikely to land one distractor exactly on another's value.
_SHIFT_DELTAS: tuple[int, ...] = (3, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43)

# First names that actually occur in this bank (measured, not guessed) and replacements that
# do not. A name swap is only cosmetic if the replacement is not already in the item.
_NAME_POOL: tuple[str, ...] = (
    "Liam",
    "Maya",
    "Leo",
    "Maria",
    "Marcus",
    "Jordan",
    "Emma",
    "Lena",
    "Mia",
    "Luca",
    "Kai",
    "Alex",
    "Sarah",
    "Ava",
    "Jamal",
    "Jonah",
    "Priya",
    "Nina",
    "Ravi",
    "Sofia",
    "Jayden",
    "Amara",
)
_NAME_REPLACEMENTS: tuple[str, ...] = (
    "Tomas",
    "Ines",
    "Hugo",
    "Zaria",
    "Otto",
    "Freya",
    "Dario",
    "Noor",
)

# Story objects only - never a unit. A unit appears in the options and in
# `canonical_solution.final_answer`, and swapping it would turn a duplicate into an
# inconsistency, which is a different defect class.
_NOUN_SWAPS: tuple[tuple[str, str], ...] = (
    ("apples", "pears"),
    ("oranges", "lemons"),
    ("stickers", "badges"),
    ("marbles", "pebbles"),
    ("cookies", "muffins"),
    ("books", "journals"),
    ("pencils", "crayons"),
    ("flowers", "tulips"),
    ("shells", "stones"),
    ("cards", "tokens"),
    ("beads", "buttons"),
    ("blocks", "bricks"),
    ("balloons", "ribbons"),
    ("candles", "lanterns"),
    ("crackers", "biscuits"),
    ("bottles", "jars"),
    ("boxes", "crates"),
    ("bags", "sacks"),
    ("stamps", "coins"),
    ("ribbons", "laces"),
)

# A standalone number: not part of a longer numeral and not a decimal fragment. The same shape
# `authored_validation._NUMBER_IN_TEXT_RE` uses, tightened with lookarounds so shifting "5"
# inside "15" is impossible.
_NUMERAL_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)(?![\d.])")
# Numerals written with a thousands separator are excluded from every shifting mutation:
# `_NUMERAL_RE` sees "1,200" as two numbers, so a shift would silently rewrite the wrong digit.
_THOUSANDS_RE = re.compile(r"\d,\d{3}")


class MutationSkipped(Exception):
    """This source item cannot carry this class's mutation - try the next source.

    Raised rather than returned so a mutator can bail from anywhere in the middle of a
    multi-step edit without every caller re-checking a sentinel. Every raise carries the
    reason, and every reason ends up in the corpus artifact's exclusion ledger, because
    "which items could not be mutated and why" is part of what makes the sample honest.
    """


@dataclass
class CorpusItem:
    corpus_id: str
    label: str  # "defect" | "clean"
    defect_class: str | None
    clean_block: str | None
    source_item_id: str
    seed: int
    mutation: dict
    item: AuthoredTemplateDef
    answer_form: str

    def as_json(self) -> dict:
        return {
            "corpus_id": self.corpus_id,
            "label": self.label,
            "defect_class": self.defect_class,
            "clean_block": self.clean_block,
            "source_item_id": self.source_item_id,
            "seed": self.seed,
            "mutation": self.mutation,
            "answer_form": self.answer_form,
            "topic_id": self.item.topic_id,
            "skill_id": self.item.skill_id,
            "difficulty_label": self.item.difficulty_label,
            "item": self.item.model_dump(mode="json"),
        }


@dataclass
class BuildResult:
    items: list[CorpusItem] = field(default_factory=list)
    source_exclusions: list[dict] = field(default_factory=list)
    mutation_skips: list[dict] = field(default_factory=list)
    bank_total: int = 0
    eligible_total: int = 0


# --- gate helpers -------------------------------------------------------------------------


def gate(item: AuthoredTemplateDef, answer_form: str) -> AuthoredValidationResult:
    """The §5.8.5 deterministic gate, invoked exactly as `loader._gate` invokes it.

    Imported and called, never restated (the AUD-C-25 lesson): a benchmark that reimplements
    the check it is scoring measures its own copy.
    """
    return validate_authored_item(
        item.difficulty_label,
        item.to_generated_item(),
        figure=item.figure_spec,
        figure_reading=item.figure_reading,
        answer_form=answer_form,
    )


def derived_answer(equation: str) -> DerivedAnswer | None:
    derivation, _ = route_answer(equation)
    return derivation


def _options(item: AuthoredTemplateDef) -> dict[str, str]:
    return {
        "a": item.option_a,
        "b": item.option_b,
        "c": item.option_c,
        "d": item.option_d,
    }


def _question_text(item: AuthoredTemplateDef) -> str:
    return f"{item.context_block or ''}\n{item.stem}"


def _numerals(text: str) -> list[str]:
    return _NUMERAL_RE.findall(text)


def _format_shift(literal: str, delta: int) -> str:
    """`"6" + 3 -> "9"`, `"6.5" + 3 -> "9.5"` - the written form is preserved, because the
    option text is student-facing and `"9.0 minutes"` would be a second, unlabeled defect.
    """
    if "." in literal:
        places = len(literal.split(".", 1)[1])
        return f"{float(literal) + delta:.{places}f}"
    return str(int(literal) + delta)


def _shift_first_numeral(text: str, delta: int) -> str:
    match = _NUMERAL_RE.search(text)
    if match is None:
        raise MutationSkipped("no standalone numeral to shift")
    if _THOUSANDS_RE.search(text):
        raise MutationSkipped("numeral written with a thousands separator")
    shifted = _format_shift(match.group(1), delta)
    return text[: match.start(1)] + shifted + text[match.end(1) :]


def _replace_sole_occurrence(text: str, literal: str, replacement: str) -> str:
    pattern = re.compile(rf"(?<![\d.]){re.escape(literal)}(?![\d.])")
    found = pattern.findall(text)
    if len(found) != 1:
        raise MutationSkipped(f"numeral {literal!r} occurs {len(found)} times, expected exactly 1")
    return pattern.sub(replacement, text, count=1)


def _require_gate_failure(
    item: AuthoredTemplateDef, answer_form: str, *, needle: str, what: str
) -> list[str]:
    """Admit a mutation only when the real gate really rejects it, for the intended reason.

    The `needle` check is the part that matters. A mutated item that fails the gate for some
    incidental reason would be scored as a caught defect while the defect the label claims was
    never actually detected - the corpus would then be measuring the gate's reaction to an
    accident and reporting it as recall on this class.
    """
    result = gate(item, answer_form)
    if result.passed:
        raise MutationSkipped(f"mutation did not make the gate fail ({what})")
    if not any(needle in failure for failure in result.failures):
        raise MutationSkipped(f"gate failed but not for {what}: {result.failures[0][:80]!r}")
    return result.failures


# --- the six mutations --------------------------------------------------------------------


def mutate_wrong_numeric_answer(
    source: AuthoredTemplateDef, *, corpus_id: str, seed: int, answer_form: str, **_: object
) -> tuple[AuthoredTemplateDef, dict]:
    """Re-point `correct_option` at a distractor - D-229's class, verbatim.

    The replacement label is chosen from the seed rather than "the next letter", so the class
    does not correlate its answer key with the source's: a panel that happened to favour one
    option would score differently on a corpus that always moved b -> c.
    """
    labels = [label for label in ("a", "b", "c", "d") if label != source.correct_option]
    chosen = labels[seed % len(labels)]
    options = _options(source)
    mutated = source.model_copy(
        update={"question_template_id": corpus_id, "correct_option": chosen}
    )
    failures = _require_gate_failure(
        mutated,
        answer_form,
        needle="does not match declared correct option",
        what="the re-pointed answer key",
    )
    return mutated, {
        "field": "correct_option",
        "from": source.correct_option,
        "to": chosen,
        "answer_text_from": options[source.correct_option],
        "answer_text_to": options[chosen],
        "gate_failures": failures,
    }


def mutate_no_correct_option(
    source: AuthoredTemplateDef, *, corpus_id: str, seed: int, answer_form: str, **_: object
) -> tuple[AuthoredTemplateDef, dict]:
    """Shift every option's first numeral by one delta, so the derived answer is in none.

    One delta for all four rather than four different ones, so the distractor *spread* the
    author designed survives - the item still looks like a question with plausible wrong
    answers, which is what a solver has to reason about.

    **The delta loop exists because a uniform shift can move a distractor onto the true
    answer**, and the obvious admission test does not catch that. With options 9 / 6 / 5 / 11
    and a derived answer of 9, delta 3 makes the 6 into a 9: the *declared* option no longer
    matches, so the gate fails with "does not match declared correct option" and a check that
    only looked for that message would admit the item - as a `no_correct_option` label on what
    is really a `wrong_numeric_answer` item, since the answer is still on the page under
    another letter. So the admission test here is `resolved_matches` returning **nothing**:
    the pipeline's own reading sequence, asked whether any option states the derived answer at
    all. The first delta that clears it is the one used.
    """
    del seed
    options = _options(source)
    if any(_THOUSANDS_RE.search(text) for text in options.values()):
        raise MutationSkipped("an option is written with a thousands separator")
    if any(_NUMERAL_RE.search(text) is None for text in options.values()):
        raise MutationSkipped("an option has no standalone numeral to shift")

    equation = source.answer_expression or ""
    derivation = derived_answer(equation)
    if derivation is None:
        raise MutationSkipped("equation does not derive")

    last_error: str | None = None
    for delta in _SHIFT_DELTAS:
        shifted = {label: _shift_first_numeral(text, delta) for label, text in options.items()}
        if len(set(shifted.values())) != len(shifted):
            last_error = f"delta {delta} collapsed two options into the same text"
            continue
        still_matching, _raw, _reading = resolved_matches(
            derivation, shifted, equation, answer_form
        )
        if still_matching:
            last_error = (
                f"delta {delta} left the derived answer on the page as option {still_matching[0]!r}"
            )
            continue
        mutated = source.model_copy(
            update={
                "question_template_id": corpus_id,
                "option_a": shifted["a"],
                "option_b": shifted["b"],
                "option_c": shifted["c"],
                "option_d": shifted["d"],
            }
        )
        try:
            failures = _require_gate_failure(
                mutated,
                answer_form,
                needle="does not match declared correct option",
                what="the removed correct answer",
            )
        except MutationSkipped as exc:
            last_error = f"delta {delta}: {exc}"
            continue
        return mutated, {
            "field": "option_a..option_d",
            "delta": delta,
            "options_from": options,
            "options_to": shifted,
            "derived_answer": str(derivation.payload),
            "gate_failures": failures,
        }
    raise MutationSkipped(last_error or "no delta removed the correct answer")


def mutate_mismatched_solution(
    source: AuthoredTemplateDef,
    *,
    corpus_id: str,
    seed: int,
    answer_form: str,
    donors: list[AuthoredTemplateDef],
    **_: object,
) -> tuple[AuthoredTemplateDef, dict]:
    """Graft another item's `canonical_solution` on, whole.

    Donors are walked from a seed-derived offset so two items of this class do not share one
    donor by construction, and a donor is accepted only when the graft actually makes
    `check_hint_solution_answer_agreement` fail - a donor whose final answer happens to agree
    with this item's key would be a mislabeled clean item.
    """
    start = seed % len(donors)
    for offset in range(len(donors)):
        donor = donors[(start + offset) % len(donors)]
        if donor.question_template_id == source.question_template_id:
            continue
        mutated = source.model_copy(
            update={
                "question_template_id": corpus_id,
                "canonical_solution": donor.canonical_solution,
            }
        )
        try:
            failures = _require_gate_failure(
                mutated,
                answer_form,
                needle="does not match the declared correct option",
                what="the grafted solution",
            )
        except MutationSkipped:
            continue
        return mutated, {
            "field": "canonical_solution",
            "donor_item_id": donor.question_template_id,
            "donor_topic_id": donor.topic_id,
            "final_answer_from": source.canonical_solution.get("final_answer"),
            "final_answer_to": donor.canonical_solution.get("final_answer"),
            "gate_failures": failures,
        }
    raise MutationSkipped("no donor solution disagreed with this item's answer key")


def mutate_mismatched_hint_ladder(
    source: AuthoredTemplateDef,
    *,
    corpus_id: str,
    seed: int,
    answer_form: str,
    donors: list[AuthoredTemplateDef],
    **_: object,
) -> tuple[AuthoredTemplateDef, dict]:
    """Graft another item's `hint_ladder` on, whole.

    The defect has to be *objective* for this class to be scoreable, because - unlike every
    other class here - no detector in this benchmark is expected to catch it, and "the hints
    read a bit off" is not a label. The donor is therefore required to share **no numeral**
    with this item's question or equation: the grafted rungs then coach a student toward
    numbers that do not appear in the question they are attached to, which is checkable
    without judgement.

    The gate verdict is recorded, not required. It should pass, and the one way it can fail is
    a donor rung that happens to state this item's answer verbatim (`check_no_answer_leakage`)
    - a real catch, for a reason that has nothing to do with hint relevance. Letting that
    happen and reporting the reason is more informative than filtering it out.
    """
    own_numerals = set(_numerals(_question_text(source))) | set(
        _numerals(source.answer_expression or "")
    )
    start = seed % len(donors)
    for offset in range(len(donors)):
        donor = donors[(start + offset) % len(donors)]
        if donor.question_template_id == source.question_template_id:
            continue
        if donor.hint_ladder == source.hint_ladder:
            continue
        donor_numerals = {n for rung in donor.hint_ladder for n in _numerals(rung)}
        if not donor_numerals or donor_numerals & own_numerals:
            continue
        mutated = source.model_copy(
            update={"question_template_id": corpus_id, "hint_ladder": list(donor.hint_ladder)}
        )
        result = gate(mutated, answer_form)
        return mutated, {
            "field": "hint_ladder",
            "donor_item_id": donor.question_template_id,
            "donor_topic_id": donor.topic_id,
            "hint_ladder_from": list(source.hint_ladder),
            "hint_ladder_to": list(donor.hint_ladder),
            "donor_numerals": sorted(donor_numerals),
            "own_numerals": sorted(own_numerals),
            "gate_failures": result.failures,
        }
    raise MutationSkipped("no donor hint ladder was numeral-disjoint from this item")


def mutate_contradictory_constraints(
    source: AuthoredTemplateDef, *, corpus_id: str, seed: int, answer_form: str, **_: object
) -> tuple[AuthoredTemplateDef, dict]:
    """Shift one stem numeral and leave the equation, options and answer key alone.

    The result is an item whose story and whose declared model disagree, which is the failure
    `check_sympy_independent_solve` explicitly cannot see: the equation still derives its
    declared answer, so the gate passes and the item is only wrong to a reader.

    Two conditions make the label defensible. The numeral must occur **exactly once** in both
    the question text and the equation, so the shift is unambiguous about which quantity it
    changed; and the *shadow equation* - the declared equation with the same shift applied -
    must derive a different answer. Without the second, a shift into an equivalent problem
    would be filed as an undetected defect while not being a defect at all.
    """
    del seed
    equation = source.answer_expression or ""
    if not equation:
        raise MutationSkipped("no equation")
    original = derived_answer(equation)
    if original is None:
        raise MutationSkipped("equation does not derive")
    if _THOUSANDS_RE.search(_question_text(source)) or _THOUSANDS_RE.search(equation):
        raise MutationSkipped("thousands separator in the question or equation")

    equation_numerals = Counter(_numerals(equation))
    stem_numerals = Counter(_numerals(source.stem))
    context_numerals = Counter(_numerals(source.context_block or ""))

    shared = [
        literal
        for literal in _numerals(source.stem) + _numerals(source.context_block or "")
        if equation_numerals[literal] == 1
        and (stem_numerals[literal] + context_numerals[literal]) == 1
    ]
    if not shared:
        raise MutationSkipped(
            "no numeral occurs exactly once in both the question text and the equation"
        )
    literal = shared[0]
    in_stem = stem_numerals[literal] == 1

    last_error: str | None = None
    for delta in _SHIFT_DELTAS:
        replacement = _format_shift(literal, delta)
        if replacement in stem_numerals or replacement in context_numerals:
            last_error = f"delta {delta} duplicates a numeral already in the question"
            continue
        shadow = _replace_sole_occurrence(equation, literal, replacement)
        shadow_derivation = derived_answer(shadow)
        if shadow_derivation is None:
            last_error = f"delta {delta}: shadow equation {shadow!r} does not derive"
            continue
        if str(shadow_derivation.payload) == str(original.payload):
            last_error = f"delta {delta}: shadow equation derives the same answer"
            continue

        update: dict = {"question_template_id": corpus_id}
        if in_stem:
            update["stem"] = _replace_sole_occurrence(source.stem, literal, replacement)
        else:
            update["context_block"] = _replace_sole_occurrence(
                source.context_block or "", literal, replacement
            )
        # The stored `rendered_question` is not what any detector reads - the gate rebuilds the
        # item from stem/context and the solvers are given `rendered_for_model()` - but leaving
        # it stale would put two different questions in one corpus record, and the artifact is
        # meant to be readable by hand.
        rendered = source.rendered_question
        if literal in _numerals(rendered):
            try:
                rendered = _replace_sole_occurrence(rendered, literal, replacement)
            except MutationSkipped:
                rendered = source.rendered_question
        update["rendered_question"] = rendered
        mutated = source.model_copy(update=update)
        result = gate(mutated, answer_form)
        return mutated, {
            "field": "stem" if in_stem else "context_block",
            "numeral_from": literal,
            "numeral_to": replacement,
            "delta": delta,
            "equation_unchanged": equation,
            "shadow_equation": shadow,
            "declared_answer": str(original.payload),
            "stem_implied_answer": str(shadow_derivation.payload),
            "gate_failures": result.failures,
        }
    raise MutationSkipped(last_error or "no delta produced a contradictory stem")


def _swap_everywhere(item: AuthoredTemplateDef, pairs: list[tuple[str, str]]) -> dict:
    """Apply word swaps to every student-facing field at once.

    All fields together, never the stem alone: swapping "apples" for "pears" in the question
    while the hints and the solution still say "apples" would produce an internally
    inconsistent item - a *different* defect class, silently mixed into this one.
    """

    def swap(text: str) -> str:
        for before, after in pairs:
            text = re.sub(rf"\b{re.escape(before)}\b", after, text)
        return text

    solution = json.loads(json.dumps(item.canonical_solution))
    for step in solution.get("steps", []):
        for key in ("explanation", "expression", "common_mistake"):
            if isinstance(step.get(key), str):
                step[key] = swap(step[key])
    if isinstance(solution.get("final_answer"), str):
        solution["final_answer"] = swap(solution["final_answer"])

    return {
        "stem": swap(item.stem),
        "context_block": swap(item.context_block) if item.context_block else item.context_block,
        "rendered_question": swap(item.rendered_question),
        "hint_ladder": [swap(rung) for rung in item.hint_ladder],
        "option_a": swap(item.option_a),
        "option_b": swap(item.option_b),
        "option_c": swap(item.option_c),
        "option_d": swap(item.option_d),
        "canonical_solution": solution,
    }


def _typography_edit(text: str) -> tuple[str, str]:
    """The smallest edit that makes two identical questions different strings.

    Ordered so the most common one is tried first, and only one is applied: this severity tier
    exists to be a *near-identical* duplicate, so it must not accumulate edits. Every one of
    these is a real copy-paste artifact, and every one defeats the pipeline's cheap exact-text
    dedup check while leaving the question word-for-word the same.
    """
    if ". " in text:
        return text.replace(". ", ".  ", 1), "double space after the first sentence"
    if "'" in text:
        return text.replace("'", "’", 1), "straight apostrophe to typographic"
    if ", " in text:
        return text.replace(", ", ",  ", 1), "double space after the first comma"
    if text.rstrip().endswith("?"):
        stripped = text.rstrip()
        return stripped[:-1] + " ?", "space before the final question mark"
    raise MutationSkipped("no cosmetic typography edit applies to this stem")


def mutate_near_duplicate(
    source: AuthoredTemplateDef,
    *,
    corpus_id: str,
    seed: int,
    answer_form: str,
    tier: str,
    **_: object,
) -> tuple[AuthoredTemplateDef, dict]:
    """Clone a clean control and edit only its surface.

    `source` is a clean control on purpose: the controls are the corpus's stand-in for the
    approved bank, and the dedup detector compares a candidate against them exactly as
    `stem_near_duplicate_exists` compares a candidate against the bank. A clone of anything
    else would have nothing to be a duplicate *of*.

    The clone must still pass the gate. That is the class definition, not a convenience: a
    near-duplicate is a valid question that should not be added, so a clone the gate rejects
    would be counted as a gate catch for a defect the gate cannot actually see.
    """
    edits: list[str] = []
    update: dict = {"question_template_id": corpus_id}

    if tier == "typography_only":
        edited, description = _typography_edit(source.stem)
        update["stem"] = edited
        update["rendered_question"] = _typography_edit(source.rendered_question)[0]
        edits.append(description)
    else:
        present = [name for name in _NAME_POOL if re.search(rf"\b{name}\b", _question_text(source))]
        if not present:
            raise MutationSkipped("no known first name in the question")
        name = present[0]
        candidates = [
            candidate
            for candidate in _NAME_REPLACEMENTS
            if not re.search(rf"\b{candidate}\b", _question_text(source))
        ]
        if not candidates:
            raise MutationSkipped("every replacement name already occurs in the question")
        replacement = candidates[seed % len(candidates)]
        pairs = [(name, replacement)]
        edits.append(f"person name {name} -> {replacement}")

        if tier == "name_and_noun_swap":
            nouns = [
                (before, after)
                for before, after in _NOUN_SWAPS
                if re.search(rf"\b{before}\b", _question_text(source))
                and not re.search(rf"\b{after}\b", _question_text(source))
            ]
            if not nouns:
                raise MutationSkipped("no swappable story noun in the question")
            pairs.append(nouns[0])
            edits.append(f"story noun {nouns[0][0]} -> {nouns[0][1]}")
        update.update(_swap_everywhere(source, pairs))

    mutated = source.model_copy(update=update)
    if mutated.stem == source.stem:
        raise MutationSkipped("cosmetic edit changed nothing")
    result = gate(mutated, answer_form)
    if not result.passed:
        raise MutationSkipped(f"clone no longer passes the gate: {result.failures[0][:80]!r}")

    source_identity = arithmetic_identity(source.answer_expression or "")
    clone_identity = arithmetic_identity(mutated.answer_expression or "")
    if source_identity != clone_identity:
        raise MutationSkipped("cosmetic edit changed the arithmetic identity")

    return mutated, {
        "field": "stem (and every field the swap touches)",
        "severity_tier": tier,
        "edits": edits,
        "duplicate_of_corpus_source": source.question_template_id,
        "stem_from": source.stem,
        "stem_to": mutated.stem,
        "arithmetic_identity": [list(clone_identity[0]), list(clone_identity[1])]
        if clone_identity
        else None,
    }


MUTATORS = {
    "wrong_numeric_answer": mutate_wrong_numeric_answer,
    "no_correct_option": mutate_no_correct_option,
    "mismatched_solution": mutate_mismatched_solution,
    "mismatched_hint_ladder": mutate_mismatched_hint_ladder,
    "contradictory_constraints": mutate_contradictory_constraints,
    "near_duplicate": mutate_near_duplicate,
}


# --- source selection ---------------------------------------------------------------------


def eligible_sources(
    banks: dict[str, list[AuthoredTemplateDef]], curriculum: CurriculumContent
) -> tuple[list[AuthoredTemplateDef], list[dict]]:
    """The bank items the deterministic checks actually apply to, plus the exclusion ledger.

    Three exclusions, all recorded rather than assumed away:

    - a `figure_reading` item deliberately **replaces** the equation as its source of truth,
      so `check_sympy_independent_solve` never runs on it (see `validate_authored_item`) and
      three of the six mutation classes would have nothing to act on;
    - a `figure_spec` item's gate verdict depends on a figure the corpus record cannot carry
      readably;
    - an equation that does not derive cannot support a wrong-answer or a shadow-equation
      mutation at all.

    An item whose gate already fails is also excluded, and finding none of those is itself a
    check: every item in this bank was approved through this gate, so a failure here would
    mean the bank and the gate had drifted apart.
    """
    eligible: list[AuthoredTemplateDef] = []
    exclusions: list[dict] = []
    for _topic, items in sorted(banks.items()):
        for item in items:
            reason: str | None = None
            if item.figure_reading is not None:
                reason = "figure_reading replaces the equation, so the SymPy checks are skipped"
            elif item.figure_spec is not None:
                reason = "figure_spec cannot be represented readably in the corpus record"
            elif not item.answer_expression:
                reason = "no equation"
            elif derived_answer(item.answer_expression) is None:
                reason = "equation does not derive"
            else:
                result = gate(item, curriculum.answer_form(item.skill_id))
                if not result.passed:
                    reason = f"already fails the gate: {result.failures[0][:100]}"
            if reason is not None:
                exclusions.append(
                    {
                        "question_template_id": item.question_template_id,
                        "topic_id": item.topic_id,
                        "reason": reason,
                    }
                )
                continue
            eligible.append(item)
    return eligible, exclusions


def stratified_order(items: list[AuthoredTemplateDef]) -> list[AuthoredTemplateDef]:
    """Round-robin over (topic, difficulty) cells, so any prefix is spread over the bank.

    Every group in this corpus is filled from a prefix of this ordering, and a class that had
    taken the file order would be a class about one topic: `algebra_2` alone would supply the
    first 74 items. Deterministic - the cells and the items inside them are sorted, and no RNG
    is involved.
    """
    cells: dict[tuple[str, int], list[AuthoredTemplateDef]] = defaultdict(list)
    for item in items:
        cells[(item.topic_id, item.difficulty_label)].append(item)
    for cell in cells.values():
        cell.sort(key=lambda i: i.question_template_id)
    ordered: list[AuthoredTemplateDef] = []
    keys = sorted(cells)
    depth = max((len(cells[key]) for key in keys), default=0)
    for index in range(depth):
        for key in keys:
            if index < len(cells[key]):
                ordered.append(cells[key][index])
    return ordered


def topic_round_robin(
    items: list[AuthoredTemplateDef], *, topic_offset: int = 0, item_offset: int = 0
) -> list[AuthoredTemplateDef]:
    """Re-order a pool so that **any prefix of it covers every topic and every tier**.

    `stratified_order` round-robins over (topic, difficulty) *cells*, and one pass over the
    cells is about 140 items long - longer than the 102 controls this corpus needs. Taking a
    prefix of it is therefore taking part of one pass, which is the alphabetically-first two
    thirds of the topics and nothing else. Measured twice while building this: the first
    attempt left `place_value`, `trigonometry` and `statistics_advanced` out of the controls
    entirely, and a second attempt that fixed the pool assignment but kept the prefix left four
    topics out.

    Rotating over topics makes one pass 29 items long, so a 102-item prefix is three and a half
    passes and every topic is in it. That alone re-created the same defect one axis over -
    every topic's pool is in ascending-difficulty order, so pass 0 was all tier 1, pass 1 all
    tier 2, and tier 5 ended up at 8 of 204 - so each topic's own list is also rotated, by its
    position in the topic order, and a prefix now cuts across tiers as well as topics.

    `topic_offset` / `item_offset` let two consumers of two different pools start at different
    places, so the six defect classes do not all sample the same seventeen topics.
    """
    by_topic: dict[str, list[AuthoredTemplateDef]] = defaultdict(list)
    for item in items:
        by_topic[item.topic_id].append(item)
    keys = sorted(by_topic)
    if not keys:
        return []
    start = topic_offset % len(keys)
    keys = keys[start:] + keys[:start]
    rotated: dict[str, list[AuthoredTemplateDef]] = {}
    for position, key in enumerate(keys):
        pool = by_topic[key]
        shift = (position + item_offset) % len(pool)
        rotated[key] = pool[shift:] + pool[:shift]
    ordered: list[AuthoredTemplateDef] = []
    for index in range(max(len(pool) for pool in rotated.values())):
        for key in keys:
            if index < len(rotated[key]):
                ordered.append(rotated[key][index])
    return ordered


def build_corpus(
    *,
    per_class: int = DEFAULT_PER_CLASS,
    classes: tuple[str, ...] = DEFECT_CLASSES,
    content_root: pathlib.Path | None = None,
) -> BuildResult:
    """Clean controls first, then the mutation classes, then the near-duplicate clones.

    The order is forced by two dependencies. The clean controls are the dedup detector's
    reference set, so they must be chosen before anything can be a duplicate *of* one; and
    every mutation source must be disjoint from them, so a mutated item is never accidentally
    a near-duplicate of the reference set it is scored against.
    """
    banks = load_authored_bank(content_root)
    curriculum = load_curriculum() if content_root is None else load_curriculum(content_root.parent)
    result = BuildResult(bank_total=sum(len(v) for v in banks.values()))
    eligible, result.source_exclusions = eligible_sources(banks, curriculum)
    result.eligible_total = len(eligible)

    ordered = stratified_order(eligible)
    clean_needed = per_class * len(classes)
    mutation_classes = [name for name in classes if name != "near_duplicate"]

    # **Every group is drawn from one interleaved walk of the stratified order, never from a
    # prefix of it.** The first version of this took `ordered[:102]` as the controls and
    # everything after as mutation sources, which looks stratified and is not: a round-robin
    # over (topic, difficulty) cells visits the cells in sorted order, so a 102-item prefix is
    # the alphabetically-first ~102 cells. The controls held no `place_value`, `trigonometry`
    # or `statistics_advanced` item at all, the defect sources held little else, and the
    # embedding dedup detector - which compares a candidate only against controls **in its own
    # topic** - had no reference set for a third of the corpus. Measured, not theorised: a
    # calibration run returned `nearest_distance: null` for exactly those items.
    #
    # One cycle of `len(classes)` control slots plus one slot per mutation class keeps the two
    # sides of the corpus drawn from the same distribution, which is the whole basis on which a
    # clean-set false-positive rate is comparable with a per-class recall.
    # The cycle counter is **per topic**, not global. Counting globally still left three
    # topics with every one of their items on a mutation slot and none on a control slot, so
    # the dedup detector had no same-topic reference for them; per-topic counting gives every
    # topic a control before it gives any topic a second one, and the pools stay in the
    # globally stratified order they were walked in.
    cycle = ["clean"] * len(classes) + mutation_classes
    pools: dict[str, list[AuthoredTemplateDef]] = defaultdict(list)
    seen_per_topic: dict[str, int] = defaultdict(int)
    for item in ordered:
        slot = cycle[seen_per_topic[item.topic_id] % len(cycle)]
        seen_per_topic[item.topic_id] += 1
        pools[slot].append(item)
    if len(pools["clean"]) < clean_needed:
        raise SystemExit(
            f"only {len(pools['clean'])} eligible control candidates, need {clean_needed}"
        )

    def form(item: AuthoredTemplateDef) -> str:
        return curriculum.answer_form(item.skill_id)

    # --- clean controls, blocked so every class has a matched negative set ------------------
    #
    # The blocks are a scoring device, not a sampling one: precision needs the false positives
    # that belong to *this* class's comparison, and a single pooled clean set would give every
    # class the same denominator and the same precision. Assigned round-robin over the
    # stratified order, so the blocks are comparable to each other as well.
    clean_sources = topic_round_robin(pools["clean"])[:clean_needed]
    for index, item in enumerate(clean_sources):
        block = classes[index % len(classes)]
        result.items.append(
            CorpusItem(
                corpus_id=f"e52-clean-{index:03d}",
                label="clean",
                defect_class=None,
                clean_block=block,
                source_item_id=item.question_template_id,
                seed=CORPUS_SEED + index,
                mutation={"field": None, "note": "unmutated approved bank item"},
                item=item,
                answer_form=form(item),
            )
        )

    # Donors for the graft classes come from the whole eligible pool: a graft replaces a field
    # and never the stem, so a donor being elsewhere in the corpus cannot affect any detector.
    donors = sorted(eligible, key=lambda i: i.question_template_id)

    for class_index, defect_class in enumerate(mutation_classes):
        mutator = MUTATORS[defect_class]
        made = 0
        # Each class starts its topic rotation five topics further round than the last, so
        # the five classes sample five overlapping-but-different slices of the bank rather
        # than the same seventeen alphabetically-first topics.
        candidates = topic_round_robin(
            pools[defect_class], topic_offset=class_index * 5, item_offset=class_index
        )
        for source in candidates:
            if made >= per_class:
                break
            corpus_id = f"e52-{defect_class}-{made:03d}"
            seed = CORPUS_SEED + made
            try:
                mutated, detail = mutator(
                    source,
                    corpus_id=corpus_id,
                    seed=seed,
                    answer_form=form(source),
                    donors=donors,
                    tier="",
                )
            except MutationSkipped as exc:
                result.mutation_skips.append(
                    {
                        "defect_class": defect_class,
                        "question_template_id": source.question_template_id,
                        "reason": str(exc),
                    }
                )
                continue
            result.items.append(
                CorpusItem(
                    corpus_id=corpus_id,
                    label="defect",
                    defect_class=defect_class,
                    clean_block=None,
                    source_item_id=source.question_template_id,
                    seed=seed,
                    mutation=detail,
                    item=mutated,
                    answer_form=form(source),
                )
            )
            made += 1
        if made < per_class:
            raise SystemExit(
                f"class {defect_class}: only {made}/{per_class} sources could carry the mutation"
            )

    # --- near-duplicate clones of the clean controls ---------------------------------------
    #
    # Split as evenly as the count allows across the three severity tiers, and each tier walks
    # the controls from its own offset so the three tiers clone three different subsets - a
    # tier whose clones were all of the same 6 controls would be measuring those 6 questions.
    if "near_duplicate" in classes:
        targets = [
            per_class // len(NEAR_DUPLICATE_TIERS)
            + (1 if i < per_class % len(NEAR_DUPLICATE_TIERS) else 0)
            for i in range(len(NEAR_DUPLICATE_TIERS))
        ]
        used: set[str] = set()
        made = 0
        for tier_index, tier in enumerate(NEAR_DUPLICATE_TIERS):
            target = targets[tier_index]
            built = 0
            offset = tier_index * (len(clean_sources) // len(NEAR_DUPLICATE_TIERS))
            for step in range(len(clean_sources)):
                if built >= target:
                    break
                source = clean_sources[(offset + step) % len(clean_sources)]
                if source.question_template_id in used:
                    continue
                corpus_id = f"e52-near_duplicate-{made:03d}"
                seed = CORPUS_SEED + made
                try:
                    mutated, detail = mutate_near_duplicate(
                        source,
                        corpus_id=corpus_id,
                        seed=seed,
                        answer_form=form(source),
                        tier=tier,
                    )
                except MutationSkipped as exc:
                    result.mutation_skips.append(
                        {
                            "defect_class": "near_duplicate",
                            "question_template_id": source.question_template_id,
                            "severity_tier": tier,
                            "reason": str(exc),
                        }
                    )
                    continue
                used.add(source.question_template_id)
                result.items.append(
                    CorpusItem(
                        corpus_id=corpus_id,
                        label="defect",
                        defect_class="near_duplicate",
                        clean_block=None,
                        source_item_id=source.question_template_id,
                        seed=seed,
                        mutation=detail,
                        item=mutated,
                        answer_form=form(source),
                    )
                )
                made += 1
                built += 1
            if built < target:
                raise SystemExit(
                    f"near_duplicate/{tier}: only {built}/{target} clones could be built"
                )

    return result


# --- artifacts ----------------------------------------------------------------------------


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):  # pragma: no cover
        return "unknown"


def corpus_header(result: BuildResult, *, per_class: int, classes: tuple[str, ...]) -> dict:
    return {
        "record": "header",
        "experiment": "E5.2",
        "artifact": "defect_corpus",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_sha": git_sha(),
        "environment": "local - deterministic mutation of the approved authored bank",
        "corpus_seed": CORPUS_SEED,
        "per_class": per_class,
        "defect_classes": list(classes),
        "near_duplicate_severity_tiers": list(NEAR_DUPLICATE_TIERS),
        "bank_items_total": result.bank_total,
        "bank_items_eligible": result.eligible_total,
        "bank_items_excluded": len(result.source_exclusions),
        "defects": sum(1 for i in result.items if i.label == "defect"),
        "clean_controls": sum(1 for i in result.items if i.label == "clean"),
        "mutation_attempts_skipped": len(result.mutation_skips),
        "source_exclusions": result.source_exclusions,
        "mutation_skips": result.mutation_skips,
    }


def write_corpus(path: pathlib.Path, result: BuildResult, header: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(header) + "\n")
        for item in result.items:
            handle.write(json.dumps({"record": "item", **item.as_json()}) + "\n")


def load_corpus(path: pathlib.Path) -> tuple[dict, list[dict]]:
    """Read a corpus artifact back - used by the detector harness and by the tests.

    The harness runs off the artifact rather than rebuilding the corpus, so the items that
    were scored are provably the items that were committed.
    """
    header: dict = {}
    items: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("record") == "header":
                header = record
            else:
                items.append(record)
    return header, items


def summarise(result: BuildResult) -> str:
    lines: list[str] = []
    lines.append(f"bank items:              {result.bank_total}")
    lines.append(
        f"  eligible as sources:   {result.eligible_total} "
        f"({len(result.source_exclusions)} excluded)"
    )
    excl = Counter(e["reason"].split(":")[0] for e in result.source_exclusions)
    for reason, count in excl.most_common():
        lines.append(f"    {count:4d}  {reason}")
    defects = [i for i in result.items if i.label == "defect"]
    clean = [i for i in result.items if i.label == "clean"]
    lines.append(f"corpus:                  {len(result.items)} items")
    lines.append(f"  defects:               {len(defects)}")
    for name, count in sorted(Counter(i.defect_class for i in defects).items()):
        lines.append(f"    {name:30s} {count}")
    tiers = Counter(
        i.mutation.get("severity_tier") for i in defects if i.defect_class == "near_duplicate"
    )
    for tier, count in sorted(tiers.items(), key=lambda kv: str(kv[0])):
        lines.append(f"      severity {str(tier):24s} {count}")
    lines.append(f"  clean controls:        {len(clean)}")
    lines.append(f"  distinct topics:       {len({i.item.topic_id for i in result.items})}")
    lines.append(
        f"  difficulty spread:     "
        f"{dict(sorted(Counter(i.item.difficulty_label for i in result.items).items()))}"
    )
    lines.append(f"  mutation attempts skipped: {len(result.mutation_skips)}")
    skips = Counter(s["reason"][:60] for s in result.mutation_skips)
    for reason, count in skips.most_common(8):
        lines.append(f"    {count:4d}  {reason}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="docs/resume_evidence/05_content_generation/defect_corpus.jsonl",
        help="where to write the corpus JSONL",
    )
    parser.add_argument(
        "--per-class",
        type=int,
        default=DEFAULT_PER_CLASS,
        help=f"defects per class, and clean controls per block (default {DEFAULT_PER_CLASS})",
    )
    parser.add_argument("--dry-run", action="store_true", help="build and summarise, write nothing")
    args = parser.parse_args()

    result = build_corpus(per_class=args.per_class)
    header = corpus_header(result, per_class=args.per_class, classes=DEFECT_CLASSES)
    print(summarise(result))
    if args.dry_run:
        print("\ndry run - nothing written")
        return 0
    out = pathlib.Path(args.out)
    write_corpus(out, result, header)
    print(f"\ncorpus written to {out} ({out.stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
