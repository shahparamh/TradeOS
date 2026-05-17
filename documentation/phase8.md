# Phase 8 — Advanced Backtesting & Portfolio Intelligence Engine

> **Goal:** Build a historical backtesting system that lets you replay the last 1–5 years of market data through any strategy, expand asset classes globally (Bluechips, Midcaps, Nasdaq, Gold), and implement a mathematical Correlation Engine to prevent overlapping sector risk.

---

## 8.1 Why Backtesting & Portfolio Intelligence?

Testing on a single live market window is valuable, but limited. To build a robust trading engine, we must replay strategy decisions across diverse economic cycles while mathematically shielding the portfolio from hidden sector over-exposure (e.g., multiple agents buying separate IT or Banking stocks concurrently).

This phase answers:
*   Would your trading strategies have survived the March 2020 COVID crash?
*   Are you secretly over-exposed to tech or banking sector sell-offs?
*   What is the optimal stop-loss % for midcaps vs. commodities?
*   Does diversifying globally (Nasdaq & Gold Spot) stabilize your equity curve?

---

## 8.2 Architecture — Combined Backtest & Correlation Framework

```
Historical OHLCV Data (Bluechips, Midcaps, Nasdaq, Gold ETFs)
                     │
                     ▼
          Backtest & Risk Replayer
┌──────────────────────────────────────────────┐
│  1. Replay historical candles chronologically │
│  2. At each candle, compute technicals        │
│  3. Consult Sector Correlation Engine         │
│     - Calculate rolling Pearson matrix       │
│     - Reject highly correlated assets (>0.7)  │
│  4. Execute simulated buy/sell with slippage │
│  5. Track portfolio equity curve & drawdowns  │
└──────────────────────────────────────────────┘
                     │
                     ▼
              Results Database
     - trade_log, equity_curve, metrics
                     │
                     ▼
           Dashboard Visualization
     - Equity curve vs. Nifty Benchmark
     - Sector allocation & correlation heatmap
```

---

## 8.3 Watchlist Expansion (No Options/F&O Leverage)

To achieve diversification without high-risk leverage, the system integrates diverse equity and spot commodity categories:

| Category | Typical Symbols | Data Source | Rationale |
| :--- | :--- | :--- | :--- |
| **Indian Bluechips** | `RELIANCE.NS`, `TCS.NS`, `HDFCBANK.NS` | Yahoo Finance | Extremely liquid, stable macro trends |
| **Indian Midcaps** | `TATAELXSI.NS`, `DIXON.NS`, `KPIT.NS` | Yahoo Finance | High momentum, rapid beta swings |
| **US Tech Giants** | `AAPL`, `MSFT`, `NVDA`, `TSLA` | Yahoo Finance | Global macro diversification, active during IST off-hours |
| **Safe Haven Spot** | `GLD` (Gold ETF), `SLV` (Silver ETF) | Yahoo Finance | Negative correlation to indices during market panics |

---

## 8.4 Mathematical Correlation Engine

If multiple agents buy different stocks in the same sector (e.g., Gemini buys `INFY`, Groq buys `TCS`, and Ollama buys `WIPRO`), the portfolio is secretly over-exposed to IT sector crashes. 

The **Correlation Engine** calculates real-time price correlations over the last 30 daily candles and rejects highly correlated positions ($r > 0.70$):

```python
# backend/broker/correlation_manager.py
import pandas as pd
import numpy as np

def calculate_correlation_matrix(symbols: list, lookback_days: int = 30) -> pd.DataFrame:
    """
    Fetches daily close prices for the lookback period and calculates
    the Pearson correlation coefficient matrix.
    """
    price_data = {}
    for symbol in symbols:
        df = fetch_daily_data(symbol, period=f"{lookback_days}d")
        if not df.empty:
            price_data[symbol] = df["Close"]
            
    matrix_df = pd.DataFrame(price_data).corr(method='pearson')
    return matrix_df

def is_trade_approved_by_correlation(
    proposed_symbol: str, 
    active_positions: list, 
    correlation_limit: float = 0.70
) -> bool:
    """
    Approves or rejects a trade based on its correlation to active holdings.
    Prevents buying assets that are too mathematically aligned with existing risk.
    """
    if not active_positions:
        return True
        
    symbols_to_check = active_positions + [proposed_symbol]
    matrix = calculate_correlation_matrix(symbols_to_check)
    
    for active_symbol in active_positions:
        r_value = matrix.loc[proposed_symbol, active_symbol]
        if r_value > correlation_limit:
            return False  # Reject: Mathematical risk overlap!
            
    return True
```

