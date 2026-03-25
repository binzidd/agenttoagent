"""
SolarAnalyst – queries Open-Meteo for real-time solar irradiance at home coords.
No API key required.
"""
import httpx
from config import settings


class SolarAnalyst:
    """Fetches 24 h solar radiation and calculates expected kWh yield."""

    OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

    async def get_solar_forecast(self) -> dict:
        params = {
            "latitude": settings.home_lat,
            "longitude": settings.home_lon,
            "daily": "shortwave_radiation_sum,precipitation_sum,weathercode",
            "hourly": "shortwave_radiation,cloudcover",
            "timezone": "Australia/Sydney",
            "forecast_days": 3,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            raw = resp.json()

        daily = raw["daily"]
        mj_today = daily["shortwave_radiation_sum"][0]
        mj_tomorrow = daily["shortwave_radiation_sum"][1]

        # kWh = MJ × 0.2778 × system_kW × panel_efficiency
        efficiency = 0.75
        factor = 0.2778 * settings.solar_system_kw * efficiency

        yield_today = round(mj_today * factor, 2)
        yield_tomorrow = round(mj_tomorrow * factor, 2)

        # Daily trend from hourly data (first 24 h)
        hourly_mj = raw["hourly"]["shortwave_radiation"][:24]
        hourly_cloud = raw["hourly"]["cloudcover"][:24]
        peak_hour = hourly_mj.index(max(hourly_mj))

        return {
            "agent": "SolarAnalyst",
            "radiation_mj_today": mj_today,
            "radiation_mj_tomorrow": mj_tomorrow,
            "forecast_yield_kwh_today": yield_today,
            "forecast_yield_kwh_tomorrow": yield_tomorrow,
            "peak_generation_hour": peak_hour,
            "avg_cloud_cover_pct": round(sum(hourly_cloud) / len(hourly_cloud), 1),
            "status": "HIGH" if yield_today > 30 else "MEDIUM" if yield_today > 15 else "LOW",
            "hourly_radiation": hourly_mj,
            "hourly_cloud": hourly_cloud,
        }
