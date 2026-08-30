# E5.3 hand audit — 30 items, drawn before reading

> Sample: `hand_audit_sample.json`, seed **20260829**, 15 machine-rejected + 15
> machine-accepted, drawn proportionally over requested difficulty **before** any item was
> read. Full item text: `hand_audit_worksheet.md`. Run
> `0e111b3f-bd93-410e-a16c-6ee2b8e753a6`, repo `dd624d8`, audited 2026-08-30.
>
> **Why this exists.** The deterministic scorer in `raw_vs_validated_scoring.py` sees
> equation-vs-key agreement, option structure, leakage, hint monotonicity, wording and
> readability. It cannot see whether the *scenario* is plausible, whether the equation
> models the story it is attached to, whether two items are the same question twice, or
> whether the stored tier is defensible. This audit is the honest bound on that blindness,
> mirroring D-285's method.
>
> **D-342.** Nothing read here is approved, exported, or counted toward any coverage
> target. "Machine-accepted" means *cleared the automated pipeline*, never *approved*.

## 1. Headline

| | machine-rejected (n=15) | machine-accepted (n=15) |
|---|---|---|
| wrong answer key / wrong arithmetic | 0/15 | **0/15** |
| carries ≥1 defect the deterministic scorer cannot see | 4/15 (26.7%) | **4/15 (26.7%)** |
| rejection judged correct on reading | **15/15 (100%)** | — |

Two numbers matter. **Zero of the 15 machine-accepted items has a wrong answer or a wrong
key** — consistent with the deterministic arm, which found 0 gate-checkable defects in the
whole 174-item accepted set. And **4 of 15 accepted items still carry a real defect**, none
of which any per-item deterministic check could have caught.

## 2. Machine-accepted arm — what the scorer missed

| defect | n/15 | rate |
|---|---|---|
| scenario repetition beyond the skeleton signal | 3/15 | 20.0% |
| tier inconsistency between near-identical items | 3/15 | 20.0% |
| scenario implausible for the mathematics attached to it | 1/15 | 6.7% |
| wrong answer, wrong key, leakage, bad hint ladder | 0/15 | 0.0% |
| **distinct items with ≥1 defect** | **4/15** | **26.7%** |

The repetition and tier rows are the same three items, counted once per defect class.

**2a. One template, three items, three digits changed (items 23, 26, 29).**

- `0d6a32da` d3 — "A library orders 32 boxes of books. Each box contains 14 books. The
  library then lends 195 books…" → 32×14−195
- `6471b751` d5 — "A school receives 36 boxes of pencils with 25 pencils in each box. The
  school then distributes 215 pencils…" → 36×25−215
- `59a25b98` d5 — "A sports equipment store receives 50 boxes of tennis balls with 14 balls
  in each box. The store then sells 220…" → 50×14−220

All three are `g3_wp_mixed`, all three are machine-accepted, all three are the same
sentence with the nouns and digits swapped. The knobless skeleton signal does **not** group
them (the verbs differ: orders/receives/receives, lends/distributes/sells), so this is
repetition that survives *both* the pipeline's dedup stage and this experiment's own
no-threshold duplicate check. It is caught only by the thresholded Jaccard signal and by
reading.

**2b. The same three items are stored two tiers apart.** `0d6a32da` is stored at d3;
`6471b751` and `59a25b98` at d5. Nothing about the mathematics separates them — 36×25 is if
anything harder than 50×14, and 50×14 is easier than 32×14. Generalised over the whole run
(deterministic, free): of the **17** near-duplicate pairs in which both members were
machine-accepted, **6 (35.3%)** are stored at different tiers, including a d5/d3 pair of
"garden centre receives N flats × M plants" items. The judge's tier on near-identical items
is not stable.

**2c. A scenario the mathematics cannot inhabit (item 28, `814b05a0`, stored d3).**
"Each cycle the population multiplies by −2, representing alternating growth and decline.
After 5 cycles, what is the population change value?" → (−2)⁵ = −32. The arithmetic and the
key are correct; a population that multiplies by a negative number is not a thing, and
"population change value" is a phrase doing the work the scenario cannot. **The judge
rejected the twin of this defect** in the same run — item 9 below, `(−3)⁴` as the "total
effect" of four 3-degree temperature drops — with a paragraph explaining that exponentiation
does not model repeated additive change. Same defect class, opposite verdicts, one run.

