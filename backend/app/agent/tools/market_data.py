"""Live market data tool with retry, timeout, and graceful degradation."""

import json
import logging
import time
from functools import wraps

from langchain_core.tools import tool
from app.config import get_settings
from app.agent.entity_resolution import mentions_sandisk

logger = logging.getLogger(__name__)

class MarketDataError(Exception):
    pass


def _fetch_with_retry(ticker: str, period: str) -> dict:
    """Fetch stock data with retry and timeout tracking."""
    import yfinance as yf

    settings = get_settings()
    max_retries = max(0, int(settings.market_data_max_retries))
    timeout_seconds = max(1.0, float(settings.market_data_timeout_sec))
    last_error = None
    for attempt in range(max_retries + 1):
        start = time.perf_counter()
        try:
            stock = yf.Ticker(ticker.upper())
            hist = stock.history(period=period, timeout=timeout_seconds)
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
                ticker, attempt + 1, max_retries + 1, elapsed, e,
            )
            # 429/rate-limit is not helped by immediate retries; return quickly so
            # the agent can finish with partial evidence instead of stalling.
            if "too many requests" in str(e).lower() or "rate limited" in str(e).lower():
                break
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))

    raise MarketDataError(
        f"All {max_retries + 1} attempts failed for {ticker}: {last_error}"
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

    normalized_ticker = "SNDK" if mentions_sandisk(ticker) else ticker

    try:
        data = _fetch_with_retry(normalized_ticker, period)
    except MarketDataError as e:
        hint = (
            "SanDisk should be checked with ticker SNDK after its 2025 separation "
            "from Western Digital (WDC). Do not substitute WDC for SanDisk."
            if mentions_sandisk(ticker)
            else "Verify the company's current ticker before trying a parent/legacy ticker."
        )
        return json.dumps({
            "error": f"Ticker '{normalized_ticker}' not found or no longer active. {hint}",
            "ticker": normalized_ticker,
            "original_ticker": ticker,
            "is_defunct_possible": True
        }, ensure_ascii=False)

    hist = data["hist"]
    info = data["info"]

    latest = hist.iloc[-1]

    # Prefer real-time price from info over historical close for accuracy
    real_time_price = (
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or float(latest["Close"])
    )
    previous_close = info.get("previousClose")

    price_data = {
        "ticker": normalized_ticker.upper(),
        "original_ticker": ticker,
        "current_price": round(float(real_time_price), 2),
        "previous_close": round(float(previous_close), 2) if previous_close else None,
        "open": round(float(info.get("regularMarketOpen", latest["Open"])), 2),
        "high": round(float(info.get("regularMarketDayHigh", latest["High"])), 2),
        "low": round(float(info.get("regularMarketDayLow", latest["Low"])), 2),
        "volume": int(info.get("regularMarketVolume", latest["Volume"])),
        "date": str(hist.index[-1].date()),
        "fetch_latency_ms": round(data["latency_ms"], 1),
    }

    # Daily change based on real-time price vs previous close
    if previous_close and real_time_price:
        daily_change_pct = ((float(real_time_price) - float(previous_close)) / float(previous_close)) * 100
        price_data["daily_change_pct"] = round(daily_change_pct, 2)

    # Period change from historical data
    if len(hist) > 1:
        first_close = float(hist.iloc[0]["Close"])
        last_close = float(real_time_price)
        change_pct = ((last_close - first_close) / first_close) * 100
        price_data["period"] = period
        price_data["period_change_pct"] = round(change_pct, 2)

    for key in [
        "marketCap", "trailingPE", "forwardPE",
        "dividendYield", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
        "shortName", "longName",
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
