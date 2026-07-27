"""Guard against the third-and-hopefully-last instance of one deployment bug (S40).

Every standalone CLI runs inside the **ops task**, whose environment supplies the
*unprefixed* five-component DSN vars (`DB_HOST`, `DB_PORT`, `DB_NAME`, plus username and
password from Secrets Manager) that `create_engine`'s D-092 fallback resolves. A CLI that
instead passes an app-settings URL - `create_engine(get_settings().database_url)` - reads
`LEARNING_`/`CHAT_`-prefixed env vars, finds none in the ops task, and silently falls back
to the hardcoded `localhost` default.

Nothing about that failure is visible locally, which is the whole problem: on a developer's
machine localhost *is* the database, so the CLI passes every manual test and every unit
test, then fails only against a real deployment. It has now happened three times:

1. S32/D-084 - `curriculum-load` against real RDS (recorded in `create_engine`'s docstring).
2. S40 - `tutor_chat_purge_cli`, found when its **first ever scheduled run** died with
   `ConnectionRefusedError: Connect call failed ('127.0.0.1', 5432)`. The 90-day retention
   promise had never once executed against the deployed database.
3. (this test exists so there is no third.)

A source-level check rather than a behavioural one, deliberately. The behaviour that needs
guarding is "does not read the app's prefixed settings", and the only honest way to observe
that at runtime is to have no database reachable at localhost - which is exactly the
condition a developer's machine cannot reproduce. `test_engine_component_dsn.py` covers the
other half: that a bare `create_engine()` really does honour the component vars.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Modules invoked as `python -m <module>` by a Makefile target or an EventBridge schedule,
# i.e. anything that runs in the ops task rather than inside a FastAPI process.
STANDALONE_CLIS = [
    "apps/learning-api/src/learning_api/services/tutor_chat_purge_cli.py",
    "packages/memory/src/intellichoice_memory/consolidate_cli.py",
    "packages/youtube/src/intellichoice_youtube/sync_cli.py",
]

# The FastAPI apps legitimately pass their own settings URL: their task definitions supply
# the prefixed components. Listed so the distinction is explicit rather than an omission.
ALLOWED_EXPLICIT_URL = [
    "apps/learning-api/src/learning_api/main.py",
    "apps/chat-api/src/chat_api/main.py",
]


def _create_engine_calls_with_arguments(source: str) -> list[int]:
    """Line numbers of `create_engine(<something>)` calls that pass an argument."""
    tree = ast.parse(source)
    offending: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name != "create_engine":
            continue
        if node.args or node.keywords:
            offending.append(node.lineno)
    return offending


@pytest.mark.parametrize("relative_path", STANDALONE_CLIS)
def test_standalone_cli_calls_create_engine_bare(relative_path: str) -> None:
    path = _REPO_ROOT / relative_path
    assert path.exists(), f"{relative_path} moved - update STANDALONE_CLIS"

    offending = _create_engine_calls_with_arguments(path.read_text())
    assert not offending, (
        f"{relative_path} lines {offending}: call `create_engine()` with no argument. "
        "Passing an app-settings URL makes this CLI read LEARNING_/CHAT_-prefixed env "
        "vars, which the ops task does not set, so it silently connects to localhost in "
        "the deployed environment. See this module's docstring."
    )


def test_the_fastapi_apps_still_pass_their_settings_url() -> None:
    """The negative arm. If this ever fails, the check above has been applied too broadly:
    the long-running apps *should* pass an explicit URL, and a blanket "never pass an
    argument" rule would be wrong for them."""
    for relative_path in ALLOWED_EXPLICIT_URL:
        path = _REPO_ROOT / relative_path
        assert path.exists(), f"{relative_path} moved - update ALLOWED_EXPLICIT_URL"
        assert _create_engine_calls_with_arguments(path.read_text()), (
            f"{relative_path} no longer passes an explicit database URL. That may be "
            "correct, but it is a deliberate change - confirm the app still resolves its "
            "DSN and update this list."
        )
