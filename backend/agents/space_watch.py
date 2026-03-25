"""
SpaceWatchAgent – real-time ISS tracking and stargazing conditions.

Data sources (all free, no API key required):
  - wheretheiss.at/v1/satellites/25544  →  current ISS position + velocity
  - Local astronomical maths             →  moon phase + illumination

The agent computes:
  - ISS ground distance and elevation angle from home (Austral, NSW)
  - Whether the ISS is currently in the visible arc overhead (elevation > 10°)
  - Moon phase + illumination percentage
  - A combined stargazing quality score (0–100)
  - A plain-English recommendation

Falls back to synthetic (but moon-accurate) data when the ISS API is unavailable.
"""
from __future__ import annotations

import math
import logging
from datetime import datetime, timezone

import httpx

from config import settings

log = logging.getLogger(__name__)

ISS_API = "https://api.wheretheiss.at/v1/satellites/25544"


# ── Moon phase (pure maths, no API) ──────────────────────────────────────────

def _moon_phase(date: datetime) -> dict:
    """
    Calculate moon phase using Meeus algorithm (simplified).

    Reference new moon: 6 January 2000, 18:14 UTC.
    Returns phase name, emoji, illumination %, and day-within-cycle.
    """
    known_new = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)

    diff_days = (date - known_new).total_seconds() / 86400
    cycle     = 29.53058770576          # synodic month in days
    phase_day = diff_days % cycle       # 0 → 29.53

    # Illumination: 0% at new moon, 100% at full moon
    illumination = (1 - math.cos(2 * math.pi * phase_day / cycle)) / 2 * 100

    if phase_day < 1.85:
        name, emoji = "New Moon",        "🌑"
    elif phase_day < 7.38:
        name, emoji = "Waxing Crescent", "🌒"
    elif phase_day < 9.22:
        name, emoji = "First Quarter",   "🌓"
    elif phase_day < 14.77:
        name, emoji = "Waxing Gibbous",  "🌔"
    elif phase_day < 16.61:
        name, emoji = "Full Moon",       "🌕"
    elif phase_day < 22.15:
        name, emoji = "Waning Gibbous",  "🌖"
    elif phase_day < 23.99:
        name, emoji = "Last Quarter",    "🌗"
    else:
        name, emoji = "Waning Crescent", "🌘"

    return {
        "phase_name":       name,
        "emoji":            emoji,
        "illumination_pct": round(illumination, 1),
        "phase_day":        round(phase_day, 1),
    }


# ── Geometry helper ───────────────────────────────────────────────────────────

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle ground distance in km between two WGS-84 coordinates."""
    R    = 6_371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a    = (math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ── Agent ─────────────────────────────────────────────────────────────────────

class SpaceWatchAgent:
    """
    Tracks the ISS overhead and evaluates stargazing conditions for Austral, NSW.
    No API key required.
    """

    async def get_space_watch(self) -> dict:
        moon = _moon_phase(datetime.now(timezone.utc))
        try:
            iss = await self._fetch_iss()
            return self._build_result(iss, moon)
        except Exception as exc:
            log.warning("SpaceWatch: ISS API error (%s) – using fallback", exc)
            return self._synthetic_fallback(moon)

    # ── Live path ─────────────────────────────────────────────────────────────

    async def _fetch_iss(self) -> dict:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(ISS_API)
            resp.raise_for_status()
            return resp.json()

    def _build_result(self, iss: dict, moon: dict) -> dict:
        iss_lat  = float(iss["latitude"])
        iss_lon  = float(iss["longitude"])
        alt_km   = round(float(iss["altitude"]),  1)
        vel_kmh  = round(float(iss["velocity"]),  0)

        # Ground distance from home → ISS sub-satellite point
        dist_km  = round(_haversine(settings.home_lat, settings.home_lon, iss_lat, iss_lon), 0)

        # Elevation angle: arcsin(altitude / slant_range)
        # Positive means ISS is above the geometric horizon
        slant_km      = math.sqrt(dist_km ** 2 + alt_km ** 2)
        elevation_deg = round(math.degrees(math.asin(alt_km / slant_km)), 1) if slant_km else 0.0

        # Visible if ISS is above 10° elevation AND within ~2 200 km ground track
        # (approximate; ignores day/night and observer shadow)
        visible_now = (dist_km < 2_200) and (elevation_deg > 10)

        return {
            "agent": "SpaceWatch",
            "iss": {
                "latitude":              round(iss_lat, 2),
                "longitude":             round(iss_lon, 2),
                "altitude_km":           alt_km,
                "velocity_kmh":          vel_kmh,
                "distance_from_home_km": int(dist_km),
                "elevation_deg":         elevation_deg,
                "visible_now":           visible_now,
            },
            "moon":              moon,
            "stargazing_score":  _stargazing_score(moon, visible_now),
            "recommendation":    _recommendation(moon, visible_now),
            "data_source":       "live",
            "fetched_at":        datetime.now(timezone.utc).isoformat() + "Z",
        }

    # ── Synthetic fallback ────────────────────────────────────────────────────

    def _synthetic_fallback(self, moon: dict) -> dict:
        return {
            "agent": "SpaceWatch",
            "iss": {
                "latitude":              -28.5,
                "longitude":             145.2,
                "altitude_km":           408.5,
                "velocity_kmh":          27_576.0,
                "distance_from_home_km": 650,
                "elevation_deg":         32.1,
                "visible_now":           False,
            },
            "moon":              moon,
            "stargazing_score":  _stargazing_score(moon, False),
            "recommendation":    _recommendation(moon, False),
            "data_source":       "fallback",
            "fetched_at":        datetime.now(timezone.utc).isoformat() + "Z",
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stargazing_score(moon: dict, visible_now: bool) -> int:
    """
    Score 0–100 for tonight's stargazing from the Austral backyard.
    Full moon ≈ 30 pts; new moon ≈ 100 pts; ISS overhead adds +15.
    """
    score = max(0, round(100 - moon["illumination_pct"] * 0.70))
    if visible_now:
        score = min(100, score + 15)
    return score


def _recommendation(moon: dict, visible_now: bool) -> str:
    score = _stargazing_score(moon, visible_now)
    parts = []
    if visible_now:
        parts.append("🛸 ISS is passing overhead right now — step outside!")
    if score >= 75:
        parts.append("Excellent stargazing tonight. Dark sky — go find the Milky Way.")
    elif score >= 50:
        parts.append("Good conditions. Some moonlight but stars are still vivid.")
    elif score >= 30:
        parts.append("Moderate. The moon will wash out faint objects — stick to bright stars and planets.")
    else:
        parts.append(f"Poor stargazing — {moon['phase_name']} means a bright sky tonight.")
    return " ".join(parts)
