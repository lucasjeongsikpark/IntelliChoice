"""D-385: every path this app serves must be admitted by *both* hand-maintained pattern
lists in terraform, and the ops/docs paths by neither.

**This failure class has already shipped once, and a user found it, not a test.** The
comment above `aws_lb_listener_rule.dev_token_learning` records it: a path-only listener
rule sent every `/dev/token` call to whichever app's rule had the lower priority, "found
live via a real 'Not found' bug report during S32/D-084". Nothing in the suite could see
it, because every test in this repo talks to the app directly and therefore never crosses
the two layers that decide whether a request reaches the app at all:

  1. **CloudFront** `api_path_patterns` (`module.cloudfront_learning`) - the edge behaviours
     that forward to the ALB origin. The *default* behaviour points at the SPA's S3 bucket
     with a SPA-fallback function and `GET, HEAD` only, so an unlisted path does not 404:
     a GET returns **cached `index.html`** (wrong content type, cached at the edge) and a
     POST returns a CloudFront **405**.
  2. **The ALB listener rule** `path_patterns` (`module.ecs_service_learning_api`). The
     listener's default action is a fixed `404 Not found`, so an unlisted path never
     reaches a target group.

The two lists are *not* identical - CloudFront's carries `/dev/token` and the ALB's does
not, because `/dev/token` is disambiguated by dedicated rules keyed on the
`X-IntelliChoice-App` header. So "I added it to the terraform" is not one edit, and a new
router under a new prefix is green locally and broken in staging.

The guard is written so a **new** route cannot pass silently: every served path must either
be admitted by both layers or be named in `_DELIBERATELY_UNREACHABLE`. Adding a route
under an existing prefix stays free; adding one under a new prefix fails here with the
list to edit.

Both directions are asserted, per D-221: `/metrics`, `/healthz`, `/readyz` and FastAPI's
own docs routes must be admitted by **neither** layer. `/metrics` behind a public cache
would be an information leak, and `/openapi.json` would publish the whole surface,
including the escalation and parent routes. They are unreachable today; this pins that
rather than leaving it to whoever next edits a pattern list.

The route walk is deliberately paranoid. FastAPI 0.141 keeps included routers as nested
`_IncludedRouter` objects, so the obvious `{r.path for r in app.routes}` finds the five
routes registered directly on `app` and **misses all six routers** - it would have made
this guard vacuous while looking correct, which is the same shape as D-378. Hence
`test_the_route_walk_is_not_vacuous`.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from learning_api.main import app

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STAGING_TF = _REPO_ROOT / "terraform" / "environments" / "staging" / "main.tf"

# Served, and intentionally not reachable from the internet by either layer.
# `/metrics` is scraped in-cluster; `/healthz` and `/readyz` are the ALB target-group
# health check, which addresses the task directly; the docs trio is FastAPI's default and
# has never been part of the public surface.
_DELIBERATELY_UNREACHABLE = {
    "/healthz",
    "/readyz",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}

# One route this app definitely serves, deep under a router prefix - the walk finding it is
# what proves the walk descended into the nested routers at all.
_A_ROUTE_ONLY_THE_NESTED_WALK_FINDS = "/learning/sessions/{learning_session_id}/answers"


def _terraform() -> str:
    return _STAGING_TF.read_text(encoding="utf-8")


def _block_body(header: str, text: str) -> str:
    """The body of a top-level terraform block, e.g. `module "cloudfront_learning"`.

    Top-level blocks in this file close with `}` in column 0, which is what bounds the
    search - a brace counter would be more general and is not needed for one file whose
    formatting `terraform fmt` already enforces.
    """
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
        "api_path_patterns", _block_body('module "cloudfront_learning"', _terraform())
    )


def _alb_patterns() -> list[str]:
    text = _terraform()
    admitted = _string_list("path_patterns", _block_body('module "ecs_service_learning_api"', text))
    # `/dev/token` reaches this app through its own rule rather than the service's list,
    # because one shared ALB cannot tell the two apps' `/dev/token` calls apart on path
    # alone. The `X-IntelliChoice-App` header condition is what disambiguates it; this
    # guard is about admission, so the path is what it collects.
    #
    # Scoped to the `path_pattern` sub-block on purpose: that rule holds **two** `values`
    # lists, the second being the header's `["learning"]`. Taking the first match happens to
    # be right today and would silently parse a header value as a path if the conditions
    # were ever reordered - precisely the drift this file exists to refuse.
    rule = _block_body('resource "aws_lb_listener_rule" "dev_token_learning"', text)
    dev_token = _string_list("values", _sub_block("path_pattern", rule))
    return [*admitted, *dev_token]


def _admits(patterns: list[str], path: str) -> bool:
    """CloudFront and ALB path patterns both use `*` as the only wildcard, and both match
    against the whole path."""
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
    assert len(paths) > 20, f"only {len(paths)} paths found; the walk is probably broken"


def test_dev_token_is_admitted_by_a_different_mechanism_at_each_layer() -> None:
    """The reason "add it to the terraform" is two edits and not one.

    The effective admission *sets* do come out equal, so asserting the lists differ would
    be false - what differs is where `/dev/token` comes from: a plain behaviour at the
    edge, a header-conditioned rule at the ALB. A future path needing the same treatment
    has to be added in both places, and only this asymmetry says so.
    """
    text = _terraform()
    service_list = _string_list(
        "path_patterns", _block_body('module "ecs_service_learning_api"', text)
    )

    assert "/dev/token" in _cloudfront_patterns()
    assert "/dev/token" not in service_list, (
        "`/dev/token` is now in the service's own path_patterns; if the dedicated "
        "`dev_token_learning` rule went away, the shared ALB can no longer tell this "
        "app's `/dev/token` calls from chat's - the exact S32/D-084 bug"
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
        "`module.cloudfront_learning` *and* `path_patterns` in "
        "`module.ecs_service_learning_api`, or add the path to "
        "`_DELIBERATELY_UNREACHABLE` here. Left alone, a GET returns the SPA's cached "
        "index.html and a POST returns 405 at the edge, or 404 at the ALB."
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
