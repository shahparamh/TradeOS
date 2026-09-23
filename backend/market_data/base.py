"""Provider-neutral market-data interface. Every market-data provider (India/yfinance,
US/Alpaca, and any future provider) implements this contract so the rest of the app
(technical engine, agents, scanner) never has to know which data source it's talking to.
"""

from abc import ABC, abstractmethod
import pandas as pd


class MarketDataError(Exception):
    """Base class for all market-data errors. `code` is a stable machine-readable string
    (see the categories in the spec: DATA_PROVIDER_ERROR, MARKET_CLOSED, SYMBOL_NOT_FOUND,
    RATE_LIMITED, AUTH_ERROR, ALPACA_NOT_CONFIGURED, ...) — callers should branch on `code`,
    not on the exception message text."""

    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message or code
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {"error": self.code, "message": self.message}


class ProviderNotConfiguredError(MarketDataError):
    def __init__(self, code: str, message: str = ""):
        super().__init__(code, message)


class MarketDataProvider(ABC):
    """Abstract market-data provider. Candle DataFrames use the same OHLCV shape the
    technical engine already expects (columns: Open, High, Low, Close, Volume, indexed by
    a datetime), so IndiaMarketDataProvider can simply pass yfinance's frames through
    unchanged and AlpacaMarketDataProvider normalizes into the same shape.

    Every OHLCV row must carry a `complete` flag (see normalize helpers below) — a candle
    with missing OHLC or NaN volume must never silently collapse into 0; it stays absent
    or explicitly flagged incomplete instead.
    """

    market: str

    @abstractmethod
    def get_quote(self, symbol: str) -> dict:
        """Returns a normalized quote dict: symbol, market, price, bid, ask, timestamp, currency."""
        ...

    @abstractmethod
    def get_bulk_quotes(self, symbols: tuple) -> dict:
        """Returns {symbol: quote_dict} for many symbols in as few provider calls as possible."""
        ...

    @abstractmethod
    def get_intraday_candles(self, symbol: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame:
        """Returns an OHLCV DataFrame (Open/High/Low/Close/Volume columns, datetime index)."""
        ...

    @abstractmethod
    def get_intraday_candles_batch(self, symbols: tuple, interval: str = "5m", period: str = "5d") -> dict:
        """Returns {symbol: OHLCV DataFrame}."""
        ...

    @abstractmethod
    def get_historical_candles(self, symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
        ...

    @abstractmethod
    def get_market_status(self) -> dict:
        """Returns {market, is_open, session, timezone, next_open, next_close}."""
        ...
