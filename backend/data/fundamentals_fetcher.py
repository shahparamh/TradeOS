import yfinance as yf
import time
from utils.logger import setup_logger
from utils.rate_limiter import rate_limited_call
from utils.cache import ttl_cache

logger = setup_logger("fundamentals_fetcher")

@ttl_cache(seconds=86400)
def fetch_yf_fundamentals(symbol: str) -> dict:

    try:
        ticker = yf.Ticker(symbol)
        # Wrap the network call ticker.info in the rate limiter
        info = rate_limited_call(lambda: ticker.info)
        
        if not info:
            raise ValueError(f"Received empty response from yfinance fundamentals for {symbol}")
            
        res = {
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
        
        return res
        
    except Exception as e:
        logger.error(f"Error fetching yfinance fundamentals for {symbol}: {e}")
        return {"symbol": symbol}

