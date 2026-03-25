"""
MT10Calculator – pure math agent.  Determines whether a detour to a cheaper
fuel station is economically worth the fuel burnt getting there.
All vehicle parameters come from config, not hardcoded.
"""
from config import settings


class MT10Calculator:
    """Profit calculator for fuel detours on the MT-10."""

    async def is_detour_worth_it(
        self,
        distance_km: float,
        local_price: float,
        target_price: float,
    ) -> dict:
        fill_l = settings.bike_tank_fill_litres
        cons = settings.bike_consumption_l_100km

        savings = round((local_price - target_price) * fill_l, 3)
        litres_burnt = round((distance_km * 2 / 100) * cons, 3)
        cost_of_detour = round(litres_burnt * target_price, 3)
        net_profit = round(savings - cost_of_detour, 3)

        return {
            "agent": "MT10Calculator",
            "local_price": local_price,
            "target_price": target_price,
            "savings_at_pump": savings,
            "litres_burnt_detour": litres_burnt,
            "cost_of_detour": cost_of_detour,
            "net_profit": net_profit,
            "profitable": net_profit > 0,
            "breakeven_price_diff": round(cost_of_detour / fill_l, 3),
            "logic": (
                f"Save ${savings:.2f} at pump; burn ${cost_of_detour:.2f} "
                f"in detour fuel → net ${net_profit:+.2f}"
            ),
        }
