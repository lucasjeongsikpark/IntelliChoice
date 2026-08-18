#!/usr/bin/env python
"""AUD-X-16 / D-417 A3: does every place a task image is recorded agree with what is running?

**What this used to be, and why it changed.** It began as a *tfvars floor* check: the two image
tags in `terraform/environments/staging/terraform.tfvars` had to match reality before any apply,
because a bare `terraform apply` would otherwise re-register whatever those tags said. That was
true when it was written, and it stopped being true with **D-244**, which made Terraform read the
image from the *deployed* container definition and left the tfvars tags as nothing but the
bootstrap fallback for an environment that has no task definition yet
(`adopt_deployed_image`, default **true**).

**Measured 2026-08-18 rather than reasoned about.** With the pin two deploys stale at
`gha-df79b290bf65`, `terraform plan` moved the task definitions **forward** to the running
`gha-44a12dfc9549` - the direction the old failure message said was impossible. So the pin was the
only disagreeing value, it has no consumer while `adopt_deployed_image` is true, and this check had
been refusing applies over it. **A check that fails on an input nothing reads is worse than no
check: it teaches its operator to bypass it.**

**What is still worth checking, and it is not the pin.** Two of the three original shapes are real:

  - the image each ECS service is actually *running* (primary deployment - reality), and
  - the image each task-definition family's *latest* revision carries, **including `ops-task`**:
    `deploy-staging.yml` resolves families by name and the EventBridge schedules run the ops-task
    family **un-pinned**, so a stale latest revision - e.g. one registered by an accidental apply,
    D-137's exact incident - is what the next scheduled `memory-consolidate` firing would run,
    silently. Nothing else in this repo checks that.

The tfvars tags are now read **only** to report them, and only when the file exists, since a fresh
checkout has no such file by design and must not be told to hand-maintain a value with no consumer.
They are excluded from the verdict.

Any disagreement between the running and latest sets exits 1 with the full table. A read failure
(no credentials, missing service) exits 2 (INVALID) rather than pretending to a verdict - the
`scan_xray_pii.py` rule that a check that cannot fail is worthless.

Read-only: describe/list calls only. Run via `make image-check`.
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


def read_bootstrap_pins() -> dict[str, str]:
    """The tfvars tags, **reported and never judged** (D-417 A3).

    Absent file, absent variable and stale value are all fine now. `adopt_deployed_image`
    defaults to true, so Terraform reads the deployed container definition and these tags are
    reached only by the `try()` fallback on an environment that has no task definition yet. A
    gitignored file is exactly the wrong place for an instruction, which is what this script was
    written to fix - so it must not now *demand* one.
    """
    if not TFVARS.exists():
        return {}
    text = TFVARS.read_text()
    pins: dict[str, str] = {}
    for var in FLOOR_VARS:
        match = re.search(rf'^\s*{var}\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if match is not None:
            pins[var] = match.group(1)
    return pins


def image_tag(image: str) -> str:
    return image.rsplit(":", 1)[1] if ":" in image else "<untagged>"


def main() -> None:
    pins = read_bootstrap_pins()

    ecs = boto3.client("ecs", region_name=REGION)
    # Deliberately does **not** seed `tags` with the tfvars pins - they are printed below and
    # excluded from the verdict (D-417 A3). Seeding them here is what made a stale, unread value
    # able to fail the check.
    tags: dict[str, str] = {}

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

    running = {tag for source, tag in tags.items() if source.startswith("running ")}
    for var, tag in pins.items():
        stale = " (stale, and harmless — see this script's docstring)" if tag not in running else ""
        print(f"bootstrap pin  {var}: {tag}{stale}")
    if not pins:
        print("bootstrap pin  none — no terraform.tfvars here, which is expected and fine")

    distinct = sorted(set(tags.values()))
    if len(distinct) == 1:
        print(f"VERDICT: OK — every deployed image agrees: {distinct[0]}")
        return

    print(f"VERDICT: FAIL — {len(distinct)} different deployed images: {', '.join(distinct)}")
    for source, tag in sorted(tags.items()):
        print(f"  {tag}  <- {source}")
    print(
        "This is a real disagreement between what a service is running and what a family's "
        "latest revision carries, so something resolving a family **by name** would run the "
        "wrong code: `deploy-staging.yml` does that, and the EventBridge schedules run the "
        "ops-task family un-pinned - D-137's incident. Finish or roll back the half-done "
        "deploy; do not bump anything by hand. Terraform adopts the deployed image itself "
        "(D-244), so the tfvars pins above are not the fix and never were."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
