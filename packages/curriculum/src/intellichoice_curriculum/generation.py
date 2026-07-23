"""Deterministic question-variant generation from a template + seed (SPEC §5.8.1, §5.8.6)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from intellichoice_curriculum.templates.registry import (
    CORRECT_OPTION_GENERATORS,
    DISTRACTOR_GENERATORS,
    SHAPES,
    ParameterSchema,
)


class VariantGenerationError(Exception):
    """A template could not produce a valid variant (shape bug or bounds too tight)."""


@dataclass(frozen=True)
class GeneratedVariant:
    random_seed: int
    rendered_question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    parameter_values: dict


_OPTION_LABELS = ["a", "b", "c", "d"]
_MAX_DISTRACTOR_ATTEMPTS = 50


def generate_variant(
    *,
    shape_key: str,
    parameter_schema: ParameterSchema,
    correct_option_generator: str,
    distractor_generator_keys: list[str],
    seed: int,
) -> GeneratedVariant:
    shape = SHAPES.get(shape_key)
    if shape is None:
        raise VariantGenerationError(f"unknown shape {shape_key!r}")
    formatter = CORRECT_OPTION_GENERATORS.get(correct_option_generator)
    if formatter is None:
        raise VariantGenerationError(
            f"unknown correct_option_generator {correct_option_generator!r}"
        )
    for key in distractor_generator_keys:
        if key not in DISTRACTOR_GENERATORS:
            raise VariantGenerationError(f"unknown distractor_generator {key!r}")

    rng = random.Random(seed)
    params = shape.sample_parameters(rng, parameter_schema)
    correct_value = shape.solve(params)
    rendered_question = shape.render(params)
    correct_text = formatter(correct_value)

    option_texts: list[str] | None = None
    for _ in range(_MAX_DISTRACTOR_ATTEMPTS):
        candidate = [correct_text]
        for key in distractor_generator_keys:
            value = DISTRACTOR_GENERATORS[key](params, correct_value, rng)
            candidate.append(formatter(value))
        if len(set(candidate)) == len(candidate):
            option_texts = candidate
            break
    if option_texts is None:
        raise VariantGenerationError("could not generate unique distractor options")

    order = list(range(len(option_texts)))
    rng.shuffle(order)
    shuffled = [option_texts[i] for i in order]
    correct_option = _OPTION_LABELS[order.index(0)]

    return GeneratedVariant(
        random_seed=seed,
        rendered_question=rendered_question,
        option_a=shuffled[0],
        option_b=shuffled[1],
        option_c=shuffled[2],
        option_d=shuffled[3],
        correct_option=correct_option,
        parameter_values=params,
    )
