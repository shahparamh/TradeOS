"""US market-data provider backed by the Alpaca Market Data API (paper trading account).
Talks to Alpaca over plain REST via `requests` — no extra SDK dependency needed. Every
public method raises MarketDataError subclasses on failure; callers must not treat a
missing/incomplete candle as a valid zero (see _normalize_bar).
"""

from datetime import datetime, timezone
import pandas as pd
import requests

from market_data.base import MarketDataProvider, MarketDataError, ProviderNotConfiguredError
from config import alpaca_settings
from utils.logger import setup_logger

logger = setup_logger("alpaca_provider")

# Alpaca intraday timeframes we support, mapped from our generic interval strings.
_TIMEFRAME_MAP = {
    "1m": "1Min",
    "5m": "5Min",
    "15m": "15Min",
    "30m": "30Min",
    "1h": "1Hour",
    "1d": "1Day",
}

_REQUEST_TIMEOUT = 10


def _require_configured():
    if not alpaca_settings.is_configured():
        raise ProviderNotConfiguredError(
            "ALPACA_NOT_CONFIGURED",
            "Alpaca API credentials are not set. Add ALPACA_API_KEY and ALPACA_SECRET_KEY to the backend .env.",
        )


def _get(url: str, params: dict | None = None) -> dict:
    _require_configured()
    try:
        resp = requests.get(url, headers=alpaca_settings.auth_headers(), params=params, timeout=_REQUEST_TIMEOUT)
    except requests.RequestException as e:
        raise MarketDataError("DATA_PROVIDER_ERROR", f"Alpaca request failed: {e}")

    if resp.status_code == 401 or resp.status_code == 403:
        raise MarketDataError("AUTH_ERROR", "Alpaca rejected the provided credentials.")
    if resp.status_code == 429:
        raise MarketDataError("RATE_LIMITED", "Alpaca API rate limit exceeded.")
    if resp.status_code == 404:
        raise MarketDataError("SYMBOL_NOT_FOUND", f"Alpaca returned 404 for {url}")
    if resp.status_code >= 400:
        raise MarketDataError("DATA_PROVIDER_ERROR", f"Alpaca error {resp.status_code}: {resp.text[:200]}")

    try:
        return resp.json()
    except ValueError:
        raise MarketDataError("DATA_PROVIDER_ERROR", "Alpaca returned a non-JSON response.")


def _normalize_bar(bar: dict) -> dict:
    """Normalizes one Alpaca bar into the shared candle shape. Missing OHLC or NaN/None
    volume is NEVER coerced to 0 — the candle is marked incomplete and the caller (technical
    engine) must skip it rather than compute indicators off fabricated data."""
    o, h, l, c, v = bar.get("o"), bar.get("h"), bar.get("l"), bar.get("c"), bar.get("v")
    missing = [name for name, val in (("open", o), ("high", h), ("low", l), ("close", c)) if val is None]
    volume_missing = v is None

    if missing:
        return {
            "timestamp": bar.get("t"),
            "open": o, "high": h, "low": l, "close": c, "volume": None,
            "complete": False,
            "status": "incomplete",
            "reason": f"OHLC_MISSING:{','.join(missing)}",
        }
    if volume_missing:
        return {
            "timestamp": bar.get("t"),
            "open": o, "high": h, "low": l, "close": c, "volume": None,
            "complete": False,
            "status": "incomplete",
            "reason": "VOLUME_MISSING",
        }

    return {
        "timestamp": bar.get("t"),
        "open": o, "high": h, "low": l, "close": c, "volume": int(v),
        "complete": True,
        "status": "complete",
    }


def _bars_to_dataframe(bars: list) -> pd.DataFrame:
    """Converts normalized bars into the same OHLCV DataFrame shape yfinance produces
    (Open/High/Low/Close/Volume columns, DatetimeIndex), so the technical engine doesn't
    care which provider produced it. Incomplete bars are dropped entirely rather than
    entering the frame with fabricated zeros."""
    complete_bars = [b for b in bars if b.get("complete")]
    if not complete_bars:
        return pd.DataFrame()

    df = pd.DataFrame(complete_bars)
    df["Datetime"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("Datetime")
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
    })[["Open", "High", "Low", "Close", "Volume"]]
    return df


