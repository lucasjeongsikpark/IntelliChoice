"""Dev/test `MapsProvider` (SPEC §5.22) - a small deterministic gazetteer plus a real
haversine distance/duration formula, standing in for the Google Maps Geocoding and
Routes APIs. A real client (API-key-restricted, per SPEC §5.22's security-best-practices
link) is selected by env config once real Google Maps credentials exist (D-002).

`fail_geocode`/`fail_routes` let a test simulate "Maps unavailable"/"Route unavailable"
(SPEC §5.22's fallback ladder) without needing a real outage.
"""

import hashlib

from intellichoice_shared.maps import (
    Coordinates,
    GeocodeQuery,
    RouteQuery,
    RouteResult,
    haversine_km,
)

# A few named dev fixture locations (Springfield-area, matching the seeded branch
# addresses) so tests can assert specific, human-readable geocode results.
_KNOWN_LOCATIONS: dict[str, Coordinates] = {
    "62704": Coordinates(latitude=39.7817, longitude=-89.6501),
    "springfield": Coordinates(latitude=39.7990, longitude=-89.6650),
    "100 learning way, springfield": Coordinates(latitude=39.7817, longitude=-89.6501),
    "45 oakridge ave, springfield": Coordinates(latitude=39.8500, longitude=-89.6900),
}

# A dev-only estimate for turning straight-line distance into a plausible drive time -
# not a real routing engine, just enough to produce a sortable, sane-looking number.
_ASSUMED_AVG_SPEED_KMH = 40.0


def _hash_to_coordinates(key: str) -> Coordinates:
    """Deterministic pseudo-geocode for any string not in `_KNOWN_LOCATIONS` - same
    input always maps to the same point, kept within continental-US-ish bounds so
    distances stay plausible in tests and manual verification.
    """
    digest = hashlib.sha256(key.encode()).hexdigest()
    lat = 25.0 + (int(digest[:8], 16) % 20_000) / 1000.0  # ~25-45 deg N
    lon = -125.0 + (int(digest[8:16], 16) % 55_000) / 1000.0  # ~-125 to -70 deg W
    return Coordinates(latitude=lat, longitude=lon)


class FakeMapsProvider:
    def __init__(self) -> None:
        self.fail_geocode = False
        self.fail_routes = False

    async def geocode(self, query: GeocodeQuery) -> Coordinates | None:
        if self.fail_geocode:
            raise ConnectionError("fake Maps geocoding outage")
        if query.latitude is not None and query.longitude is not None:
            return Coordinates(latitude=query.latitude, longitude=query.longitude)
        key = (query.zip_code or query.city or query.address or "").strip().lower()
        if not key:
            return None
        return _KNOWN_LOCATIONS.get(key) or _hash_to_coordinates(key)

    async def compute_route(self, query: RouteQuery) -> RouteResult | None:
        if self.fail_routes:
            raise ConnectionError("fake Maps routing outage")
        distance_km = haversine_km(query.origin, query.destination)
        duration_minutes = (distance_km / _ASSUMED_AVG_SPEED_KMH) * 60
        return RouteResult(
            distance_km=round(distance_km, 2), duration_minutes=round(duration_minutes, 1)
        )
