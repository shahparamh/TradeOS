import pandas as pd
import pandas_ta as ta
import numpy as np

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 50:
        return df

    # We make a copy to avoid SettingWithCopyWarning
    df = df.copy()

    # --- Momentum Indicators ---
    df["rsi"] = ta.rsi(df["Close"], length=14)

    # --- Trend Indicators ---
    macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
    if macd is not None:
        df["macd"] = macd.iloc[:, 0]
        df["macd_signal"] = macd.iloc[:, 1]
        df["macd_histogram"] = macd.iloc[:, 2]

    df["ema_20"] = ta.ema(df["Close"], length=20)
    df["ema_50"] = ta.ema(df["Close"], length=50)

    # --- Volume Indicators ---
    # VWAP usually requires a DatetimeIndex
    try:
        df["vwap"] = ta.vwap(df["High"], df["Low"], df["Close"], df["Volume"])
    except:
        df["vwap"] = df["Close"] # Fallback

    df["volume_sma_20"] = ta.sma(df["Volume"], length=20)
    
    # Avoid division by zero
    df["volume_ratio"] = np.where(
        df["volume_sma_20"] > 0, 
        df["Volume"] / df["volume_sma_20"], 
        1.0
    )

    # --- Volatility Indicators ---
    bbands = ta.bbands(df["Close"], length=20, std=2)
    if bbands is not None:
        df["bb_lower"] = bbands.iloc[:, 0]
        df["bb_middle"] = bbands.iloc[:, 1]
        df["bb_upper"] = bbands.iloc[:, 2]

    df["atr"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)

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
