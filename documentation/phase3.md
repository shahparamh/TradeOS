# Phase 3 — Technical Analysis & Opportunity Scanner

> **Goal:** Transform raw OHLCV data into actionable technical indicators, then build an intelligent scanner that filters the entire watchlist down to only the highest-probability trade setups. The AIs should never evaluate random stocks — they only receive pre-vetted opportunities.

---

## 3.1 Architecture Overview

```
  Raw OHLCV Data (from Phase 2)
          │
          ▼
  ┌────────────────────────┐
  │  Technical Engine      │
  │  (pandas_ta)           │
  │                        │
  │  Calculates:           │
  │  RSI, MACD, EMA,       │
  │  VWAP, ATR, BB,        │
  │  Volume SMA            │
  └──────────┬─────────────┘
             │
             ▼
  ┌────────────────────────┐
  │  Opportunity Scanner   │
  │                        │
  │  Filters:              │
  │  - Momentum Breakout   │
  │  - Bearish Breakdown   │
  │  - Earnings Momentum   │
  │  - Panic Sell-Off      │
  │  - Mean Reversion      │
  └──────────┬─────────────┘
             │
             ▼
  Filtered Opportunities JSON
  (sent to AI Decision Engine)
```

---

## 3.2 Technical Indicator Engine — `scanner/technical_engine.py`

### 3.2.1 Core Library

We use **`pandas_ta`** — a powerful, free, pandas-native library that calculates 130+ indicators.

### 3.2.2 Indicator Calculation Function

**`calculate_all_indicators(df: pd.DataFrame) → pd.DataFrame`**

```python
import pandas as pd
import pandas_ta as ta

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes a DataFrame with columns: Open, High, Low, Close, Volume
    Adds all required technical indicator columns and returns the enriched DataFrame.

    Input DataFrame (from yfinance):
    | Datetime            | Open  | High  | Low   | Close | Volume   |
    |---------------------|-------|-------|-------|-------|----------|
    | 2026-05-16 09:15:00 | 2875  | 2880  | 2870  | 2878  | 500000   |
    | 2026-05-16 09:20:00 | 2878  | 2892  | 2876  | 2890  | 750000   |
    | ...                 | ...   | ...   | ...   | ...   | ...      |
    """

    # --- Momentum Indicators ---

    # RSI (Relative Strength Index) — 14 period
    # Purpose: Identify overbought (>70) and oversold (<30) conditions
    df["rsi"] = ta.rsi(df["Close"], length=14)

    # --- Trend Indicators ---

    # MACD (Moving Average Convergence Divergence)
    # Purpose: Identify trend direction and momentum shifts
    # Returns: MACD line, Signal line, Histogram
    macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
    df["macd"] = macd.iloc[:, 0]           # MACD line
    df["macd_signal"] = macd.iloc[:, 1]    # Signal line
    df["macd_histogram"] = macd.iloc[:, 2] # Histogram

    # EMA 20 (Exponential Moving Average — Short Term)
    # Purpose: Short-term trend direction
    df["ema_20"] = ta.ema(df["Close"], length=20)

    # EMA 50 (Exponential Moving Average — Medium Term)
    # Purpose: Medium-term trend direction
    df["ema_50"] = ta.ema(df["Close"], length=50)

    # EMA 200 (Exponential Moving Average — Long Term)
    # Purpose: Long-term trend, institutional reference
    df["ema_200"] = ta.ema(df["Close"], length=200)

    # --- Volume Indicators ---

    # VWAP (Volume Weighted Average Price)
    # Purpose: Intraday institutional buying/selling reference
    # Note: VWAP resets daily — only valid for intraday analysis
    df["vwap"] = ta.vwap(df["High"], df["Low"], df["Close"], df["Volume"])

    # Volume SMA (20-period Simple Moving Average of Volume)
    # Purpose: Detect volume spikes (current vol vs average vol)
    df["volume_sma_20"] = ta.sma(df["Volume"], length=20)

    # Volume Ratio (current volume / average volume)
    # Values > 2.0 indicate significant volume spike
    df["volume_ratio"] = df["Volume"] / df["volume_sma_20"]

    # --- Volatility Indicators ---

    # Bollinger Bands (20-period, 2 std dev)
    # Purpose: Identify overbought/oversold via volatility envelope
    bbands = ta.bbands(df["Close"], length=20, std=2)
    df["bb_upper"] = bbands.iloc[:, 0]   # Upper band
    df["bb_middle"] = bbands.iloc[:, 1]  # Middle band (20 SMA)
    df["bb_lower"] = bbands.iloc[:, 2]   # Lower band

    # ATR (Average True Range — 14 period)
    # Purpose: Measure volatility for dynamic stop-loss sizing
    # A larger ATR = wider stop loss needed
    df["atr"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)

    # --- Support & Resistance ---

    # Pivot Points (Standard)
    # Purpose: Key intraday support/resistance levels
    df["pivot"] = (df["High"].shift(1) + df["Low"].shift(1) + df["Close"].shift(1)) / 3
    df["support_1"] = (2 * df["pivot"]) - df["High"].shift(1)
    df["resistance_1"] = (2 * df["pivot"]) - df["Low"].shift(1)

    return df
```

