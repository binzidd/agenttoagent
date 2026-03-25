from agents.solar_analyst import SolarAnalyst
from agents.fuel_scout import FuelScoutAgent
from agents.mt10_calculator import MT10Calculator
from agents.logistics import LogisticsAgent

class AustralSupervisor:
    def __init__(self):
        self.solar = SolarAnalyst()
        self.fuel = FuelScoutAgent()
        self.math = MT10Calculator()
        self.maps = LogisticsAgent()

    async def execute_workflow(self, user_intent: str):
        """
        High-level orchestration:
        1. Identify domain (Solar vs Fuel).
        2. Sequence workers.
        3. Pass data from Worker A to Worker B.
        """
        # Step 1: Sequential Agent Handoff
        pumps = self.fuel.find_best_p98_prices.invoke({})
        best_pump = min(pumps, key=lambda x: x['price'])
        
        # Step 2: Handoff to Logistics
        dist = self.maps.get_distance(best_pump['lat'], best_pump['lon'])
        
        # Step 3: Handoff to MT10 Math
        profit_data = self.math.calculate_refuel_profit.invoke({
            "dist_km": dist, 
            "local_price": 2.58, 
            "cheap_price": best_pump['price']
        })

        return {
            "decision": "GO" if profit_data['is_worth_it'] else "STAY",
            "details": f"Drive to {best_pump['name']} for ${best_pump['price']}/L. Net profit: ${profit_data['net_profit']}",
            "agent_trace": [
                {"from": "FuelScout", "to": "Logistics", "data": f"Pump at {best_pump['name']}"},
                {"from": "Logistics", "to": "MT10Calc", "data": f"Distance: {dist}km"}
            ]
        }