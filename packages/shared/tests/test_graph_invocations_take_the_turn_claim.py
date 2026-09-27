"""HB-LEARN-F1's contract, made executable: every graph invocation in the apps takes the turn
claim.

A LangGraph thread is not safe to invoke concurrently (D-346): `AsyncPostgresSaver` has no
optimistic-concurrency check, so two supersteps branching from one parent checkpoint both
write, and E3 measured the consequence at the graph layer - two simultaneous resumes of one
attendance pause both completed and sent two emails (`HB-LEARN-F1`). The serialization point
is deliberately the *route*, not the graph: chat-api's `_claim_turn` and learning-api's (D-376)
take `pg_try_advisory_xact_lock` on the thread before any invoke.

That is only a property of the code while every caller keeps doing it. This module turns it
from a convention into a failing test: it reads `apps/*/src` (source only - nothing is
imported or run) and asserts that the graph call sites, and the callers of the two wrappers
that hold them, are exactly the reviewed lists below, each annotated with the claim that
guards it. **A new call site fails here until someone reviews it and adds it with its claim.**
"""

import ast
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

CHAT_ROUTER = "apps/chat-api/src/chat_api/routers/sessions.py"
LEARNING_ROUTER = "apps/learning-api/src/learning_api/routers/sessions.py"

#: The methods that run a compiled graph. Matched on any receiver: nothing else in
#: `apps/*/src` uses these names today, and a false positive costs one review, while a
#: receiver-name heuristic could miss `self._graph.ainvoke(...)`.
GRAPH_RUN_METHODS = frozenset(
    {"ainvoke", "astream", "astream_events", "abatch", "invoke", "stream", "batch"}
)

#: `(file, enclosing function, method)` -> the claim that guards it.
GRAPH_CALL_SITES = {
    (CHAT_ROUTER, "_run_turn", "astream"): (
        "chat's only graph run. `_run_turn` takes no claim itself; every caller holds "
        "`_claim_turn` (D-346) before calling it - see RUN_TURN_CALLERS."
    ),
    (LEARNING_ROUTER, "_invoke_with_deadline", "ainvoke"): (
        "learning's only graph run. Takes `_claim_turn` itself before invoking whenever `db` "
        "is passed (D-376) - see INVOKE_WITH_DEADLINE_CALLERS, each of which passes it."
    ),
}

#: Callers of chat's `_run_turn` -> how the claim is already held when they call it.
RUN_TURN_CALLERS = {
    "post_message": "calls `_claim_turn` before `_reject_if_paused` and the turn",
    "respond_to_interrupt": "calls `_claim_turn` first, before reading the checkpoint",
    "_reject_if_paused": (
        "the expired-pause decline (HB-CHAT-F1); only ever called by `post_message`, "
        "after its `_claim_turn`"
    ),
}

#: Callers of learning's `_invoke_with_deadline` -> why that call is claimed. Each must pass
#: `db`, since the wrapper skips the claim without it (a test-only affordance).
INVOKE_WITH_DEADLINE_CALLERS = {
    "select_student": "passes `db`",
    "select_topic": "passes `db`",
    "resolve_attendance_choice": "passes `db`",
    "submit_answer": "passes `db`",
    "finalize_exam": "passes `db`",
    "respond_to_interrupt": "passes `db`",
    "resume_session": "passes `db`",
    "_decline_expired_pause": (
        "passes `db` (HB-CHAT-F1); its callers already took the claim in "
        "`_claim_if_pause_expired`, and the xact lock is re-entrant"
    ),
}


def _enclosing_calls(tree: ast.AST) -> list[tuple[str, ast.Call]]:
    """Every call in `tree`, paired with the name of its nearest enclosing function
    (`<module>` for a module-level call)."""
    found: list[tuple[str, ast.Call]] = []

    def visit(node: ast.AST, owner: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Call):
                found.append((owner, child))
            visit(child, owner)

    visit(tree, "<module>")
    return found


