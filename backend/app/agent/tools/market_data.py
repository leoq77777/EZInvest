"""Live market data tool with retry, timeout, and graceful degradation."""

import json
import logging
import time
from functools import wraps

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_TIMEOUT_SECONDS = 10


class MarketDataError(Exception):
    pass


def _fetch_with_retry(ticker: str, period: str) -> dict:
    """Fetch stock data with retry and timeout tracking."""
    import yfinance as yf

    last_error = None
    for attempt in range(_MAX_RETRIES + 1):
        start = time.perf_counter()
        try:
            stock = yf.Ticker(ticker.upper())
            hist = stock.history(period=period, timeout=_TIMEOUT_SECONDS)
            elapsed = (time.perf_counter() - start) * 1000

            if hist.empty:
                raise MarketDataError(f"No data returned for '{ticker}'")

            info = stock.info
            logger.info(
                "yfinance fetch OK: ticker=%s attempt=%d latency=%.0fms",
                ticker, attempt + 1, elapsed,
            )
            return {"hist": hist, "info": info, "latency_ms": elapsed}

        except Exception as e:
            last_error = e
            elapsed = (time.perf_counter() - start) * 1000
            logger.warning(
                "yfinance fetch FAIL: ticker=%s attempt=%d/%d latency=%.0fms error=%s",
                ticker, attempt + 1, _MAX_RETRIES + 1, elapsed, e,
            )
            if attempt < _MAX_RETRIES:
                time.sleep(0.5 * (attempt + 1))

    raise MarketDataError(
        f"All {_MAX_RETRIES + 1} attempts failed for {ticker}: {last_error}"
    )


@tool
def market_data_tool(ticker: str, period: str = "1mo") -> str:
    """Fetch recent stock price data and basic market metrics.

    Use this tool when the user asks about current stock prices, recent
    price movements, or basic market statistics.

    Args:
        ticker: Stock ticker symbol (e.g., "NVDA", "AAPL", "MSFT").
        period: Historical period to fetch. One of: 1d, 5d, 1mo, 3mo, 6mo, 1y.
    """
    try:
        import yfinance  # noqa: F401
    except ImportError:
        return "yfinance is not installed. Please install it: pip install yfinance"

    try:
        data = _fetch_with_retry(ticker, period)
    except MarketDataError as e:
        return json.dumps({"error": str(e), "ticker": ticker}, ensure_ascii=False)

    hist = data["hist"]
    info = data["info"]

    latest = hist.iloc[-1]
    price_data = {
        "ticker": ticker.upper(),
        "current_price": round(float(latest["Close"]), 2),
        "open": round(float(latest["Open"]), 2),
        "high": round(float(latest["High"]), 2),
        "low": round(float(latest["Low"]), 2),
        "volume": int(latest["Volume"]),
        "date": str(hist.index[-1].date()),
        "fetch_latency_ms": round(data["latency_ms"], 1),
    }

    if len(hist) > 1:
        first_close = float(hist.iloc[0]["Close"])
        last_close = float(hist.iloc[-1]["Close"])
        change_pct = ((last_close - first_close) / first_close) * 100
        price_data["period"] = period
        price_data["period_change_pct"] = round(change_pct, 2)

    for key in [
        "marketCap", "trailingPE", "forwardPE",
        "dividendYield", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
    ]:
        if key in info and info[key] is not None:
            price_data[key] = info[key]

    return json.dumps(price_data, ensure_ascii=False)


async def check_market_data_health() -> dict:
    """Probe yfinance availability with a lightweight request.

    Used by the /health endpoint to verify the external API is reachable.
    Returns {"status": "ok"/"degraded"/"down", "latency_ms": ...}
    """
    try:
        import yfinance as yf
    except ImportError:
        return {"status": "down", "error": "yfinance not installed"}

    start = time.perf_counter()
    try:
        stock = yf.Ticker("AAPL")
        hist = stock.history(period="1d", timeout=5)
        elapsed = (time.perf_counter() - start) * 1000

        if hist.empty:
            return {"status": "degraded", "latency_ms": round(elapsed, 1), "error": "empty response"}

        status = "ok" if elapsed < 3000 else "degraded"
        return {"status": status, "latency_ms": round(elapsed, 1)}

    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {"status": "down", "latency_ms": round(elapsed, 1), "error": str(e)}
