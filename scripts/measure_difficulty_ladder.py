"""Does a skill's difficulty ladder actually ascend? (D-287)

The hand audit (D-285) found three "mean of five numbers" items at d1, d2 and d3 that were
the same task with different digits. Every automated check in this pipeline scores an item
**against a rubric, on its own**: the judge reads one question and rates it 1-5, and a
disagreement of 2 or more with the slot's tier rejects it. Nothing anywhere asks whether d3
is harder than d2 *for this skill*. A ladder whose rungs are level passes every check.

**What "ascends" means here, operationally.** A tier is compared only to the tier directly
below it in the same skill, and it counts as a real step if **either**:

1. it uses an **equation shape** that no lower tier used - `Eq(#*x + #, #)` after
   `Eq(x, # + #)` is a new kind of problem; or
2. its **numbers are bigger** - mean largest operand at least 5% above the tier below.

Two signals rather than one because the skills need different things. For `alg1_quadratics`
the shape is the difficulty and the digits are incidental; for `g1_add_within_20` the shape
is `Eq(x, # + #)` forever and the difficulty is entirely in whether the operands cross ten.
Scoring only shape would condemn every arithmetic-fluency skill; scoring only magnitude
would condemn every structural one.

**This reports; it does not reject.** A gate here would refuse correct content: 9 + 8 and
7 + 2 are the same shape and nearly the same magnitude, and one is genuinely harder for a
six-year-old in a way no expression captures. The output is for whoever authors the next
wave, not for the pipeline.

Free: no model call, no database - reads the exported bank, which is what ships.

Run: uv run python scripts/measure_difficulty_ladder.py [--show 12]
"""

from __future__ import annotations

import argparse
import glob
import pathlib
import re
from collections import defaultdict

import yaml

_BANK = pathlib.Path(__file__).resolve().parents[1] / "curriculum" / "internal_math" / "authored"
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

# How much bigger the numbers must get to count as a step. Deliberately small: the claim is
# only "this tier is not a repeat of the one below", not "this tier is appropriately harder",
# and a large threshold would start asserting the second.
_MAGNITUDE_HEADROOM = 1.05


def shape_of(equation: str) -> str:
    return _NUMBER_RE.sub("#", equation)


def magnitude_of(equation: str) -> float:
    numbers = [abs(float(n)) for n in _NUMBER_RE.findall(equation)]
    return max(numbers) if numbers else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", type=int, default=12, help="flat rungs to print (12)")
    args = parser.parse_args()

    shapes: dict[tuple[str, str], dict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    magnitudes: dict[tuple[str, str], dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for path in sorted(glob.glob(str(_BANK / "*.yaml"))):
        for template in yaml.safe_load(pathlib.Path(path).read_text())["templates"]:
            equation = template.get("answer_expression")
            if not equation:
                continue  # family-C: verified by its figure, and it has no ladder to score
            key = (template["topic_id"], template["skill_id"])
            tier = template["difficulty_label"]
            shapes[key][tier].add(shape_of(equation))
            magnitudes[key][tier].append(magnitude_of(equation))

    flat: list[tuple[tuple[str, str], int, str, float, float]] = []
    rungs = 0
    for key, tiers in shapes.items():
        if len(tiers) < 3:
            continue  # a two-tier skill has too little ladder to judge
        seen: set[str] = set()
        previous: float | None = None
        for tier in sorted(tiers):
            mean = sum(magnitudes[key][tier]) / len(magnitudes[key][tier])
            if previous is not None:
                rungs += 1
                new_shape = bool(shapes[key][tier] - seen)
                bigger = mean > previous * _MAGNITUDE_HEADROOM
                if not new_shape and not bigger:
                    flat.append((key, tier, sorted(shapes[key][tier])[0], previous, mean))
            seen |= shapes[key][tier]
            previous = mean

    skills = len({k for k in shapes if len(shapes[k]) >= 3})
    print(f"\nSkills with three or more tiers : {skills}")
    print(f"Rungs compared to the one below : {rungs}")
    share = 100 * len(flat) / rungs if rungs else 0.0
    print(f"  FLAT - no new shape, no bigger numbers: {len(flat)}  ({share:.0f}%)\n")

    # Worst first: a rung whose numbers actually *shrank* is a ladder pointing downhill.
    for (topic, skill), tier, shape, before, after in sorted(flat, key=lambda r: r[4] - r[3])[
        : args.show
    ]:
        direction = "SHRANK" if after < before else "flat"
        print(f"  {topic}/{skill} d{tier}: {shape[:56]}")
        print(f"      mean largest operand {before:.0f} -> {after:.0f}  ({direction})")


if __name__ == "__main__":
    main()
