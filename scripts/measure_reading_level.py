"""Is the bank's student-facing text at the reading level its grade band implies? (D-303)

**The clause this answers.** ROADMAP C1 Phase 6 asks for "grade-1 reading level in stems *and*
tutor replies", and D-288 recorded it as the one part of that phase nothing was done against.
Two things were true and are worth separating:

- **The generative tutor path has no readability check at all** - `generate_hint`,
  `generate_solution` and `generate_personalized_hint` say "age-appropriate" in a prompt and
  measure nothing. There is also no corpus to measure: `tutor_chat_messages` holds **0 rows**
  in dev, so unlike every other measurement in this session there is no stored evidence to
  read. Measuring it needs paid generation, and that measures a fresh sample rather than
  production behaviour.
- **The deterministic path is 912 items of stored student-facing text and is free to measure.**
  A student who asks for help reads the bank's `hint_ladder`; a student who asks for the answer
  reads its `canonical_solution`. Those *are* the tutor replies for the common path, and this is
  what the script measures.

**What the gate enforces today, and the question that exposes.** `_MAX_WORDS_PER_SENTENCE = 30`,
flat, for every field and every grade band - a grade-1 item and a calculus item face the same
ceiling. Thirty words is nowhere near a grade-1 sentence, so the interesting number is not "does
the bank pass its own gate" (it does, by construction) but **how far the youngest bands sit from
the level their students actually read at**.

**Two instruments, and the weaker one is labelled as such.**

- *Words per sentence* is robust and is what the gate already uses. Rough public guidance puts
  grade 1-2 around 8-10 words, grade 3-5 around 11-14, grade 6-8 around 15-18.
- *Flesch-Kincaid grade level* needs syllables, estimated here by vowel groups. It is a **weak**
  instrument on one- and two-sentence math text - a single number like "2.5" or a symbol read as
  a word swings it - so it is reported for shape, never as a verdict.

Free and read-only.

    uv run python scripts/measure_reading_level.py
    uv run python scripts/measure_reading_level.py --worst 15
"""

from __future__ import annotations

import argparse
import collections
import re
import statistics
import sys

from intellichoice_curriculum.authored_bank import load_authored_bank
from intellichoice_curriculum.content import load_curriculum

# Rough public guidance for words per sentence by band. Not a standard anyone owns - used to
# say "how far off" rather than to pass or fail anything.
BAND_WORD_TARGET = {"1-2": 10, "3-5": 14, "6-7": 18, "6-8": 18, "8-9": 20, "10-11": 22, "12": 22}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_VOWEL_GROUP = re.compile(r"[aeiouy]+")


def _syllables(word: str) -> int:
    """Vowel groups, with a silent-final-e correction. An estimate, deliberately cheap."""
    lowered = word.lower()
    groups = len(_VOWEL_GROUP.findall(lowered))
    if lowered.endswith("e") and groups > 1 and not lowered.endswith(("le", "ee")):
        groups -= 1
    return max(1, groups)


def _sentences(text: str) -> list[str]:
    return [s for s in (part.strip() for part in _SENTENCE_SPLIT.split(text or "")) if s]


def _flesch_kincaid(text: str) -> float | None:
    sentences = _sentences(text)
    words = _WORD.findall(text or "")
    if not sentences or not words:
        return None
    syllables = sum(_syllables(w) for w in words)
    return 0.39 * (len(words) / len(sentences)) + 11.8 * (syllables / len(words)) - 15.59


def _fields(template) -> list[tuple[str, str]]:
    """Every field a student actually reads, named so a finding is actionable.

    `step.expression` is excluded on purpose: it renders inside `<code>` and is arithmetic, not
    prose - the same exemption `check_math_notation_is_readable` makes (D-288).
    """
    out: list[tuple[str, str]] = [("stem", template.rendered_question)]
    out += [("option", getattr(template, f"option_{k}") or "") for k in "abcd"]
    out += [(f"hint[{i}]", h) for i, h in enumerate(template.hint_ladder or [])]
    solution = template.canonical_solution or {}
    if isinstance(solution, dict):
        out += [
            (f"step[{i}].explanation", (step or {}).get("explanation") or "")
            for i, step in enumerate(solution.get("steps") or [])
        ]
        out.append(("final_answer", solution.get("final_answer") or ""))
    return [(name, text) for name, text in out if text and _WORD.findall(text)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worst", type=int, default=10, help="How many worst sentences to show")
    args = parser.parse_args()

    curriculum = load_curriculum()
    band_of = {t.topic_id: t.grade_band for t in curriculum.topics}
    bank = load_authored_bank()

    per_band: dict[str, list[int]] = collections.defaultdict(list)
    per_band_fk: dict[str, list[float]] = collections.defaultdict(list)
    worst: list[tuple[int, str, str, str, str]] = []
    items = 0

    for topic_id, templates in sorted(bank.items()):
        band = band_of.get(topic_id, "?")
        for template in templates:
            items += 1
            for field_name, text in _fields(template):
                for sentence in _sentences(text):
                    words = len(_WORD.findall(sentence))
                    if not words:
                        continue
                    per_band[band].append(words)
                    worst.append((words, band, topic_id, field_name, sentence[:110]))
                fk = _flesch_kincaid(text)
                if fk is not None:
                    per_band_fk[band].append(fk)

    print(f"items read: {items}; sentences measured: {sum(len(v) for v in per_band.values())}")
    print("\nwords per sentence, by grade band (the gate's flat ceiling is 30):")
    print(f"  {'band':<8}{'n':>7}{'median':>8}{'p90':>7}{'max':>6}{'target':>8}{'over target':>13}")
    for band in sorted(per_band, key=lambda b: (len(b), b)):
        lengths = sorted(per_band[band])
        target = BAND_WORD_TARGET.get(band)
        over = sum(1 for x in lengths if target and x > target)
        p90 = lengths[int(len(lengths) * 0.9)]
        share = f"{over / len(lengths) * 100:.0f}%" if target else "-"
        print(
            f"  {band:<8}{len(lengths):>7}{statistics.median(lengths):>8.0f}{p90:>7}"
            f"{lengths[-1]:>6}{(target or '-'):>8}{share:>13}"
        )

    print("\nFlesch-Kincaid grade estimate, by band (weak on short math text - shape only):")
    for band in sorted(per_band_fk, key=lambda b: (len(b), b)):
        values = sorted(per_band_fk[band])
        print(
            f"  {band:<8} median {statistics.median(values):>5.1f}   "
            f"p90 {values[int(len(values) * 0.9)]:>5.1f}"
        )

    print(f"\nlongest {args.worst} sentences a student is shown:")
    for words, band, topic_id, field_name, sentence in sorted(worst, reverse=True)[: args.worst]:
        print(f"  {words:>3}w  {band:<6} {topic_id:<24} {field_name:<22} {sentence!r}")

    youngest = [b for b in per_band if b in ("1-2",)]
    if youngest:
        lengths = per_band[youngest[0]]
        target = BAND_WORD_TARGET["1-2"]
        over = sum(1 for x in lengths if x > target)
        print(
            f"\nthe Phase 6 clause, stated as a number: in band 1-2, "
            f"{over} of {len(lengths)} sentences ({over / len(lengths) * 100:.0f}%) run longer "
            f"than {target} words, and the gate permits {30}."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
