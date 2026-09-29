"""Force a new deployment of the API services after an RDS master-secret rotation (D-455).

Invoked by the EventBridge rule in `../main.tf` on Secrets Manager's `RotationSucceeded`
service event. The ECS tasks resolve the database password once, at task start, so after a
rotation every *new* connection fails until the tasks are replaced; this is the automated form
of the manual `aws ecs update-service --force-new-deployment` in INCIDENT_RESPONSE.md.

Every configured service is attempted even if an earlier one fails - one service's
`UpdateService` error must not leave the other on stale credentials - and the invocation then
raises, so Lambda marks it failed and the `Errors` alarm pages. Logs carry the cluster and
service names only: never the event payload, never anything read from the secret.
"""

import json
import os
from typing import Any

import boto3


def restart_services(ecs: Any, cluster: str, services: list[str]) -> list[str]:
    """Call `UpdateService(forceNewDeployment=True)` for each service; return the failures."""
    failed: list[str] = []
    for service in services:
        record: dict[str, str] = {
            "action": "force_new_deployment",
            "cluster": cluster,
            "service": service,
        }
        try:
            ecs.update_service(cluster=cluster, service=service, forceNewDeployment=True)
        except Exception as exc:
            # The exception class only: a ClientError message carries nothing secret today,
            # but "logs service names only" is simpler to keep true than to re-audit.
            record |= {"result": "error", "error": type(exc).__name__}
            failed.append(service)
        else:
            record["result"] = "ok"
        print(json.dumps(record))
    return failed


def _services_from_env() -> tuple[str, list[str]]:
    cluster = os.environ["ECS_CLUSTER_NAME"]
    services = [s.strip() for s in os.environ["ECS_SERVICE_NAMES"].split(",") if s.strip()]
    if not services:
        # An empty list would "succeed" while restarting nothing - the silent shape of D-455.
        raise RuntimeError("ECS_SERVICE_NAMES is empty; nothing would be restarted")
    return cluster, services


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    cluster, services = _services_from_env()
    failed = restart_services(boto3.client("ecs"), cluster, services)
    if failed:
        raise RuntimeError(f"force-new-deployment failed for: {', '.join(failed)}")
    return {"restarted": services}