### 3.2.3 Indicator Summary Generator

Converts the raw indicator DataFrame into a clean summary dict for the AIs.

**`generate_indicator_summary(df: pd.DataFrame, symbol: str) → dict`**

```python
def generate_indicator_summary(df: pd.DataFrame, symbol: str) -> dict:
    """
    Takes the enriched DataFrame and extracts the LATEST values
    into a structured summary.

    Returns:
    {
        "symbol": "RELIANCE.NS",
        "price": 2890.50,
        "rsi": 61.3,
        "macd": "bullish",              # macd > signal = bullish
        "macd_histogram": 2.45,
        "ema_20": 2870.00,
        "ema_50": 2845.00,
        "ema_200": 2780.00,
        "price_vs_ema20": "above",      # Price above 20 EMA
        "price_vs_ema50": "above",      # Price above 50 EMA
        "vwap": 2882.00,
        "price_vs_vwap": "above",       # Price above VWAP
        "volume_ratio": 3.2,            # 3.2x average volume
        "volume_signal": "spike",       # > 2x = spike, 1-2x = normal, < 1x = low
        "bb_position": "upper_half",    # Where price is within Bollinger Bands
        "atr": 35.50,                   # Used for stop-loss sizing
        "pivot": 2875.00,
        "support_1": 2855.00,
        "resistance_1": 2910.00,
        "trend": "bullish"              # Based on EMA alignment
    }
    """
    latest = df.iloc[-1]

    # Determine MACD signal
    macd_signal = "bullish" if latest["macd"] > latest["macd_signal"] else "bearish"

    # Determine trend based on EMA alignment
    if latest["Close"] > latest["ema_20"] > latest["ema_50"]:
        trend = "strong_bullish"
    elif latest["Close"] > latest["ema_20"]:
        trend = "bullish"
    elif latest["Close"] < latest["ema_20"] < latest["ema_50"]:
        trend = "strong_bearish"
    elif latest["Close"] < latest["ema_20"]:
        trend = "bearish"
    else:
        trend = "sideways"

    # Determine volume signal
    vol_ratio = latest["volume_ratio"]
    if vol_ratio > 2.0:
        volume_signal = "spike"
    elif vol_ratio > 1.0:
        volume_signal = "normal"
    else:
        volume_signal = "low"

    # Bollinger Band position
    bb_range = latest["bb_upper"] - latest["bb_lower"]
    bb_pos = (latest["Close"] - latest["bb_lower"]) / bb_range if bb_range > 0 else 0.5

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
        "price": round(latest["Close"], 2),
        "rsi": round(latest["rsi"], 1),
        "macd": macd_signal,
        "macd_histogram": round(latest["macd_histogram"], 2),
        "ema_20": round(latest["ema_20"], 2),
        "ema_50": round(latest["ema_50"], 2),
        "price_vs_ema20": "above" if latest["Close"] > latest["ema_20"] else "below",
        "price_vs_ema50": "above" if latest["Close"] > latest["ema_50"] else "below",
        "vwap": round(latest["vwap"], 2),
        "price_vs_vwap": "above" if latest["Close"] > latest["vwap"] else "below",
        "volume_ratio": round(vol_ratio, 2),
        "volume_signal": volume_signal,
        "bb_position": bb_position,
        "atr": round(latest["atr"], 2),
        "pivot": round(latest["pivot"], 2),
        "support_1": round(latest["support_1"], 2),
        "resistance_1": round(latest["resistance_1"], 2),
        "trend": trend,
    }
```

