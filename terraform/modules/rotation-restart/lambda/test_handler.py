"""Plain-Python tests for the rotation-restart handler, with a stubbed ECS client.

Outside pytest's `testpaths` (apps, packages) on purpose - run it explicitly:
`uv run pytest terraform/modules/rotation-restart/lambda/test_handler.py`.
"""

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

# Loaded by path: the repo runs pytest with `--import-mode=importlib`, which does not put this
# directory on sys.path, and the Lambda's module is deliberately a bare `handler.py`.
_spec = importlib.util.spec_from_file_location(
    "rotation_restart_handler", Path(__file__).with_name("handler.py")
)
assert _spec is not None and _spec.loader is not None
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)


class StubEcs:
    def __init__(self, fail: frozenset[str] = frozenset()) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def update_service(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if kwargs["service"] in self.fail:
            raise RuntimeError("stubbed UpdateService failure")
        return {"service": {"serviceName": kwargs["service"]}}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ECS_CLUSTER_NAME", "c")
    monkeypatch.setenv("ECS_SERVICE_NAMES", "learning, chat")


def _patch_client(monkeypatch: pytest.MonkeyPatch, stub: StubEcs) -> None:
    monkeypatch.setattr(h.boto3, "client", lambda name: stub)


def test_restarts_every_service(env: None, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    stub = StubEcs()
    _patch_client(monkeypatch, stub)

    assert h.handler({}, None) == {"restarted": ["learning", "chat"]}
    assert stub.calls == [
        {"cluster": "c", "service": "learning", "forceNewDeployment": True},
        {"cluster": "c", "service": "chat", "forceNewDeployment": True},
    ]
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [(r["service"], r["result"]) for r in lines] == [("learning", "ok"), ("chat", "ok")]


def test_one_failure_still_attempts_the_other_then_raises(
    env: None, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    stub = StubEcs(fail=frozenset({"learning"}))
    _patch_client(monkeypatch, stub)

    with pytest.raises(RuntimeError, match="learning"):
        h.handler({}, None)
    # The failing first service must not stop the second from being restarted.
    assert [c["service"] for c in stub.calls] == ["learning", "chat"]
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0] == {
        "action": "force_new_deployment",
        "cluster": "c",
        "service": "learning",
        "result": "error",
        "error": "RuntimeError",
    }
    assert lines[1]["result"] == "ok"


def test_empty_service_list_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ECS_CLUSTER_NAME", "c")
    monkeypatch.setenv("ECS_SERVICE_NAMES", " , ")
    _patch_client(monkeypatch, StubEcs())

    with pytest.raises(RuntimeError, match="empty"):
        h.handler({}, None)
