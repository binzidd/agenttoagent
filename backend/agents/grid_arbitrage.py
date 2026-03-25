"""
GridArbitrageAgent – NEW fun agent ⚡
Fetches the live NSW NEM electricity spot price from the public AEMO API
and advises whether to EXPORT solar to the grid, STORE in battery,
or CONSUME directly — maximising value from the rooftop system.

Data source: AEMO public data (no API key required)
Fallback:    Time-of-day TOU estimate when AEMO is unreachable.
"""
import httpx
from datetime import datetime
from config import settings


class GridArbitrageAgent:
    """Live NEM spot price arbitrage for solar export decisions."""

    # AEMO's public 5-minute summary endpoint (NSW region = NSW1)
    AEMO_URL = "https://visualisations.aemo.com.au/aemo/apps/api/report/5MIN"

    # Typical NSW residential tariffs (cents/kWh) – used as floor values
    PEAK_IMPORT_RATE = 35.0    # c/kWh, ~6–10pm weekday peak
    SHOULDER_IMPORT_RATE = 22.0
    OFFPEAK_IMPORT_RATE = 14.0

    async def get_arbitrage_advice(self, battery_fill_pct: float = 50.0) -> dict:
        spot = await self._fetch_nem_spot()
        return self._calculate_advice(spot, battery_fill_pct)

    async def _fetch_nem_spot(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(self.AEMO_URL)
                resp.raise_for_status()
                data = resp.json()

            # Extract NSW1 region price
            for item in data.get("5MIN", []):
                if item.get("REGIONID") == "NSW1":
                    rrp = float(item["RRP"])  # $/MWh
                    c_kwh = round(rrp / 10, 2)  # convert to c/kWh
                    return {
                        "spot_rrp_mwh": rrp,
                        "spot_cents_kwh": c_kwh,
                        "period": item.get("SETTLEMENTDATE", ""),
                        "source": "live_aemo",
                    }
        except Exception as exc:
            pass  # fall through to TOU estimate

        return self._tou_estimate()

    def _tou_estimate(self) -> dict:
        """Time-of-use estimate when AEMO API is unreachable."""
        h = datetime.now().hour
        if 17 <= h <= 21:          # peak
            rate = self.PEAK_IMPORT_RATE
            period_label = "peak"
        elif 7 <= h <= 22:         # shoulder
            rate = self.SHOULDER_IMPORT_RATE
            period_label = "shoulder"
        else:                       # off-peak
            rate = self.OFFPEAK_IMPORT_RATE
            period_label = "off-peak"

        return {
            "spot_rrp_mwh": rate * 10,
            "spot_cents_kwh": rate,
            "period": period_label,
            "source": "tou_estimate",
        }

    def _calculate_advice(self, spot: dict, battery_fill_pct: float) -> dict:
        spot_c = spot["spot_cents_kwh"]
        fit = settings.feed_in_tariff_cents

        # Decision logic
        if spot_c >= self.PEAK_IMPORT_RATE and battery_fill_pct >= 80:
            action = "EXPORT"
            reason = (
                f"Spot price {spot_c:.1f} c/kWh is HIGH and battery is "
                f"{battery_fill_pct:.0f}% full → export excess now for max revenue."
            )
            value_per_kwh = spot_c
        elif battery_fill_pct < 60 and spot_c < self.SHOULDER_IMPORT_RATE:
            action = "STORE"
            reason = (
                f"Battery only {battery_fill_pct:.0f}% full and grid price low. "
                "Charge battery first – avoid expensive peak imports tonight."
            )
            value_per_kwh = self.PEAK_IMPORT_RATE  # avoided cost
        elif spot_c > fit * 1.5:
            action = "EXPORT"
            reason = (
                f"Spot ({spot_c:.1f} c/kWh) well above feed-in tariff ({fit} c/kWh). "
                "Export to grid while profitable."
            )
            value_per_kwh = spot_c
        else:
            action = "CONSUME"
            reason = (
                f"Spot ({spot_c:.1f} c/kWh) near feed-in tariff. "
                "Self-consume solar to avoid import costs."
            )
            value_per_kwh = self.SHOULDER_IMPORT_RATE

        return {
            "agent": "GridArbitrage",
            "nem_spot_cents_kwh": spot_c,
            "feed_in_tariff_cents": fit,
            "battery_fill_pct": battery_fill_pct,
            "recommended_action": action,
            "reason": reason,
            "estimated_value_cents_kwh": value_per_kwh,
            "data_source": spot["source"],
            "period": spot.get("period", ""),
        }
