"""E5.3 - is each roster model *invocable* on this account, right now?

    uv run python benchmarks/resume_evidence/05_content_generation/model_invocability_probe.py \
        --out docs/resume_evidence/05_content_generation/e5_3/model_invocability.json

**Why this exists as its own artifact.** `pipeline_cli --preflight` already probes the same
models (`_unavailable_models`), but it prints one aggregate `model access: PASS/FAIL` line -
a paid run's evidence needs the per-model verdict, the account, the region and the
timestamp, because the fact being recorded expires. D-273 is the reason: Sonnet 5 reports
`agreementAvailability = AVAILABLE` and returns `AccessDenied` when invoked, so availability
is not invocability, and QUESTION_GENERATION.md's rule is to *re-measure* before a paid run
rather than trust the 2026-08-11 stratum's date.

**Cost.** One `converse` per distinct model id with `maxTokens: 1` - the same shape the
preflight uses. Four ids, deduplicated to the two distinct models the roster resolves to;
well under a tenth of a cent in total.

The probe classifies exactly as the preflight does: only `AccessDeniedException`,
`ValidationException` and `ResourceNotFoundException` mean "not invocable". A throttle or a
transient fault is recorded as `inconclusive`, never as a failure - failing a run on a
throttle would be worse than the problem this check solves.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
from datetime import UTC, datetime
from typing import Any

from intellichoice_curriculum.settings import get_pipeline_settings

BLOCKING_ERROR_CODES = ("AccessDeniedException", "ValidationException", "ResourceNotFoundException")


def roster(settings: Any) -> dict[str, str]:
    """The four generation-pipeline slots, by role. `equation_design` falls back to the
    authored-generation model exactly as `pipeline_cli._build_gateway` does, so the probe
    covers what the run will actually call."""
    return {
        "generator (authored)": settings.bedrock_authored_generation_model_id,
        "solver_a": settings.bedrock_generation_model_id,
        "solver_b": settings.bedrock_review_model_id,
        "judge": settings.bedrock_judge_model_id,
        "equation_design": (
            settings.bedrock_equation_design_model_id
            or settings.bedrock_authored_generation_model_id
        ),
    }


def classify(error_code: str | None) -> str:
    """`invocable` | `not_invocable` | `inconclusive`. Pure, so it is unit-testable without
    an AWS account."""
    if error_code is None:
        return "invocable"
    if error_code in BLOCKING_ERROR_CODES:
        return "not_invocable"
    return "inconclusive"


def probe(model_id: str, region: str) -> dict[str, Any]:
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client("bedrock-runtime", region_name=region)
    started = datetime.now(UTC)
    try:
        client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "ok"}]}],
            inferenceConfig={"maxTokens": 1},
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "") or None
        return {
            "model_id": model_id,
            "verdict": classify(code),
            "error_code": code,
            "error_message": exc.response.get("Error", {}).get("Message", ""),
            "probed_at": started.isoformat(),
        }
    except Exception as exc:  # noqa: BLE001 - a probe must never be the thing that breaks a run
        return {
            "model_id": model_id,
            "verdict": "inconclusive",
            "error_code": type(exc).__name__,
            "error_message": str(exc),
            "probed_at": started.isoformat(),
        }
    return {
        "model_id": model_id,
        "verdict": "invocable",
        "error_code": None,
        "error_message": "",
        "probed_at": started.isoformat(),
    }


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _account(region: str) -> str:
    try:
        import boto3

        return str(boto3.client("sts", region_name=region).get_caller_identity()["Account"])
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None, help="write the JSON artifact here")
    args = parser.parse_args()

    settings = get_pipeline_settings()
    slots = roster(settings)
    if settings.bedrock_provider != "bedrock":
        print(
            f"provider is {settings.bedrock_provider!r}, not 'bedrock' - nothing to probe. "
            "Set CURRICULUM_BEDROCK_PROVIDER=bedrock to measure invocability."
        )
        return 2

    distinct = sorted({model_id for model_id in slots.values() if model_id})
    results = {model_id: probe(model_id, settings.bedrock_aws_region) for model_id in distinct}

    payload = {
        "experiment": "E5.3",
        "measured_at": datetime.now(UTC).isoformat(),
        "git_sha": _git_sha(),
        "environment": "real Bedrock (bedrock-runtime converse, maxTokens=1)",
        "aws_region": settings.bedrock_aws_region,
        "aws_account": _account(settings.bedrock_aws_region),
        "roster": slots,
        "distinct_model_ids": distinct,
        "results": results,
        "all_invocable": all(r["verdict"] == "invocable" for r in results.values()),
    }

    text = json.dumps(payload, indent=2)
    print(text)
    if args.out:
        path = pathlib.Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(f"\nwrote {path}")
    return 0 if payload["all_invocable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
