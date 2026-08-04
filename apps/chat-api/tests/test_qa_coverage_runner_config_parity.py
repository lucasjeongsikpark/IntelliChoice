"""AUD-C-23 / D-175: the paid eval's `TurnContext` must carry every tuned value the real
route carries, and this asserts it mechanically instead of by reading.

Why this test exists rather than a third careful review. The eval harness
(`qa_coverage_runner.ask`) hand-builds a `TurnContext`, the HTTP route
(`chat_api.routers.sessions._turn_context`) builds its own, and the two drifted twice in the
same way: AUD-C-21/D-166 found `access_probe_max_distance` missing while trying to make an
assertion fail on purpose, D-172 found `min_relevance_score` missing for the same reason, and
each fix closed exactly the one field that session needed. Three more (`candidate_limit`,
`top_k`, `confidence_threshold`) were still missing when AUD-C-23 asked "is the harness the
route?" - not causing a wrong measurement, because the `TurnContext` defaults happen to equal
the `Settings` defaults, but leaving the instrument unable to see a tuned config on those
axes. `CHAT_RETRIEVAL_TOP_K=3` would have changed the route's behaviour and not the eval's.

The rule this encodes: **a field the route derives from `Settings` is a field the harness must
pass.** Fields that legitimately differ (`claims`, `client_ip`, the fakes) are ignored, because
they are what makes it a harness. Read from source with `ast` rather than by importing and
introspecting, so the test can see *which expression* supplies each keyword - the distinction
between "passed from settings" and "left to the dataclass default" is invisible at runtime,
and it is the whole thing being checked.
"""

import ast
from pathlib import Path

_CHAT_API_SRC = Path(__file__).resolve().parents[1] / "src" / "chat_api"
_ROUTE_FILE = _CHAT_API_SRC / "routers" / "sessions.py"
_HARNESS_FILE = Path(__file__).resolve().parent / "qa_coverage_runner.py"


def _turn_context_keywords(source_file: Path) -> dict[str, str]:
    """Every `TurnContext(...)` keyword in `source_file`, mapped to its argument source.

    Asserts there is exactly one such call per file: two would mean this test is reading one
    construction site while some other code path uses another, which is the class of mistake
    D-159 recorded (a guard written into a function with no callers).
    """
    tree = ast.parse(source_file.read_text())
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "TurnContext"
    ]
    assert len(calls) == 1, (
        f"expected exactly one TurnContext(...) construction in {source_file.name}, "
        f"found {len(calls)} - this test would only be checking one of them"
    )
    return {
        keyword.arg: ast.unparse(keyword.value)
        for keyword in calls[0].keywords
        if keyword.arg is not None
    }


def _settings_derived(keywords: dict[str, str]) -> set[str]:
    """Keywords whose value reads a `Settings` attribute, however it was spelled -
    `settings.x`, `get_settings().x`, or a conditional with one of those as a branch (which is
    how `min_relevance_score` carries its deliberate per-run override).
    """
    return {name for name, expression in keywords.items() if "settings" in expression}


def test_the_eval_harness_passes_every_tuned_value_the_route_passes() -> None:
    route_tuned = _settings_derived(_turn_context_keywords(_ROUTE_FILE))
    harness_passed = set(_turn_context_keywords(_HARNESS_FILE))

    missing = sorted(route_tuned - harness_passed)

    assert missing == [], (
        f"the paid coverage eval leaves these to TurnContext's defaults while the real route "
        f"reads them from Settings: {missing}. An eval that cannot see a tuned config cannot "
        f"be used to tune one - pass them in qa_coverage_runner.ask()."
    )


def test_the_route_is_still_the_thing_being_compared_against() -> None:
    """A control for the test above: if `_turn_context` stopped reading `Settings` at all, the
    parity assertion would pass vacuously with an empty set. Six fields are tuned today
    (candidate_limit, top_k, confidence_threshold, access_probe_max_distance,
    min_relevance_score, and whatever a future session adds); asserting a non-trivial floor
    means the comparison keeps having content.
    """
    route_tuned = _settings_derived(_turn_context_keywords(_ROUTE_FILE))

    assert len(route_tuned) >= 5, (
        f"only {sorted(route_tuned)} appear to come from Settings in the real route - either "
        f"the route changed shape or this test's detection did, and in both cases the parity "
        f"test above is now weaker than it reads"
    )
