"""Build the C1 content-coverage matrix from the source CSV (D-273, Phase 0).

Free and read-only with respect to every model and database: it reads
`knowledge-content/intellichoice_math_topics.csv` and writes
`curriculum/coverage/csv_row_dispositions.csv`. Nothing here calls Bedrock, touches
Postgres, or reads a credential.

**Why a script rather than a hand-maintained table.** The disposition of a row is a
judgement, but the *derivation* around it - topic id, skill id, family rollups, the
counts quoted in docs - is mechanical, and a hand-maintained matrix of 246 rows drifts
from the CSV the first time either changes. The judgement lives in `ANSWER_MODEL`
below, keyed by row index; everything else is computed. Re-run it after editing either.

**The axis is the answer model, not the subject.** What decides whether the existing
§5.8.5 gate can verify an item is the shape of its answer, and that cuts across topics:
"round 3,847 to the nearest hundred" and "solve 3x + 2 = 11" are both `value` and both
work today, while "which number is larger" and "factor x^2 - 9" fail for unrelated
reasons. Measured against the real `derive_answer` on 2026-08-11 - see D-273's
"Corrected by verification" section for the transcript that settled each case.
"""

import csv
import pathlib
import re
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "knowledge-content" / "intellichoice_math_topics.csv"
OUT = ROOT / "curriculum" / "coverage" / "csv_row_dispositions.csv"

# Answer models, and what each means for the pipeline as it stands today.
#
# `value` is the only one the current gate serves, and it is broader than "arithmetic":
# `Eq(x, <expression>)` is fully supported, so rounding, GCF, exponents, order of
# operations, averages and formula-driven area/volume are all `value`.
FAMILIES = {
    "value": ("A", "works today - one equation, one unknown, one solution"),
    "selection": ("B", "answer is one of the stated objects (which is larger/odd/prime)"),
    "ordering": ("B", "answer is an arrangement of the stated objects"),
    "multi_root": ("B", "two or more roots - `x**2 = 9` is rejected as '2 solutions'"),
    "interval": ("B", "inequality solution set - rejected as 'not a single equation'"),
    "tuple": ("B", "system - rejected as 'has 2 unknowns'"),
    "symbolic": ("B", "answer is an expression, compared by equivalence not value"),
    "figure": ("C", "cannot be posed in text alone"),
    "reshape": ("D", "not MCQ-able as written; reshape into another model or drop"),
}

# The judgement, by row index. Every index not listed is `value` - the majority case,
# and listing 160 of them would bury the 85 that carry the real information.
ANSWER_MODEL: dict[int, str] = {
    # g1 Addition / Subtraction - number formation and number-line reading
    0: "reshape",  # Writing Numbers: numeral<->word; reshape to "which shows ...?"
    24: "selection",  # Ordinal Numbers: who is third in line
    # g1 Geometry & Measurement
    26: "selection",  # Numbers up to 10 - comparison/counting
    27: "selection",
    28: "selection",
    29: "figure",  # Telling Time - clock face
    30: "figure",  # Measurements - non-standard units against a picture
    32: "figure",  # Shapes
    # g2
    53: "figure",  # Tables & Graphs
    54: "selection",  # Numbers up to 1000 - place-value comparison
    55: "selection",  # Numbers up to 10000
    56: "figure",  # Telling Time
    60: "figure",  # Triangles and Quadrilaterals
    # g3
    86: "figure",  # Graphs & Tables
    87: "selection",  # Large Numbers - comparison
    93: "figure",  # Telling Time
    94: "figure",  # Triangles & Quadrilaterals
    95: "figure",  # Boxes (nets/solids)
    # g4
    121: "figure",  # Graphs & Tables
    122: "selection",  # Large Numbers
    128: "figure",  # Circles and Spheres
    129: "figure",  # Areas and Triangles
    # g5
    136: "selection",  # Round Numbers, Odd & Even - the odd/even half is selection
    140: "figure",  # Graphs, Percentages & Ratios
    142: "selection",  # Odd & Even Numbers
    145: "figure",  # Perpendicular & Parallel Lines
    146: "figure",  # Quadrilaterals, Angles, and Polygons
    147: "figure",  # Congruent Figures
    148: "figure",  # Axial and Rotational Symmetry
    149: "figure",  # Coordinate Geometry
    # g6
    173: "figure",  # Solids
    175: "figure",  # Scale Drawing
    # Pre-Algebra 6-8
    178: "selection",  # "Comparing, adding, ... fractions" - the comparing half
    # Algebra 6-8
    184: "symbolic",  # Simplifying algebraic expressions
    186: "symbolic",  # The distributive property
    188: "symbolic",  # Linear functions - name the function
    189: "tuple",  # Simultaneous linear equations
    191: "interval",  # Inequalities
    192: "figure",  # Graphs
    # Intro to Geometry 6-8
    193: "figure",
    194: "figure",
    195: "figure",
    # Geometry 6-8
    199: "figure",
    200: "figure",
    202: "figure",
    203: "figure",
    204: "figure",
    205: "figure",
    206: "figure",
    207: "figure",
    # Word Problems 6-8
    212: "symbolic",  # Algebraic expressions
    215: "interval",  # Inequalities
    216: "figure",  # Graphs
    217: "symbolic",  # Linear functions
    # Algebra I
    218: "multi_root",  # Square Roots
    219: "multi_root",  # Quadratic Equations
    220: "interval",  # Inequalities
    221: "symbolic",  # Functions and Graphs
    222: "tuple",  # Systems of Equations
    223: "symbolic",  # Factorization
    # Geometry / Algebra II
    226: "symbolic",  # Polynomial Factorization
    228: "symbolic",  # Factor Theorem
    229: "symbolic",  # Quadratic Functions
    # Algebra II / Precalculus
    230: "symbolic",  # Rational Functions
    231: "symbolic",  # Radical Functions
    235: "symbolic",  # Trigonometric Functions
    # Precalculus / Calculus
    238: "symbolic",  # Differentiation
    239: "symbolic",  # Integration
    240: "symbolic",  # Differential Equations
    # Statistics & Advanced
    243: "symbolic",  # Matrices
    244: "symbolic",  # Vectors
    245: "symbolic",  # Lines and Planes in Space
}


