import yfinance as yf
from utils.logger import setup_logger

logger = setup_logger("fundamentals_fetcher")

def fetch_yf_fundamentals(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
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
    except Exception as e:
        logger.error(f"Error fetching yfinance fundamentals for {symbol}: {e}")
        return {"symbol": symbol}
