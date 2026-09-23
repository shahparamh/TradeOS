from fastapi import APIRouter, HTTPException
from data.news_fetcher import fetch_all_news_for_stock, fetch_market_news
from data.fundamentals_fetcher import fetch_yf_fundamentals
from data.data_aggregator import aggregate_all_watchlist
from utils.constants import WATCHLIST
from market_data.market_config import normalize_market, get_watchlist
from market_data.factory import get_provider
from market_data.base import MarketDataError

router = APIRouter(prefix="/market", tags=["Market Data"])


def _provider_or_error(market: str):
    try:
        m = normalize_market(market)
        return m, get_provider(m)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/price/{symbol}")
def get_price(symbol: str, market: str = "IN"):
    m, provider = _provider_or_error(market)
    try:
        return provider.get_quote(symbol)
    except MarketDataError as e:
        raise HTTPException(status_code=502, detail=e.to_dict())

@router.get("/prices")
def get_prices(symbols: str, market: str = "IN"):
    """Batch price+change lookup: /market/prices?symbols=RELIANCE.NS,TCS.NS,...&market=IN
    One provider call for the whole list instead of one request per symbol."""
    m, provider = _provider_or_error(market)
    symbol_list = tuple(s.strip() for s in symbols.split(",") if s.strip())
    try:
        return provider.get_bulk_quotes(symbol_list)
    except MarketDataError as e:
        raise HTTPException(status_code=502, detail=e.to_dict())

@router.get("/indices")
def get_indices(market: str = "IN"):
    if normalize_market(market) != "IN":
        # US index quotes (SPY/QQQ) aren't wired into this endpoint's response shape yet;
        # avoid silently returning Indian indices for a US request.
        raise HTTPException(status_code=501, detail={"error": "NOT_IMPLEMENTED", "message": "US index data not yet available on this endpoint."})
    from data.market_fetcher import fetch_index_data
    return fetch_index_data()

@router.get("/candles/{symbol}")
def get_candles(symbol: str, interval: str = "5m", period: str = "5d", market: str = "IN"):
    m, provider = _provider_or_error(market)
    try:
        df = provider.get_intraday_candles(symbol, interval, period)
    except MarketDataError as e:
        raise HTTPException(status_code=502, detail=e.to_dict())
    if df.empty:
        return []

    candles = []
    df_reset = df.reset_index()
    date_col = "Datetime" if "Datetime" in df_reset.columns else "Date"

    for _, row in df_reset.iterrows():
        candles.append({
            "datetime": str(row[date_col]),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"])
        })
    return candles

@router.get("/status")
def get_market_status(market: str = "IN"):
    m, provider = _provider_or_error(market)
    try:
        return provider.get_market_status()
    except MarketDataError as e:
        raise HTTPException(status_code=502, detail=e.to_dict())

@router.get("/news/macro")
def get_macro_news():
    return fetch_market_news()

@router.get("/news/{symbol}")
def get_stock_news(symbol: str):
    return fetch_all_news_for_stock(symbol)

@router.get("/fundamentals/{symbol}")
def get_fundamentals(symbol: str, market: str = "IN"):
    if normalize_market(market) != "IN":
        # Alpaca doesn't provide fundamentals data on the free/paper tier; not implemented yet.
        raise HTTPException(status_code=501, detail={"error": "NOT_IMPLEMENTED", "message": "US fundamentals not yet available."})
    return fetch_yf_fundamentals(symbol)

@router.get("/watchlist")
async def get_watchlist_route(market: str = "IN"):
    m, _ = _provider_or_error(market)
    return {"market": m, "symbols": get_watchlist(m)}
