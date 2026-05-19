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
        
        change = round(current_price - prev_close, 2) if prev_close else 0
        change_pct = round(((current_price - prev_close) / prev_close) * 100, 2) if prev_close else 0

        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "open": round(info.open, 2) if info.open else None,
            "high": round(info.day_high, 2) if info.day_high else None,
            "low": round(info.day_low, 2) if info.day_low else None,
            "volume": int(info.last_volume) if info.last_volume else 0,
            "prev_close": round(prev_close, 2) if prev_close else None,
            "change": change,
            "percent_change": change_pct,
            "change_pct": change_pct,  # keep backward compat
        }
    except Exception as e:
        logger.error(f"Error fetching live price for {symbol}: {str(e)}")
        return {"symbol": symbol, "price": 0, "change": 0, "percent_change": 0}

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
        
        vix_val = 14.5 # Standard defensive default
        try:
            vix = yf.Ticker("^INDIAVIX").fast_info
            raw_vix = vix.last_price
            if raw_vix is not None and not pd.isna(raw_vix) and raw_vix > 0:
                vix_val = raw_vix
        except Exception:
            pass
        
        n_change = ((nifty.last_price - nifty.previous_close) / nifty.previous_close) * 100
        s_change = ((sensex.last_price - sensex.previous_close) / sensex.previous_close) * 100
        
        vix_status = "low" if vix_val < 15 else "moderate" if vix_val <= 20 else "high"
        
        return [
            {
                "symbol": "Nifty 50",
                "price": round(nifty.last_price, 2),
                "change": round(nifty.last_price - nifty.previous_close, 2),
                "percent_change": round(n_change, 2)
            },
            {
                "symbol": "Sensex",
                "price": round(sensex.last_price, 2),
                "change": round(sensex.last_price - sensex.previous_close, 2),
                "percent_change": round(s_change, 2)
            },
            {
                "symbol": "India VIX",
                "price": round(vix_val, 2),
                "change": 0,
                "percent_change": 0,
                "status": vix_status
            }
        ]
    except Exception as e:
        logger.error(f"Error fetching index data: {str(e)}")
        return []
 
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

def fetch_option_oi_metrics(symbol: str) -> dict:
    """Fetches option chain Open Interest from the nearest monthly expiry to compute Put-Call Ratio (PCR)."""
    try:
        ticker = yf.Ticker(symbol)
        expiries = ticker.options
        if not expiries:
            return {"oi_pcr": 1.0, "total_call_oi": 0, "total_put_oi": 0, "oi_sentiment": "NEUTRAL"}
            
        # Target the nearest expiry (usually represents 90% of open interest)
        opt = ticker.option_chain(expiries[0])
        calls = opt.calls
        puts = opt.puts
        
        # Guard against empty options tables
        total_call_oi = int(calls["openInterest"].fillna(0).sum()) if "openInterest" in calls.columns else 0
        total_put_oi = int(puts["openInterest"].fillna(0).sum()) if "openInterest" in puts.columns else 0
        
        if total_call_oi > 0:
            oi_pcr = round(total_put_oi / total_call_oi, 2)
        else:
            oi_pcr = 1.0
            
        if oi_pcr >= 1.15:
            sentiment = "BULLISH"
        elif oi_pcr <= 0.75:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"
            
        return {
            "oi_pcr": oi_pcr,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "oi_sentiment": sentiment
        }
    except Exception as e:
        logger.warning(f"Option OI chain fetch bypassed or not available for {symbol}: {e}")
        return {
            "oi_pcr": 1.0,
            "total_call_oi": 0,
            "total_put_oi": 0,
            "oi_sentiment": "NEUTRAL"
        }
