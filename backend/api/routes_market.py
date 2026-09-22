from fastapi import APIRouter
from data.market_fetcher import fetch_live_price, fetch_index_data, fetch_intraday_candles, fetch_bulk_quotes
from data.news_fetcher import fetch_all_news_for_stock, fetch_market_news
from data.fundamentals_fetcher import fetch_yf_fundamentals
from data.data_aggregator import aggregate_all_watchlist
from utils.constants import WATCHLIST

router = APIRouter(prefix="/market", tags=["Market Data"])

@router.get("/price/{symbol}")
def get_price(symbol: str):
    return fetch_live_price(symbol)

@router.get("/prices")
def get_prices(symbols: str):
    """Batch price+change lookup: /market/prices?symbols=RELIANCE.NS,TCS.NS,...
    One yfinance call for the whole list instead of one request per symbol — use this
    from any UI that needs prices for more than a couple of symbols at once."""
    symbol_list = tuple(s.strip() for s in symbols.split(",") if s.strip())
    return fetch_bulk_quotes(symbol_list)

@router.get("/indices")
def get_indices():
    return fetch_index_data()

@router.get("/candles/{symbol}")
def get_candles(symbol: str, interval: str = "5m", period: str = "5d"):
    df = fetch_intraday_candles(symbol, interval, period)
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

@router.get("/news/macro")
def get_macro_news():
    return fetch_market_news()

@router.get("/news/{symbol}")
def get_stock_news(symbol: str):
    return fetch_all_news_for_stock(symbol)

@router.get("/fundamentals/{symbol}")
def get_fundamentals(symbol: str):
    return fetch_yf_fundamentals(symbol)

@router.get("/watchlist")
async def get_watchlist():
    # Note: For dashboard real-time updates, we would probably pull from DB cache
    # instead of fetching all live every time to avoid rate limits.
    # But for now, we just return the static watchlist symbols.
    return {"symbols": WATCHLIST}
