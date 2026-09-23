"""Per-market configuration: watchlists, timezone, currency, exchange, trading hours.

Single source of truth for "what market am I in" — everything else (providers, scheduler,
diagnostics, API routes) should read from here rather than hardcoding NSE or US values.
"""

SUPPORTED_MARKETS = ("IN", "US")

US_WATCHLIST = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "AMD",
    "JPM",
    "AVGO",
]

# India's equity watchlist duplicated here (not imported from utils/constants.py) to avoid
# a circular import — utils/constants.py imports WATCHLISTS from this module for backward
# compatibility, so this module cannot import back from it. Keep in sync with
# utils/constants.py's WATCHLIST if that list changes.
_IN_EQUITY_WATCHLIST = [
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "SBIN.NS",
    "INFY.NS",
    "TCS.NS",
    "HCLTECH.NS",
    "WIPRO.NS",
    "CIPLA.NS",
    "VEDL.NS",
    "DIVISLAB.NS",
    "VBL.NS",
]

WATCHLISTS = {
    "IN": _IN_EQUITY_WATCHLIST,
    "US": US_WATCHLIST,
}

# Indices/benchmarks are excluded from the arena watchlists above but kept available per market.
INDEX_SYMBOLS = {
    "IN": ["^NSEI", "^BSESN", "^INDIAVIX"],
    "US": ["SPY", "QQQ"],
}

MARKET_META = {
    "IN": {
        "market": "IN",
        "currency": "INR",
        "currency_symbol": "₹",
        "timezone": "Asia/Kolkata",
        "exchange": "NSE",
        "label": "India (NSE)",
        "session_open": "09:15",
        "session_close": "15:30",
    },
    "US": {
        "market": "US",
        "currency": "USD",
        "currency_symbol": "$",
        "timezone": "America/New_York",
        "exchange": "NASDAQ/NYSE",
        "label": "United States",
        "session_open": "09:30",
        "session_close": "16:00",
    },
}


def normalize_market(market: str | None) -> str:
    """Validates/normalizes a market string. Raises ValueError for unsupported values."""
    m = (market or "IN").strip().upper()
    if m not in SUPPORTED_MARKETS:
        raise ValueError(f"Unsupported market '{market}'. Supported: {SUPPORTED_MARKETS}")
    return m


def get_watchlist(market: str) -> list:
    return list(WATCHLISTS[normalize_market(market)])


def symbol_metadata(symbol: str, market: str) -> dict:
    m = normalize_market(market)
    meta = MARKET_META[m]
    return {
        "symbol": symbol,
        "market": m,
        "exchange": meta["exchange"],
        "currency": meta["currency"],
    }
