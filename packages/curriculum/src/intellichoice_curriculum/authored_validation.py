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
from tokenize import TokenError

import sympy
from intellichoice_shared.bedrock import AuthoredGeneratedItemResponse
from intellichoice_shared.figures import (
    FigureSpec,
    figure_derived_answer,
    figure_numbers_missing_from_item,
)
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
    # D-223, found by the shape half's negative controls: the list carried "died"/"dying"
    # but not the present tense, so "the character dies after x turns" passed. Distinct
    # from the "die" D-191 deliberately left off - that one is also the singular of dice,
    # a math object; "dies" in a K-12 word problem is the verb. No shipped item uses it.
    "dies",
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
    # D-278: in mathematics `^` is exponentiation; in Python it is bitwise XOR, so SymPy
    # reads `x^2` as `Xor(x, 2)` and quietly derives a different expression rather than
    # failing. Nobody writing a question means XOR, and the 6-12 wave is the first content
    # where powers are routine. Safe on both sides of the flag below: an equation with a
    # caret means the same thing an option with one does.
    "^": "**",
}
# "x = 7" as an option means the value 7 - a restated equation, not a different answer.
_ASSIGNMENT_PREFIX_RE = re.compile(r"^\s*[A-Za-z]\w*\s*=\s*")

# A thousands separator: a comma between digits, followed by exactly three more digits and
# no whitespace on either side. `sympy.sympify('4,700')` returns the *tuple* `(4, 700)`, so
# without this an option written the way a grade-4 answer is naturally written parses as two
# numbers (D-274). Found by probing the router before the 3-5 wave, where large numbers are
# routine; K-2 never reached four digits in an option and so never hit it.
#
# Deliberately narrow, because a comma is genuinely overloaded here - `_option_as_value_set`
# splits multi-root answers on it. Requiring no surrounding whitespace and exactly three
# trailing digits leaves `'3, -3'`, `'100, 200'` and `'(2, 3)'` untouched.
#
# **The one case no rule can separate is `'100,200'` written tight**: a thousands separator
# and a two-root set are the same six characters. It is read as 100200, which makes a correct
# two-root item *fail* the gate rather than pass it - the safe direction, and a review finding
# rather than a defect in front of a student.
_THOUSANDS_SEPARATOR_RE = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")


