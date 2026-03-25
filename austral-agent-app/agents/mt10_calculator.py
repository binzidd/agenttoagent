from langchain_core.tools import tool

class MT10Calculator:
    """Calculates if a detour is worth the 7.5L/100km fuel cost of an MT-10."""
    
    CONS_L_100KM = 7.5  # Your MT-10 is a 'thirsty pig'
    TANK_FILL_L = 15.0  # Average fill volume

    @tool
    def is_it_profitable(self, dist_km: float, local_p: float, target_p: float):
        """
        Compares savings at the pump vs cost of fuel burnt during the detour.
        """
        savings = (local_p - target_p) * self.TANK_FILL_L
        burnt_l = (dist_km * 2 / 100) * self.CONS_L_100KM
        cost_to_get_there = burnt_l * target_p
        
        net = round(savings - cost_to_get_there, 2)
        return {
            "net_profit": net,
            "profitable": net > 0,
            "logic": f"Saved ${round(savings, 2)} at pump, but burnt ${round(cost_to_get_there, 2)} getting there."
        }