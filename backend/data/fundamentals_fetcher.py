import threading
import time
from datetime import time as dt_time

import yfinance as yf

from utils.helpers import get_ist_now
from utils.logger import setup_logger
from utils.rate_limiter import rate_limited_call
from utils.yf_session import get_yf_session

logger = setup_logger("fundamentals_fetcher")

FUNDAMENTALS_REFRESH_START = dt_time(0, 30)
FUNDAMENTALS_REFRESH_END = dt_time(2, 30)

_cache_lock = threading.Lock()
_fundamentals_cache: dict[str, tuple[dict, str]] = {}
_last_refresh_date: str | None = None

# Yahoo sometimes answers a request with a real (non-empty) response that's nonetheless
# missing all the actual financial fields — seen in practice from Render's outbound IP
# getting a stripped-down reply where a home/dev IP gets the full one. That response
# doesn't raise, so it used to get cached as "successful" for a full 24h with every field
# null. These are the fields that should never ALL be null for a real equity — if they are,
# treat the fetch as a soft failure instead of caching it for the rest of the day.
_MEANINGFUL_FIELDS = ("market_cap", "pe_ratio", "pb_ratio", "eps", "sector", "industry")


def _is_effectively_empty(data: dict) -> bool:
    return all(data.get(k) is None for k in _MEANINGFUL_FIELDS)


def _is_refresh_window(now) -> bool:
    t = now.time()
    return FUNDAMENTALS_REFRESH_START <= t <= FUNDAMENTALS_REFRESH_END


def _fetch_remote_fundamentals(symbol: str) -> dict:
    if symbol.startswith("^"):
        return {
            "symbol": symbol,
            "market_cap": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "dividend_yield": None,
            "eps": None,
            "52_week_high": None,
            "52_week_low": None,
            "sector": "Indices",
            "industry": "Market Index",
            "revenue_growth": None,
            "profit_growth": None,
            "roe": None,
            "debt_to_equity": None
        }

    ticker = yf.Ticker(symbol, session=get_yf_session())
    info = rate_limited_call(lambda: ticker.info)

    if not info:
        raise ValueError(f"Received empty response from yfinance fundamentals for {symbol}")

    return {
        "symbol": symbol,
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "pb_ratio": info.get("priceToBook"),
        "dividend_yield": info.get("dividendYield"),
        "eps": info.get("trailingEps"),
        "52_week_high": info.get("fiftyTwoWeekHigh"),
        "52_week_low": info.get("fiftyTwoWeekLow"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "revenue_growth": info.get("revenueGrowth", 0) * 100 if info.get("revenueGrowth") else None,
        "profit_growth": info.get("earningsGrowth", 0) * 100 if info.get("earningsGrowth") else None,
        "roe": info.get("returnOnEquity", 0) * 100 if info.get("returnOnEquity") else None,
        "debt_to_equity": info.get("debtToEquity")
    }


def fetch_yf_fundamentals(symbol: str) -> dict:
    """Fetch fundamentals with 1-day caching. 
    During refresh window (00:30-02:30 IST): fetch fresh and cache.
    Outside refresh window: if cached today, return cache; if cache miss, fetch on-demand and cache."""
    now = get_ist_now()
    today_str = now.date().isoformat()

    with _cache_lock:
        cached = _fundamentals_cache.get(symbol)
        if cached and cached[1] == today_str:
            return cached[0]

    # If in refresh window, fetch fresh
    if _is_refresh_window(now):
        try:
            data = _fetch_remote_fundamentals(symbol)
            if _is_effectively_empty(data):
                logger.warning(f"Fundamentals for {symbol} came back empty (likely a degraded Yahoo response) — not caching, will retry on next call.")
                return cached[0] if cached else data
            with _cache_lock:
                _fundamentals_cache[symbol] = (data, today_str)
            return data
        except Exception as e:
            logger.error(f"Error fetching yfinance fundamentals for {symbol}: {e}")
            if cached:
                return cached[0]
            return {"symbol": symbol}

    # Outside refresh window: if cache hit, return it
    if cached:
        logger.info(f"Returning cached fundamentals for {symbol} outside refresh window.")
        return cached[0]

    # Outside refresh window + cache miss: fetch on-demand for trading
    logger.debug(f"On-demand fundamentals fetch for {symbol} during trading hours (cache miss).")
    try:
        data = _fetch_remote_fundamentals(symbol)
        if _is_effectively_empty(data):
            logger.warning(f"On-demand fundamentals for {symbol} came back empty (likely a degraded Yahoo response) — not caching, will retry next time.")
            return data
        with _cache_lock:
            _fundamentals_cache[symbol] = (data, today_str)
        return data
    except Exception as e:
        logger.error(f"Error fetching on-demand fundamentals for {symbol}: {e}")
        return {"symbol": symbol}


def refresh_daily_fundamentals(symbols: list[str], force: bool = False) -> None:
    now = get_ist_now()
    today_str = now.date().isoformat()

    with _cache_lock:
        if not force:
            if _last_refresh_date == today_str:
                logger.info("Daily fundamentals already refreshed for today.")
                return
            if not _is_refresh_window(now):
                logger.info("Skipping daily fundamentals refresh outside window.")
                return

    refreshed = 0
    empty = 0
    for symbol in symbols:
        try:
            data = _fetch_remote_fundamentals(symbol)
            if _is_effectively_empty(data):
                # Don't cache it — leaves this symbol as a cache miss, so the on-demand
                # path in fetch_yf_fundamentals retries it individually during the day
                # instead of it being stuck empty until tomorrow's refresh.
                empty += 1
                continue
            with _cache_lock:
                _fundamentals_cache[symbol] = (data, today_str)
            refreshed += 1
        except Exception as e:
            logger.error(f"Daily fundamentals refresh failed for {symbol}: {e}")

    with _cache_lock:
        _last_refresh_date = today_str
    logger.info(f"Daily fundamentals refresh complete. Updated {refreshed}/{len(symbols)} symbols ({empty} came back empty and will retry on-demand).")

