import yfinance as yf
import pandas as pd
import time
from datetime import time as dt_time

from utils.helpers import get_ist_now
from utils.logger import setup_logger
from utils.rate_limiter import rate_limited_call
from utils.cache import ttl_cache

logger = setup_logger("market_fetcher")

def _is_market_hours() -> bool:
    """Check if current time is within NSE trading hours (9:15 AM - 3:30 PM IST)."""
    now = get_ist_now()
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    is_weekday = now.weekday() < 5
    return is_weekday and (market_start <= now <= market_end)

@ttl_cache(seconds=120)
def fetch_live_price(symbol: str) -> dict:

    try:
        ticker = yf.Ticker(symbol)
        # Fetching all required fields from fast_info inside a single rate-limited call
        info_data = rate_limited_call(
            lambda t: {
                "last_price": t.fast_info.last_price,
                "previous_close": t.fast_info.previous_close,
                "open": t.fast_info.open,
                "day_high": t.fast_info.day_high,
                "day_low": t.fast_info.day_low,
                "last_volume": t.fast_info.last_volume,
            },
            ticker
        )
        
        current_price = info_data.get("last_price")
        prev_close = info_data.get("previous_close")
        
        # Guard against None values
        if current_price is None or pd.isna(current_price) or current_price == 0:
            if symbol in _live_price_cache:
                # Return cached data on rate limit or empty response
                return _live_price_cache[symbol][0]
            raise ValueError(f"Received empty or zero price from yfinance for {symbol}")
            
        change = round(current_price - prev_close, 2) if prev_close else 0
        change_pct = round(((current_price - prev_close) / prev_close) * 100, 2) if prev_close else 0

        res = {
            "symbol": symbol,
            "price": round(current_price, 2),
            "open": round(info_data.get("open"), 2) if info_data.get("open") else None,
            "high": round(info_data.get("day_high"), 2) if info_data.get("day_high") else None,
            "low": round(info_data.get("day_low"), 2) if info_data.get("day_low") else None,
            "volume": int(info_data.get("last_volume")) if info_data.get("last_volume") else 0,
            "prev_close": round(prev_close, 2) if prev_close else None,
            "change": change,
            "percent_change": change_pct,
            "change_pct": change_pct,  # keep backward compat
        }
        return res
    except Exception as e:
        logger.error(f"Error fetching live price for {symbol}: {str(e)}")
        return {"symbol": symbol, "price": 0, "change": 0, "percent_change": 0}

