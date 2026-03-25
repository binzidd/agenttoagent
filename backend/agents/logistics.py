"""
LogisticsAgent – calculates riding distance from home to a target coordinate
using the free OSRM routing engine.  No API key required.
Falls back to straight-line haversine estimate on network failure.
"""
from __future__ import annotations

import math
import logging

import httpx

from config import settings

log = logging.getLogger(__name__)


class LogisticsAgent:
    """Calculates riding distance from home to a target GPS coordinate."""

    OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"
    TIMEOUT = 12

    async def get_route(self, target_lat: float, target_lon: float) -> dict:
        try:
            return await self._fetch(target_lat, target_lon)
        except Exception as exc:
            log.warning("Logistics: OSRM error (%s) – using haversine fallback", exc)
            return self._haversine_fallback(target_lat, target_lon, str(exc))

    async def _fetch(self, target_lat: float, target_lon: float) -> dict:
        url = (
            f"{self.OSRM_BASE}/"
            f"{settings.home_lon},{settings.home_lat};"
            f"{target_lon},{target_lat}"
            "?overview=false&steps=false"
        )
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM returned code={data.get('code')}")

        route = data["routes"][0]
        distance_km  = round(route["distance"] / 1000, 2)
        duration_min = round(route["duration"] / 60, 1)

        return {
            "agent":         "Logistics",
            "distance_km":   distance_km,
            "duration_min":  duration_min,
            "round_trip_km": round(distance_km * 2, 2),
            "data_source":   "live",
        }

    def _haversine_fallback(self, target_lat: float, target_lon: float, error: str) -> dict:
        """
        Straight-line distance multiplied by a road-factor of 1.35.
        Less accurate than OSRM but never crashes the analysis.
        """
        R = 6_371.0
        dlat = math.radians(target_lat - settings.home_lat)
        dlon = math.radians(target_lon - settings.home_lon)
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(settings.home_lat))
             * math.cos(math.radians(target_lat))
             * math.sin(dlon / 2) ** 2)
        straight_km = R * 2 * math.asin(math.sqrt(a))
        road_km     = round(straight_km * 1.35, 2)
        duration    = round(road_km / 50 * 60, 1)  # ~50 km/h average

        return {
            "agent":         "Logistics",
            "distance_km":   road_km,
            "duration_min":  duration,
            "round_trip_km": round(road_km * 2, 2),
            "data_source":   "haversine_fallback",
            "error":         error,
        }
