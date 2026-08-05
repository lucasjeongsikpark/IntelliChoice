"""The one place SPEC §18-C3's access-probe distance ceiling is defined, plus the shape the
probe reports a match in.

Same shape as `mastery_policy` (D-156) and for the same reason: the number was written into
three files at once - `chat_api.config.Settings`, `chat_api.graph.nodes.TurnContext` and
`intellichoice_db.repositories.rag.count_matching_by_audience`, which is a package and so
cannot import an app. Three copies of a threshold is how production ends up applying one
value while the tests assert another, and this particular threshold has already moved once on
measurement (D-165 chose it, D-166 raised it), so it will move again.

`AudienceMatch` lives here for the same reason: `intellichoice_db` (which produces it) and
`chat_api.services.role_access` (which consumes it) have no other common home.
"""

from dataclasses import dataclass

# AUD-C-20/D-165, raised by AUD-C-21/D-166. Cosine distance: a non-accessible chunk this
# close to the caller's question counts as evidence that an answer exists behind a login, so
# §18-C3 says "log in as a <role>" instead of "no approved source".
#
# **Chosen against phrasing a person would actually use, which is the whole of AUD-C-21.**
# D-165 set 0.40 against `probe_eval.yaml`'s chunk-derived questions and it did not fire live.
# Re-measured over the same cases rewritten by a pass that never saw the source passage
# (`scripts/generate_probe_eval_fixture.py --from-fixture`), scored by
# `scripts/measure_access_probe_rules.py --query-field human_query`:
#
#   ceiling | right role | wrong role | false hint: public | false hint: unanswerable
#   0.40    |    17/38   |     0      |         0          |            0
#   0.45    |  **23/38** |     1      |       **0**        |          **0**
#   0.50    |    26/38   |     3      |         0          |            2
#
# 0.45 is the last ceiling with a clean record on both negative classes, and it is that
# second column - a hint on a question *nothing* answers - that does the damage: it tells a
# person to go log in for an answer that does not exist. 0.50 buys three more correct hints
# and starts producing exactly that. Do not raise this without re-running the sweep.
#
# **Since D-168 this is the *fallback* ceiling, not the live rule.** It is what a
# distance-only probe uses: the lexical/`MockBedrockProvider` path, and the degraded path
# when the reranker is unavailable. The live rule is the three constants below.
ACCESS_PROBE_MAX_DISTANCE = 0.45

