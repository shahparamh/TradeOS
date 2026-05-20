import yfinance as yf
import time
from utils.logger import setup_logger
from utils.rate_limiter import rate_limited_call

logger = setup_logger("fundamentals_fetcher")

# In-memory cache for fundamentals: {symbol: (data, timestamp)}
_fundamentals_cache = {}
FUNDAMENTALS_CACHE_TTL = 6 * 3600  # 6 hours

def fetch_yf_fundamentals(symbol: str) -> dict:
    current_time = time.time()
    
    # Check if we have a valid cache entry within TTL
    if symbol in _fundamentals_cache:
        cached_data, cached_time = _fundamentals_cache[symbol]
        if current_time - cached_time < FUNDAMENTALS_CACHE_TTL:
            logger.info(f"Using cached fundamentals for {symbol}")
            return cached_data

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
        
        # Save to cache
        _fundamentals_cache[symbol] = (res, current_time)
        return res
        
    except Exception as e:
        logger.error(f"Error fetching yfinance fundamentals for {symbol}: {e}")
        # Return stale cached data on rate limit or fetch failure if it exists
        if symbol in _fundamentals_cache:
            logger.info(f"Using stale cached fundamentals for {symbol} due to API error.")
            return _fundamentals_cache[symbol][0]
        return {"symbol": symbol}

