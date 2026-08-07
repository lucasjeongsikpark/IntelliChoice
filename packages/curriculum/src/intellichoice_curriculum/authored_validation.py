"""SPEC §5.8.5 automated validation for S20's *authored* generation mode (plan §7 step
2) - deterministic/executable checks distinct from `validation.py`'s, which assume a
registered `SHAPES` solver a parameterized template always has. An authored item has no
shape: its "exactly one correct answer" is checked by independently solving
`answer_expression` with SymPy (when it parses) instead of recomputing from a shape
function, and it carries its own hint ladder/solution, which the shape pipeline doesn't
generate at all.

Near-duplicate detection (embedding + a DB query) and the LLM solver/judge stages are
NOT here - this module only covers the parts of §5.8.5 checkable with plain Python
against the values already in hand, mirroring `validation.py`'s own scope split (see
`ai_pipeline.generate_authored_candidate` for where the DB/embedding/LLM stages live).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy
from intellichoice_shared.bedrock import AuthoredGeneratedItemResponse
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_OPTION_LABELS = ("a", "b", "c", "d")
_REQUIRED_HINT_LEVELS = 3
# Substring matching made this check reject correct, harmless questions, and the words it
# hit are ones a math item is *likely* to contain: "skill" contains "kill", "studies"
# contains "die", and so do "medium", "diet", "audience". Measured on the first scenario
# run (D-191), which lost a question about rolling a die - the singular of dice, a math
# object, not a word about death.
#
# So: word-boundary matching, and "die" is deliberately not on the list. The concern is
# violence and insult, which the unambiguous forms below carry; "a die" does not. The
# boundary assertions mirror `answer_text_leaked`'s, which was fixed for the same class of
# bug (a `\b` that could never fire) - see its docstring.
_DISALLOWED_WORDING = (
    "kill",
    "kills",
    "killed",
    "killing",
    "died",
    "dying",
    "death",
    "deaths",
    "stupid",
    "dumb",
)
_DISALLOWED_WORDING_RE = re.compile(
    r"(?<![0-9A-Za-z])(?:" + "|".join(_DISALLOWED_WORDING) + r")(?![0-9A-Za-z])",
    re.IGNORECASE,
)
_LEAK_PHRASES = (
    "the answer is",
    "correct answer is",
    "correct answer:",
    "the correct option is",
)
_HTML_OR_LINK_RE = re.compile(r"<[^>]+>|https?://|www\.")
# Phrases in which the model talks about *authoring the item* inside content a student
# reads (D-195). Not hypothetical: the first four-candidate pilot produced a stem
# containing "The question is adjusted to ask for the number of rides after...", which the
# gate caught only incidentally, as a 30-word sentence. A shorter sentence would have
# shipped model-to-itself narration to a child.
#
# Phrase matching, not single words, and every phrase names the *act of authoring*
# ("adjusted to", "revised to") rather than a bare verb. "The recipe was adjusted to serve
# eight people" is a legitimate math scenario and must survive; "the question was adjusted"
# never is. The judge remains the check for subtler drift - this catches the blatant form
# for free, before any model is paid to read it.
_META_COMMENTARY_PHRASES = (
    "the question is adjusted",
    "the question was adjusted",
    "the question has been adjusted",
    "the problem is adjusted",
    "the problem was adjusted",
    "the question is revised",
    "the question was revised",
    "the problem was revised",
    "this version asks",
    "this version of the question",
    "as requested",
    "as instructed",
    "per the instructions",
    "the prompt asks",
    "i have generated",
    "i have created",
    "i have written",
    "note to the reviewer",
    "note for the reviewer",
    # D-217: a whole class the earlier list missed - text that describes the problem *as a
    # problem to a reviewer* ("This is a concrete real-world scenario requiring students to
    # set up and solve...") rather than posing it to the student. Found live in a served
    # study item's stem, the same context-block leak D-215 fixed by hand for other items.
    # Every phrase talks *about* the student in the third person, which a finished stem
    # written *to* the student never does.
    "requiring students to",
    "requires students to",
    "requiring the student to",
    "requires the student to",
    "students to set up",
    "real-world scenario",
    "this is a concrete",
    "scenario requiring",
    "this problem requires",
    "this problem tests",
    "this problem is designed",
    "designed to test",
)
_META_COMMENTARY_RE = re.compile(
    "|".join(re.escape(phrase) for phrase in _META_COMMENTARY_PHRASES), re.IGNORECASE
)
# Heuristic readability ceiling (§5.8.5 "age-appropriate wording") - a rough proxy only;
# real nuance is the LLM judge's job (plan §7 step 3), not this deterministic gate's.
_MAX_WORDS_PER_SENTENCE = 30
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5


@dataclass
class AuthoredValidationResult:
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def fail(self, reason: str) -> None:
        self.failures.append(reason)


def _options(item: AuthoredGeneratedItemResponse) -> dict[str, str]:
    return {
        "a": item.option_a,
        "b": item.option_b,
        "c": item.option_c,
        "d": item.option_d,
    }


def _text_fields(item: AuthoredGeneratedItemResponse) -> list[str]:
    fields = [item.stem, *item.hint_ladder, item.canonical_solution.final_answer]
    if item.context_block:
        fields.append(item.context_block)
    fields.extend(_options(item).values())
    for step in item.canonical_solution.steps:
        fields.append(step.explanation)
        fields.append(step.expression)
    return fields


def check_schema_and_markdown_safety(
    item: AuthoredGeneratedItemResponse, result: AuthoredValidationResult
) -> None:
    if not item.stem.strip():
        result.fail("stem is empty")
    if "{" in item.stem or "}" in item.stem:
        result.fail("stem has an unrendered placeholder")
    if len(item.hint_ladder) != _REQUIRED_HINT_LEVELS:
        result.fail(
            f"hint_ladder has {len(item.hint_ladder)} levels, expected exactly "
            f"{_REQUIRED_HINT_LEVELS}"
        )
    elif any(not level.strip() for level in item.hint_ladder):
        result.fail("hint_ladder contains an empty level")
    if not item.canonical_solution.steps:
        result.fail("canonical_solution has no steps")
    for text in _text_fields(item):
        if _HTML_OR_LINK_RE.search(text):
            result.fail(f"raw HTML or a link was found in generated content: {text[:60]!r}")
            break


def check_unique_options(
    item: AuthoredGeneratedItemResponse, result: AuthoredValidationResult
) -> None:
    texts = list(_options(item).values())
    if len(set(texts)) != len(texts):
        result.fail("options are not all unique")


# Typographic characters a real model emits freely in math text but SymPy cannot parse.
# U+2212 MINUS SIGN is the one actually observed (the first real-Bedrock authoring run,
# 2026-08-05); the dashes are its near neighbours on the same keyboard-vs-typography
# fault line and are cheap to accept here rather than after another paid run finds them.
_MATH_TEXT_SUBSTITUTIONS = {
    "−": "-",  # minus sign
    "–": "-",  # en dash
    "—": "-",  # em dash
    "×": "*",  # multiplication sign
    "÷": "/",  # division sign
}
# "x = 7" as an option means the value 7 - a restated equation, not a different answer.
_ASSIGNMENT_PREFIX_RE = re.compile(r"^\s*[A-Za-z]\w*\s*=\s*")


def _normalize_math_text(text: str, *, strip_assignment: bool = True) -> str:
    """Make human-written math text parseable without changing what it asserts.

    `strip_assignment` is off for equations. Stripping `x =` from an *option* recovers the
    value it names; stripping it from an *equation* deletes half the relation, which is
    the thing being solved.

    Both transformations were found by the first real authoring run against Bedrock
    (2026-08-05), where they cost six of eleven candidates: the model wrote correct
    answers as `'x = 7'` and `'−4'`, neither of which `sympy.sympify` accepts, so the
    independent-solve gate reported a mismatch for items whose math was right.

    This makes the gate *stricter*, not looser, which is the reason it is safe to do at
    the parse site. A value that could not be parsed was silently exempt from
    `check_sympy_independent_solve`'s "no distractor also matches" arm - the run that
    prompted this produced exactly that, an item whose `'−3'` distractor was never
    compared to the solved answer at all. Nothing here can turn a wrong answer into a
    matching one: the text still has to denote the same value.
    """
    for character, replacement in _MATH_TEXT_SUBSTITUTIONS.items():
        text = text.replace(character, replacement)
    if not strip_assignment:
        return text
    return _ASSIGNMENT_PREFIX_RE.sub("", text, count=1)


# A trailing unit ("12 minutes", "40 cm", "2/3 of a cup") or a leading currency symbol.
# Both are how a *word problem's* answer naturally reads, which is why they matter: the
# bare-equation items the pipeline produced never needed them, so the gap only appears
# once questions get more interesting (D-191).
_TRAILING_UNIT_RE = re.compile(r"\s*[A-Za-z]{2}[A-Za-z.\s]*$")
_LEADING_CURRENCY_RE = re.compile(r"^\s*[$€£¥₩]\s*")


def _sympify(text: str) -> sympy.Basic | None:
    """Parse human-written answer text as a value, trying the literal form first.

    The unit-stripping fallback runs **only after a direct parse has already failed**, so
    it cannot change the result for anything that parses today. That ordering is what
    makes it safe: `'2x'` is not silently read as `2`, because two-letter minimum keeps a
    single-letter variable from looking like a unit, and anything that does parse is never
    rewritten at all.

    Stripping a unit does not weaken the check it feeds. `check_sympy_independent_solve`
    still re-solves the expression and compares values, so `'12 minutes'` and
    `'15 minutes'` remain different answers - what changes is that both are now comparable
    instead of both being unparseable and therefore silently exempt.
    """
    normalized = _normalize_math_text(text)
    try:
        return sympy.sympify(normalized)
    except (sympy.SympifyError, TypeError, ValueError, AttributeError):
        pass
    stripped = _TRAILING_UNIT_RE.sub("", _LEADING_CURRENCY_RE.sub("", normalized)).strip()
    if not stripped or stripped == normalized:
        return None
    try:
        return sympy.sympify(stripped)
    except (sympy.SympifyError, TypeError, ValueError, AttributeError):
        return None


def _values_equal(a: sympy.Basic, b: sympy.Basic) -> bool:
    # `Basic.equals` exists at runtime (handles simplification internally, avoiding a
    # `Basic - Basic` subtraction pyright's incomplete sympy stubs don't type) but isn't
    # in the stub's declared attribute set.
    return bool(a.equals(b))  # type: ignore[attr-defined]


def answers_agree(candidate: str, expected: str) -> bool:
    """Do two human-written answer texts name the same value?

    Case- and whitespace-insensitive string equality first, then - only if that fails -
    the same numeric comparison `check_sympy_independent_solve` uses, so `'8'` and
    `'8 weeks'` agree while `'8'` and `'18'` still do not. `_sympify` only strips a unit
    *after* a direct parse has already failed, which is what keeps the fallback from
    quietly widening anything that parses today.

    Extracted from `check_hint_solution_answer_agreement` (which still uses it) so the
    serving path can apply the identical rule. `tutor.generate_solution` previously
    compared with `!=` on stripped strings and therefore discarded a correct model
    solution whenever it wrote the answer with its unit - measured live on staging
    (D-207), where the student's "show me the solution" returned a two-step placeholder
    because the model had answered `'8 weeks'` to a question whose option read `'8'`.
    """
    if candidate.strip().casefold() == expected.strip().casefold():
        return True
    candidate_value = _sympify(candidate)
    expected_value = _sympify(expected)
    if candidate_value is None or expected_value is None:
        return False
    return _values_equal(candidate_value, expected_value)


# One `=` that is not part of `==`, `<=`, `>=` or `!=`.
_RELATION_SPLIT_RE = re.compile(r"(?<![<>!=])=(?!=)")
_PARSE_TRANSFORMS = standard_transformations + (implicit_multiplication_application,)


def _parse_side(text: str) -> sympy.Basic:
    return parse_expr(text, transformations=_PARSE_TRANSFORMS, evaluate=True)


def derive_answer(equation: str) -> tuple[sympy.Basic | None, str | None]:
    """Solve the equation that models the question, returning `(value, error)`.

    This is the check that was missing rather than merely weak. `answer_expression` was
    documented as the thing SymPy solves "independently of the generator's own claim", but
    the generator wrote the *answer* into it - all five items from the first real run had
    `answer_expression: '7'`, `'4'`, `'-4'`, `'8'`, `'6'`. `sympify('7')` returns 7, so the
    gate confirmed the correct option said 7, which the generator had also said. It could
    not have caught a wrong answer, and never did (D-191).

    Requiring a *relation* is what makes it independent: `Eq(2*x + 5, x + 12)` is a claim
    about the situation, and the answer is derived from it here rather than accepted. A
    generator that models the question wrong now produces a value that disagrees with its
    own options, which is exactly the failure we want surfaced.

    Implicit multiplication is accepted (`2x + 5` as well as `2*x + 5`) because a model
    writing mathematics naturally omits the star, and rejecting that would be the same
    formatting-over-substance mistake the unit and typographic-minus fixes corrected.

    **What this cannot check.** It verifies equation -> answer, never situation ->
    equation. A model that equates two robots' *rates* instead of their *totals* gets a
    faithfully-solved wrong answer. That step is what the two independent solver agents
    exist for: they read the scenario blind and must land on the same option.
    """
    normalized = _normalize_math_text(equation, strip_assignment=False)
    try:
        if "Eq(" in normalized:
            relation = _parse_side(normalized)
        else:
            sides = _RELATION_SPLIT_RE.split(normalized)
            if len(sides) != 2:
                return None, (
                    f"equation {equation!r} is not a single equation - model the question "
                    f"as one relation with one unknown, e.g. 'Eq(3 + 7*m, 4 + 4*m)'"
                )
            relation = sympy.Eq(_parse_side(sides[0]), _parse_side(sides[1]))
    except (sympy.SympifyError, SyntaxError, TypeError, ValueError, AttributeError):
        return None, f"equation {equation!r} did not parse with SymPy"

    if not isinstance(relation, sympy.Equality):
        # `Eq(4, 4)` collapses to `BooleanTrue`, and a bare value parses to a Number -
        # both are the tautology this check exists to stop accepting.
        return None, (
            f"equation {equation!r} is not a solvable equation - it restates the answer "
            f"instead of deriving it"
        )
    unknowns = sorted(relation.free_symbols, key=str)
    if len(unknowns) != 1:
        return None, (
            f"equation {equation!r} has {len(unknowns)} unknowns, expected exactly one"
        )
    try:
        solutions = sympy.solve(relation, unknowns[0])
    except (NotImplementedError, TypeError, ValueError):
        return None, f"equation {equation!r} could not be solved by SymPy"
    if len(solutions) != 1:
        return None, (
            f"equation {equation!r} has {len(solutions)} solutions, expected exactly one"
        )
    return solutions[0], None


def check_sympy_independent_solve(
    item: AuthoredGeneratedItemResponse, result: AuthoredValidationResult
) -> None:
    """SPEC §5.8.5: derive the answer from the item's own equation and confirm it matches
    the declared correct option (and that no distractor also matches) - the same
    "recompute, don't trust" posture the shape pipeline's `check_exactly_one_correct_answer`
    has, applied to free-form authored content instead of a registered shape function.

    The equation is **required** as of D-191. It used to be optional, which meant a
    generator that omitted it skipped verification entirely - a hole that costs nothing to
    close and that a model would eventually find, since omitting a field is easier than
    getting one right.
    """
    if not item.equation:
        result.fail(
            "equation is missing - every item must model its question as a solvable "
            "equation so the answer can be derived rather than taken on trust"
        )
        return
    solved, error = derive_answer(item.equation)
    if solved is None:
        result.fail(error or f"equation {item.equation!r} could not be solved")
        return

    options = _options(item)
    matches = [
        label
        for label, text in options.items()
        if (parsed := _sympify(text)) is not None and _values_equal(parsed, solved)
    ]
    if item.correct_option not in matches:
        result.fail(
            f"SymPy-solved answer {solved} does not match declared correct option "
            f"{item.correct_option!r} ({options[item.correct_option]!r})"
        )
    elif len(matches) > 1:
        result.fail(
            f"more than one option matches the SymPy-solved answer {solved}: {matches}"
        )


def check_exactly_one_correct_answer(
    item: AuthoredGeneratedItemResponse, result: AuthoredValidationResult
) -> None:
    options = _options(item)
    correct_text = options[item.correct_option].strip().lower()
    matches = [
        label for label, text in options.items() if text.strip().lower() == correct_text
    ]
    if len(matches) != 1:
        result.fail(
            f"expected exactly one option textually matching the correct option, found "
            f"{matches}"
        )


def leak_phrase_present(text: str) -> bool:
    """Shared by authored-item validation (below) and S21's hand-authored shape hint
    ladders (`hint_ladders.py`) - a plain-string check with no dependency on
    `AuthoredGeneratedItemResponse` so both callers share one leak-phrase list.
    """
    lowered = text.lower()
    return any(phrase in lowered for phrase in _LEAK_PHRASES)


def answer_text_leaked(text: str, correct_answer_text: str) -> bool:
    """Case-insensitive check that `text` doesn't state `correct_answer_text` outright -
    shared by authored-item validation and S21's runtime personalized-hint check
    (`learning_api.services.tutor`), where `correct_answer_text` is the real answer for
    the specific question being served.

    S30 (plan §13's leak-detection evaluator, `packages/evals`) found this used a plain
    `\\b...\\b` word-boundary match, which silently never fires for any answer text that
    itself starts with a non-word character - `\\b` requires exactly one side of the
    boundary to be a word character, so `\\b-4\\b` has no boundary at all between a
    leading space and `-` (both non-word) and therefore can never match "-4" anywhere,
    even printed outright. Negative-integer answers are a real, reachable format here
    (`templates/registry.py`'s `format_integer` calls `str()` on a `Fraction` whose
    numerator can be negative), so this was a live gap in a safety-critical check, not a
    theoretical one. Replaced with explicit lookaround assertions that a boundary
    position is not immediately adjacent to another alphanumeric character on either
    side - this still rejects "4" embedded inside "24" (preceded by the digit "2") while
    correctly matching "-4" preceded by a space, punctuation, or string start.

    D-195's repeat pilot found the mirror image of that bug. The alphanumeric guards treat
    a decimal point as a boundary, so answer `"8"` matched the `8` inside `"0.8"`, and a
    correct, well-built item was rejected for `hint_ladder[2] leaks the correct answer text
    verbatim` when hint 2 merely said "Jake starts 0.8 km from the park". A single-digit
    answer in a scenario that uses decimals is not a corner case for this topic - it is
    most of them. Hence the two extra assertions: a match may not be immediately preceded
    by `<digit>.` nor immediately followed by `.<digit>`, which is precisely "this digit is
    part of a larger decimal number". `"the answer is 8."` at the end of a sentence still
    matches, because the `.` there is not followed by a digit.

    Both directions matter, and a false positive here is not harmless in either place it is
    used: in authoring it destroys correct content, and on the S21 runtime path it
    suppresses a legitimate hint for any question whose scenario contains a decimal.
    """
    correct_text = correct_answer_text.strip()
    if not correct_text:
        return False
    pattern = re.compile(
        rf"(?<![0-9A-Za-z])(?<!\d\.){re.escape(correct_text)}(?![0-9A-Za-z])(?!\.\d)",
        re.IGNORECASE,
    )
    return bool(pattern.search(text))


def answer_leaked_beyond_the_question(
    *, hint_text: str, correct_answer_text: str, question_text: str
) -> bool:
    """True when a hint states the answer AND the question does not already show it.

    `answer_text_leaked` alone cannot tell "the answer is 4" from "he buys a 4-pack", and
    that is not a fixable ambiguity in a text match - the two are the same characters. It
    destroyed four correct items before this existed: a juice-box question whose answer
    equalled the pack size, an item whose answer was the `+ 4` inside its own
    `Eq(3*(x + 4) + 10, 34)`, and two others.

    The rule that resolves it is about what the student can see. A value already printed in
    the question is one they are holding; a hint repeating it hands over nothing new, and
    an item whose answer happens to coincide with one of its given quantities is a normal
    item, not a defect (product call, 2026-08-06).

    **What this deliberately does not weaken.** `leak_phrase_present` still catches an
    explicit "the answer is 4" wherever it appears, and it is checked separately and
    unconditionally - so the escape hatch here cannot be used to state the answer outright.
    What remains uncaught is a hint that names a value which is both the answer and a given,
    without saying it is the answer; that is genuinely ambiguous to a reader too, and the
    hint-quality judge sees the whole ladder.

    Note `question_text` must be the stem and context block only. Passing the options would
    disable the check entirely, since the correct option's text *is* the answer.
    """
    if not answer_text_leaked(hint_text, correct_answer_text):
        return False
    return not answer_text_leaked(question_text, correct_answer_text)


def hint_ladder_monotonicity_violations(hint_ladder: list[str]) -> list[int]:
    """SPEC §5.8.5/plan §7: an earlier hint level must not already contain a later
    level's more-revealing content - checked as substring containment, matching the
    plan's own phrasing ("level n must not contain level n+1's revealed content").
    Returns the 1-based indices of levels found to violate this, shared by authored-item
    validation and S21's hand-authored shape ladders / runtime personalized-hint check.
    """
    violations = []
    for i in range(len(hint_ladder) - 1):
        earlier, later = hint_ladder[i], hint_ladder[i + 1]
        if later.strip() and later.strip() in earlier:
            violations.append(i + 1)
    return violations


def check_no_answer_leakage(
    item: AuthoredGeneratedItemResponse, result: AuthoredValidationResult
) -> None:
    correct_text = _options(item)[item.correct_option].strip()
    haystacks = {"stem": item.stem}
    if item.context_block:
        haystacks["context_block"] = item.context_block
    for i, level in enumerate(item.hint_ladder, start=1):
        haystacks[f"hint_ladder[{i}]"] = level

    for field_name, text in haystacks.items():
        if leak_phrase_present(text):
            result.fail(f"{field_name} contains an explicit answer-leak phrase")
    # A hint should never simply state the correct option's exact text outright - the
    # solution is where the final answer is meant to be revealed, not the hint ladder.
    # Stem and context only - never the options, whose correct entry *is* the answer.
    question_text = f"{item.context_block or ''}\n{item.stem}"
    for i, level in enumerate(item.hint_ladder, start=1):
        if answer_leaked_beyond_the_question(
            hint_text=level, correct_answer_text=correct_text, question_text=question_text
        ):
            result.fail(f"hint_ladder[{i}] leaks the correct answer text verbatim")


def check_hint_ladder_monotonicity(
    item: AuthoredGeneratedItemResponse, result: AuthoredValidationResult
) -> None:
    for i in hint_ladder_monotonicity_violations(item.hint_ladder):
        result.fail(f"hint_ladder[{i}] already reveals hint_ladder[{i + 1}]'s content")


def check_hint_solution_answer_agreement(
    item: AuthoredGeneratedItemResponse, result: AuthoredValidationResult
) -> None:
    correct_text = _options(item)[item.correct_option]
    if not answers_agree(item.canonical_solution.final_answer, correct_text):
        result.fail(
            f"canonical_solution.final_answer {item.canonical_solution.final_answer!r} "
            f"does not match the declared correct option {correct_text!r}"
        )


def check_difficulty_rubric_compliance(
    difficulty_label: int, item: AuthoredGeneratedItemResponse, result: AuthoredValidationResult
) -> None:
    if not (MIN_DIFFICULTY <= difficulty_label <= MAX_DIFFICULTY):
        result.fail(f"difficulty_label {difficulty_label} out of range")
    if item.estimated_time_seconds <= 0:
        result.fail("estimated_time_seconds must be positive")


def check_age_appropriate_wording(
    item: AuthoredGeneratedItemResponse, result: AuthoredValidationResult
) -> None:
    for text in _text_fields(item):
        for match in _DISALLOWED_WORDING_RE.finditer(text):
            result.fail(f"disallowed wording found: {match.group(0).lower()!r}")
        for sentence in re.split(r"[.!?]", text):
            word_count = len(sentence.split())
            if word_count > _MAX_WORDS_PER_SENTENCE:
                result.fail(
                    f"a sentence has {word_count} words, exceeding the "
                    f"{_MAX_WORDS_PER_SENTENCE}-word readability ceiling: {sentence[:60]!r}"
                )


def check_no_meta_commentary(
    item: AuthoredGeneratedItemResponse, result: AuthoredValidationResult
) -> None:
    """§5.8.5 "student-facing content is a finished question": reject text in which the
    model narrates its own authoring (D-195). Scoped to `_text_fields`, which is exactly
    the student-visible surface - `difficulty_rationale` and `reasoning` are written *for
    the reviewer* and are allowed, indeed expected, to discuss the authoring.
    """
    for text in _text_fields(item):
        for match in _META_COMMENTARY_RE.finditer(text):
            result.fail(
                f"student-facing text contains authoring commentary: {match.group(0).lower()!r} "
                f"- the stem must read as a finished question written to a student"
            )


def validate_authored_item(
    difficulty_label: int, item: AuthoredGeneratedItemResponse
) -> AuthoredValidationResult:
    """Runs every deterministic §5.8.5 check this module owns against one authored
    generator proposal, before any LLM solver/judge call (plan §7 step 2).
    """
    result = AuthoredValidationResult()
    check_schema_and_markdown_safety(item, result)
    check_unique_options(item, result)
    check_sympy_independent_solve(item, result)
    check_exactly_one_correct_answer(item, result)
    check_no_answer_leakage(item, result)
    check_hint_ladder_monotonicity(item, result)
    check_hint_solution_answer_agreement(item, result)
    check_difficulty_rubric_compliance(difficulty_label, item, result)
    check_age_appropriate_wording(item, result)
    check_no_meta_commentary(item, result)
    return result
