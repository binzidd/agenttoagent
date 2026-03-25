from langchain_core.tools import tool

class BatteryManager:
    """Worker: The Grid Strategist. Logic for SolarEdge Nexis battery."""

    @tool
    def define_storage_strategy(self, forecast_yield: float, battery_cap: float = 9.0):
        """
        Determines charge/discharge cycles based on yield vs capacity.
        Math: Space Required = capacity - (yield * 0.8 self-consumption).
        """
        self_consumption_est = forecast_yield * 0.7
        excess_solar = forecast_yield - self_consumption_est
        
        if excess_solar > battery_cap:
            return "GRID_EXPORT_ENABLED: Battery will hit 100% by 11:00 AM. Prepare to export."
        return "SOLAR_SOAK_MODE: Low yield. Preserve 100% of solar for overnight battery usage."