---

## 3.3 Opportunity Scanner — `scanner/opportunity_scanner.py`

The scanner receives enriched indicator data for all watchlist stocks and filters them through specific trading setup conditions.

### 3.3.1 Scanner Architecture

```python
class OpportunityScanner:
    """
    The scanner runs multiple detection strategies on each stock.
    A stock can trigger multiple signals.
    Each signal has a type, strength, and the data backing it.
    """

    def scan_all(self, watchlist_data: list[dict], news_data: dict, fundamentals: dict) -> list[dict]:
        """
        Main entry point. Runs all scanners on all stocks.

        Returns:
        [
            {
                "symbol": "BEL.NS",
                "signal_type": "bullish_breakout",
                "signal_strength": "strong",
                "reasons": [
                    "Price above 20 EMA",
                    "Volume 3.2x average",
                    "RSI 61 (bullish momentum)",
                    "MACD bullish crossover"
                ],
                "indicators": { ... },  # Full indicator summary
                "news": [ ... ],        # Related news
                "fundamentals": { ... } # Fundamental data
            },
            ...
        ]
        """
        opportunities = []
        for stock in watchlist_data:
            results = []
            results += self.scan_momentum_breakout(stock)
            results += self.scan_bearish_breakdown(stock, news_data)
            results += self.scan_earnings_momentum(stock, fundamentals)
            results += self.scan_panic_selloff(stock, news_data)
            results += self.scan_mean_reversion(stock)
            opportunities.extend(results)
        return opportunities
```

### 3.3.2 Scanner Strategy 1: Momentum Breakout (LONG)

Detects stocks breaking out with strong momentum.

```python
def scan_momentum_breakout(self, stock: dict) -> list[dict]:
    """
    CONDITIONS (ALL must be true):
    ✅ Price > 20 EMA (trending up)
    ✅ Price > VWAP (institutional buying)
    ✅ Volume Ratio > 2.0 (significant volume spike)
    ✅ RSI > 55 and RSI < 80 (momentum without being overbought)
    ✅ MACD = "bullish" (trend confirmation)

    OPTIONAL BOOSTERS (increase signal strength):
    ⭐ Price > 50 EMA (medium-term trend confirmation)
    ⭐ Volume Ratio > 3.0 (extreme volume)
    ⭐ Positive news sentiment

    Signal Strength:
    - "strong" = all conditions + 2+ boosters
    - "moderate" = all conditions + 0-1 boosters
    """
    symbol = stock["symbol"]
    price = stock["price"]
    rsi = stock["rsi"]
    macd = stock["macd"]
    vol_ratio = stock["volume_ratio"]
    price_vs_ema20 = stock["price_vs_ema20"]
    price_vs_vwap = stock["price_vs_vwap"]

    # Core conditions
    if (price_vs_ema20 == "above" and
        price_vs_vwap == "above" and
        vol_ratio > 2.0 and
        55 < rsi < 80 and
        macd == "bullish"):

        reasons = [
            f"Price above 20 EMA ({stock['ema_20']})",
            f"Price above VWAP ({stock['vwap']})",
            f"Volume {vol_ratio}x average (spike)",
            f"RSI at {rsi} (bullish momentum)",
            f"MACD bullish crossover"
        ]

        # Count boosters
        boosters = 0
        if stock["price_vs_ema50"] == "above":
            boosters += 1
            reasons.append(f"Price above 50 EMA ({stock['ema_50']})")
        if vol_ratio > 3.0:
            boosters += 1
            reasons.append(f"Extreme volume spike ({vol_ratio}x)")

        strength = "strong" if boosters >= 2 else "moderate"

        return [{
            "symbol": symbol,
            "signal_type": "bullish_breakout",
            "signal_strength": strength,
            "suggested_action": "BUY",
            "suggested_position": "LONG",
            "reasons": reasons,
            "indicators": stock
        }]

    return []
```

