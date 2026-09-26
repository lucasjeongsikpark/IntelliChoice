"""Guard: both apps are served with uvicorn's `--reset-contextvars` (D-464).

`test_trace_id_isolation_across_keepalive.py` proves the flag is what keeps two requests on one
keep-alive connection in separate traces. That proof is only worth anything if the flag is
actually on the command line that serves traffic, and nothing else would notice it going
missing: without it every request still succeeds, and the damage (0.14% of traces nested inside
an unrelated request, E6.2) is visible only in X-Ray after a deploy.

A source-level check, like `test_standalone_clis_use_the_env_fallback.py`, because the command
line lives in a Dockerfile `CMD` and a Makefile recipe - neither is Python that a behavioural
test could import.
"""

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

_FLAG = "--reset-contextvars"

DOCKERFILES = [
    "apps/learning-api/Dockerfile",
    "apps/chat-api/Dockerfile",
]

MAKEFILE_DEV_TARGETS = ["dev-learning", "dev-chat"]


def _cmd_argv(dockerfile: str) -> list[str]:
    """The exec-form `CMD [...]` array, parsed as JSON - so the flag has to be a real argv
    element, not a word in a comment."""
    lines = [
        line
        for line in (_REPO_ROOT / dockerfile).read_text().splitlines()
        if line.startswith("CMD [")
    ]
    assert len(lines) == 1, f"{dockerfile}: expected exactly one exec-form CMD, found {lines}"
    return json.loads(lines[0].removeprefix("CMD "))


def _recipe(target: str) -> list[str]:
    """The recipe lines (tab-indented) of one Makefile target."""
    lines = (_REPO_ROOT / "Makefile").read_text().splitlines()
    header = re.compile(rf"^{re.escape(target)}:")
    start = next((i for i, line in enumerate(lines) if header.match(line)), None)
    assert start is not None, f"Makefile has no `{target}` target"
    recipe: list[str] = []
    for line in lines[start + 1 :]:
        if not line.startswith("\t"):
            break
        recipe.append(line.strip())
    return recipe


@pytest.mark.parametrize("dockerfile", DOCKERFILES)
def test_the_container_cmd_resets_contextvars_per_request(dockerfile: str) -> None:
    argv = _cmd_argv(dockerfile)
    assert argv[0] == "uvicorn", f"{dockerfile}: CMD no longer runs uvicorn directly: {argv}"
    assert _FLAG in argv, (
        f"{dockerfile}: CMD lost {_FLAG}, so a keep-alive request can inherit the previous "
        "request's OTel span and join its trace (D-464)"
    )


@pytest.mark.parametrize("target", MAKEFILE_DEV_TARGETS)
def test_the_local_dev_server_resets_contextvars_per_request(target: str) -> None:
    uvicorn_lines = [line for line in _recipe(target) if "uvicorn" in line]
    assert uvicorn_lines, f"Makefile `{target}` no longer runs uvicorn"
    for line in uvicorn_lines:
        assert _FLAG in line.split(), (
            f"Makefile `{target}` serves without {_FLAG}, unlike the containers: {line}"
        )
