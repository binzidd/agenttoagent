"""
MacroGeopoliticsAgent – fetches live Brent Crude oil price via yfinance
(no API key required) and derives a fuel price trend sentiment.
"""
import asyncio
from datetime import datetime
import httpx


class MacroGeopoliticsAgent:
    """Real-time global energy market context."""

    BRENT_TICKER = "BZ=F"      # Brent Crude front-month futures on Yahoo Finance
    WTI_TICKER = "CL=F"        # WTI crude for cross-reference
    AUD_USD_TICKER = "AUDUSD=X"  # AUD/USD exchange rate

    async def get_market_context(self) -> dict:
        """Fetch live crude + FX data and derive a buy/wait sentiment."""
        data = await self._fetch_quotes()
        return self._derive_sentiment(data)

    async def _fetch_quotes(self) -> dict:
        # yfinance is sync; run in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_fetch)

    def _sync_fetch(self) -> dict:
        try:
            import yfinance as yf

            tickers = yf.download(
                [self.BRENT_TICKER, self.WTI_TICKER, self.AUD_USD_TICKER],
                period="5d",
                interval="1d",
                progress=False,
                auto_adjust=True,
            )
            close = tickers["Close"]

            brent_now = float(close[self.BRENT_TICKER].dropna().iloc[-1])
            brent_prev = float(close[self.BRENT_TICKER].dropna().iloc[-2])
            wti_now = float(close[self.WTI_TICKER].dropna().iloc[-1])
            aud_usd = float(close[self.AUD_USD_TICKER].dropna().iloc[-1])

            return {
                "brent_usd": round(brent_now, 2),
                "brent_prev_usd": round(brent_prev, 2),
                "wti_usd": round(wti_now, 2),
                "aud_usd": round(aud_usd, 4),
                "source": "live",
            }
        except Exception as exc:
            # Graceful fallback – use last-known typical values
            return {
                "brent_usd": 82.5,
                "brent_prev_usd": 81.9,
                "wti_usd": 78.3,
                "aud_usd": 0.625,
                "source": "fallback",
                "error": str(exc),
            }

    def _derive_sentiment(self, data: dict) -> dict:
        brent = data["brent_usd"]
        brent_prev = data["brent_prev_usd"]
        aud_usd = data["aud_usd"]
        change_pct = round((brent - brent_prev) / brent_prev * 100, 2)

        # Higher crude + weaker AUD → higher pump prices in AU
        aud_impact = "BULLISH_AU_PRICE" if aud_usd < 0.63 else "NEUTRAL"

        if change_pct > 1.5:
            trend = "RISING"
            recommendation = "Fill tank now – crude prices trending up."
        elif change_pct < -1.5:
            trend = "FALLING"
            recommendation = "Consider waiting – crude prices falling, pump relief likely in 48h."
        else:
            trend = "STABLE"
            recommendation = "No urgency. Fill when convenient."

        return {
            "agent": "MacroGeopolitics",
            "brent_crude_usd": brent,
            "brent_change_pct": change_pct,
            "wti_usd": data["wti_usd"],
            "aud_usd": aud_usd,
            "crude_trend": trend,
            "aud_fx_impact": aud_impact,
            "recommendation": recommendation,
            "data_source": data["source"],
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        }
