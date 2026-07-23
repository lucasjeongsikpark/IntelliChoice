"""Template "shape" registry for hand-authored question templates (SPEC §5.8.2).

`QuestionTemplate.solution_function`, `.correct_option_generator`, and
`.distractor_generators` are stored as plain strings and resolved through this
registry at generation time — never `eval`'d or executed as arbitrary code. Each
"shape" bundles the three things that always travel together for one equation form:
how to sample its integer parameters from a seeded RNG, how to render the question
text, and how to solve it (recomputing the answer from the rendered parameters,
the way an independent solver agent would in the S9 pipeline).

Every shape is constructed so the correct answer is guaranteed to be an exact
integer (SPEC §5.8.1 "x is integer" constraint) — parameters are derived from a
chosen integer answer rather than solved after the fact.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from typing import NotRequired, TypedDict


class ParamBounds(TypedDict):
    min: int
    max: int
    exclude: NotRequired[list[int]]


ParameterSchema = dict[str, ParamBounds]
Params = dict[str, int]


def _sample_int(rng: random.Random, bounds: ParamBounds) -> int:
    exclude = set(bounds.get("exclude", []))
    for _ in range(200):
        value = rng.randint(bounds["min"], bounds["max"])
        if value not in exclude:
            return value
    raise RuntimeError(f"could not sample a value satisfying bounds {bounds}")


@dataclass(frozen=True)
class ShapeSpec:
    key: str
    sample_parameters: Callable[[random.Random, ParameterSchema], Params]
    render: Callable[[Params], str]
    solve: Callable[[Params], Fraction]


SHAPES: dict[str, ShapeSpec] = {}


def _register(shape: ShapeSpec) -> None:
    SHAPES[shape.key] = shape


# --- one_step_add: x + b = c ------------------------------------------------
def _one_step_add_sample(rng: random.Random, schema: ParameterSchema) -> Params:
    b = _sample_int(rng, schema["b"])
    x = _sample_int(rng, schema["x"])
    return {"b": b, "c": x + b}


def _one_step_add_render(params: Params) -> str:
    return f"Solve for x: x + {params['b']} = {params['c']}"


def _one_step_add_solve(params: Params) -> Fraction:
    return Fraction(params["c"] - params["b"])


_register(
    ShapeSpec("one_step_add", _one_step_add_sample, _one_step_add_render, _one_step_add_solve)
)


# --- one_step_sub: x - b = c ------------------------------------------------
def _one_step_sub_sample(rng: random.Random, schema: ParameterSchema) -> Params:
    b = _sample_int(rng, schema["b"])
    x = _sample_int(rng, schema["x"])
    return {"b": b, "c": x - b}


def _one_step_sub_render(params: Params) -> str:
    return f"Solve for x: x - {params['b']} = {params['c']}"


def _one_step_sub_solve(params: Params) -> Fraction:
    return Fraction(params["c"] + params["b"])


_register(
    ShapeSpec("one_step_sub", _one_step_sub_sample, _one_step_sub_render, _one_step_sub_solve)
)


# --- one_step_mul: a*x = c ---------------------------------------------------
def _one_step_mul_sample(rng: random.Random, schema: ParameterSchema) -> Params:
    a = _sample_int(rng, schema["a"])
    x = _sample_int(rng, schema["x"])
    return {"a": a, "c": a * x}


def _one_step_mul_render(params: Params) -> str:
    return f"Solve for x: {params['a']}x = {params['c']}"


def _one_step_mul_solve(params: Params) -> Fraction:
    return Fraction(params["c"], params["a"])


_register(
    ShapeSpec("one_step_mul", _one_step_mul_sample, _one_step_mul_render, _one_step_mul_solve)
)


# --- two_step: a*x + b = c ---------------------------------------------------
def _two_step_sample(rng: random.Random, schema: ParameterSchema) -> Params:
    a = _sample_int(rng, schema["a"])
    b = _sample_int(rng, schema["b"])
    x = _sample_int(rng, schema["x"])
    return {"a": a, "b": b, "c": a * x + b}


def _two_step_render(params: Params) -> str:
    return f"Solve for x: {params['a']}x + {params['b']} = {params['c']}"


def _two_step_solve(params: Params) -> Fraction:
    return Fraction(params["c"] - params["b"], params["a"])


_register(ShapeSpec("two_step", _two_step_sample, _two_step_render, _two_step_solve))


# --- two_step_sub_b: a*x - b = c ---------------------------------------------
def _two_step_sub_b_sample(rng: random.Random, schema: ParameterSchema) -> Params:
    a = _sample_int(rng, schema["a"])
    b = _sample_int(rng, schema["b"])
    x = _sample_int(rng, schema["x"])
    return {"a": a, "b": b, "c": a * x - b}


def _two_step_sub_b_render(params: Params) -> str:
    return f"Solve for x: {params['a']}x - {params['b']} = {params['c']}"


def _two_step_sub_b_solve(params: Params) -> Fraction:
    return Fraction(params["c"] + params["b"], params["a"])


_register(
    ShapeSpec(
        "two_step_sub_b", _two_step_sub_b_sample, _two_step_sub_b_render, _two_step_sub_b_solve
    )
)


# --- frac_coeff: x/d + b = c -------------------------------------------------
def _frac_coeff_sample(rng: random.Random, schema: ParameterSchema) -> Params:
    d = _sample_int(rng, schema["d"])
    b = _sample_int(rng, schema["b"])
    x_over_d = _sample_int(rng, schema["x_over_d"])
    return {"d": d, "b": b, "c": x_over_d + b}


def _frac_coeff_render(params: Params) -> str:
    return f"Solve for x: x/{params['d']} + {params['b']} = {params['c']}"


def _frac_coeff_solve(params: Params) -> Fraction:
    return Fraction(params["d"]) * Fraction(params["c"] - params["b"])


_register(ShapeSpec("frac_coeff", _frac_coeff_sample, _frac_coeff_render, _frac_coeff_solve))


# --- neg_coeff: -a*x + b = c --------------------------------------------------
def _neg_coeff_sample(rng: random.Random, schema: ParameterSchema) -> Params:
    a = _sample_int(rng, schema["a"])
    b = _sample_int(rng, schema["b"])
    x = _sample_int(rng, schema["x"])
    return {"a": a, "b": b, "c": -a * x + b}


def _neg_coeff_render(params: Params) -> str:
    return f"Solve for x: -{params['a']}x + {params['b']} = {params['c']}"


def _neg_coeff_solve(params: Params) -> Fraction:
    return Fraction(params["b"] - params["c"], params["a"])


_register(ShapeSpec("neg_coeff", _neg_coeff_sample, _neg_coeff_render, _neg_coeff_solve))


# --- both_sides: a*x + b = d*x + e -------------------------------------------
def _both_sides_sample(rng: random.Random, schema: ParameterSchema) -> Params:
    for _ in range(200):
        a = _sample_int(rng, schema["a"])
        d = _sample_int(rng, schema["d"])
        if a != d:
            break
    else:
        raise RuntimeError("could not sample a != d for both_sides")
    b = _sample_int(rng, schema["b"])
    x = _sample_int(rng, schema["x"])
    e = (a - d) * x + b
    return {"a": a, "d": d, "b": b, "e": e}


def _both_sides_render(params: Params) -> str:
    return f"Solve for x: {params['a']}x + {params['b']} = {params['d']}x + {params['e']}"


def _both_sides_solve(params: Params) -> Fraction:
    return Fraction(params["e"] - params["b"], params["a"] - params["d"])


_register(ShapeSpec("both_sides", _both_sides_sample, _both_sides_render, _both_sides_solve))


# --- both_sides_alt: a*x - b = d*x + e ----------------------------------------
def _both_sides_alt_sample(rng: random.Random, schema: ParameterSchema) -> Params:
    for _ in range(200):
        a = _sample_int(rng, schema["a"])
        d = _sample_int(rng, schema["d"])
        if a != d:
            break
    else:
        raise RuntimeError("could not sample a != d for both_sides_alt")
    b = _sample_int(rng, schema["b"])
    x = _sample_int(rng, schema["x"])
    e = (a - d) * x - b
    return {"a": a, "d": d, "b": b, "e": e}


def _both_sides_alt_render(params: Params) -> str:
    return f"Solve for x: {params['a']}x - {params['b']} = {params['d']}x + {params['e']}"


def _both_sides_alt_solve(params: Params) -> Fraction:
    return Fraction(params["e"] + params["b"], params["a"] - params["d"])


_register(
    ShapeSpec(
        "both_sides_alt", _both_sides_alt_sample, _both_sides_alt_render, _both_sides_alt_solve
    )
)


# --- distribute_simple: a*(x - b) = c -----------------------------------------
def _distribute_simple_sample(rng: random.Random, schema: ParameterSchema) -> Params:
    a = _sample_int(rng, schema["a"])
    b = _sample_int(rng, schema["b"])
    x = _sample_int(rng, schema["x"])
    return {"a": a, "b": b, "c": a * (x - b)}


def _distribute_simple_render(params: Params) -> str:
    return f"Solve for x: {params['a']}(x - {params['b']}) = {params['c']}"


def _distribute_simple_solve(params: Params) -> Fraction:
    return Fraction(params["c"], params["a"]) + params["b"]


_register(
    ShapeSpec(
        "distribute_simple",
        _distribute_simple_sample,
        _distribute_simple_render,
        _distribute_simple_solve,
    )
)


# --- distribute_combine: a*(x + b) + d*x = c ----------------------------------
def _distribute_combine_sample(rng: random.Random, schema: ParameterSchema) -> Params:
    for _ in range(200):
        a = _sample_int(rng, schema["a"])
        d = _sample_int(rng, schema["d"])
        if a + d != 0:
            break
    else:
        raise RuntimeError("could not sample a + d != 0 for distribute_combine")
    b = _sample_int(rng, schema["b"])
    x = _sample_int(rng, schema["x"])
    c = (a + d) * x + a * b
    return {"a": a, "b": b, "d": d, "c": c}


def _distribute_combine_render(params: Params) -> str:
    return f"Solve for x: {params['a']}(x + {params['b']}) + {params['d']}x = {params['c']}"


def _distribute_combine_solve(params: Params) -> Fraction:
    return Fraction(params["c"] - params["a"] * params["b"], params["a"] + params["d"])


_register(
    ShapeSpec(
        "distribute_combine",
        _distribute_combine_sample,
        _distribute_combine_render,
        _distribute_combine_solve,
    )
)


# --- correct-option formatting -----------------------------------------------
def format_integer(value: Fraction) -> str:
    if value.denominator != 1:
        raise ValueError(f"expected an integer answer, got {value}")
    return str(value.numerator)


CORRECT_OPTION_GENERATORS: dict[str, Callable[[Fraction], str]] = {
    "format_integer": format_integer,
}


# --- distractor generators -----------------------------------------------------
# Each returns a plausible wrong answer modeling a specific student error
# (SPEC §5.8.2 common_error_tags). Distractor uniqueness against the correct
# answer and each other is enforced by the caller (generation.py), not here.
DistractorFn = Callable[[Params, Fraction, random.Random], Fraction]


def distractor_sign_flip(params: Params, correct: Fraction, rng: random.Random) -> Fraction:
    flipped = -correct
    return flipped if flipped != correct else correct + 1


def distractor_off_by_one(params: Params, correct: Fraction, rng: random.Random) -> Fraction:
    return correct + rng.choice([-1, 1])


def distractor_scaled(params: Params, correct: Fraction, rng: random.Random) -> Fraction:
    return correct + rng.choice([-5, -4, -3, -2, 2, 3, 4, 5])


DISTRACTOR_GENERATORS: dict[str, DistractorFn] = {
    "distractor_sign_flip": distractor_sign_flip,
    "distractor_off_by_one": distractor_off_by_one,
    "distractor_scaled": distractor_scaled,
}
