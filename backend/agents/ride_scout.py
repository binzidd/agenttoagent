"""
RideScout – NEW fun agent 🏍️
Analyses today's 24-hour weather forecast (Open-Meteo) and produces a
"Ride Score" (0–100) and best ride window for the MT-10.

Scoring factors (all sourced from the API, nothing hardcoded):
  • Temperature  – ideal 16–28 °C → 30 pts
  • Wind speed   – under 30 km/h ideal → 25 pts
  • Rain prob    – lower is better → 25 pts
  • Cloud cover  – clear sky bonus → 20 pts
"""
import httpx
from config import settings


class RideScoutAgent:
    """Finds the best ride window today based on live weather data."""

    OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

    async def get_ride_window(self) -> dict:
        params = {
            "latitude": settings.home_lat,
            "longitude": settings.home_lon,
            "hourly": (
                "temperature_2m,apparent_temperature,windspeed_10m,"
                "precipitation_probability,cloudcover,weathercode"
            ),
            "daily": "sunrise,sunset",
            "timezone": "Australia/Sydney",
            "forecast_days": 1,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            raw = resp.json()

        return self._analyse(raw)

    def _score_hour(
        self,
        temp: float,
        wind: float,
        rain_prob: float,
        cloud: float,
    ) -> float:
        """Return a 0–100 riding score for a single hour."""
        # Temperature: 16–28 °C → full 30 pts, tapers off outside
        if 16 <= temp <= 28:
            t_score = 30
        elif 10 <= temp < 16 or 28 < temp <= 34:
            t_score = 18
        else:
            t_score = 5

        # Wind: 0–20 great, 20–35 ok, >50 dangerous
        if wind <= 20:
            w_score = 25
        elif wind <= 35:
            w_score = 15
        elif wind <= 50:
            w_score = 5
        else:
            w_score = 0

        # Rain probability: inverse linear
        r_score = max(0, 25 * (1 - rain_prob / 100))

        # Cloud cover: clear sky bonus
        c_score = max(0, 20 * (1 - cloud / 100))

        return round(t_score + w_score + r_score + c_score, 1)

    def _analyse(self, raw: dict) -> dict:
        hourly = raw["hourly"]
        sunrise = raw["daily"]["sunrise"][0]  # e.g. "2026-03-25T06:12"
        sunset = raw["daily"]["sunset"][0]

        sunrise_h = int(sunrise.split("T")[1].split(":")[0])
        sunset_h = int(sunset.split("T")[1].split(":")[0])

        scores = []
        for i in range(24):
            h = int(hourly["time"][i].split("T")[1].split(":")[0])
            # Only score daylight + reasonable hours (6am–9pm)
            if h < 6 or h > 21:
                scores.append({"hour": h, "score": 0, "reason": "night"})
                continue

            score = self._score_hour(
                temp=hourly["temperature_2m"][i],
                wind=hourly["windspeed_10m"][i],
                rain_prob=hourly["precipitation_probability"][i],
                cloud=hourly["cloudcover"][i],
            )
            scores.append(
                {
                    "hour": h,
                    "score": score,
                    "temp_c": hourly["temperature_2m"][i],
                    "feels_like_c": hourly["apparent_temperature"][i],
                    "wind_kmh": hourly["windspeed_10m"][i],
                    "rain_prob_pct": hourly["precipitation_probability"][i],
                    "cloud_pct": hourly["cloudcover"][i],
                }
            )

        valid = [s for s in scores if s["score"] > 0]
        best = max(valid, key=lambda x: x["score"]) if valid else None
        avg_score = round(sum(s["score"] for s in valid) / len(valid), 1) if valid else 0

        # Find consecutive best window (2 h block with highest combined score)
        best_window_start = None
        best_window_score = 0
        for i in range(len(valid) - 1):
            combined = valid[i]["score"] + valid[i + 1]["score"]
            if combined > best_window_score:
                best_window_score = combined
                best_window_start = valid[i]["hour"]

        recommendation = "NO RIDE – unfavourable conditions"
        if avg_score >= 70:
            recommendation = f"GREAT DAY TO RIDE – peak window {best_window_start}:00–{best_window_start + 2 if best_window_start else '?'}:00"
        elif avg_score >= 50:
            recommendation = f"DECENT RIDE WINDOW – best around {best['hour']}:00" if best else "OK conditions"
        elif avg_score >= 30:
            recommendation = "MARGINAL – suit up fully, conditions ok but not ideal"

        return {
            "agent": "RideScout",
            "overall_day_score": avg_score,
            "best_hour": best["hour"] if best else None,
            "best_hour_score": best["score"] if best else 0,
            "best_window_start": best_window_start,
            "sunrise": sunrise,
            "sunset": sunset,
            "hourly_scores": scores,
            "recommendation": recommendation,
        }
