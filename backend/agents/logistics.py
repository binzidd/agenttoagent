"""
LogisticsAgent – calculates riding distance & duration from home to any
target coordinates using the free OSRM routing engine.  No API key required.
"""
import httpx
from config import settings


class LogisticsAgent:
    """Calculates riding distance from home to a target GPS coordinate."""

    OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"

    async def get_route(self, target_lat: float, target_lon: float) -> dict:
        url = (
            f"{self.OSRM_BASE}/"
            f"{settings.home_lon},{settings.home_lat};"
            f"{target_lon},{target_lat}"
            "?overview=false&steps=false"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        route = data["routes"][0]
        distance_km = round(route["distance"] / 1000, 2)
        duration_min = round(route["duration"] / 60, 1)

        return {
            "agent": "Logistics",
            "distance_km": distance_km,
            "duration_min": duration_min,
            "round_trip_km": round(distance_km * 2, 2),
        }