# D-168/AUD-C-22, retuned by AUD-C-23 - and these three are one rule; none of them means
# anything alone.
#
# The probe mirrors the real retrieval pipeline instead of paraphrasing it: candidates
# under `CANDIDATE_MAX_DISTANCE`, reranked by the same `BedrockTask.RERANK` model `retrieve`
# uses, a tier named only if it beats the runner-up tier by `TIER_MARGIN` **computed over the
# pre-floor per-audience bests**, and only if the winner scores above `RERANK_MIN_SCORE`. The
# model scores *passages*; the passage -> audience -> fixed message mapping stays
# deterministic (CLAUDE.md #3).
#
# **AUD-C-23 (2026-08-04) is why the floor is 0.9 and the margin is pre-floor.** The live
# system told 6 of 10 anonymous askers of a question *nothing* answers to log in as a branch
# manager. Repeated-rerank measurement (10x per arm, sample size fixed before the run per
# D-175's rule) found the mechanism: on that question the best branch_manager passage scores
# 0.75-0.90 - rerank noise straddling the old 0.8 floor - while the runner-up sits at 0.2-0.3,
# so the tier margin never applied. The floor was the operative knob, but raising it alone
# resurrects AUD-C-22: with a floor-first rule at 0.9, corpus-phrasing "how do I fix an
# attendance error for my child" scores branch_manager 0.95 / parent 0.90, the parent passage
# is truncated *before* the margin can see it, and the wrong tier is named 3/10. Hence both
# changes together: floor 0.9 gates only the winner; the margin sees every audience.
#
# Measured by `scripts/measure_access_probe_rules.py` over both phrasings of the same 38
# gated / 12 public / 8 unanswerable cases, single-shot table plus 10x stability reranks of
# the two noise-flipped cases (`no-answer-missed-1`, `probe-parent-013`):
#
#   rule                                  | right | wrong tier | FP public | FP unanswerable
#   floor .8, post-floor margin (human)   | 29/38 |     1      |     0+    |       1
#   floor .8, post-floor margin (corpus)  | 29/38 |     0      |     0+    |       0*
#   this rule                    (human)  | 27/38 |   **0**    |   **1**   |     **0**
#   this rule                    (corpus) | 26/38 |   **0**    |     0     |     **0**
#
#   * flips run to run: the old rule fired on the unanswerable case 2/10 (human arm) and
#     3/10 (corpus arm) stability repeats; this rule 0/40 across every repeat of both cases.
#   + a lower bound only, and the reason is AUD-C-25 (see below): every row in this table
#     except "this rule" was produced by a *reimplementation* of the rule that models no
#     lexical arm, so its negative-class columns cannot see the branch that produces the 1.
#
# **⚠️ The FP-public 1 on the human arm was 0 in this table until D-179, and the correction is
# AUD-C-25's** - `measure_access_probe_rules.py` scored candidate rules by restating them,
# and no restatement modelled `probe_access`'s earliest exit: when *nothing* is within
# `CANDIDATE_MAX_DISTANCE` the probe never calls the reranker and asks the keyword arm alone.
# That branch is reached on **18 of 58 cases** in the human arm, and on one of them
# (`probe-public-025`, *"How do I get or delete my kid's school records?"*, nearest non-public
# chunk at distance **0.7251** against a 0.60 ceiling) the keyword arm names **parent** for a
# question the **public** Privacy Notice answers. The rule constants are not implicated: no
# floor or margin runs on that path. Re-measure with `--shipped`, which replays the real
# `probe_access` over a dump for free, and read the `SHIPPED probe_access` row - it is the
# only row in the table that is the code.
#
# **The margin is what buys the zero wrong tiers; the floor is what buys the zero false
# hints.** AUD-C-22's argument stands: a wrong tier is worse than silence, and every miss
# this rule adds over the old one is a silence, not a misdirection. The remaining knife
# edges, so nobody re-trips them: the unanswerable case's winning score reached **0.90** once
# in 22 samples, so a 0.85 floor still leaks and 0.9 has exactly one quantization step of
# headroom (the reranker emits 0.05 steps); and a margin of 0.05 only ever "worked" through
# float error (0.95 - 0.90 < 0.05 is True in binary), so do not lower it to the score grid.
#
# Two older negative results, still standing: **HyDE** measured no better for one extra
# generation per refusal, and a floor of 0.9 **with the post-floor margin** is worse than
# either rule here (wrong tiers 3/10 on the stability control) - the floor raise is only
# safe because the margin moved in front of it.
ACCESS_PROBE_CANDIDATE_MAX_DISTANCE = 0.60
ACCESS_PROBE_RERANK_MIN_SCORE = 0.9
ACCESS_PROBE_TIER_MARGIN = 0.10
# Candidates sent to the reranker. `retrieve` uses 30; the probe needs far fewer because it
# only has to decide *which audience*, and every candidate is a passage the caller may not
# read - a smaller pool is less text sent to the model for a turn that will not answer anyway.
ACCESS_PROBE_CANDIDATE_LIMIT = 10


@dataclass(frozen=True)
class AudienceMatch:
    """What the access probe found for one non-accessible `audience`, and *how good* the
    find was - the second half is AUD-C-22.

    The probe used to return `dict[str, int]`, so `build_access_hint` could only rank
    audiences by a fixed tier priority. Live, on the question AUD-C-21 was filed about, that
    told a parent asking about their own child's attendance to "log in with a branch manager
    account": both tiers matched, and the wrong one won on rank. The relevance information
    existed one layer down and was thrown away by `count(*)`.

    `score` is "higher is more relevant", comparable *across* audiences, and deliberately not
    a distance - the probe has more than one way to produce it (`1 - cosine_distance`, or a
    reranker's relevance score) and the selector must not care which. `None` means this
    audience matched on a signal that has no relevance scale at all - the lexical arm, or
    `MockBedrockProvider`'s hash-seeded vectors - and the selector then falls back to tier
    priority, which is exactly the pre-AUD-C-22 behaviour.
    """

    count: int
    score: float | None = None