---

## 8.5 Key Components of the Backtest Engine

### `backtest/engine.py` — Core Replay Loop
```python
class BacktestEngine:
    def __init__(self, strategy, symbols, start_date, end_date, capital=100000):
        self.strategy = strategy
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        self.capital = capital
        self.equity_curve = []
        self.trades = []

    def run(self):
        # 1. Fetch full OHLCV history for all symbols
        data_map = {s: fetch_historical_data(s, self.start_date, self.end_date) for s in self.symbols}
        
        # 2. Replay candle by candle chronologically
        timeline = sorted(list(set().union(*[df.index for df in data_map.values() if not df.empty])))
        
        for current_time in timeline:
            active_holdings = [t["symbol"] for t in self.trades if t["status"] == "OPEN"]
            
            for symbol in self.symbols:
                df = data_map[symbol]
                if current_time not in df.index:
                    continue
                    
                window = df.loc[:current_time]
                if len(window) < 50:
                    continue
                    
                indicators = calculate_all_indicators(window)
                
                # Check Correlation Engine before executing strategy
                if not is_trade_approved_by_correlation(symbol, active_holdings):
                    continue  # Correlation buffer block!
                
                # Run strategy decision
                signal = self.strategy.decide(indicators)
                
                if signal in ["BUY", "SHORT"]:
                    self._open_trade(symbol, signal, df.loc[current_time], indicators)
                    
            self._check_exits(current_time, data_map)
            self._record_equity(current_time, data_map)
            
        return self._generate_report()
```

---

## 8.6 API Endpoints & Dashboard Visuals

```
POST /api/backtest/run
Body: { symbols: [], strategy, start_date, end_date, capital }

GET  /api/backtest/correlation  — returns rolling Pearson correlation matrix
GET  /api/backtest/results/{id} — returns complete backtest report with Sharpe ratio
```

### Dashboard Upgrades
*   **Asset Correlation Heatmap**: A gorgeous interactive matrix showing rolling Pearson correlations between Bluechips, Midcaps, US Tech, and Gold.
*   **Backtest Equity Chart**: Line chart comparing the strategy's diversified equity curve against a standard Nifty 50 Buy & Hold benchmark.
*   **Drawdown Visualizer**: Identifies the portfolio's deepest historical peak-to-trough drops.

---

## 8.7 Phase 8 Consolidated Checklist

| # | Task | Status |
| :--- | :--- | :--- |
| 1 | Build `BacktestEngine` chronological replay loop | ☐ |
| 2 | Add support for Nifty Midcaps, US Tech, and Gold Spot datasets | ☐ |
| 3 | Create mathematical Pearson correlation matrix solver | ☐ |
| 4 | Hook up `is_trade_approved_by_correlation` inside Risk Manager | ☐ |
| 5 | Build the rolling correlation heatmap in the React UI | ☐ |
| 6 | Create `generate_report()` solving Sharpe, Max Drawdown, and Calmar ratios | ☐ |
| 7 | Create the `/api/backtest/run` and `/api/backtest/correlation` endpoints | ☐ |
| 8 | Run a 2-year backtest on a diversified portfolio vs. Nifty baseline | ☐ |

---

> **Phase 8 is COMPLETE when:** You can choose a diversified watchlist, trigger a historical backtest, and view a visual equity curve alongside an interactive asset correlation matrix in your dashboard.
