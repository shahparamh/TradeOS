import asyncio
from datetime import datetime
from utils.logger import setup_logger
from utils.constants import WATCHLIST
from utils.helpers import get_ist_now
from .market_fetcher import fetch_live_price, fetch_index_data, fetch_intraday_candles, fetch_bulk_prices_cached
from .news_fetcher import fetch_all_news_for_stock, fetch_market_news
from .fundamentals_fetcher import fetch_yf_fundamentals

logger = setup_logger("data_aggregator")

async def aggregate_stock_data(symbol: str, price_override: dict | None = None) -> dict:
    try:
        # We can run these synchronously inside async function for simplicity,
        # or use asyncio.to_thread to prevent blocking if they were heavy.
        # Since this is a POC/Simulation, blocking calls are okay if run in threadpool.
        if price_override:
            price_data = price_override
        else:
            price_data = await asyncio.to_thread(fetch_live_price, symbol)
        candles_df = await asyncio.to_thread(fetch_intraday_candles, symbol, "5m", "5d")
        news = await asyncio.to_thread(fetch_all_news_for_stock, symbol)
        fundamentals = await asyncio.to_thread(fetch_yf_fundamentals, symbol)
        
        # Convert candles to list of dicts for JSON
        candles_list = []
        if not candles_df.empty:
            df_reset = candles_df.reset_index()
            for _, row in df_reset.tail(100).iterrows(): # Keep last 100 candles
                candles_list.append({
                    "datetime": str(row["Datetime"]),
                    "open": round(row["Open"], 2),
                    "high": round(row["High"], 2),
                    "low": round(row["Low"], 2),
                    "close": round(row["Close"], 2),
                    "volume": int(row["Volume"])
                })

        return {
            "symbol": symbol,
            "timestamp": get_ist_now().isoformat(),
            "price_data": price_data,
            "candles": candles_list,
            "fundamentals": fundamentals,
            "news": news
        }
    except Exception as e:
        logger.error(f"Error aggregating data for {symbol}: {e}")
        return {"symbol": symbol, "error": str(e)}

async def aggregate_market_context() -> dict:
    try:
        indices = await asyncio.to_thread(fetch_index_data)
        macro_news = await asyncio.to_thread(fetch_market_news)
        
        return {
            "indices": indices,
            "macro_news": macro_news,
            "timestamp": get_ist_now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error aggregating market context: {e}")
        return {}

async def aggregate_all_watchlist() -> list:
    logger.info(f"Aggregating data for {len(WATCHLIST)} stocks...")
    results = []
    bulk_prices = await asyncio.to_thread(fetch_bulk_prices_cached, WATCHLIST)
    for symbol in WATCHLIST:
        bulk_item = bulk_prices.get(symbol)
        price_override = None
        if bulk_item:
            price_override = {
                "symbol": symbol,
                "price": bulk_item.get("price", 0),
                "volume": bulk_item.get("volume", 0),
                "change": 0,
                "percent_change": 0,
                "change_pct": 0
            }
        res = await aggregate_stock_data(symbol, price_override=price_override)
        results.append(res)
        await asyncio.sleep(2)
    return results
