"""D-385: chat-api's half of the deployed-route admission guard.

See `apps/learning-api/tests/test_deployed_route_admission_parity.py` for the full
argument: two hand-maintained pattern lists (CloudFront's `api_path_patterns` and the ALB
listener rule's `path_patterns`) decide whether a request reaches this app at all, neither
is exercised by any other test in this repo, and the failure is silent - a GET on an
unlisted path returns the SPA's cached `index.html`, a POST returns 405, and an unlisted
path at the ALB gets the listener's fixed 404.

The parsing helpers are duplicated rather than shared because `--import-mode=importlib`
with `testpaths = ["apps", "packages"]` gives no importable home for a helper used by two
app test suites, and a shared test package for two callers costs more than 30 duplicated
lines.

Chat's own asymmetry is `/me`: registered directly on `app` rather than under the `/chat`
router prefix, so it needs its own entry in both lists, and the terraform comment above
`module.cloudfront_chat` already says so. That is the same shape as `/dev/token`, which
needs a third mechanism again - a header-conditioned rule, because one shared ALB cannot
tell chat's `/dev/token` from learning's on path alone (S32/D-084, found by a user).
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from chat_api.main import app

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STAGING_TF = _REPO_ROOT / "terraform" / "environments" / "staging" / "main.tf"

_DELIBERATELY_UNREACHABLE = {
    "/healthz",
    "/readyz",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}

_A_ROUTE_ONLY_THE_NESTED_WALK_FINDS = "/chat/sessions/{chat_session_id}/messages"


def _terraform() -> str:
    return _STAGING_TF.read_text(encoding="utf-8")


def _block_body(header: str, text: str) -> str:
    start = text.index(f"{header} {{")
    end = text.index("\n}\n", start)
    return text[start:end]


def _sub_block(name: str, block: str) -> str:
    """The body of a nested block such as `path_pattern {` inside a listener rule."""
    start = block.index(f"{name} {{")
    end = block.index("\n    }", start)
    return block[start:end]


def _string_list(field: str, block: str) -> list[str]:
    match = re.search(rf"^\s*{field}\s*=\s*\[([^\]]*)\]", block, re.MULTILINE)
    assert match is not None, f"`{field}` not found in the terraform block"
    values = re.findall(r'"([^"]+)"', match.group(1))
    assert values, f"`{field}` parsed as empty, which would make this guard vacuous"
    return values


def _cloudfront_patterns() -> list[str]:
    return _string_list(
        "api_path_patterns", _block_body('module "cloudfront_chat"', _terraform())
    )


def _alb_patterns() -> list[str]:
    text = _terraform()
    admitted = _string_list(
        "path_patterns", _block_body('module "ecs_service_chat_api"', text)
    )
    # Scoped to the `path_pattern` sub-block because that rule holds **two** `values` lists,
    # the second being the `X-IntelliChoice-App` header's `["chat"]` - see the sibling file
    # for why taking the first match would be a silent trap.
    rule = _block_body('resource "aws_lb_listener_rule" "dev_token_chat"', text)
    dev_token = _string_list("values", _sub_block("path_pattern", rule))
    return [*admitted, *dev_token]


def _admits(patterns: list[str], path: str) -> bool:
    return any(
        re.fullmatch(re.escape(pattern).replace(r"\*", ".*"), path) is not None
        for pattern in patterns
    )


def _served_paths() -> set[str]:
    def walk(routes: list[Any]) -> Iterator[str]:
        for route in routes:
            path = getattr(route, "path", None)
            if path:
                yield path
            nested = getattr(route, "original_router", None)
            if nested is not None:
                yield from walk(nested.routes)

    return set(walk(list(app.routes)))


def test_the_route_walk_is_not_vacuous() -> None:
    paths = _served_paths()

    assert _A_ROUTE_ONLY_THE_NESTED_WALK_FINDS in paths, (
        "the walk did not descend into the included routers, so every other assertion in "
        "this file would pass while checking almost nothing"
    )
    assert len(paths) > 10, f"only {len(paths)} paths found; the walk is probably broken"


def test_the_two_paths_registered_outside_the_router_prefix_are_listed_explicitly() -> None:
    """`/me` and `/dev/token` are the ones a `/chat/*` pattern does not cover."""
    text = _terraform()
    service_list = _string_list(
        "path_patterns", _block_body('module "ecs_service_chat_api"', text)
    )

    assert "/me" in _cloudfront_patterns() and "/me" in service_list
    assert "/dev/token" in _cloudfront_patterns()
    assert "/dev/token" not in service_list, (
        "`/dev/token` is now in the service's own path_patterns; if the dedicated "
        "`dev_token_chat` rule went away, the shared ALB can no longer tell this app's "
        "`/dev/token` calls from learning's - the exact S32/D-084 bug"
    )
    assert "/dev/token" in _alb_patterns()


def test_every_served_path_is_admitted_by_both_layers_or_named_unreachable() -> None:
    cloudfront, alb = _cloudfront_patterns(), _alb_patterns()

    unclassified = sorted(
        path
        for path in _served_paths()
        if path not in _DELIBERATELY_UNREACHABLE
        and not (_admits(cloudfront, path) and _admits(alb, path))
    )

    assert not unclassified, (
        "these paths are served but not admitted by both deployment layers: "
        f"{unclassified}. Either add the prefix to `api_path_patterns` in "
        "`module.cloudfront_chat` *and* `path_patterns` in `module.ecs_service_chat_api`, "
        "or add the path to `_DELIBERATELY_UNREACHABLE` here. Left alone, a GET returns "
        "the SPA's cached index.html and a POST returns 405 at the edge, or 404 at the ALB."
    )


def test_the_ops_and_docs_paths_are_admitted_by_neither_layer() -> None:
    cloudfront, alb = _cloudfront_patterns(), _alb_patterns()

    leaked = sorted(
        path
        for path in _DELIBERATELY_UNREACHABLE
        if _admits(cloudfront, path) or _admits(alb, path)
    )

    assert not leaked, (
        f"{leaked} are now admitted from the internet. `/metrics` behind a public cache "
        "leaks operational data and `/openapi.json` publishes the whole API surface; if "
        "one of these is meant to be public, that is a decision, not a pattern edit."
    )


def test_the_unreachable_list_has_no_stale_entries() -> None:
    served = _served_paths()

    stale = sorted(path for path in _DELIBERATELY_UNREACHABLE if path not in served)

    assert not stale, (
        f"{stale} are listed as deliberately unreachable but this app no longer serves "
        "them, so the entries assert nothing - drop them"
    )
