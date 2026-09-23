"""India/NSE market-data provider. Wraps the existing, unmodified yfinance implementation
in data/market_fetcher.py behind the MarketDataProvider interface — no behavior change for
the existing Indian pipeline, just a stable seam so callers stop depending on yfinance
directly. Swapping this out later (e.g. for a dedicated Indian market-data API) only means
writing a new provider class; nothing upstream of this file needs to change.
"""

from datetime import datetime
import pandas as pd

from market_data.base import MarketDataProvider
from market_data.market_config import MARKET_META
from utils.helpers import get_ist_now, is_market_open
from data.market_fetcher import (
    fetch_live_price,
    fetch_bulk_quotes,
    fetch_intraday_candles,
    fetch_intraday_candles_batch,
    fetch_historical_data,
)


class IndiaMarketDataProvider(MarketDataProvider):
    market = "IN"

    def get_quote(self, symbol: str) -> dict:
        raw = fetch_live_price(symbol)
        if not raw:
            return None
        return {
            "symbol": symbol,
            "market": "IN",
            "price": raw.get("price"),
            "bid": None,
            "ask": None,
            "volume": raw.get("volume"),
            "change": raw.get("change"),
            "percent_change": raw.get("percent_change"),
            "timestamp": get_ist_now().isoformat(),
            "currency": "INR",
        }

    def get_bulk_quotes(self, symbols: tuple) -> dict:
        raw = fetch_bulk_quotes(tuple(symbols))
        return {
            sym: {**q, "market": "IN", "currency": "INR"}
            for sym, q in raw.items()
        }

    def get_intraday_candles(self, symbol: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame:
        return fetch_intraday_candles(symbol, interval, period)

    def get_intraday_candles_batch(self, symbols: tuple, interval: str = "5m", period: str = "5d") -> dict:
        return fetch_intraday_candles_batch(tuple(symbols), interval, period)

    def get_historical_candles(self, symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
        return fetch_historical_data(symbol, period, interval)

    def get_market_status(self) -> dict:
        meta = MARKET_META["IN"]
        now = get_ist_now()
        return {
            "market": "IN",
            "is_open": is_market_open(),
            "session": "regular",
            "timezone": meta["timezone"],
            "current_time": now.isoformat(),
            "session_open": meta["session_open"],
            "session_close": meta["session_close"],
        }