def graph_run_calls(source: str) -> list[tuple[str, str]]:
    """`(enclosing function, method)` for every `<x>.<graph-run method>(...)` in `source`."""
    return [
        (owner, call.func.attr)
        for owner, call in _enclosing_calls(ast.parse(source))
        if isinstance(call.func, ast.Attribute) and call.func.attr in GRAPH_RUN_METHODS
    ]


def calls_to(source: str, name: str) -> list[tuple[str, ast.Call]]:
    """`(enclosing function, call)` for every direct call of the bare name `name`."""
    return [
        (owner, call)
        for owner, call in _enclosing_calls(ast.parse(source))
        if isinstance(call.func, ast.Name) and call.func.id == name
    ]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text()


def test_every_graph_run_in_the_apps_is_a_reviewed_call_site() -> None:
    sources = sorted((REPO_ROOT / "apps").glob("*/src/**/*.py"))
    assert sources, "found no app sources - is REPO_ROOT right?"
    observed = {
        (str(path.relative_to(REPO_ROOT)), owner, method)
        for path in sources
        for owner, method in graph_run_calls(path.read_text())
    }
    unreviewed = observed - GRAPH_CALL_SITES.keys()
    assert not unreviewed, (
        f"new graph invocation(s) {sorted(unreviewed)}: a LangGraph thread is not safe to "
        "invoke concurrently (D-346), so each call site must take the route's turn claim. "
        "Review it, then add it to GRAPH_CALL_SITES with the claim that guards it."
    )
    gone = GRAPH_CALL_SITES.keys() - observed
    assert not gone, f"allowlisted call site(s) no longer exist: {sorted(gone)} - prune them"


def test_every_caller_of_chat_run_turn_holds_the_claim() -> None:
    source = _read(CHAT_ROUTER)
    callers = {owner for owner, _ in calls_to(source, "_run_turn")}
    assert callers == RUN_TURN_CALLERS.keys(), (
        f"`_run_turn` callers changed to {sorted(callers)}: review how each holds "
        "`_claim_turn` and update RUN_TURN_CALLERS"
    )
    claimers = {owner for owner, _ in calls_to(source, "_claim_turn")}
    assert {"post_message", "respond_to_interrupt"} <= claimers
    # `_reject_if_paused` resumes a pause itself, so it may only run under a claim its
    # caller already holds.
    assert {owner for owner, _ in calls_to(source, "_reject_if_paused")} == {"post_message"}


def test_every_caller_of_learning_invoke_with_deadline_passes_db() -> None:
    source = _read(LEARNING_ROUTER)
    sites = calls_to(source, "_invoke_with_deadline")
    callers = {owner for owner, _ in sites}
    assert callers == INVOKE_WITH_DEADLINE_CALLERS.keys(), (
        f"`_invoke_with_deadline` callers changed to {sorted(callers)}: review each and "
        "update INVOKE_WITH_DEADLINE_CALLERS"
    )
    for owner, call in sites:
        passes_db = len(call.args) >= 5 or any(k.arg == "db" for k in call.keywords)
        assert passes_db, f"{owner} calls `_invoke_with_deadline` without `db` - no turn claim"
    assert "_invoke_with_deadline" in {owner for owner, _ in calls_to(source, "_claim_turn")}


@pytest.mark.parametrize(
    "snippet, expected",
    [
        ("async def f(g):\n    await g.ainvoke(1)\n", [("f", "ainvoke")]),
        (
            "class C:\n    async def run(self):\n"
            "        async for s in self._graph.astream(1):\n            pass\n",
            [("run", "astream")],
        ),
        ("async def outer(g):\n    def inner():\n        g.invoke(1)\n", [("inner", "invoke")]),
        ("x = g.stream(1)\n", [("<module>", "stream")]),
        ("async def f(g):\n    await g.aget_state(1)\n", []),
    ],
)
def test_the_scanner_finds_a_graph_run_wherever_it_is(
    snippet: str, expected: list[tuple[str, str]]
) -> None:
    """The guard is only as good as its scanner: a fifth call site must be *seen*."""
    assert graph_run_calls(snippet) == expected
