"""
BatteryManager – advises charge / discharge strategy based on forecast solar
yield and battery capacity from config.
"""
from config import settings


class BatteryManager:
    """Grid strategy for the SolarEdge Nexis home battery."""

    async def get_strategy(self, forecast_yield_kwh: float) -> dict:
        cap = settings.battery_capacity_kwh
        self_consumption_ratio = 0.70  # ~70 % consumed directly
        self_consumption_kwh = round(forecast_yield_kwh * self_consumption_ratio, 2)
        excess_kwh = round(forecast_yield_kwh - self_consumption_kwh, 2)

        if excess_kwh >= cap:
            mode = "GRID_EXPORT"
            detail = (
                f"Battery ({cap} kWh) will hit 100% before noon. "
                "Recommend enabling grid export."
            )
        elif excess_kwh > cap * 0.5:
            mode = "SOLAR_SOAK"
            detail = (
                f"Moderate yield. Charging battery with {excess_kwh:.1f} kWh excess. "
                "No export needed yet."
            )
        else:
            mode = "PRESERVE"
            detail = (
                "Low yield. Use all solar for self-consumption and preserve "
                "grid import for overnight."
            )

        fill_pct = min(100, round((excess_kwh / cap) * 100, 1))

        return {
            "agent": "BatteryManager",
            "forecast_yield_kwh": forecast_yield_kwh,
            "self_consumption_kwh": self_consumption_kwh,
            "excess_solar_kwh": excess_kwh,
            "estimated_battery_fill_pct": fill_pct,
            "mode": mode,
            "detail": detail,
        }
