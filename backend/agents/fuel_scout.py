"""
FuelScoutAgent – fetches live P98 prices from the NSW FuelCheck API.

Authentication:  OAuth 2.0 client credentials (NSW Apigee gateway)
Token endpoint:  POST https://api.nsw.gov.au/oauth/client_credential/accesstoken
Prices endpoint: GET  https://api.nsw.gov.au/api/v1/fuel/prices/new

The /new endpoint returns all stations + prices (updated since last call).
Filtering to nearby stations is done client-side using the Haversine formula
because the API does not expose a /nearby endpoint.

Falls back to time-varying synthetic data when:
  - No API key is configured, OR
  - The API returns any error (network, auth, 4xx, 5xx)
"""
from __future__ import annotations

import math
import logging
from datetime import datetime
from typing import Optional

import httpx

from config import settings

log = logging.getLogger(__name__)

# P98 fuel type codes the NSW FuelCheck API may return
P98_CODES = {"P98", "U98", "PUP98", "PULP98", "PREMIUM98"}


class FuelScoutAgent:
    """Fetches current P98 fuel prices near the home postcode."""

    TOKEN_URL  = "https://api.nsw.gov.au/oauth/client_credential/accesstoken"
    PRICES_URL = "https://api.nsw.gov.au/api/v1/fuel/prices/new"
    SEARCH_RADIUS_KM = 25

    # ── Public interface ──────────────────────────────────────────────────────

    async def get_cheapest_p98(self) -> list:
        if settings.nsw_fuelcheck_api_key:
            try:
                stations = await self._fetch_live()
                if stations:
                    return stations
                log.warning("FuelScout: live API returned 0 P98 stations – using fallback")
            except Exception as exc:
                log.warning("FuelScout: live API error (%s) – using synthetic fallback", exc)
        return self._synthetic_fallback()

    # ── Live API path ─────────────────────────────────────────────────────────

    async def _get_token(self) -> str:
        """
        Acquire an OAuth 2.0 Bearer token from the NSW Apigee gateway.
        The grant_type must be in the query string; the API key goes in a header.
        """
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self.TOKEN_URL,
                params={"grant_type": "client_credentials"},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "apikey": settings.nsw_fuelcheck_api_key,
                },
            )
            resp.raise_for_status()
            token = resp.json().get("access_token")
            if not token:
                raise ValueError(f"No access_token in response: {resp.text[:200]}")
            return token

    async def _fetch_live(self) -> list:
        token = await self._get_token()

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                self.PRICES_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": settings.nsw_fuelcheck_api_key,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return self._parse(data)

    def _parse(self, data: dict) -> list:
        """
        Parse the NSW FuelCheck /new response.

        Expected structure:
          {
            "stations": [{"code": "...", "name": "...", "brand": "...",
                          "address": "...",
                          "location": {"latitude": -33.x, "longitude": 150.x}}],
            "prices":   [{"stationcode": "...", "fueltype": "P98",
                          "price": 218.9, "lastupdated": "DD/MM/YYYY HH:MM:SS"}]
          }

        Price field is in cents per litre (e.g. 218.9 → $2.189/L).
        """
        station_map: dict = {}
        for s in data.get("stations", []):
            code = str(s.get("code") or s.get("stationid") or "")
            if code:
                station_map[code] = s

        results = []
        for p in data.get("prices", []):
            if p.get("fueltype", "").upper() not in P98_CODES:
                continue

            code = str(p.get("stationcode") or p.get("code") or "")
            station = station_map.get(code, {})

            loc = station.get("location", {})
            lat = float(loc.get("latitude") or station.get("latitude") or 0)
            lon = float(loc.get("longitude") or station.get("longitude") or 0)
            if not lat or not lon:
                continue

            dist = _haversine(settings.home_lat, settings.home_lon, lat, lon)
            if dist > self.SEARCH_RADIUS_KM:
                continue

            raw = float(p.get("price", 0))
            # NSW API returns price in cents/L (e.g. 218.9 = $2.189)
            price_per_litre = round(raw / 100, 3)

            results.append({
                "name":       station.get("name", f"Station {code}"),
                "brand":      station.get("brand", ""),
                "address":    station.get("address", ""),
                "price":      price_per_litre,
                "lat":        lat,
                "lon":        lon,
                "fuel_type":  "P98",
                "distance_km": round(dist, 1),
                "last_updated": p.get("lastupdated", ""),
                "source":     "live",
            })

        results.sort(key=lambda x: x["price"])
        return results[:10]

    # ── Synthetic fallback ────────────────────────────────────────────────────

    def _synthetic_fallback(self) -> list:
        """
        Time-varying synthetic prices for when the live API is unavailable.
        The small drift makes the data look plausible without being static.
        Clearly labelled source='synthetic' so consumers can distinguish.
        """
        drift = round(math.sin(datetime.now().hour) * 0.04, 3)
        base  = 2.059 + drift
        return [
            _synth("7-Eleven Austral",           "7-Eleven", "Fifteenth Ave, Austral NSW 2179",   base + 0.12, -33.931, 150.819, 0.8),
            _synth("Ampol Leppington",            "Ampol",    "Bringelly Rd, Leppington NSW 2179", base + 0.02, -33.955, 150.801, 3.2),
            _synth("Costco Casula",               "Costco",   "Cosgrove Ave, Casula NSW 2170",      base - 0.09, -33.945, 150.885, 6.5),
            _synth("BP Prestons",                 "BP",       "Bernera Rd, Prestons NSW 2170",      base + 0.06, -33.952, 150.857, 4.8),
            _synth("United Petroleum Leppington", "United",   "Gurner Ave, Leppington NSW 2179",    base - 0.03, -33.961, 150.813, 3.9),
        ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two WGS-84 coordinates."""
    R = 6_371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _synth(name, brand, address, price, lat, lon, dist_km) -> dict:
    return {
        "name": name, "brand": brand, "address": address,
        "price": round(price, 3), "lat": lat, "lon": lon,
        "fuel_type": "P98", "distance_km": dist_km,
        "last_updated": "", "source": "synthetic",
    }
