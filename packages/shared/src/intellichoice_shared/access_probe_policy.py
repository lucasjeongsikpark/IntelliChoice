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

# D-168/AUD-C-22, and these three are one rule - none of them means anything alone.
#
# The probe now mirrors the real retrieval pipeline instead of paraphrasing it: candidates
# under `CANDIDATE_MAX_DISTANCE`, reranked by the same `BedrockTask.RERANK` model `retrieve`
# uses, an audience kept only if its best passage scores above `RERANK_MIN_SCORE`, and a tier
# named only if it beats the runner-up tier by `TIER_MARGIN`. The model scores *passages*; the
# passage -> audience -> fixed message mapping stays deterministic (CLAUDE.md #3).
#
# Measured by `scripts/measure_access_probe_rules.py` over both phrasings of the same 38
# gated / 12 public / 8 unanswerable cases (blind-rewrite `human_query`, and the
# corpus-derived `query`):
#
#   rule                                  | right | wrong tier | FP public | FP unanswerable
#   PRIORITY <=0.45  (D-166, human)       | 23/38 |     1      |     0     |       0
#   PRIORITY <=0.45  (D-166, corpus)      | 23/38 |     4      |     0     |       0
#   this rule                    (human)  | 29/38 |   **0**    |     0     |       0
#   this rule                    (corpus) | 28/38 |   **0**    |     0     |       1
#
# **The margin is what buys the zero.** Without it, reranking alone gets 33-36 right but 2-5
# wrong tiers: on attendance questions the parent handbook and the branch-manager procedure
# both genuinely answer, and *something* has to lose. AUD-C-22's whole argument is that a
# wrong tier is worse than silence - a parent told to log in as a branch manager cannot act on
# it at all - so when the reranker cannot separate two tiers this stays silent and the honest
# no-source message (plus its escalation offer) stands. Every remaining miss in the table
# above is a silence, not a misdirection.
#
# Two negative results, so nobody re-proposes them: **HyDE** (generate a hypothetical answer,
# embed that) was measured and is not better - 28/0 human, 31/0 corpus with a false public
# hint - for one extra generation per refusal. And a **floor of 0.9** is unstable across the
# two phrasings (24 right vs 28), which is the reranker's own scoring noise, not a signal.
ACCESS_PROBE_CANDIDATE_MAX_DISTANCE = 0.60
ACCESS_PROBE_RERANK_MIN_SCORE = 0.8
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
