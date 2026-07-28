"""Google Maps MCP stand-in schemas (SPEC §5.22, §5.1.3).

Two tools are registered against `MapsProvider` (`maps.geocode`/`maps.compute_routes`),
mirroring `CalendarTransport`'s shape - real Google Maps credentials don't exist yet
(D-002's posture), so a fake provider is the dev/test default. "Sort branches" (the
diagram's third step, `maps.find_nearest_branch`) is local business logic over already
-fetched branch coordinates, not a second external call, so it isn't its own MCP tool -
see `chat_api.services.branch_locator`.

No field here is ever persisted past the single request that consumes it (SPEC §5.1.3
"discard precise coordinates after the ... request completes" / "do not store precise
coordinates in PostgreSQL, MySQL, LangSmith, or application logs").
"""

import math
from typing import Protocol

from pydantic import BaseModel, model_validator

_EARTH_RADIUS_KM = 6371.0


class GeocodeQuery(BaseModel):
    """Exactly one location form - SPEC §5.1.3's ZIP/city/address/precise-coordinate
    ladder. `extra="forbid"` isn't needed here (this never crosses the Bedrock gateway,
    only the MCP registry's own Pydantic validation boundary), but the exactly-one-form
    invariant still matters: a query with two forms set is ambiguous about which the
    caller actually means.
    """

    zip_code: str | None = None
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @model_validator(mode="after")
    def _exactly_one_form(self) -> "GeocodeQuery":
        forms = [
            bool(self.zip_code and self.zip_code.strip()),
            bool(self.city and self.city.strip()),
            bool(self.address and self.address.strip()),
            self.latitude is not None and self.longitude is not None,
        ]
        if sum(forms) != 1:
            raise ValueError(
                "exactly one of zip_code, city, address, or (latitude, longitude) "
                "must be provided"
            )
        return self


class Coordinates(BaseModel):
    latitude: float
    longitude: float


class RouteQuery(BaseModel):
    origin: Coordinates
    destination: Coordinates


class RouteResult(BaseModel):
    distance_km: float
    duration_minutes: float


class MapsProvider(Protocol):
    async def geocode(self, query: GeocodeQuery) -> Coordinates | None: ...

    async def compute_route(self, query: RouteQuery) -> RouteResult | None: ...


def haversine_km(a: Coordinates, b: Coordinates) -> float:
    """Pure great-circle distance - used by `FakeMapsProvider.compute_route` for its
    normal path, and directly by `chat_api.services.branch_locator`'s "Route unavailable
    -> clearly labeled straight-line estimate" fallback (SPEC §5.22), which must not
    depend on the same Maps routing call that just failed.
    """
    lat1, lon1, lat2, lon2 = map(math.radians, (a.latitude, a.longitude, b.latitude, b.longitude))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(h))
