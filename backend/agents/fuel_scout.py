"""
FuelScoutAgent – queries the NSW Government FuelCheck API for real P98 prices
near the home postcode.  Falls back to synthetic data when no API credentials
are provided so the stack still runs out of the box.
"""
import httpx
from config import settings


class FuelScoutAgent:
    """Fetches current fuel prices in the home postcode area."""

    FUELCHECK_BASE = "https://api.nsw.gov.au/api/v1/fuel/prices"

    async def get_cheapest_p98(self) -> list[dict]:
        if settings.nsw_fuelcheck_api_key:
            return await self._fetch_live()
        return await self._synthetic_fallback()

    async def _fetch_live(self) -> list[dict]:
        """Hit the real NSW FuelCheck API."""
        headers = {
            "apikey": settings.nsw_fuelcheck_api_key,
            "Authorization": f"Bearer {settings.nsw_fuelcheck_api_secret}",
        }
        params = {
            "fueltype": settings.preferred_fuel_type,
            "latitude": settings.home_lat,
            "longitude": settings.home_lon,
            "radius": 20,
            "sortby": "Price",
            "sortascending": "true",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.FUELCHECK_BASE}/nearby", headers=headers, params=params
            )
            resp.raise_for_status()
            data = resp.json()

        stations = []
        for s in data.get("stations", [])[:10]:
            stations.append(
                {
                    "name": s["Name"],
                    "brand": s.get("Brand", ""),
                    "address": s.get("Address", ""),
                    "price": s["Price"] / 10,  # API returns tenths of a cent
                    "lat": s["Latitude"],
                    "lon": s["Longitude"],
                    "fuel_type": settings.preferred_fuel_type,
                }
            )
        return stations

    async def _synthetic_fallback(self) -> list[dict]:
        """
        Returns plausible synthetic prices when no API key is configured.
        Prices drift using current hour as a seed to look 'live'.
        """
        from datetime import datetime
        import math

        # Small pseudo-random variation based on time of day
        hour_seed = datetime.now().hour
        drift = round(math.sin(hour_seed) * 0.04, 3)

        base = 2.059 + drift
        return [
            {
                "name": "7-Eleven Austral",
                "brand": "7-Eleven",
                "address": "Fifteenth Ave, Austral NSW 2179",
                "price": round(base + 0.12, 3),
                "lat": -33.931,
                "lon": 150.819,
                "fuel_type": "P98",
                "source": "synthetic",
            },
            {
                "name": "Ampol Leppington",
                "brand": "Ampol",
                "address": "Bringelly Rd, Leppington NSW 2179",
                "price": round(base + 0.02, 3),
                "lat": -33.955,
                "lon": 150.801,
                "fuel_type": "P98",
                "source": "synthetic",
            },
            {
                "name": "Costco Casula",
                "brand": "Costco",
                "address": "1 Cosgrove Ave, Casula NSW 2170",
                "price": round(base - 0.09, 3),
                "lat": -33.945,
                "lon": 150.885,
                "fuel_type": "P98",
                "source": "synthetic",
            },
            {
                "name": "BP Prestons",
                "brand": "BP",
                "address": "Bernera Rd, Prestons NSW 2170",
                "price": round(base + 0.06, 3),
                "lat": -33.952,
                "lon": 150.857,
                "fuel_type": "P98",
                "source": "synthetic",
            },
            {
                "name": "United Petroleum Leppington",
                "brand": "United",
                "address": "Gurner Ave, Leppington NSW 2179",
                "price": round(base - 0.03, 3),
                "lat": -33.961,
                "lon": 150.813,
                "fuel_type": "P98",
                "source": "synthetic",
            },
        ]