def _strip_thousands_separators(text: str) -> str:
    """`'34,281'` -> `'34281'`, leaving every other comma alone. See the regex above."""
    return _THOUSANDS_SEPARATOR_RE.sub("", text)


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
        # `strip_assignment=False` means "this is an equation", and thousands separators must
        # NOT be stripped from one. An equation is written in SymPy syntax, where a comma is
        # an argument separator: rewriting `Max(340,218)` to `Max(340218)` would silently turn
        # a comparison of two numbers into one number. The separator only ever appears in text
        # a human wrote to be *read*, which is the other branch.
        return text
    return _ASSIGNMENT_PREFIX_RE.sub("", _strip_thousands_separators(text), count=1)


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

    **Returns None for anything that is not a single value, and that is a correctness fix,
    not defensive padding** (D-274). `sympy.sympify` does not only raise or return a `Basic`
    - handed comma-separated text it returns a plain Python *tuple*, which has no `.equals`,
    so every caller that compared the result crashed with `AttributeError` instead of
    reporting a verdict. That made the gate order-dependent: `answers_agree('4,700', '4700')`
    raised while `answers_agree('4700', '4,700')` returned False. Same defect class as the
    `TokenError` that escaped `derive_answer` in Phase R - a crash where a decision belongs.
    """
    normalized = _normalize_math_text(text)
    try:
        parsed = sympy.sympify(normalized)
    except _PARSE_ERRORS:
        parsed = None
    if isinstance(parsed, sympy.Basic):
        return parsed
    stripped = _TRAILING_UNIT_RE.sub("", _LEADING_CURRENCY_RE.sub("", normalized)).strip()
    if not stripped or stripped == normalized:
        return None
    try:
        retried = sympy.sympify(stripped)
    except _PARSE_ERRORS:
        return None
    return retried if isinstance(retried, sympy.Basic) else None


def _is_whole_number(value: sympy.Basic) -> bool:
    """Is this value a whole number, however it happens to be represented?

    **Not `value.is_Integer`**, which asks about the SymPy *type* rather than the number
    (D-274). `Eq(x, 8.4 / 0.7)` solves to `Float(12.0)` - a whole number by any reading a
    student would recognise - and `is_Integer` is False for it, while `is_integer` is
    `None`. So a decimal division that comes out even was reported as "not a whole number",
    which is both wrong and, since the message told the designer to change the quantities,
    unfixable by doing what it asked.

    `.equals` is the same numeric comparison `_values_equal` uses, so a value is whole
    exactly when it equals its own floor.
    """
    try:
        return bool(value.equals(sympy.floor(value)))  # type: ignore[attr-defined]
    except _PARSE_ERRORS:
        return False


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


# Everything `parse_expr` can raise on text a person or a model wrote.
#
# **`TokenError` was missing, and its absence was a live fail-open** (found 2026-08-11 by the
# router's own rejection test). `derive_answer('Eq(x, ((')` and `derive_answer('x = (')`
# *raised* instead of returning an error, so an unbalanced paren propagated out of the §5.8.5
# gate: a curriculum load would crash rather than report the item, and the whole posture of
# this module is that an item nothing can check is rejected, not that checking it explodes.
# No shipped item is malformed, so it never fired - but every new answer form added below is
# a new way for a generator to write something this has to survive.
_PARSE_ERRORS = (
    sympy.SympifyError,
    SyntaxError,
    TokenError,
    TypeError,
    ValueError,
    AttributeError,
)


def _parse_side(text: str) -> sympy.Basic:
    """Parse one side of a relation, or raise so the caller's `except` turns it into a
    rejection.

    **The `isinstance` is the fix, and it belongs here rather than at any one call site
    (D-275).** `parse_expr` does not only raise or return a `Basic`: handed `'None'`,
    `'True'` or `'...'` it returns the plain Python object, which has no `.free_symbols`
    and no `.subs`. `route_answer` then died with `AttributeError` instead of returning
    `(None, reason)` - a crash where a verdict belongs, and the check is documented as
    fail-closed.

    Third time this codebase has hit this exact class: Phase R's `TokenError` escaping
    `derive_answer`, D-274's `sympify('4,700')` returning a tuple, and this. The first two
    were fixed at the site that reported them; this one is fixed at the shared parser, so
    all ten callers - each already wrapping this in `except _PARSE_ERRORS` - are covered
    at once. `TypeError` is a member of `_PARSE_ERRORS`, so no caller changes.
    """
    parsed = parse_expr(text, transformations=_PARSE_TRANSFORMS, evaluate=True)
    if not isinstance(parsed, sympy.Basic):
        raise TypeError(f"{text!r} parsed to {type(parsed).__name__}, not a value")
    return parsed


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
    except _PARSE_ERRORS:
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


# --------------------------------------------------------------------------------------
# The answer-model router (D-273, C1 Phase R)
#
# `derive_answer` above answers exactly one question: "what single value does this equation
# solve to?" That is the right question for most of this bank and the wrong one for the rest
# of the taxonomy, and the difference is not stylistic - measured against the real function
# on 2026-08-11, `x**2 = 9` is rejected as "has 2 solutions", `3*x + 2 > 11` as "not a single
# equation", and `Eq(x + y, 10)` as "has 2 unknowns". Every row of Algebra I - all six -
# fails on one of those three. The pipeline could not author a single item in that book.
#
# **What this does not change.** `value` items route to `derive_answer` unchanged, so all 130
# shipped items take the identical path they took before. This adds models rather than
# altering the one that works.
#
# **Two latent holes closed here, both measured at 0 of 130 and both about to become live.**
#
#   1. `Eq(x, 43)` **passes** `derive_answer` and verifies nothing - it is D-191's defect
#      wearing a relation costume. D-191 closed the bare-string form (`answer_expression:
#      '7'`) and left this one open, because the check it added tests the *shape* of the
#      model rather than whether the model does any work. It is rejected below.
#   2. `Eq(x, diff(x**2, x))` returns **0**, not `2*x` - it solves `x = 2x`. A confident
#      wrong answer with no error. Symbolic content smuggled through the value path fails
#      this way silently, which is why `symbolic` gets its own form rather than a convention.
#
# **What did NOT need building, and the measurement that saved the work.** `selection` -
# "which number is larger" - was scoped as a router family and turns out to be fully
# expressible today: `Eq(x, Max(34, 43))` derives 43. So `place_value_compare`'s 15-of-15
# reshaping into "how many more" was never forced by the gate. It is an authoring failure,
# and its repair is authoring, not code.
# --------------------------------------------------------------------------------------

_RELATIONAL_OPS = (sympy.StrictLessThan, sympy.StrictGreaterThan, sympy.LessThan, sympy.GreaterThan)

# How a multi-valued answer may be written by a human: "3 or -3", "3, -3", "3 and -3".
_ANSWER_SET_SPLIT_RE = re.compile(r"\s*(?:,|\bor\b|\band\b)\s*", re.IGNORECASE)
# "x = 2, y = 3" - strip each component's own assignment prefix before parsing.
_COMPONENT_ASSIGNMENT_RE = re.compile(r"^\s*[A-Za-z]\w*\s*=\s*")


_IDENTIFIER_ONLY_RE = re.compile(r"[A-Za-z]\w*")
_NUMERIC_LITERAL_RE = re.compile(r"[+-]?\d+(?:\.\d+)?")


def _equation_side_texts(normalized: str) -> tuple[str, str] | None:
    """The two sides of the equation **as written**, before SymPy evaluates anything.

    Needed only by the vacuous-form check, which is a question about authorship rather than
    about value: `Eq(x, 43)` and `Eq(x, Max(34, 43))` parse to the identical expression, and
    only one of them models a question.

    Splits `Eq(a, b)` at its top-level comma so a nested call (`Max(34, 43)`) stays intact.
    Returns None when the form is not one of the two it understands, and the caller then
    skips the check rather than guessing - a missed vacuous item is a review finding, while
    a false positive here would ban a legitimate form.
    """
    text = normalized.strip()
    if text.startswith("Eq(") and text.endswith(")"):
        inner = text[3:-1]
        depth = 0
        for index, char in enumerate(inner):
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            elif char == "," and depth == 0:
                return inner[:index].strip(), inner[index + 1 :].strip()
        return None
    sides = _RELATION_SPLIT_RE.split(text)
    if len(sides) == 2:
        return sides[0].strip(), sides[1].strip()
    return None


@dataclass(frozen=True)
class DerivedAnswer:
    """What the item's stated model derives, and under which answer model.

    `payload` is read according to `model` and never otherwise:

    | model | payload |
    |---|---|
    | `value` | a one-element tuple - the solution |
    | `multi_root` | every root, as a frozenset of values |
    | `interval` | the solution set, as a SymPy `Set` |
    | `tuple` | the components, ordered by their symbols' names |
    | `symbolic` | the expression itself, compared by equivalence rather than value |
    """

    model: str
    payload: object


def route_answer(equation: str) -> tuple[DerivedAnswer | None, str | None]:
    """Derive the answer under whichever model the stated equation is written in.

    Returns `(derivation, error)`, exactly one of which is populated. **Fail closed:** a form
    no model claims is an error, never a skip - an item whose answer nothing can check must
    not reach a student on the strength of nobody having checked it.

    The model is inferred from the equation's *form* rather than declared in a separate
    field, deliberately. A declared model is a second thing that can disagree with the
    first, and this project has measured what happens when a model is asked to keep two
    fields consistent (D-252: a prompt clause protecting one field scored 0 of 52). The form
    cannot disagree with itself.
    """
    normalized = _normalize_math_text(equation, strip_assignment=False)

    # A system: two or more relations, separated the way a person separates them.
    if ";" in normalized:
        return _route_system(equation, normalized)

    # An inequality. Checked before the equation split because `_RELATION_SPLIT_RE` ignores
    # the `=` in `>=`, so `x >= 3` would otherwise fall through to "not a single equation".
    if any(op in normalized for op in ("<", ">")):
        return _route_inequality(equation, normalized)

    if "Eq(" in normalized or _RELATION_SPLIT_RE.search(normalized):
        return _route_equation(equation, normalized)

    # No relation at all: the answer is an expression, judged by equivalence. A bare
    # constant is not - that is the item restating its own answer, which is the whole
    # reason `derive_answer` requires a relation (D-191).
    try:
        expression = _parse_side(normalized)
    except _PARSE_ERRORS:
        return None, f"equation {equation!r} did not parse with SymPy"
    if not expression.free_symbols:
        return None, (
            f"equation {equation!r} is a bare value, not a model of the question - it "
            f"restates the answer instead of deriving it"
        )
    return DerivedAnswer("symbolic", expression), None


def _route_equation(equation: str, normalized: str) -> tuple[DerivedAnswer | None, str | None]:
    """`Eq(...)` or `lhs = rhs`: one unknown, one or more roots."""
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
    except _PARSE_ERRORS:
        return None, f"equation {equation!r} did not parse with SymPy"

    if not isinstance(relation, sympy.Equality):
        return None, (
            f"equation {equation!r} is not a solvable equation - it restates the answer "
            f"instead of deriving it"
        )

    # Hole 1, closed - and closed on the *source text*, which took one wrong attempt to get
    # right. `Eq(x, 43)` is a valid Equality with one unknown and one solution, so every
    # structural check above passes and the "independent solve" recovers the constant the
    # author already wrote.
    #
    # The obvious test - "is the far side a number after parsing?" - **rejects
    # `Eq(x, Max(34, 43))` too**, because SymPy folds `Max(34, 43)` to `43` while parsing,
    # and `evaluate=False` does not prevent it (measured: `Max` and `gcd` both fold anyway).
    # That would have banned the exact form that makes comparison questions expressible,
    # which is the form this phase exists to promote. What separates them is not the value
    # but what the author wrote, so the check reads the text.
    side_texts = _equation_side_texts(normalized)
    if side_texts is not None:
        lhs_text, rhs_text = side_texts
        for near_text, far_text in ((lhs_text, rhs_text), (rhs_text, lhs_text)):
            if _IDENTIFIER_ONLY_RE.fullmatch(near_text) and _NUMERIC_LITERAL_RE.fullmatch(far_text):
                return None, (
                    f"equation {equation!r} states the answer rather than deriving it - the "
                    f"unknown is alone on one side and a bare number on the other, so solving "
                    f"it returns what was written. Model the question instead: "
                    f"'Eq(x, Max(34, 43))' for a comparison, 'Eq(34 + x, 43)' for a difference"
                )

    unknowns = sorted(relation.free_symbols, key=str)
    if len(unknowns) != 1:
        return None, (
            f"equation {equation!r} has {len(unknowns)} unknowns, expected exactly one - "
            f"write a system as 'Eq(...); Eq(...)' if that is what the question asks"
        )
    try:
        solutions = sympy.solve(relation, unknowns[0])
    except (NotImplementedError, TypeError, ValueError):
        return None, f"equation {equation!r} could not be solved by SymPy"
    if not solutions:
        return None, f"equation {equation!r} has no solution"
    if len(solutions) == 1:
        return DerivedAnswer("value", (solutions[0],)), None
    return DerivedAnswer("multi_root", frozenset(solutions)), None


def _route_inequality(equation: str, normalized: str) -> tuple[DerivedAnswer | None, str | None]:
    """`3*x + 2 > 11`: the answer is a solution *set*, not a value."""
    try:
        relation = _parse_side(normalized)
    except _PARSE_ERRORS:
        return None, f"inequality {equation!r} did not parse with SymPy"
    if not isinstance(relation, _RELATIONAL_OPS):
        return None, f"inequality {equation!r} did not parse as an inequality"
    unknowns = sorted(relation.free_symbols, key=str)
    if len(unknowns) != 1:
        return None, (
            f"inequality {equation!r} has {len(unknowns)} unknowns, expected exactly one"
        )
    try:
        solution_set = sympy.solveset(relation, unknowns[0], sympy.S.Reals)
    except (NotImplementedError, TypeError, ValueError):
        return None, f"inequality {equation!r} could not be solved by SymPy"
    return DerivedAnswer("interval", solution_set), None


def _route_system(equation: str, normalized: str) -> tuple[DerivedAnswer | None, str | None]:
    """`Eq(x + y, 10); Eq(x - y, 2)`: the answer is a tuple, ordered by symbol name."""
    parts = [p.strip() for p in normalized.split(";") if p.strip()]
    if len(parts) < 2:
        return None, f"system {equation!r} needs at least two equations separated by ';'"
    relations = []
    for part in parts:
        try:
            if "Eq(" in part:
                relation = _parse_side(part)
            else:
                sides = _RELATION_SPLIT_RE.split(part)
                if len(sides) != 2:
                    return None, f"system {equation!r} has a part that is not an equation: {part!r}"
                relation = sympy.Eq(_parse_side(sides[0]), _parse_side(sides[1]))
        except _PARSE_ERRORS:
            return None, f"system {equation!r} did not parse with SymPy"
        if not isinstance(relation, sympy.Equality):
            return None, f"system {equation!r} has a part that is not an equation: {part!r}"
        relations.append(relation)

    unknowns = sorted({s for r in relations for s in r.free_symbols}, key=str)
    if len(unknowns) < 2:
        return None, (
            f"system {equation!r} has {len(unknowns)} unknowns - a system the question "
            f"poses as one should have at least two"
        )
    try:
        solved = sympy.solve(relations, unknowns, dict=True)
    except (NotImplementedError, TypeError, ValueError):
        return None, f"system {equation!r} could not be solved by SymPy"
    if len(solved) != 1:
        return None, (
            f"system {equation!r} has {len(solved)} solutions, expected exactly one"
        )
    return DerivedAnswer("tuple", tuple(solved[0][s] for s in unknowns)), None


def arithmetic_identity(equation: str) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    """What calculation this item actually asks for, ignoring the story around it.

    **Measured need (D-273, C1 wave K-2).** The first 55 generated items reported 86%
    acceptance and read well one at a time. Counted by their arithmetic, **27 of the 55
    shared their number set with another item** - four separate items were `9 + 9`, three
    were `4 + 5` or `5 + 4`. Every one passed dedup, because dedup asks two questions and
    neither is about the mathematics: exact `rendered_question` text, then stem-embedding
    cosine distance. "Liam has 9 apples and gets 9 more" and "Maria has 9 stickers and gets
    9 more" are different stems by both measures and the same problem by any that matters.

    The consequence is the one D-223 measured for bank depth: a topic whose items repeat
    their arithmetic serves a student the same sum under new names, and two independently
    built exams draw it twice.

    Returns `(sorted numeric literals, sorted operators)`, so `4 + 5` and `5 + 4` collide
    while `9 + 9` and `9 - 9` do not. Deliberately coarse: it is a *duplicate* check, not an
    equivalence proof, and a false collision costs one candidate while a missed one costs a
    repeat in front of a child. Returns None when the equation does not parse, and the
    caller then skips the check - an unparseable equation is already rejected upstream by
    `route_answer`, so there is nothing to add here.
    """
    normalized = _normalize_math_text(equation, strip_assignment=False)
    numbers = tuple(sorted(re.findall(r"\d+(?:\.\d+)?", normalized)))
    if not numbers:
        return None
    operators = tuple(sorted({ch for ch in normalized if ch in "+-*/"}))
    return numbers, operators


def _option_as_value_set(text: str) -> frozenset[sympy.Basic] | None:
    """`'3 or -3'`, `'3, -3'`, `'x = 3 or x = -3'` -> {3, -3}.

    Thousands separators come out **before** the split, not after: this function splits on
    commas, so `'1,200 or -1,200'` would otherwise become four roots instead of two (D-274).
    """
    text = _strip_thousands_separators(text)
    parts = [p for p in _ANSWER_SET_SPLIT_RE.split(text.strip()) if p.strip()]
    if not parts:
        return None
    values = []
    for part in parts:
        value = _sympify(_COMPONENT_ASSIGNMENT_RE.sub("", part))
        if value is None:
            return None
        values.append(value)
    return frozenset(values)


def _option_matches(derivation: DerivedAnswer, text: str) -> bool:
    """Does this option state the derived answer, read under its own model?

    Every arm returns False rather than raising on an unparseable option, so a distractor
    nobody can parse is *not* counted as matching - the direction that keeps an ambiguous
    item from passing.
    """
    if derivation.model == "value":
        (expected,) = derivation.payload  # type: ignore[misc]
        parsed = _sympify(text)
        return parsed is not None and _values_equal(parsed, expected)

    if derivation.model == "multi_root":
        stated = _option_as_value_set(text)
        if stated is None:
            return False
        expected_roots = derivation.payload
        assert isinstance(expected_roots, frozenset)
        if len(stated) != len(expected_roots):
            return False
        return all(
            any(_values_equal(s, e) for e in expected_roots) for s in stated
        )

    if derivation.model == "interval":
        parsed = _option_as_solution_set(text)
        return parsed is not None and parsed == derivation.payload

    if derivation.model == "tuple":
        parsed = _option_as_tuple(text)
        expected_components = derivation.payload
        assert isinstance(expected_components, tuple)
        if parsed is None or len(parsed) != len(expected_components):
            return False
        return all(_values_equal(p, e) for p, e in zip(parsed, expected_components, strict=True))

    if derivation.model == "symbolic":
        # **Parsed the way the EQUATION was parsed, not the way a value option is (D-278).**
        # `_sympify` is `sympy.sympify`, which has no implicit multiplication; `_parse_side`
        # carries `_PARSE_TRANSFORMS`, which does. So `2x(x + 1)(x + 3)` - the natural way
        # anyone writes a factored answer, and a form the equation side has accepted since
        # D-191 on the grounds that "a model writing mathematics naturally omits the star" -
        # failed to parse as an *option* and the item was rejected as wrong. Measured on the
        # 6-12 wave: correct factorisations rejected across every symbolic skill.
        #
        # Scoped to this arm on purpose. Turning implicit multiplication on inside `_sympify`
        # would change what a *value* option means: `'12 minutes'` currently fails the direct
        # parse and reaches the unit-stripping fallback, and with transforms on it would
        # succeed as a product of eight symbols and never get there.
        expression: sympy.Basic | None
        try:
            expression = _parse_side(_normalize_math_text(text))
        except _PARSE_ERRORS:
            expression = _sympify(text)
        if expression is None:
            return False
        expected_expression = derivation.payload
        assert isinstance(expected_expression, sympy.Basic)
        # Equivalence, not equality: `(x-3)*(x+3)` and `x**2 - 9` are the same answer
        # written two ways, and an author who writes either should not be rejected for it.
        try:
            return bool(sympy.simplify(expression - expected_expression) == 0)  # type: ignore[operator]
        except (TypeError, ValueError, AttributeError):
            return False

    return False


def _option_as_solution_set(text: str) -> sympy.Set | None:
    """`'x > 3'` -> the same `Set` `solveset` returns, so the two are comparable.

    **A trailing unit is stripped, and only after a direct parse has failed (D-280.)** A
    word problem's answer carries one - `'x >= 6 weeks'`, `'t < 12 hours'` - and without this
    the interval arm was the only answer model that could not read the way its own questions
    are written. Measured on the 6-12 wave: correct inequality items rejected across
    `alg1_inequalities` and `g68_wp_inequalities`.

    `_sympify` has had this fallback since D-191 for exactly the same reason, with the same
    ordering rule: anything that parses as written is never rewritten, so nothing that
    works today can change meaning. Strictness is untouched - `'x > 6'` still does not match
    `Interval(6, oo)`, because the unit is the only thing removed.
    """
    normalized = _normalize_math_text(text, strip_assignment=False)
    if not any(op in normalized for op in ("<", ">")):
        return None

    def _usable(candidate: str) -> sympy.Basic | None:
        """A relation in exactly one unknown, or None."""
        try:
            parsed = _parse_side(candidate)
        except _PARSE_ERRORS:
            return None
        if not isinstance(parsed, _RELATIONAL_OPS):
            return None
        return parsed if len(parsed.free_symbols) == 1 else None

    # The retry is on an UNUSABLE result, not merely an unparseable one - which is the
    # subtlety that made a first attempt at this fix do nothing. `_parse_side` carries
    # implicit multiplication, so `'x >= 6 weeks'` parses happily as `x >= 6*w*e*e*k*s`
    # and fails later on the unknown count. Catching only the exception left the fallback
    # unreachable for every unit that is a word.
    relation = _usable(normalized)
    if relation is None:
        stripped = _TRAILING_UNIT_RE.sub("", normalized).strip()
        if stripped and stripped != normalized:
            relation = _usable(stripped)
    if relation is None:
        return None
    unknowns = sorted(relation.free_symbols, key=str)
    try:
        return sympy.solveset(relation, unknowns[0], sympy.S.Reals)
    except (NotImplementedError, TypeError, ValueError):
        return None


def _option_as_tuple(text: str) -> tuple[sympy.Basic, ...] | None:
    """`'(2, 3)'` or `'x = 2, y = 3'` -> (2, 3), ordered as written.

    Ordered as written is only correct because `_route_system` orders its components by
    symbol name and an author writing `x` before `y` matches that. A question whose
    variables are not alphabetical in the order the option states them would need the
    option to name them - which `_COMPONENT_ASSIGNMENT_RE` strips, so it is not read here.
    That limit is real and is why systems are worth one careful review each.

    Thousands separators come out before the comma split, for the same reason as
    `_option_as_value_set`: `'(1,200, 3)'` is a two-component tuple, not a four-component one.
    """
    stripped = _strip_thousands_separators(text).strip().strip("()").strip()
    parts = [p for p in re.split(r"\s*,\s*", stripped) if p.strip()]
    if len(parts) < 2:
        return None
    values = []
    for part in parts:
        value = _sympify(_COMPONENT_ASSIGNMENT_RE.sub("", part))
        if value is None:
            return None
        values.append(value)
    return tuple(values)


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
    derivation, error = route_answer(item.equation)
    if derivation is None:
        result.fail(error or f"equation {item.equation!r} could not be solved")
        return

    options = _options(item)
    matches = [label for label, text in options.items() if _option_matches(derivation, text)]
    derived = derivation.payload
    if item.correct_option not in matches:
        result.fail(
            f"{derivation.model} answer {derived} derived from the equation does not match "
            f"declared correct option {item.correct_option!r} "
            f"({options[item.correct_option]!r})"
        )
    elif len(matches) > 1:
        result.fail(
            f"more than one option matches the derived {derivation.model} answer "
            f"{derived}: {matches}"
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

    **The name is broader than the check, and that gap is deliberate (D-251).** This is
    verbatim containment and nothing else: `later.strip() in earlier`. It does not fire on a
    paraphrase, on a reordered ladder, or on a rung that adds nothing new in different words -
    all of which are failures of progression that this function will report as clean.

    It is kept because what it *does* cover it covers exactly and for free, which is the bar
    for a deterministic check here. Real rung-to-rung progression is a semantic judgment and
    belongs to LLM review (HINT_SOLUTION_REVIEW.md §3). **Do not read the name and conclude
    monotonicity is handled**, and do not widen this into a heuristic - a fuzzy "novelty"
    string rule would punish legitimate restatement and reward synonym-swapping, which is the
    D-249 failure mode one layer down.
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


def disallowed_wording_found(text: str) -> list[str]:
    """The disallowed words present in `text`, lowercased, in order of appearance.

    Public so the *shape* half of the §5.8.5 gate (`validation.check_age_appropriate_wording`)
    can call the same matcher rather than keeping its own copy - which is how it came to still
    be running the pre-D-191 rule: a four-word tuple matched as a plain substring, so "skill"
    read as "kill", "studies" and "diet" as "die". Sharing is the fix that holds; the same
    list, matched two ways, drifts again the next time either side is corrected.
    """
    return [match.group(0).lower() for match in _DISALLOWED_WORDING_RE.finditer(text)]


def check_age_appropriate_wording(
    item: AuthoredGeneratedItemResponse, result: AuthoredValidationResult
) -> None:
    for text in _text_fields(item):
        for word in disallowed_wording_found(text):
            result.fail(f"disallowed wording found: {word!r}")
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


def check_figure_agrees_with_the_question(
    figure: FigureSpec | None,
    item: AuthoredGeneratedItemResponse,
    result: AuthoredValidationResult,
) -> None:
    """Every number in the figure must appear somewhere in the item (D-279).

    A figure is the only part of an item not derived from the verified equation, so this is
    the property that keeps it honest: a clock showing 3:45 beside a stem about 4:15 is a
    defect no other check can see and a reader can miss. Reads the options and the solution
    as well as the stem, because for "what time does this clock show" the numbers are
    deliberately *not* in the stem - they are the answer.
    """
    if figure is None:
        return
    solution = " ".join(
        [step.expression or "" for step in item.canonical_solution.steps]
        + [item.canonical_solution.final_answer]
    )
    text = " ".join(
        [
            item.stem,
            item.context_block or "",
            item.option_a,
            item.option_b,
            item.option_c,
            item.option_d,
            solution,
        ]
    )
    missing = figure_numbers_missing_from_item(figure, item_text=text)
    if missing:
        result.fail(
            f"figure carries {missing} which appear nowhere in the question, its options or "
            f"its solution - a figure must be about the item it is attached to"
        )


def check_reading_matches_the_figure(
    figure: FigureSpec | None,
    reading: str | None,
    item: AuthoredGeneratedItemResponse,
    result: AuthoredValidationResult,
) -> None:
    """For a question the figure *answers*, the figure is what verifies it (D-279).

    `check_sympy_independent_solve` cannot help here: "what time does this clock show" has
    no arithmetic, so `derive_answer` produces a number and the option says "3:45" - the
    exact mismatch that made `Museum B` fail in the 3-5 wave. A figure determines its own
    answer, though, so it can play the part the equation plays everywhere else.

    Fails closed on a reading the figure cannot answer, rather than skipping: an item
    declaring `chart_max_label` over a clock is precisely the mismatch worth catching.
    """
    if reading is None:
        return
    if figure is None:
        result.fail(f"figure_reading {reading!r} is declared but the item has no figure")
        return
    expected = figure_derived_answer(figure, reading)
    if expected is None:
        result.fail(
            f"figure_reading {reading!r} does not apply to a {figure.kind} figure"
        )
        return
    declared = _options(item)[item.correct_option]
    if _normalise_for_reading(declared) != _normalise_for_reading(expected):
        result.fail(
            f"the figure reads {expected!r}, but the declared correct option "
            f"{item.correct_option!r} says {declared!r}"
        )
        return
    others = [
        label
        for label, text in _options(item).items()
        if label != item.correct_option
        and _normalise_for_reading(text) == _normalise_for_reading(expected)
    ]
    if others:
        result.fail(f"more than one option states what the figure reads: {others}")


def _normalise_for_reading(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def validate_authored_item(
    difficulty_label: int,
    item: AuthoredGeneratedItemResponse,
    *,
    figure: FigureSpec | None = None,
    figure_reading: str | None = None,
) -> AuthoredValidationResult:
    """Runs every deterministic §5.8.5 check this module owns against one authored
    generator proposal, before any LLM solver/judge call (plan §7 step 2).

    `figure` is optional and defaults to None, which is what the *pipeline* passes: family-C
    items are authored deterministically rather than generated (D-279), so the generator's
    response schema is untouched and no structured-output contract had to change. The loader
    passes the figure from the bank file, so one gate covers both paths.
    """
    result = AuthoredValidationResult()
    check_figure_agrees_with_the_question(figure, item, result)
    check_reading_matches_the_figure(figure, figure_reading, item, result)
    check_schema_and_markdown_safety(item, result)
    check_unique_options(item, result)
    # A reading REPLACES the equation as the source of truth, so the two answer-derivation
    # checks are skipped for it - not weakened, exchanged. `check_reading_matches_the_figure`
    # above does the same job from the figure, including the "no other option matches" arm.
    if figure_reading is None:
        check_sympy_independent_solve(item, result)
        check_exactly_one_correct_answer(item, result)
    check_no_answer_leakage(item, result)
    check_hint_ladder_monotonicity(item, result)
    check_hint_solution_answer_agreement(item, result)
    check_difficulty_rubric_compliance(difficulty_label, item, result)
    check_age_appropriate_wording(item, result)
    check_no_meta_commentary(item, result)
    return result
