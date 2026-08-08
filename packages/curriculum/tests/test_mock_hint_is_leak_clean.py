"""S36 continuation (AUD-L, hint ladder): the default mock's personalized-hint text must
survive the same runtime leak check `tutor.generate_personalized_hint` applies to it.

Why this exists. `MockBedrockProvider` is the default provider for local dev *and* the
whole test suite, and the tutor rejects any personalized hint in which
`answer_text_leaked` finds the served question's correct answer standing alone -
substituting the canonical ladder text instead. So a mock whose own boilerplate contains
a bare small integer silently loses personalization for exactly those variants whose
answer is that integer, and every test asserting on personalized output becomes a coin
flip weighted by an unseeded per-request RNG's variant choice. That is not hypothetical:
`Level {level} hint` collided with the answer "1" and made
`test_hint_reflects_the_students_actual_wrong_option` fail 8 times in 60 standalone runs.

The check is data-driven from the authored bank's own hint ladders rather than a frozen
string, so it also covers the canonical text the mock embeds - if a future content edit
introduces a digit, this fails here instead of as an intermittent flake three files away.
"""

from __future__ import annotations

import asyncio
import json

from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_curriculum.authored_bank import load_authored_bank
from intellichoice_curriculum.authored_validation import (
    answer_text_leaked,
    leak_phrase_present,
)

_PERSONALIZATION_SCHEMA = {"title": "HintPersonalizationResponse"}

# Answer texts a served item can actually carry. Single digits are the collision-prone
# ones - short enough to appear incidentally in any prose a hint might carry - and the
# fractions and negatives come from `fraction_operations` and `linear_equations`.
_REACHABLE_ANSWER_TEXTS = [str(n) for n in range(-9, 10)] + ["1/2", "-1/2", "3/4", "10"]


def _canonical_ladders() -> list[tuple[str, list[str]]]:
    """Every canonical hint ladder a student can actually be shown, keyed by item id.

    D-226 re-pointed this at the authored bank. It used to read `SHAPE_HINT_LADDERS`, the
    per-shape static ladders, which were the ladders for templates `_servable()` had
    filtered out of every serving read since D-210 - so this was proving the mock provider
    leak-clean against text no student could receive. The authored ladders are the ones the
    serving path actually personalises, and there are now far more of them.
    """
    return [
        (t.question_template_id, list(t.hint_ladder))
        for templates in load_authored_bank().values()
        for t in templates
    ]


def _personalized_hint(*, level: int, canonical: str, misconception: str) -> dict:
    provider = MockBedrockProvider()

    async def run() -> dict:
        raw = await provider.raw_generate(
            model_id="mock",
            system_prompt="",
            user_message=json.dumps(
                {
                    "hint_level": level,
                    "misconception_tag": misconception,
                    "skill": "solve_one_step_linear",
                    "canonical_hint_text": canonical,
                }
            ),
            json_schema=_PERSONALIZATION_SCHEMA,
            max_output_tokens=512,
        )
        return json.loads(raw.text)

    return asyncio.run(run())


def test_mock_personalization_introduces_no_answer_the_canonical_text_did_not() -> None:
    """The mock's own wrapper text must never make a hint leak an answer.

    Scoped to what the mock is responsible for (D-226). It used to assert the personalized
    hint leaks *no* answer in `_REACHABLE_ANSWER_TEXTS`, which held while the corpus was
    `SHAPE_HINT_LADDERS` - those ladders are per-shape and carry no numbers at all, so any
    digit in the output came from the mock. Against the authored ladders that premise is
    simply false: `"Add the two top numbers together and keep 8 as the bottom number"` is a
    correct hint for an item about eighths, and the 8 is the question's own denominator.

    So the property is stated as an implication instead: the mock may not *introduce* a
    leak. Whether the canonical text names one of the question's own numbers is content's
    business, and `check_no_answer_leakage` already gates it on every load with the context
    to judge it - it compares against that item's actual answer, which this test cannot.

    This still pins the collision the docstring above describes. The mock writes `Hint L3`
    rather than `Level 3` precisely so its level digit is glued to a letter and cannot match
    as a standalone token; write it the other way and this fails.
    """
    for item_id, ladder in _canonical_ladders():
        for index, canonical in enumerate(ladder):
            level = index + 1
            hint_text = _personalized_hint(
                level=level, canonical=canonical, misconception="sign_error"
            )["hint_text"]
            for answer in _REACHABLE_ANSWER_TEXTS:
                if answer_text_leaked(hint_text, answer):
                    assert answer_text_leaked(canonical, answer), (
                        item_id,
                        level,
                        answer,
                        hint_text,
                    )


def test_mock_personalized_hint_never_trips_the_leak_phrase_check() -> None:
    for shape, ladder in _canonical_ladders():
        for index, canonical in enumerate(ladder):
            hint_text = _personalized_hint(
                level=index + 1, canonical=canonical, misconception="sign_error"
            )["hint_text"]
            assert not leak_phrase_present(hint_text), (shape, index + 1, hint_text)


def test_mock_personalized_hint_still_names_the_misconception_and_varies_by_level() -> None:
    """The two properties the mock exists to provide, pinned alongside leak-cleanliness -
    a "fix" that made the text leak-clean by dropping either one would defeat the tests
    this mock supports.
    """
    _, ladder = _canonical_ladders()[0]
    texts = [
        _personalized_hint(
            level=index + 1, canonical=canonical, misconception="off_by_one"
        )["hint_text"]
        for index, canonical in enumerate(ladder)
    ]
    assert all("off_by_one" in text for text in texts)
    assert len(set(texts)) == len(texts)