### 3.3.3 Scanner Strategy 2: Bearish Breakdown (SHORT)

Detects stocks breaking down through support with volume.

```python
def scan_bearish_breakdown(self, stock: dict, news_data: dict) -> list[dict]:
    """
    CONDITIONS (ALL must be true):
    ✅ Price < 20 EMA (trending down)
    ✅ Price < VWAP (institutional selling)
    ✅ Volume Ratio > 1.5 (elevated volume on decline)
    ✅ RSI < 45 (bearish momentum)
    ✅ MACD = "bearish" (trend confirmation)

    OPTIONAL BOOSTERS:
    ⭐ Price < 50 EMA (medium-term bearish)
    ⭐ Negative news sentiment for this stock
    ⭐ Price below support_1 (pivot point breakdown)
    ⭐ Price near or below lower Bollinger Band

    NOTE: Short selling is INTRADAY ONLY per our risk rules.
    """
```

### 3.3.4 Scanner Strategy 3: Earnings Momentum (LONG/SHORT)

Based on fundamental data — identifies stocks with strong earnings growth.

```python
def scan_earnings_momentum(self, stock: dict, fundamentals: dict) -> list[dict]:
    """
    CONDITIONS FOR BULLISH EARNINGS MOMENTUM:
    ✅ Revenue growth > 10% YoY
    ✅ Profit growth > 15% YoY
    ✅ Recent positive news about quarterly results
    ✅ RSI > 50 (price confirming fundamentals)
    ✅ Volume Ratio > 1.5 (market reacting to results)

    CONDITIONS FOR BEARISH EARNINGS MISS:
    ✅ Revenue growth < 0% (declining revenue)
    ✅ Profit growth < -10% (significant profit decline)
    ✅ Recent negative news about earnings
    ✅ RSI < 50 (price declining)
    """
```

### 3.3.5 Scanner Strategy 4: Panic Sell-Off (LONG — Counter-Trend)

Identifies stocks that have crashed excessively and may be ripe for a bounce.

```python
def scan_panic_selloff(self, stock: dict, news_data: dict) -> list[dict]:
    """
    CONDITIONS (ALL must be true):
    ✅ Gap down > 3% from previous close
    ✅ Volume Ratio > 3.0 (panic volume)
    ✅ RSI < 30 (deeply oversold)
    ✅ Price < Lower Bollinger Band (extreme deviation)

    ADDITIONAL CHECKS:
    ⚠️ Verify no fraud/scam news (avoid catching falling knives)
    ⚠️ Check fundamentals are still intact (healthy company having bad day)
    ⚠️ Check if sector is broadly weak (sector rotation vs company-specific)

    Signal: BUY LONG with tight stop-loss (high risk, high reward)
    """
```

### 3.3.6 Scanner Strategy 5: Mean Reversion (LONG/SHORT)

Identifies stocks that have deviated significantly from their mean and may revert.

