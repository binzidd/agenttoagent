import requests
from langchain_core.tools import tool

class LogisticsAgent:
    """Calculates riding distance from Austral to target fuel pumps."""

    @tool
    def get_route_distance(self, target_lat: float, target_lon: float):
        """
        Uses OSRM to find the exact riding distance (km) from Austral center.
        """
        # Start: Austral Center (-33.93, 150.82)
        url = f"http://router.project-osrm.org/route/v1/driving/150.82,-33.93;{target_lon},{target_lat}?overview=false"
        res = requests.get(url).json()
        distance_km = res['routes'][0]['distance'] / 1000
        return round(distance_km, 2)