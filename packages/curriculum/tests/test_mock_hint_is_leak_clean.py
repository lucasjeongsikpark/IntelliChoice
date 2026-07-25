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

The check is data-driven from `SHAPE_HINT_LADDERS` rather than a frozen string, so it
also covers the canonical text the mock embeds - if a future ladder edit introduces a
digit, this fails here instead of as an intermittent flake three files away.
"""

from __future__ import annotations

import asyncio
import json

from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_curriculum.authored_validation import (
    answer_text_leaked,
    leak_phrase_present,
)
from intellichoice_curriculum.hint_ladders import SHAPE_HINT_LADDERS

_PERSONALIZATION_SCHEMA = {"title": "HintPersonalizationResponse"}

# Every answer text the shape bank actually renders for a one-unknown linear equation:
# `format_integer` stringifies a `Fraction`, so single digits, negatives, and reduced
# fractions are all reachable. The single digits are the collision-prone ones - they are
# short enough to appear incidentally in any prose a hint might carry.
_REACHABLE_ANSWER_TEXTS = [str(n) for n in range(-9, 10)] + ["1/2", "-1/2", "3/4", "10"]


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


def test_mock_personalized_hint_never_trips_the_answer_leak_check() -> None:
    for shape, ladder in SHAPE_HINT_LADDERS.items():
        for index, canonical in enumerate(ladder):
            level = index + 1
            hint_text = _personalized_hint(
                level=level, canonical=canonical, misconception="sign_error"
            )["hint_text"]
            for answer in _REACHABLE_ANSWER_TEXTS:
                assert not answer_text_leaked(hint_text, answer), (
                    shape,
                    level,
                    answer,
                    hint_text,
                )


def test_mock_personalized_hint_never_trips_the_leak_phrase_check() -> None:
    for shape, ladder in SHAPE_HINT_LADDERS.items():
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
    ladder = SHAPE_HINT_LADDERS["one_step_add"]
    texts = [
        _personalized_hint(
            level=index + 1, canonical=canonical, misconception="off_by_one"
        )["hint_text"]
        for index, canonical in enumerate(ladder)
    ]
    assert all("off_by_one" in text for text in texts)
    assert len(set(texts)) == len(texts)
