import requests
from langchain_core.tools import tool

class SolarAnalyst:
    """Worker: Eyes in the Sky. Analyzes solar irradiance in Austral."""

    @tool
    def get_solar_yield_forecast(self, system_size_kw: float = 9.0):
        """
        Fetches 24h solar radiation (MJ/m2) and calculates kWh yield.
        Math: Yield = MJ * 0.277 (kWh conversion) * system_size * 0.75 (Efficiency).
        """
        # Austral, NSW Coordinates
        url = "https://api.open-meteo.com/v1/forecast?latitude=-33.93&longitude=150.82&daily=shortwave_radiation_sum&timezone=Australia%2FSydney"
        data = requests.get(url).json()
        mj_today = data['daily']['shortwave_radiation_sum'][0]
        
        # Core Math Function
        yield_kwh = round(mj_today * 0.277 * system_size_kw * 0.75, 2)
        
        return {
            "radiation_mj": mj_today,
            "forecast_yield_kwh": yield_kwh,
            "status": "High" if yield_kwh > 25 else "Low"
        }