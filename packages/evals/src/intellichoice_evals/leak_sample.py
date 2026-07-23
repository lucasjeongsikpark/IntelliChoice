"""SPEC §5.31.2 executable evaluator: hint-leak detection (plan §13).

Reuses `intellichoice_curriculum.authored_validation`'s existing `leak_phrase_present`/
`answer_text_leaked` - both already run for real, on every generated hint/chat reply, at
S20's pipeline gate and S21/S24's runtime fallback checks (`learning_api.services.tutor`/
`tutor_chat`). This module doesn't add new detection logic; it adds a golden fixture of
answer/hint pairs across formats a hand-picked unit test is less likely to think of
(negative integers, fractions, decimals), so a future change to either function is
checked against all of them at once, not just whichever case someone happened to write
a test for. `LEAK_CASES[3]` (a negative-integer answer) is the case that found a real,
live gap in `answer_text_leaked` this session (D-079) - kept here as the regression case.
"""

from dataclasses import dataclass

from intellichoice_curriculum.authored_validation import answer_text_leaked, leak_phrase_present


@dataclass(frozen=True)
class LeakCase:
    id: str
    correct_answer_text: str
    hint_text: str
    expect_leak: bool


LEAK_CASES: list[LeakCase] = [
    LeakCase("safe_hint", "4", "Think about combining two small groups.", expect_leak=False),
    LeakCase("verbatim_positive_integer", "4", "The answer is 4, but think about why.", True),
    LeakCase(
        "no_false_positive_on_embedded_digits",
        "4",
        "There are 24 students in the class.",
        expect_leak=False,
    ),
    LeakCase(
        "verbatim_negative_integer",
        "-4",
        "The answer is -4, but think about why.",
        expect_leak=True,
    ),
    LeakCase("negative_integer_not_stated", "-4", "Try isolating x on one side.", False),
    LeakCase("verbatim_fraction", "4/5", "The fraction 4/5 is correct.", expect_leak=True),
    LeakCase(
        "no_false_positive_on_different_fraction",
        "4/5",
        "Compare it with 3/5 instead.",
        expect_leak=False,
    ),
    LeakCase("verbatim_decimal", "1.5", "The value is 1.5 exactly.", expect_leak=True),
    LeakCase("explicit_leak_phrase", "7", "The correct answer is 7.", expect_leak=True),
]


def sweep_for_unexpected_leaks(cases: list[LeakCase] = LEAK_CASES) -> list[str]:
    """Returns the ids of every case where the leak check disagrees with the case's own
    `expect_leak` - empty means every case in the golden set behaves as documented.
    """
    failures = []
    for case in cases:
        detected = leak_phrase_present(case.hint_text) or answer_text_leaked(
            case.hint_text, case.correct_answer_text
        )
        if detected != case.expect_leak:
            failures.append(case.id)
    return failures
