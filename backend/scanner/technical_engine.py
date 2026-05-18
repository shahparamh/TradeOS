import pandas as pd
import numpy as np

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 50:
        return df

    # We make a copy to avoid SettingWithCopyWarning
    df = df.copy()

    # --- Momentum Indicators ---
    # Native High-Performance RSI (Wilder's EMA method exactly matching standard charts)
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan) # Avoid division by zero
    df["rsi"] = 100 - (100 / (1 + rs))
    df["rsi"] = df["rsi"].fillna(50)

    # --- Trend Indicators (MACD) ---
    # Native High-Performance MACD (12, 26, 9)
    ema_fast = df["Close"].ewm(span=12, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_histogram"] = df["macd"] - df["macd_signal"]

    # Native High-Performance EMA
    df["ema_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["ema_50"] = df["Close"].ewm(span=50, adjust=False).mean()

    # --- Volume Indicators ---
    # Native High-Performance VWAP
    # VWAP = Sum(Volume * Typical Price) / Sum(Volume)
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    df["vwap"] = (typical_price * df["Volume"]).cumsum() / df["Volume"].cumsum().replace(0, np.nan)
    df["vwap"] = df["vwap"].fillna(df["Close"])

    df["volume_sma_20"] = df["Volume"].rolling(window=20).mean()
    
    # Avoid division by zero
    df["volume_ratio"] = np.where(
        df["volume_sma_20"] > 0, 
        df["Volume"] / df["volume_sma_20"], 
        1.0
    )

    # --- Volatility Indicators (Bollinger Bands) ---
    # Native High-Performance Bollinger Bands (20, 2)
    std = df["Close"].rolling(window=20).std()
    df["bb_middle"] = df["Close"].rolling(window=20).mean()
    df["bb_upper"] = df["bb_middle"] + (std * 2)
    df["bb_lower"] = df["bb_middle"] - (std * 2)

    # Native High-Performance ATR (14)
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['atr'] = true_range.ewm(alpha=1/14, adjust=False).mean()
    df['atr'] = df['atr'].fillna(df["Close"] * 0.01)

    # --- Support & Resistance (Pivot Points) ---
    df["pivot"] = (df["High"].shift(1) + df["Low"].shift(1) + df["Close"].shift(1)) / 3
    df["support_1"] = (2 * df["pivot"]) - df["High"].shift(1)
    df["resistance_1"] = (2 * df["pivot"]) - df["Low"].shift(1)

    return df

def generate_indicator_summary(df: pd.DataFrame, symbol: str) -> dict:
    if df.empty or "rsi" not in df.columns:
        return {"symbol": symbol, "error": "Insufficient data"}

    # Get the latest row
    latest = df.iloc[-1].fillna(0) # Fill NaNs with 0 to avoid JSON serialization issues

    macd_signal = "bullish" if latest.get("macd", 0) > latest.get("macd_signal", 0) else "bearish"

    # Determine trend
    close_price = latest["Close"]
    ema20 = latest.get("ema_20", 0)
    ema50 = latest.get("ema_50", 0)

    if close_price > ema20 and ema20 > ema50:
        trend = "strong_bullish"
    elif close_price > ema20:
        trend = "bullish"
    elif close_price < ema20 and ema20 < ema50:
        trend = "strong_bearish"
    elif close_price < ema20:
        trend = "bearish"
    else:
        trend = "sideways"

    # Volume Signal
    vol_ratio = latest.get("volume_ratio", 1.0)
    if vol_ratio > 2.0:
        volume_signal = "spike"
    elif vol_ratio > 1.0:
        volume_signal = "normal"
    else:
        volume_signal = "low"

    # Bollinger Bands Position
    bb_lower = latest.get("bb_lower", 0)
    bb_upper = latest.get("bb_upper", 0)
    bb_range = bb_upper - bb_lower
    
    if bb_range > 0:
        bb_pos = (close_price - bb_lower) / bb_range
    else:
        bb_pos = 0.5

    if bb_pos > 0.8:
        bb_position = "overbought"
    elif bb_pos < 0.2:
        bb_position = "oversold"
    elif bb_pos > 0.5:
        bb_position = "upper_half"
    else:
        bb_position = "lower_half"

    return {
        "symbol": symbol,
        "price": round(float(close_price), 2),
        "rsi": round(float(latest.get("rsi", 50)), 1),
        "macd": macd_signal,
        "macd_histogram": round(float(latest.get("macd_histogram", 0)), 2),
        "ema_20": round(float(ema20), 2),
        "ema_50": round(float(ema50), 2),
        "price_vs_ema20": "above" if close_price > ema20 else "below",
        "price_vs_ema50": "above" if close_price > ema50 else "below",
        "vwap": round(float(latest.get("vwap", close_price)), 2),
        "price_vs_vwap": "above" if close_price > latest.get("vwap", close_price) else "below",
        "volume_ratio": round(float(vol_ratio), 2),
        "volume_signal": volume_signal,
        "bb_position": bb_position,
        "atr": round(float(latest.get("atr", close_price * 0.01)), 2),
        "pivot": round(float(latest.get("pivot", close_price)), 2),
        "support_1": round(float(latest.get("support_1", close_price)), 2),
        "resistance_1": round(float(latest.get("resistance_1", close_price)), 2),
        "trend": trend,
    }
