"""E3.4 - builds the machine-readable HITL bypass-case inventory, and proves the count.

Run with:

    uv run python benchmarks/resume_evidence/03_gateway_agents/hitl_bypass_inventory.py
    uv run python .../hitl_bypass_inventory.py --out-dir /tmp/x

**Tier 1, $0.** Reads source and runs `pytest --collect-only`; executes no test, calls no
model, touches no database.

## Why the denominator is generated rather than written down

"N bypass attempts, 0 side effects" is only worth anything if N is a *collected* count.
This tool takes the two halves from different places and refuses to emit an inventory
unless they agree:

1. **The catalog** - each suite's module-level `BYPASS_CASES` list, read out of the source
   with `ast.literal_eval`. No import, so this works without the app packages on the path
   and cannot execute anything.
2. **The collection** - `pytest --collect-only -q` over the same files, giving the node ids
   that really exist.

A case in the catalog with no collected test, or a `[HB-...]` parametrization id with no
catalog entry, fails the run. The JSON it writes is what `E3_REPORT.md` quotes.

## Case kinds, and what each one may be counted inside

- `bypass` - an attempt that must produce no unauthorized external side effect. Only these
  are in the "N attempts, 0 side effects" numerator/denominator.
- `control` - a legitimate approval that must still work, so the suite cannot pass by
  refusing everything.
- `finding` / `architecture` - documented weaknesses or deliberate layer boundaries, with
  their own counts. Never folded into the bypass claim.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "resume_evidence" / "03_gateway_agents"

SUITES = (
    ("chat-api", "apps/chat-api/tests/test_hitl_bypass_suite.py"),
    ("learning-api", "apps/learning-api/tests/test_hitl_bypass_suite.py"),
    ("shared/mcp", "packages/shared/tests/test_hitl_bypass_mcp.py"),
)

_PARAM_ID_RE = re.compile(r"\[(HB-[A-Z]+-[A-Z0-9]+)\]")


def _resolve(node: ast.AST, constants: dict[str, object]) -> object:
    """`ast.literal_eval` plus module-level string constants.

    The catalogs use a few named placeholders (`OVERSIZED_NOTE`, `RESUME_ABSENT`,
    `LONG_NAME`, `VALID_ARGS`) so the payloads that need a computed value stay literal in
    the source. Resolving those names here keeps the reader import-free - it never
    executes the module, it only substitutes constants the module itself defines.
    """
    if isinstance(node, ast.Name):
        if node.id not in constants:
            raise AssertionError(f"catalog references undefined constant {node.id!r}")
        return constants[node.id]
    if isinstance(node, ast.List):
        return [_resolve(e, constants) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_resolve(e, constants) for e in node.elts)
    if isinstance(node, ast.Dict):
        return {
            _resolve(k, constants): _resolve(v, constants)
            for k, v in zip(node.keys, node.values, strict=True)
            if k is not None
        }
    return ast.literal_eval(node)


def read_catalog(path: pathlib.Path) -> list[dict]:
    """Pull `BYPASS_CASES` out of a test module without importing it."""
    tree = ast.parse(path.read_text())
    constants: dict[str, object] = {}
    catalog_node: ast.AST | None = None
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id == "BYPASS_CASES":
            catalog_node = node.value
            continue
        try:
            constants[target.id] = _resolve(node.value, constants)
        except (ValueError, AssertionError, TypeError):
            continue
    if catalog_node is None:
        raise AssertionError(f"{path} has no module-level BYPASS_CASES list")
    result = _resolve(catalog_node, constants)
    assert isinstance(result, list)
    return result


def collect_node_ids(paths: list[str]) -> list[str]:
    result = subprocess.run(
        ["uv", "run", "pytest", "--collect-only", "-q", *paths],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"pytest --collect-only failed ({result.returncode}):\n"
            f"{result.stdout[-3000:]}\n{result.stderr[-2000:]}"
        )
    return [line.strip() for line in result.stdout.splitlines() if "::" in line]


def node_ids_for(case_id: str, node_ids: list[str], suite_path: str) -> list[str]:
    """Match a catalog id to the tests that drive it.

    Two conventions, both used by the suites: a parametrized case carries its id in
    brackets (`...::test_x[HB-CHAT-01]`), and a case that needs its own function names it
    in snake case (`...::test_hb_chat_18_unknown_session_id`).
    """
    snake = case_id.lower().replace("-", "_")
    mine = [n for n in node_ids if n.startswith(suite_path)]
    return [n for n in mine if f"[{case_id}]" in n or snake in n.rsplit("::", 1)[-1]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    node_ids = collect_node_ids([path for _, path in SUITES])

    entries: list[dict] = []
    problems: list[str] = []
    for suite, rel_path in SUITES:
        catalog = read_catalog(REPO_ROOT / rel_path)
        for case in catalog:
            matched = node_ids_for(case["id"], node_ids, rel_path)
            if not matched:
                problems.append(f"{case['id']} ({suite}) is catalogued but collects no test")
            entries.append(
                {
                    "case_id": case["id"],
                    "kind": case["kind"],
                    "suite": suite,
                    "file": rel_path,
                    "surface": case["surface"],
                    "attack": case["attack"],
                    "expected_invariant": case["invariant"],
                    "test_node_ids": matched,
                }
            )

    catalogued_ids = {e["case_id"] for e in entries}
    for node in node_ids:
        found = _PARAM_ID_RE.search(node)
        if found and found.group(1) not in catalogued_ids:
            problems.append(
                f"{found.group(1)} is a collected parametrization with no catalog entry"
            )

    if problems:
        for problem in problems:
            print(f"INCONSISTENT: {problem}", file=sys.stderr)
        raise SystemExit(1)

    kinds = Counter(e["kind"] for e in entries)
    by_suite = Counter(e["suite"] for e in entries)
    bypass_nodes = sum(len(e["test_node_ids"]) for e in entries if e["kind"] == "bypass")

    inventory = {
        "generated_at": datetime.now(UTC).isoformat(),
        "git_sha": _git_sha(),
        "environment": (
            "local - pytest collection over the three permanent bypass suites; no test "
            "executed by this tool"
        ),
        "cost_usd": 0.0,
        "totals": {
            "cases": len(entries),
            "bypass_attempts": kinds["bypass"],
            "controls": kinds["control"],
            "findings": kinds["finding"],
            "architecture_notes": kinds["architecture"],
            "collected_tests_for_bypass_cases": bypass_nodes,
            "collected_tests_total": len(node_ids),
        },
        "by_suite": dict(by_suite),
        "suites": [{"suite": s, "file": p} for s, p in SUITES],
        "cases": entries,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / "hitl_bypass_inventory.json"
    out.write_text(json.dumps(inventory, indent=2) + "\n")

    print(f"{len(entries)} catalogued cases across {len(SUITES)} suites -> {out}")
    for kind, count in sorted(kinds.items()):
        print(f"  {kind:<14} {count}")
    print(f"  collected tests (all) {len(node_ids)}")
    return 0


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):  # pragma: no cover
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
