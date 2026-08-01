#!/usr/bin/env python
"""AUD-X-16: the tfvars image-tag floor check, as an executable step.

**Why this is a script.** `terraform/environments/staging/terraform.tfvars` holds the
image tags Terraform registers when it (re)creates the task definitions — the *floor*,
since `deploy-staging.yml` patches the real tag on top. Three times in three days
(S39/AUD-F-30, D-137, D-142/AUD-F-34) that floor went stale behind the deployed
reality, and each time a bare `terraform apply` was one step away from re-registering
an image that predates the fix that mattered most that week. The instruction "check the
floor against the running image before every apply" lived as a comment **inside a
gitignored file** — invisible to any fresh checkout, which explains the repetition
better than inattention does. This script is that comment made executable and tracked.

**The invariant it checks is one sentence: every place a task image tag is recorded
must agree.** Concretely, all of these must be the same tag:

  - the two floor tags in terraform.tfvars (`learning_api_image_tag`,
    `chat_api_image_tag`),
  - the image each ECS service is actually *running* (primary deployment's task
    definition — reality),
  - the image each task-definition family's *latest* revision carries, including
    `ops-task`: `deploy-staging.yml` resolves families by name and the EventBridge
    schedules run the ops-task family **un-pinned**, so a stale latest revision — e.g.
    one registered by an accidental apply, D-137's exact incident — is what the next
    scheduled `memory-consolidate` firing would run, silently.

Any disagreement exits 1 with the full table, because every disagreement is one of the
shapes above waiting to happen. A read failure (no credentials, missing service) exits
2 (INVALID) rather than pretending to a verdict — the `scan_xray_pii.py` rule that a
check that cannot fail is worthless.

Read-only: describe/list calls only. Run via `make tfvars-floor-check`, and as the
first step before any `terraform apply` in `terraform/environments/staging`.
"""

import re
import sys
from pathlib import Path

import boto3

REGION = "us-east-1"
CLUSTER = "intellichoice-staging"
SERVICES = ["intellichoice-staging-learning-api", "intellichoice-staging-chat-api"]
FAMILIES = [
    "intellichoice-staging-learning-api",
    "intellichoice-staging-chat-api",
    "intellichoice-staging-ops-task",
]
TFVARS = Path(__file__).resolve().parents[1] / "terraform/environments/staging/terraform.tfvars"
FLOOR_VARS = ["learning_api_image_tag", "chat_api_image_tag"]


def fail(message: str, code: int) -> None:
    print(f"VERDICT: {'INVALID' if code == 2 else 'FAIL'} — {message}")
    sys.exit(code)


def read_floor() -> dict[str, str]:
    if not TFVARS.exists():
        fail(
            f"{TFVARS} does not exist. The file is gitignored (*.tfvars), so a fresh "
            "checkout does not have it — copy terraform.tfvars.example and set the "
            "image-tag floor to the RUNNING image (see this script's docstring and "
            "D-137/D-142 in docs/DECISIONS.md) before any apply.",
            1,
        )
    text = TFVARS.read_text()
    floor: dict[str, str] = {}
    for var in FLOOR_VARS:
        match = re.search(rf'^\s*{var}\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if match is None:
            fail(f"{var} not found in {TFVARS} — the floor is unset, not merely stale.", 1)
        else:
            floor[var] = match.group(1)
    return floor


def image_tag(image: str) -> str:
    return image.rsplit(":", 1)[1] if ":" in image else "<untagged>"


def main() -> None:
    floor = read_floor()

    ecs = boto3.client("ecs", region_name=REGION)
    tags: dict[str, str] = {f"tfvars {var}": tag for var, tag in floor.items()}

    try:
        described = ecs.describe_services(cluster=CLUSTER, services=SERVICES)["services"]
        by_name = {service["serviceName"]: service for service in described}
        for name in SERVICES:
            service = by_name.get(name)
            if service is None or service.get("status") != "ACTIVE":
                fail(f"service {name} not found/ACTIVE in cluster {CLUSTER}", 2)
                return
            # The PRIMARY deployment is what is serving traffic (or rolling out now);
            # service["taskDefinition"] is the same target but doesn't reflect an
            # in-flight rollout's source, so read the deployment explicitly.
            primary = next(d for d in service["deployments"] if d["status"] == "PRIMARY")
            taskdef = ecs.describe_task_definition(taskDefinition=primary["taskDefinition"])
            image = taskdef["taskDefinition"]["containerDefinitions"][0]["image"]
            revision = primary["taskDefinition"].rsplit("/", 1)[-1]
            print(f"running  {name}: {image_tag(image)}  ({revision})")
            tags[f"running {name}"] = image_tag(image)

        for family in FAMILIES:
            taskdef = ecs.describe_task_definition(taskDefinition=family)["taskDefinition"]
            image = taskdef["containerDefinitions"][0]["image"]
            revision = taskdef["revision"]
            print(f"latest   {family}: {image_tag(image)}  (revision {revision})")
            tags[f"latest {family}"] = image_tag(image)
    except Exception as exc:  # noqa: BLE001 - INVALID beats a stack trace here
        fail(f"AWS read failed ({type(exc).__name__}: {exc})", 2)
        return

    for var, tag in floor.items():
        print(f"floor    {var}: {tag}")

    distinct = sorted(set(tags.values()))
    if len(distinct) == 1:
        print(f"VERDICT: OK — every recorded image tag agrees: {distinct[0]}")
        return

    print(f"VERDICT: FAIL — {len(distinct)} different tags recorded: {', '.join(distinct)}")
    for source, tag in sorted(tags.items()):
        print(f"  {tag}  <- {source}")
    print(
        "A bare `terraform apply` (or the next un-pinned scheduled ops-task firing) "
        "would run a tag that disagrees with what is deployed. Bump the floor in "
        f"{TFVARS} to the running tag (or finish/roll back the half-done deploy) "
        "before applying — D-137/D-142 in docs/DECISIONS.md are the incidents this "
        "check exists to prevent."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
