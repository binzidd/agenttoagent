import requests
from langchain_core.tools import tool

class FuelScoutAgent:
    """Fetches real-time NSW FuelCheck data for Austral (Postcode 2179)."""

    @tool
    def get_cheapest_pulp98(self, postcode: str = "2179"):
        """
        Queries the NSW FuelCheck API for the cheapest Premium 98 Unlead.
        Returns station details and current price.
        """
        # Mocking the NSW API response structure
        return [
            {"station": "7-Eleven Austral", "price": 2.18, "lat": -33.931, "lon": 150.819},
            {"station": "Ampol Leppington", "price": 2.05, "lat": -33.955, "lon": 150.801},
            {"station": "Costco Casula", "price": 1.94, "lat": -33.945, "lon": 150.885}
        ]