```python
def scan_mean_reversion(self, stock: dict) -> list[dict]:
    """
    BULLISH MEAN REVERSION:
    ✅ Price < Lower Bollinger Band
    ✅ RSI < 30
    ✅ Price below 20 EMA by > 2%
    ✅ Volume declining (selling exhaustion)

    BEARISH MEAN REVERSION:
    ✅ Price > Upper Bollinger Band
    ✅ RSI > 70
    ✅ Price above 20 EMA by > 2%
    ✅ Volume declining (buying exhaustion)

    Signal: Counter-trend trade with tight stop-loss
    """
```

---

## 3.4 Scanner Output Format

Every opportunity that passes the scanner's filters is formatted as:

```json
{
    "symbol": "BEL.NS",
    "signal_type": "bullish_breakout",
    "signal_strength": "strong",
    "suggested_action": "BUY",
    "suggested_position": "LONG",
    "reasons": [
        "Price above 20 EMA (245.50)",
        "Volume 3.2x average (spike)",
        "RSI at 61.3 (bullish momentum)",
        "MACD bullish crossover",
        "Price above 50 EMA (238.20)"
    ],
    "indicators": {
        "price": 248.90,
        "rsi": 61.3,
        "macd": "bullish",
        "ema_20": 245.50,
        "ema_50": 238.20,
        "vwap": 246.00,
        "volume_ratio": 3.2,
        "atr": 5.80,
        "support_1": 242.00,
        "resistance_1": 255.00
    },
    "news": [
        {"headline": "BEL bags ₹2,400 crore order from Indian Navy", "sentiment": "positive"}
    ],
    "fundamentals": {
        "pe_ratio": 35.2,
        "revenue_growth": 18.5,
        "profit_growth": 24.1,
        "roe": 22.3
    }
}
```

---

## 3.5 Scanner Execution Rules

| Rule | Description |
|------|-------------|
| **Minimum Data** | A stock must have at least 50 candles of data to calculate reliable indicators. Skip if insufficient data. |
| **No Duplicate Signals** | If a stock already has an open position for an agent, don't generate the same signal again. |
| **Signal Expiry** | Signals are valid for 1 scan cycle only. If not acted upon, they are discarded. |
| **Max Opportunities** | Maximum 5 opportunities per scan cycle to prevent information overload for AIs. |
| **Priority Ranking** | If more than 5 opportunities exist, rank by signal_strength and volume_ratio. |

---

## 3.6 API Endpoints

Expose scanner results through FastAPI:

```python
# GET /api/scanner/run                → Manually trigger a scan cycle
# GET /api/scanner/opportunities      → Get current scan results
# GET /api/scanner/history            → Past scan results with outcomes
# GET /api/scanner/indicators/{symbol} → Technical indicators for one stock
```

---

## 3.7 Phase 3 Completion Checklist

| #  | Task                                              | Status |
|----|---------------------------------------------------|--------|
| 1  | Implement `technical_engine.py` with all indicators | ☐     |
| 2  | Test indicators on RELIANCE.NS intraday data       | ☐     |
| 3  | Verify RSI, MACD, EMA values against TradingView   | ☐     |
| 4  | Implement `opportunity_scanner.py` with all 5 strategies | ☐ |
| 5  | Test Momentum Breakout scanner on real market data  | ☐     |
| 6  | Test Bearish Breakdown scanner                      | ☐     |
| 7  | Test Earnings Momentum scanner                      | ☐     |
| 8  | Test Panic Sell-Off scanner                         | ☐     |
| 9  | Test Mean Reversion scanner                         | ☐     |
| 10 | Verify scanner respects signal limits and priorities | ☐    |
| 11 | Test full pipeline: data → indicators → scanner → JSON output | ☐ |
| 12 | Create `/api/scanner/*` endpoints                   | ☐     |

---

> **Phase 3 is COMPLETE when:** The scanner can analyze all 12 watchlist stocks, calculate technical indicators, identify high-probability trade setups, and output clean JSON opportunities ready for the AI Decision Engine.

> **Next →** [Phase 4: AI Decision Engine & Agent Integration](./phase4.md)