**2d. The difficulty adjudicator corrected two tier inversions.** Worth recording because
the first reading of the *requested* tiers suggested a defect that is not there:
`3224d9fd` (1+7) and `b33f982d` (3+2) were both requested at d2 and both **stored at d1**,
alongside `e37e2916` (4+3) requested and stored at d1. Read at the stored label — which is
what a student meets — the ladder is right. Any tier claim about this pipeline has to be
made against `stored_difficulty`, not the slot's request (D-302).

## 3. Machine-rejected arm — was the rejection right?

**15/15 justified.** They split into two very different groups.

| group | n/15 | what it is |
|---|---|---|
| unverifiable answer, sound item | 11/15 (73.3%) | the `equation` field is a bare expression (`x**2 + 4*x - 60`) or absent, so nothing can derive the answer — but the question, the key and the worked solution are all correct |
| substantive content defect | 4/15 (26.7%) | the item is genuinely wrong or unusable |

**3a. The 11 unverifiable items are one systematic failure, not eleven.** Ten are
`alg1_quadratics`, which wrote the quadratic in standard form as an *expression* instead of
`Eq(expr, 0)`; one is `trig_functions` with no `equation` at all. Every one of them has the
right answer. The gate is right to refuse them — an answer nobody can derive must not
ship — but the raw-arm figure must not be read as "19 wrong answer keys". Across the whole
run the same class is 17 bare expressions + 1 multi-root set vs a single declared key + 1
absent equation = the 19 `answer key: derived answer disagrees` rows, and it is why
`alg1_quadratics` accepted **0 of 18**. The pipeline's own summary said so unprompted:
*"a skill at zero is a structural failure, not a low yield — re-running will not change it."*

**3b. The 4 substantive rejections are all defects SymPy cannot see.**

- `afc436a6` (trig d1) — "the ramp rises 1 metre for every 2 metres of horizontal distance.
  What is the sine of the angle?" with `equation = Eq(x, sin(pi/6))` and key 1/2. The
  equation agrees with the key, so the deterministic gate passed it. The stated scenario
  gives sin θ = 1/√5 ≈ 0.447, not 1/2. **Solver A caught it.** This is the exact mirror of
  D-276: the free gate checks *equation ↔ key*, never *scenario ↔ equation*, and a
  generator that writes both fields to agree with each other defeats it.
- `0084cf0e` (trig d3) — sin(5π/6) is correct, but a surveyor's *angle of elevation* of
  150° is physically impossible. Judge caught it.
- `3d8ec0d3` (exponents d4) — (−3)⁴ as the "total effect" of four temperature drops. Judge
  caught it. (See 2c: its twin was accepted.)
- `6f29199c` (exponents d5) — a 32-word sentence against the 30-word readability ceiling.
  Deterministic; correctly caught free.

## 4. What this audit changes about the headline numbers

1. The raw arm's **9.41% answer-key disagreement rate is a verifiability rate, not an
   error rate.** The underlying items are mathematically right; what is broken is the field
   the pipeline derives the answer from. Both readings are damning for shipping raw — an
   item whose answer cannot be checked is exactly as unshippable as one whose answer is
   wrong — but they are different defects and the report says so.
2. The validated arm's **4.60% residual is real and is entirely duplication**, and the hand
   audit shows the true repetition rate is *higher* than the deterministic 4.60%, because
   the reworded triple in 2a is invisible to the knobless signal.
3. **Machine acceptance is not human approval**, and 26.7% of a 15-item accepted sample
   would not survive a reviewer: three repeated scenarios, three unstable tiers, one
   scenario that cannot host its own arithmetic.

## 5. Method limits

- n=30 (15+15) supports rates to roughly ±12 points at 95% confidence; every figure above
  is a sample rate on a single run, not a bank-wide property.
- One reader, one pass, no blinding: the auditor could see each item's machine verdict and
  the deterministic scorer's families. D-285 has the same limitation.
- The accepted arm is drawn from 174 items across 9 skills; `alg1_quadratics` contributes
  nothing to it because it accepted nothing, so the accepted-arm rates describe the skills
  that worked.
