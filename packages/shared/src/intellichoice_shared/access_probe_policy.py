"""The one place SPEC §18-C3's access-probe distance ceiling is defined.

Same shape as `mastery_policy` (D-156) and for the same reason: the number was written into
three files at once - `chat_api.config.Settings`, `chat_api.graph.nodes.TurnContext` and
`intellichoice_db.repositories.rag.count_matching_by_audience`, which is a package and so
cannot import an app. Three copies of a threshold is how production ends up applying one
value while the tests assert another, and this particular threshold has already moved once on
measurement (D-165 chose it, D-166 raised it), so it will move again.
"""

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
ACCESS_PROBE_MAX_DISTANCE = 0.45
