"""Branch Locator (SPEC §5.1.3, §5.22): geocode the caller's location, compute a route
to every branch via the Google Maps MCP tools, and sort nearest-first. All three §5.22
fallbacks are handled here rather than surfaced as errors:

- "Location denied" (no location given at all) is handled one level up, before this
  service is ever called - `chat_api.graph.nodes.branch_locator_request` asks for a
  ZIP/city/address instead.
- "Maps unavailable" (`maps.geocode` fails or can't resolve the input) -> the branch
  address list only, no distances (`BranchLocatorStatus.MAPS_UNAVAILABLE`/
  `LOCATION_NOT_FOUND`).
- "Route unavailable" (`maps.compute_routes` fails for one branch) -> a locally computed
  straight-line distance, clearly labeled `is_estimate=True` - computed directly via
  `haversine_km`, never by retrying the same Maps call that just failed.

Precise coordinates never leave this function: `origin` (the geocoded caller location)
is used only to call `maps.compute_routes` and is discarded once this call returns -
only branch names/addresses/distances are handed back to the caller.
"""

from dataclasses import dataclass
from enum import StrEnum

from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_observability.metrics import QA_MAPS_CALLS
from intellichoice_observability.tracing import traced_span
from intellichoice_shared.maps import Coordinates, GeocodeQuery, RouteQuery, haversine_km
from intellichoice_shared.mcp import McpToolError, McpToolRegistry
from intellichoice_shared.profiles import BranchInfo, ProfileAdapter


class BranchLocatorStatus(StrEnum):
    OK = "ok"
    MAPS_UNAVAILABLE = "maps_unavailable"
    LOCATION_NOT_FOUND = "location_not_found"


@dataclass(frozen=True)
class BranchDistance:
    branch_external_id: str
    name: str
    address: str
    distance_km: float | None
    duration_minutes: float | None
    is_estimate: bool


@dataclass(frozen=True)
class BranchLocatorResult:
    status: BranchLocatorStatus
    branches: list[BranchDistance]


async def find_nearest_branches(
    *,
    profile_adapter: ProfileAdapter,
    mcp_registry: McpToolRegistry,
    mcp_call_repo: McpToolCallRepository,
    location: GeocodeQuery,
    caller_external_id: str | None,
) -> BranchLocatorResult:
    branches = await profile_adapter.list_branches()

    try:
        with traced_span("mcp.maps.geocode"):
            origin = await mcp_registry.call(
                "maps.geocode",
                location.model_dump(),
                caller_external_id=caller_external_id,
                audit_repo=mcp_call_repo,
            )
    except McpToolError:
        QA_MAPS_CALLS.labels(result="failure").inc()
        return BranchLocatorResult(
            status=BranchLocatorStatus.MAPS_UNAVAILABLE,
            branches=[_undistanced(b) for b in branches],
        )
    QA_MAPS_CALLS.labels(result="success").inc()

    if origin is None:
        return BranchLocatorResult(
            status=BranchLocatorStatus.LOCATION_NOT_FOUND,
            branches=[_undistanced(b) for b in branches],
        )

    assert isinstance(origin, Coordinates)
    results: list[BranchDistance] = []
    for branch in branches:
        destination = Coordinates(latitude=branch.latitude, longitude=branch.longitude)
        try:
            with traced_span("mcp.maps.compute_routes"):
                route = await mcp_registry.call(
                    "maps.compute_routes",
                    RouteQuery(origin=origin, destination=destination).model_dump(),
                    caller_external_id=caller_external_id,
                    audit_repo=mcp_call_repo,
                )
            results.append(
                BranchDistance(
                    branch_external_id=branch.branch_external_id,
                    name=branch.name,
                    address=branch.address,
                    distance_km=route.distance_km,
                    duration_minutes=route.duration_minutes,
                    is_estimate=False,
                )
            )
        except McpToolError:
            results.append(
                BranchDistance(
                    branch_external_id=branch.branch_external_id,
                    name=branch.name,
                    address=branch.address,
                    distance_km=round(haversine_km(origin, destination), 2),
                    duration_minutes=None,
                    is_estimate=True,
                )
            )

    results.sort(key=lambda r: r.distance_km if r.distance_km is not None else float("inf"))
    return BranchLocatorResult(status=BranchLocatorStatus.OK, branches=results)


def _undistanced(branch: BranchInfo) -> BranchDistance:
    return BranchDistance(
        branch_external_id=branch.branch_external_id,
        name=branch.name,
        address=branch.address,
        distance_km=None,
        duration_minutes=None,
        is_estimate=False,
    )