class AlpacaMarketDataProvider(MarketDataProvider):
    market = "US"

    def get_quote(self, symbol: str) -> dict:
        _require_configured()
        data = _get(f"{alpaca_settings.DATA_BASE_URL}/stocks/{symbol}/quotes/latest")
        quote = data.get("quote") or {}
        bid, ask = quote.get("bp"), quote.get("ap")
        price = ask if ask else bid
        if price is None:
            # Fall back to latest trade if no live quote is available.
            trade_data = _get(f"{alpaca_settings.DATA_BASE_URL}/stocks/{symbol}/trades/latest")
            price = (trade_data.get("trade") or {}).get("p")
        return {
            "symbol": symbol,
            "market": "US",
            "price": price,
            "bid": bid,
            "ask": ask,
            "timestamp": quote.get("t") or datetime.now(timezone.utc).isoformat(),
            "currency": "USD",
        }

    def get_bulk_quotes(self, symbols: tuple) -> dict:
        _require_configured()
        if not symbols:
            return {}
        data = _get(f"{alpaca_settings.DATA_BASE_URL}/stocks/quotes/latest", params={"symbols": ",".join(symbols)})
        quotes = data.get("quotes") or {}
        results = {}
        for sym, quote in quotes.items():
            bid, ask = quote.get("bp"), quote.get("ap")
            price = ask if ask else bid
            results[sym] = {
                "symbol": sym,
                "market": "US",
                "price": price,
                "bid": bid,
                "ask": ask,
                "timestamp": quote.get("t"),
                "currency": "USD",
            }
        return results

    def get_intraday_candles(self, symbol: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame:
        raw = self._fetch_bars(symbol, interval, period)
        return _bars_to_dataframe(raw)

    def get_intraday_candles_batch(self, symbols: tuple, interval: str = "5m", period: str = "5d") -> dict:
        results = {}
        for symbol in symbols:
            try:
                results[symbol] = self.get_intraday_candles(symbol, interval, period)
            except MarketDataError as e:
                logger.warning(f"Alpaca candle fetch failed for {symbol}: {e.code} {e.message}")
                results[symbol] = pd.DataFrame()
        return results

    def get_historical_candles(self, symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
        raw = self._fetch_bars(symbol, interval, period)
        return _bars_to_dataframe(raw)

    def _fetch_bars(self, symbol: str, interval: str, period: str) -> list:
        _require_configured()
        timeframe = _TIMEFRAME_MAP.get(interval)
        if not timeframe:
            raise MarketDataError("DATA_PROVIDER_ERROR", f"Unsupported interval '{interval}' for Alpaca provider.")

        start = self._period_to_start(period)
        params = {
            "timeframe": timeframe,
            "start": start.isoformat(),
            "limit": 10000,
            "adjustment": "raw",
            "feed": "iex",  # free/paper accounts only have IEX feed access
        }
        data = _get(f"{alpaca_settings.DATA_BASE_URL}/stocks/{symbol}/bars", params=params)
        bars = data.get("bars") or []
        return [_normalize_bar(b) for b in bars]

    @staticmethod
    def _period_to_start(period: str) -> datetime:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        unit = period[-1]
        try:
            amount = int(period[:-1])
        except ValueError:
            amount = 5
        if unit == "d":
            delta = timedelta(days=amount)
        elif unit == "mo":
            delta = timedelta(days=amount * 30)
        elif unit == "y":
            delta = timedelta(days=amount * 365)
        else:
            delta = timedelta(days=5)
        return now - delta

    def get_market_status(self) -> dict:
        _require_configured()
        clock = _get(f"{alpaca_settings.TRADING_BASE_URL}/clock")
        return {
            "market": "US",
            "is_open": clock.get("is_open", False),
            "session": "regular",
            "timezone": "America/New_York",
            "current_time": clock.get("timestamp"),
            "next_open": clock.get("next_open"),
            "next_close": clock.get("next_close"),
        }
