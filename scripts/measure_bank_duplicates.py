"""How much of the shipped bank is the same question twice? (D-285 follow-up)

The first hand audit found **15 of 54 sampled items sitting in a near-identical pair or
trio** - three "mean of five numbers" tasks at d1, d2 and d3 differing only in the digits,
two "X / (1/4) / needed * 100" items that both answer 50%, and nearly the same gift-bag
sentence in *two different topics*. A sample of 54 cannot say whether that is 28% of the
bank or an unlucky draw, and the bank is 620. This measures all of it.

**Deterministic, and that is the point.** A scenario is reduced to its *skeleton*: lower-cased,
every number replaced by `#`, punctuation dropped. So

    "A teacher has 48 pencils and 36 erasers to divide into identical gift bags"
    "A teacher has 48 pencils and 72 erasers to divide into identical gift bags"

collapse to one string and collide. That is exactly the repetition a student notices and
exactly the kind no per-item gate can see, because each item is individually fine.

Two signals, because they fail differently:

1. **Skeleton collision** - same sentence, different numbers. High confidence, no tuning.
2. **Token overlap** (Jaccard over content words) - catches rewordings the skeleton misses,
   at the cost of a threshold. Reported separately and never merged into the first number,
   so the headline figure stays the one with no knob in it.

Cross-skill and cross-topic collisions are counted separately, because that is where the
fix has to happen: `_SCENARIO_MEMORY` in `pipeline_cli` is keyed on `skill_id`, so a
generator working on `prealg_gcf_lcm` is structurally unable to know what
`g6_factors_multiples` just wrote.

Free: no model call, no database - reads the exported bank files, which are what ships.

Run: uv run python scripts/measure_bank_duplicates.py [--threshold 0.75] [--show 15]
"""

from __future__ import annotations

import argparse
import glob
import pathlib
import re
from collections import Counter, defaultdict

import yaml

_BANK = pathlib.Path(__file__).resolve().parents[1] / "curriculum" / "internal_math" / "authored"

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_NON_WORD_RE = re.compile(r"[^a-z#\s]")
_WHITESPACE_RE = re.compile(r"\s+")

# Words carrying no scenario information. Deliberately short: the goal is to compare
# *settings* ("a teacher ... pencils ... gift bags"), and over-stripping would make two
# genuinely different questions look alike, which is the expensive direction for a number
# that will be used to justify changing the generator.
_STOPWORDS = frozenset(
    """a an the of to in on at for from with and or is are was were be been has have had
    what which how many much does do did she he they it her his their this that these those
    if then than each per into out up down by as
    """.split()
)


def skeleton(text: str) -> str:
    """The sentence with every number replaced by `#` - what makes two items 'the same'."""
    lowered = _NUMBER_RE.sub("#", text.lower())
    return _WHITESPACE_RE.sub(" ", _NON_WORD_RE.sub(" ", lowered)).strip()


def content_words(text: str) -> frozenset[str]:
    return frozenset(w for w in skeleton(text).split() if w not in _STOPWORDS and w != "#")


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# A capitalised word that is not a sentence-opening function word - a person's name, in
# practice. It is the cheap signal that separates a *story* from a *template*.
#
# The stoplist rather than a "not first word" rule, which was the first version and got
# "Leo has three digit cards" wrong three times: a scenario very often *opens* with the
# name, so excluding position 0 excludes exactly the cases worth catching.
_CAPITALISED_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")
_SENTENCE_OPENERS = frozenset(
    """Which What How Many Much The Find Calculate Solve Write Round Estimate Simplify
    Evaluate Compare Order After Each Every Given Suppose Two Three Four Five Six Seven
    Eight Nine Ten Twelve During Between Complete Choose Identify Determine Work Use
    """.split()
)


def _is_scenario(stem: str) -> bool:
    """Does this stem tell a story, or is it a bare instruction?

    "Which of these numbers is the largest?" is a template: it *should* recur, because the
    question lives in the options and there is no other way to phrase it. "Liam has 9
    stickers in his album" is a scenario, and a student meeting Liam and his 9 stickers
    twice notices. Only the second kind is a defect, so counting them together would put a
    number on the wrong thing - which is what the 54-item audit did.
    """
    return any(w not in _SENTENCE_OPENERS for w in _CAPITALISED_RE.findall(stem))