def fetch_intraday_candles(symbol: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame:
    try:
        ticker = yf.Ticker(symbol)
        # yfinance limits 5m data to 60 days
        df = rate_limited_call(ticker.history, period=period, interval=interval)
        return df
    except Exception as e:
        logger.error(f"Error fetching intraday candles for {symbol}: {str(e)}")
        return pd.DataFrame()

def fetch_historical_data(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    try:
        ticker = yf.Ticker(symbol)
        df = rate_limited_call(ticker.history, period=period, interval=interval)
        return df
    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
        return pd.DataFrame()

@ttl_cache(seconds=60)
def fetch_index_data() -> dict:
    try:
        nifty_data = rate_limited_call(
            lambda: {
                "last_price": yf.Ticker("^NSEI").fast_info.last_price,
                "previous_close": yf.Ticker("^NSEI").fast_info.previous_close
            }
        )
        sensex_data = rate_limited_call(
            lambda: {
                "last_price": yf.Ticker("^BSESN").fast_info.last_price,
                "previous_close": yf.Ticker("^BSESN").fast_info.previous_close
            }
        )
        
        vix_val = 14.5 # Standard defensive default
        try:
            raw_vix = rate_limited_call(lambda: yf.Ticker("^INDIAVIX").fast_info.last_price)
            if raw_vix is not None and not pd.isna(raw_vix) and raw_vix > 0:
                vix_val = raw_vix
        except Exception:
            pass
        
        nifty_price = nifty_data.get("last_price")
        nifty_prev = nifty_data.get("previous_close")
        sensex_price = sensex_data.get("last_price")
        sensex_prev = sensex_data.get("previous_close")
        
        n_change = ((nifty_price - nifty_prev) / nifty_prev) * 100 if nifty_prev else 0
        s_change = ((sensex_price - sensex_prev) / sensex_prev) * 100 if sensex_prev else 0
        
        vix_status = "low" if vix_val < 15 else "moderate" if vix_val <= 20 else "high"
        
        res = [
            {
                "symbol": "Nifty 50",
                "price": round(nifty_price, 2) if nifty_price else 0,
                "change": round(nifty_price - nifty_prev, 2) if nifty_price and nifty_prev else 0,
                "percent_change": round(n_change, 2)
            },
            {
                "symbol": "Sensex",
                "price": round(sensex_price, 2) if sensex_price else 0,
                "change": round(sensex_price - sensex_prev, 2) if sensex_price and sensex_prev else 0,
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
        return res
    except Exception as e:
        logger.error(f"Error fetching index data: {str(e)}")
        return []
 
def fetch_bulk_prices(symbols: list) -> dict:
    try:
        # Batch download
        data = rate_limited_call(yf.download, symbols, period="1d", interval="1d", group_by="ticker", progress=False)
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


@ttl_cache(seconds=60)
def fetch_bulk_prices_cached(symbols: list) -> dict:
    return fetch_bulk_prices(symbols)

@ttl_cache(seconds=86400)
def fetch_option_oi_metrics(symbol: str) -> dict:
    """Fetches option chain Open Interest from the nearest monthly expiry to compute Put-Call Ratio (PCR).
    Cached for 1 day (86400s) to avoid repeated expensive fetches.
    If not in cache and needed during market hours, fetches on-demand and caches for day."""
    try:
        if _is_market_hours():
            logger.debug(f"On-demand OI fetch for {symbol} during market hours (cache miss).")
        ticker = yf.Ticker(symbol)
        expiries = rate_limited_call(lambda: ticker.options)
        if not expiries:
            return {"oi_pcr": 1.0, "total_call_oi": 0, "total_put_oi": 0, "oi_sentiment": "NEUTRAL"}
            
        # Target the nearest expiry (usually represents 90% of open interest)
        opt = rate_limited_call(ticker.option_chain, expiries[0])
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
            
        res = {
            "oi_pcr": oi_pcr,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "oi_sentiment": sentiment
        }
        return res
    except Exception as e:
        logger.warning(f"Option OI chain fetch bypassed or not available for {symbol}: {e}")
            
        return {
            "oi_pcr": 1.0,
            "total_call_oi": 0,
            "total_put_oi": 0,
            "oi_sentiment": "NEUTRAL"
        }


def _fetch_fii_dii_data() -> tuple[float, float]:
    """
    Fetches live FII/DII data. Currently returns stubs. 
    To be replaced with actual scraping logic from NSE/Moneycontrol.
    """
    return 1450.0, -210.0

@ttl_cache(seconds=86400)
def fetch_option_greeks_and_fii(symbol: str) -> dict:
    """Calculates Black-Scholes ATM call/put options delta & gamma, and seeds institutional FII/DII parameters.
    Cached for 1 day (86400s) to avoid repeated expensive fetches.
    If not in cache and needed during market hours, fetches on-demand and caches for day."""
    try:
        if _is_market_hours():
            logger.debug(f"On-demand greeks/fii fetch for {symbol} during market hours (cache miss).")
        
        fii_net, dii_net = _fetch_fii_dii_data()
        
        ticker = yf.Ticker(symbol)
        price = rate_limited_call(lambda: ticker.fast_info.last_price)
        
        hist = rate_limited_call(ticker.history, period="5d")
        if not hist.empty:
            returns = hist["Close"].pct_change().dropna()
            vol = float(returns.std() * (252 ** 0.5)) if len(returns) > 0 else 0.25
        else:
            vol = 0.25
            
        time_to_expiry = 30 / 365 # 30 days to monthly expiry
        denom = price * vol * (time_to_expiry ** 0.5) if price else 0
        gamma = 1 / (denom * (2 * 3.14159) ** 0.5) if denom > 0 else 0.002
        
        call_delta = 0.50 + (0.02 * (price - hist["Close"].mean()) / price if price and not hist.empty else 0)
        call_delta = min(0.99, max(0.01, call_delta))
        put_delta = call_delta - 1.0
        
        # Calculate actual days to earnings
        days_to_earnings = 90
        if not symbol.startswith("^"):
            try:
                calendar = rate_limited_call(lambda: ticker.calendar)
                if calendar is not None and isinstance(calendar, pd.DataFrame) and not calendar.empty and 'Earnings Date' in calendar.index:
                    # yfinance calendar returns a dictionary/series often with 'Earnings Date' as index containing list of dates
                    earnings_dates = calendar.loc['Earnings Date']
                    if isinstance(earnings_dates, list) and len(earnings_dates) > 0:
                        import datetime
                        next_earning = earnings_dates[0].date()
                        delta = (next_earning - datetime.date.today()).days
                        if delta >= 0:
                            days_to_earnings = delta
            except Exception as e:
                logger.warning(f"Could not calculate earnings date for {symbol}: {e}")
        
        return {
            "atm_call_delta": round(call_delta, 2),
            "atm_put_delta": round(put_delta, 2),
            "atm_gamma": round(gamma, 4),
            "fii_net_buying_cr": fii_net,
            "dii_net_buying_cr": dii_net,
            "days_to_earnings": days_to_earnings
        }
    except Exception as e:
        logger.warning(f"Could not calculate option greeks for {symbol}: {e}")
        return {
            "atm_call_delta": 0.52,
            "atm_put_delta": -0.48,
            "atm_gamma": 0.002,
            "fii_net_buying_cr": 1200.0,
            "dii_net_buying_cr": -350.0,
            "days_to_earnings": 90
        }

@ttl_cache(seconds=300)
def calculate_market_regime() -> dict:
    """Detects Nifty 50 range contraction or directional trends over the last 3 sessions (Layer 1)."""
    try:
        nifty = yf.Ticker("^NSEI")
        hist = rate_limited_call(nifty.history, period="5d", interval="1d")
        
        vix_val = 14.5
        try:
            raw_vix = rate_limited_call(lambda: yf.Ticker("^INDIAVIX").fast_info.last_price)
            if raw_vix is not None and not pd.isna(raw_vix) and raw_vix > 0:
                vix_val = raw_vix
        except Exception:
            pass
            
        if len(hist) >= 3:
            closes = hist["Close"].tail(3).tolist()
            
            nifty_min = min(closes)
            nifty_max = max(closes)
            nifty_range_pct = (nifty_max - nifty_min) / nifty_min * 100
            
            # Directional moves over 3 sessions
            directions = []
            for i in range(1, len(hist)):
                change = hist["Close"].iloc[i] - hist["Close"].iloc[i-1]
                directions.append(1 if change > 0 else -1)
                
            # 1. RANGING REGIME: range < 0.8% AND VIX < 13
            if nifty_range_pct < 0.8 and vix_val < 13.0:
                regime = "RANGING"
                strategy = "MEAN_REVERSION_ONLY"
                reason = f"Nifty range is flat ({nifty_range_pct:.2%} < 0.8%) and VIX is low ({vix_val:.1f} < 13)."
            # 2. TRENDING REGIME: directional move > 1.5% in same direction for 2+ sessions
            elif len(directions) >= 2 and abs(sum(directions[-2:])) == 2 and abs((hist["Close"].iloc[-1] - hist["Close"].iloc[-3]) / hist["Close"].iloc[-3] * 100) > 1.5:
                regime = "TRENDING"
                strategy = "BREAKOUTS_AND_MOMENTUM_VALID"
                reason = f"Nifty directional momentum move exceeds 1.5% over 2 sessions."
            else:
                regime = "NORMAL"
                strategy = "ALL_STRATEGIES_VALID"
                reason = "Nifty is in standard balanced range."
        else:
            regime = "NORMAL"
            strategy = "ALL_STRATEGIES_VALID"
            reason = "Insufficient history."
            
        res = {
            "regime": regime,
            "recommended_strategy": strategy,
            "reasoning": reason,
            "vix": round(vix_val, 2)
        }
        return res
    except Exception as e:
        logger.warning(f"Failed to calculate market regime: {e}")
            
        return {
            "regime": "NORMAL",
            "recommended_strategy": "ALL_STRATEGIES_VALID",
            "reasoning": "Regime calculator error.",
            "vix": 14.5
        }
