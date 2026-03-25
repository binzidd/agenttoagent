"""
RideScoutAgent – scores every hour of the day (0-100) for motorcycle riding
suitability.  Falls back to a conservative "data unavailable" result on error.
"""
from __future__ import annotations

import logging

import httpx

from config import settings

log = logging.getLogger(__name__)


class RideScoutAgent:
    """Finds the best ride window today based on live weather data."""

    OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
    TIMEOUT = 12

    async def get_ride_window(self) -> dict:
        try:
            return await self._fetch()
        except Exception as exc:
            log.warning("RideScout: API error (%s) – returning fallback", exc)
            return self._fallback(str(exc))

    async def _fetch(self) -> dict:
        params = {
            "latitude":  settings.home_lat,
            "longitude": settings.home_lon,
            "hourly": (
                "temperature_2m,apparent_temperature,windspeed_10m,"
                "precipitation_probability,cloudcover,weathercode"
            ),
            "daily":        "sunrise,sunset",
            "timezone":     "Australia/Sydney",
            "forecast_days": 1,
        }
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.get(self.OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            raw = resp.json()

        return self._analyse(raw)

    # ── Scoring logic ─────────────────────────────────────────────────────────

    @staticmethod
    def _score_hour(temp: float, wind: float, rain_prob: float, cloud: float) -> float:
        if 16 <= temp <= 28:
            t_score = 30
        elif 10 <= temp < 16 or 28 < temp <= 34:
            t_score = 18
        else:
            t_score = 5

        if wind <= 20:   w_score = 25
        elif wind <= 35: w_score = 15
        elif wind <= 50: w_score = 5
        else:            w_score = 0

        r_score = max(0, 25 * (1 - rain_prob / 100))
        c_score = max(0, 20 * (1 - cloud / 100))
        return round(t_score + w_score + r_score + c_score, 1)

    def _analyse(self, raw: dict) -> dict:
        hourly  = raw["hourly"]
        sunrise = raw["daily"]["sunrise"][0]
        sunset  = raw["daily"]["sunset"][0]

        sunrise_h = int(sunrise.split("T")[1].split(":")[0])
        sunset_h  = int(sunset.split("T")[1].split(":")[0])

        scores = []
        for i in range(24):
            h = int(hourly["time"][i].split("T")[1].split(":")[0])
            if h < 6 or h > 21:
                scores.append({"hour": h, "score": 0})
                continue

            score = self._score_hour(
                temp=hourly["temperature_2m"][i],
                wind=hourly["windspeed_10m"][i],
                rain_prob=hourly["precipitation_probability"][i],
                cloud=hourly["cloudcover"][i],
            )
            scores.append({
                "hour":          h,
                "score":         score,
                "temp_c":        hourly["temperature_2m"][i],
                "feels_like_c":  hourly["apparent_temperature"][i],
                "wind_kmh":      hourly["windspeed_10m"][i],
                "rain_prob_pct": hourly["precipitation_probability"][i],
                "cloud_pct":     hourly["cloudcover"][i],
            })

        valid = [s for s in scores if s["score"] > 0]
        best  = max(valid, key=lambda x: x["score"]) if valid else None
        avg   = round(sum(s["score"] for s in valid) / len(valid), 1) if valid else 0.0

        best_window_start = None
        best_window_score = 0
        for i in range(len(valid) - 1):
            combined = valid[i]["score"] + valid[i + 1]["score"]
            if combined > best_window_score:
                best_window_score = combined
                best_window_start = valid[i]["hour"]

        if avg >= 70:
            rec = f"GREAT DAY TO RIDE – peak window {best_window_start}:00–{(best_window_start or 0) + 2}:00"
        elif avg >= 50:
            rec = f"DECENT RIDE WINDOW – best around {best['hour']}:00" if best else "OK conditions"
        elif avg >= 30:
            rec = "MARGINAL – suit up fully, conditions ok but not ideal"
        else:
            rec = "NO RIDE – unfavourable conditions"

        return {
            "agent":             "RideScout",
            "overall_day_score": avg,
            "best_hour":         best["hour"] if best else None,
            "best_hour_score":   best["score"] if best else 0,
            "best_window_start": best_window_start,
            "sunrise":           sunrise,
            "sunset":            sunset,
            "hourly_scores":     scores,
            "recommendation":    rec,
            "data_source":       "live",
        }

    def _fallback(self, error: str) -> dict:
        return {
            "agent":             "RideScout",
            "overall_day_score": 0.0,
            "best_hour":         None,
            "best_hour_score":   0,
            "best_window_start": None,
            "sunrise":           "unknown",
            "sunset":            "unknown",
            "hourly_scores":     [{"hour": h, "score": 0} for h in range(24)],
            "recommendation":    "DATA UNAVAILABLE – weather API unreachable",
            "data_source":       "fallback",
            "error":             error,
        }
