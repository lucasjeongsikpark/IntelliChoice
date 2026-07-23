"""Hand-authored canonical hint ladders for the shape-based template bank (SPEC
§5.11.4, ROADMAP S21). Unlike S20's authored items, a shape has no single stem or
correct-answer text - the same `ShapeSpec` renders countless numeric variants from
different seeds - so these ladders are static, per-shape, and describe *method* only
(which operation to apply and why), never a sampled number or a computed value. Keyed
by `ShapeSpec.key` / `QuestionTemplate.solution_function` (the existing shape lookup,
`templates/registry.py::SHAPES`), one entry per registered shape.

Validated by `tests/test_hint_ladders.py` against the same leak-phrase and
monotonicity checks `authored_validation.py` runs for S20's LLM-authored ladders
(shared pure functions, not duplicated) - exactly `_REQUIRED_HINT_LEVELS` (3) levels
each, escalating from general strategy to the concrete next step.
"""

from __future__ import annotations

SHAPE_HINT_LADDERS: dict[str, list[str]] = {
    "one_step_add": [
        "This equation has one thing added to x. Think about what operation "
        "would undo an addition.",
        "Subtract the number that's added to x from both sides of the equation.",
        "Subtract that number from the value on the right side of the equals "
        "sign - whatever is left is x.",
    ],
    "one_step_sub": [
        "This equation has one thing subtracted from x. Think about what "
        "operation would undo a subtraction.",
        "Add the number that's subtracted from x to both sides of the equation.",
        "Add that number to the value on the right side of the equals sign - "
        "whatever you get is x.",
    ],
    "one_step_mul": [
        "x is being multiplied by a number here. Think about what operation "
        "would undo a multiplication.",
        "Divide both sides of the equation by the number multiplying x.",
        "Divide the number on the right side of the equals sign by x's "
        "coefficient - that quotient is x.",
    ],
    "two_step": [
        "This equation has two things happening to x: a multiplication and an "
        "addition. Undo them in reverse order.",
        "First subtract the added number from both sides, then divide both "
        "sides by x's coefficient.",
        "Subtract the added number from the right side first, then divide "
        "what's left by the coefficient in front of x.",
    ],
    "two_step_sub_b": [
        "This equation has two things happening to x: a multiplication and a "
        "subtraction. Undo them in reverse order.",
        "First add the subtracted number to both sides, then divide both "
        "sides by x's coefficient.",
        "Add the subtracted number to the right side first, then divide "
        "what's left by the coefficient in front of x.",
    ],
    "frac_coeff": [
        "x is being divided by a number here, plus something is added. Undo "
        "the addition first, then the division.",
        "First subtract the added number from both sides, then multiply both "
        "sides by the number x is divided by.",
        "Subtract the added number from the right side first, then multiply "
        "what's left by the number under x.",
    ],
    "neg_coeff": [
        "x's coefficient here is negative. Think about what two operations "
        "would undo a negative multiplication and an addition.",
        "First subtract the added number from both sides, then divide both "
        "sides by the negative coefficient in front of x.",
        "Subtract the added number from the right side first, then divide "
        "what's left by the negative number in front of x - watch the sign.",
    ],
    "both_sides": [
        "x appears on both sides of this equation. Try to gather all the x "
        "terms on one side and all the plain numbers on the other.",
        "Subtract the smaller x term from both sides so x only appears once, "
        "then subtract or add to isolate it.",
        "Move every x term to one side and every constant to the other, then "
        "divide by whatever coefficient is left in front of x.",
    ],
    "both_sides_alt": [
        "x appears on both sides of this equation, and one side has a "
        "subtraction. Try to gather all the x terms on one side and all the "
        "plain numbers on the other.",
        "Subtract the smaller x term from both sides so x only appears once, "
        "then add or subtract to isolate it.",
        "Move every x term to one side and every constant to the other, then "
        "divide by whatever coefficient is left in front of x - watch the "
        "sign on the subtracted number.",
    ],
    "distribute_simple": [
        "There's a number multiplying a group in parentheses. Think about "
        "distributing it across both terms inside.",
        "Divide both sides by the number outside the parentheses first, then "
        "add the number that was being subtracted inside.",
        "Divide the right side by the outside number, then add the inside "
        "number to what's left - that's x.",
    ],
    "distribute_combine": [
        "There's a distribution to do, and x also appears outside the "
        "parentheses. Distribute first, then combine the x terms.",
        "Distribute the outside number across the parentheses, combine the x "
        "terms into one, then isolate x.",
        "After distributing and combining like terms, subtract the constant "
        "from the right side and divide by the combined x coefficient.",
    ],
}