def slug(text: str) -> str:
    """A stable identifier fragment. Unicode dashes and the multiplication sign appear
    in this CSV (`6-8`, `2x Tables`, `Grades 6-8`), so normalise before stripping.
    """
    text = text.replace("×", "x").replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9]+", "_", text.lower())
    return text.strip("_")


def main() -> None:
    rows = list(csv.DictReader(SOURCE.open()))
    OUT.parent.mkdir(parents=True, exist_ok=True)

    seen: set[tuple[str, str, str]] = set()
    out_rows = []
    for i, r in enumerate(rows):
        key = (r["grade"], r["book"], r["topic"])
        duplicate = key in seen
        seen.add(key)

        model = ANSWER_MODEL.get(i, "value")
        family, _ = FAMILIES[model]
        topic_id = slug(r["book"])
        # Book-qualified: only 194 of the 246 topic strings are distinct - "Fractions"
        # appears in seven different books - so a bare topic slug would collide across
        # books and silently merge two skills.
        skill_id = f"{topic_id}__{slug(r['topic'])}"

        out_rows.append(
            {
                "row_index": i,
                "grade": r["grade"],
                "book": r["book"],
                "topic": r["topic"],
                "topic_id": topic_id,
                "skill_id": skill_id,
                "answer_model": model,
                "family": family,
                "duplicate_of_earlier_row": "yes" if duplicate else "",
            }
        )

    with OUT.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
        writer.writeheader()
        writer.writerows(out_rows)

    unique = [r for r in out_rows if not r["duplicate_of_earlier_row"]]
    by_model = Counter(r["answer_model"] for r in unique)
    by_family = Counter(r["family"] for r in unique)
    topics = {r["topic_id"] for r in unique}

    print(f"source rows      {len(out_rows)}")
    print(f"unique rows      {len(unique)}  (denominator for coverage)")
    print(f"internal topics  {len(topics)}")
    print(f"distinct skills  {len({r['skill_id'] for r in unique})}")
    print()
    for family in sorted(by_family):
        pct = 100 * by_family[family] / len(unique)
        print(f"  family {family}  {by_family[family]:3}  ({pct:4.1f}%)")
    print()
    for model, n in by_model.most_common():
        print(f"    {model:12} {n:3}  {FAMILIES[model][1]}")
    # `relative_to` raises when the caller has redirected OUT outside the repo, which the
    # regeneration test does deliberately - a nicer path is not worth crashing the write
    # that already succeeded.
    display = OUT.relative_to(ROOT) if OUT.is_relative_to(ROOT) else OUT
    print(f"\nwrote {display}")


if __name__ == "__main__":
    main()
