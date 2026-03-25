import requests
from langchain_core.tools import tool

class MacroGeopoliticsAgent:
    """
    Analyzes global energy markets. March 2026 Context: Middle East 
    supply disruptions vs. IEA emergency reserve releases.
    """

    @tool
    def get_market_sentiment(self):
        """
        Synthesizes current world events into a 'Buy' or 'Wait' sentiment.
        Current Context: Brent Crude at $92/bbl; IEA releasing 400m barrels.
        """
        # In production, this queries a news/finance API
        return {
            "global_price_trend": "VOLATILE_BEARISH",
            "context": "IEA reserve release (400mb) likely to cool prices by weekend.",
            "recommendation": "Fill minimum needed if price > $2.10; wait for reserve drop."
        }