def _severity(members: list[dict[str, str]]) -> str:
    """Where a collision sits, worst first. Crossing a topic boundary is the worst case
    because no per-skill memory could ever have prevented it."""
    scenario = _is_scenario(members[0]["stem"])
    if len({m["topic"] for m in members}) > 1:
        return "ACROSS TOPICS - scenario" if scenario else "across topics - template"
    if len({m["skill"] for m in members}) > 1:
        return "across skills - scenario" if scenario else "across skills - template"
    return "within one skill - scenario" if scenario else "within one skill - template (by design)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=0.75, help="Jaccard floor (0.75)")
    parser.add_argument("--show", type=int, default=12, help="examples to print (12)")
    args = parser.parse_args()

    items: list[dict[str, str]] = []
    figures = 0
    for path in sorted(glob.glob(str(_BANK / "*.yaml"))):
        for template in yaml.safe_load(pathlib.Path(path).read_text())["templates"]:
            # A family-C item's stem is *meant* to be invariant - "What time does this clock
            # show?" is the only sensible phrasing, and the variation lives in the figure,
            # which `figure_numbers_missing_from_item` already checks item by item. Counting
            # eight identical clock stems as eight duplicates measures the detector, not the
            # bank. Excluded and reported, never silently dropped.
            if template.get("figure_spec"):
                figures += 1
                continue
            items.append(
                {
                    "id": template["question_template_id"],
                    "topic": template["topic_id"],
                    "skill": template["skill_id"],
                    "difficulty": str(template["difficulty_label"]),
                    "stem": template["stem"],
                }
            )

    # ---------------------------------------------------------------------------------
    # 1. Skeleton collisions - no threshold, no tuning
    # ---------------------------------------------------------------------------------
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in items:
        groups[skeleton(item["stem"])].append(item)
    collided = {k: v for k, v in groups.items() if len(v) > 1}

    in_collision = sum(len(v) for v in collided.values())
    spans: Counter[str] = Counter()
    for members in collided.values():
        spans[_severity(members)] += 1

    print(f"\nBank: {len(items)} items in {len(set(i['topic'] for i in items))} topics.")
    print(f"({figures} family-C figure items excluded - their stems are invariant by design.)\n")
    print("=== 1. Skeleton collisions (same sentence, different numbers) ===")
    print(f"  groups          : {len(collided)}")
    share = 100 * in_collision / len(items)
    print(f"  items involved  : {in_collision}  ({share:.0f}% of the bank)")
    for label, n in spans.most_common():
        print(f"    {label:<34} {n:>3} groups")

    # Worst first: a repeated *story* across topics, then everything else. Sorting by group
    # size would lead with the by-design templates, which is the least actionable end.
    ranked = sorted(
        collided.values(), key=lambda m: (not _severity(m).startswith("ACROSS"), -len(m))
    )
    for members in ranked[: args.show]:
        print(f"\n  [{len(members)}x, {_severity(members)}] {members[0]['stem'][:118]}")
        for m in members:
            print(f"      {m['topic']}/{m['skill']} d{m['difficulty']}  {m['id']}")

    # ---------------------------------------------------------------------------------
    # 2. Token overlap - catches rewordings, at the cost of a knob
    # ---------------------------------------------------------------------------------
    print(f"\n\n=== 2. Token overlap >= {args.threshold} (rewordings the skeleton misses) ===")
    words = [(item, content_words(item["stem"])) for item in items]
    seen_pairs: set[tuple[str, str]] = set()
    near: list[tuple[float, dict[str, str], dict[str, str]]] = []
    for i, (a, wa) in enumerate(words):
        for b, wb in words[i + 1 :]:
            if skeleton(a["stem"]) == skeleton(b["stem"]):
                continue  # already counted above, and counted once is the honest way
            score = jaccard(wa, wb)
            if score >= args.threshold:
                key = tuple(sorted((a["id"], b["id"])))
                if key not in seen_pairs:
                    seen_pairs.add(key)  # type: ignore[arg-type]
                    near.append((score, a, b))

    involved = {i["id"] for _, a, b in near for i in (a, b)}
    print(f"  pairs           : {len(near)}")
    near_share = 100 * len(involved) / len(items)
    print(f"  items involved  : {len(involved)}  ({near_share:.0f}% of the bank)")
    cross = sum(1 for _, a, b in near if a["skill"] != b["skill"])
    print(f"    of which cross-skill: {cross}")
    for score, a, b in sorted(near, key=lambda t: -t[0])[: args.show]:
        print(
            f"\n  [{score:.2f}] {a['topic']}/{a['skill']} d{a['difficulty']}  vs  "
            f"{b['topic']}/{b['skill']} d{b['difficulty']}"
        )
        print(f"      A: {a['stem'][:110]}")
        print(f"      B: {b['stem'][:110]}")


if __name__ == "__main__":
    main()
