import yfinance as yf
import pandas as pd
from utils.logger import setup_logger

logger = setup_logger("market_fetcher")

def fetch_live_price(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        
        # fast_info provides real-time data faster than .info
        current_price = info.last_price
        prev_close = info.previous_close
        
        change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0
        
        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "open": round(info.open, 2),
            "high": round(info.day_high, 2),
            "low": round(info.day_low, 2),
            "volume": int(info.last_volume),
            "prev_close": round(prev_close, 2),
            "change_pct": round(change_pct, 2)
        }
    except Exception as e:
        logger.error(f"Error fetching live price for {symbol}: {str(e)}")
        return {}

def fetch_intraday_candles(symbol: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame:
    try:
        ticker = yf.Ticker(symbol)
        # yfinance limits 5m data to 60 days
        df = ticker.history(period=period, interval=interval)
        return df
    except Exception as e:
        logger.error(f"Error fetching intraday candles for {symbol}: {str(e)}")
        return pd.DataFrame()

def fetch_historical_data(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        return df
    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
        return pd.DataFrame()

def fetch_index_data() -> dict:
    try:
        nifty = yf.Ticker("^NSEI").fast_info
        sensex = yf.Ticker("^BSESN").fast_info
        vix = yf.Ticker("^INDIAVIX").fast_info
        
        n_change = ((nifty.last_price - nifty.previous_close) / nifty.previous_close) * 100
        s_change = ((sensex.last_price - sensex.previous_close) / sensex.previous_close) * 100
        
        vix_val = vix.last_price
        vix_status = "low" if vix_val < 15 else "moderate" if vix_val <= 20 else "high"
        
        return {
            "nifty50": {
                "value": round(nifty.last_price, 2),
                "change_pct": round(n_change, 2),
                "trend": "bullish" if n_change > 0 else "bearish"
            },
            "sensex": {
                "value": round(sensex.last_price, 2),
                "change_pct": round(s_change, 2)
            },
            "india_vix": {
                "value": round(vix_val, 2),
                "status": vix_status
            }
        }
    except Exception as e:
        logger.error(f"Error fetching index data: {str(e)}")
        return {}

def fetch_bulk_prices(symbols: list) -> dict:
    try:
        # Batch download
        data = yf.download(symbols, period="1d", interval="1d", group_by="ticker", progress=False)
        results = {}
        for symbol in symbols:
            try:
                # Handle single symbol vs multi symbol DataFrame structure
                if len(symbols) == 1:
                    stock_data = data
                else:
                    stock_data = data[symbol]
                
                if not stock_data.empty:
                    latest = stock_data.iloc[-1]
                    results[symbol] = {
                        "price": round(float(latest["Close"]), 2),
                        "volume": int(latest["Volume"])
                    }
            except Exception as e:
                logger.warning(f"Failed to parse bulk data for {symbol}: {e}")
                
        return results
    except Exception as e:
        logger.error(f"Error fetching bulk prices: {str(e)}")
        return {}
