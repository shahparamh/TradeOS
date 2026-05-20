# Fix yfinance Rate Limiting ("Too Many Requests")

## Problem

yfinance hits Yahoo Finance's undocumented rate limits (~2000 requests/hour, but variable). Your system fires **many concurrent requests** because:

1. **Trading loop** scans 10 watchlist symbols with `Semaphore(3)` — 3 symbols concurrently, each calling `fetch_intraday_candles` + `fetch_yf_fundamentals` + `fetch_option_oi_metrics` = **~30 yfinance calls per cycle**
2. **`aggregate_market_context`** fetches Nifty, Sensex, VIX = 3 more calls
3. **WebSocket live price** calls `fetch_live_price` (60s cache, but still fires)
4. **Pre-market session** iterates all symbols × agents with no rate control
5. **`aggregate_all_watchlist`** fires ALL 10 symbols in parallel via `asyncio.gather` with no throttling

**Result**: Bursts of 30-50+ requests in seconds → Yahoo returns HTTP 429 → all data fails.

## Proposed Changes

### 1. Centralized Rate Limiter Utility

#### [NEW] [rate_limiter.py](file:///c:/Users/evanc/Desktop/TradeOS/backend/utils/rate_limiter.py)

A `threading.Lock`-based rate limiter that enforces a minimum delay between yfinance API calls globally. This is a simple token-bucket approach:

- **`MIN_REQUEST_INTERVAL`**: 1.5 seconds between any two yfinance calls (configurable)
- All yfinance calls go through `rate_limited_call(callable, *args, **kwargs)` which acquires a lock, sleeps if needed, then executes
- Thread-safe for use with `asyncio.to_thread`

---

### 2. Cache Fundamentals in DB (They Rarely Change)

#### [MODIFY] [fundamentals_fetcher.py](file:///c:/Users/evanc/Desktop/TradeOS/backend/data/fundamentals_fetcher.py)

- Add an **in-memory cache with 6-hour TTL** for fundamentals (P/E, market cap, sector don't change intraday)
- On cache miss, call yfinance through the rate limiter
- On rate-limit error, return stale cached data instead of an empty dict

---

### 3. Rate-Limit All yfinance Calls in `market_fetcher.py`

#### [MODIFY] [market_fetcher.py](file:///c:/Users/evanc/Desktop/TradeOS/backend/data/market_fetcher.py)

- Route every `yf.Ticker(...)` call through the rate limiter
- Increase `CACHE_TTL_SECONDS` from 60 → **120** for live prices (2 min is fine for a 10-min scan cycle)
- Add caching to `fetch_index_data` and `calculate_market_regime` (these indices don't change second-by-second)
- Add caching to `fetch_option_oi_metrics` with **30-min TTL** (OI changes slowly)

---

### 4. Sequential Scanning in Trading Loop

#### [MODIFY] [trading_loop.py](file:///c:/Users/evanc/Desktop/TradeOS/backend/scheduler/trading_loop.py)

- **Remove the `Semaphore(3)` parallel scan** — scan symbols **sequentially** with a 3-second delay between each
- Increase the inter-symbol `asyncio.sleep` from 2 → **5** seconds
- The 15-minute cooldown already exists — this is good, keep it

---

### 5. Throttle `aggregate_all_watchlist`

#### [MODIFY] [data_aggregator.py](file:///c:/Users/evanc/Desktop/TradeOS/backend/data/data_aggregator.py)

- Replace `asyncio.gather(*tasks)` with **sequential execution + 2s delay** between symbols
- This prevents 10 parallel bursts of 4 calls each

---

## Summary of Rate-Limiting Strategy

| Layer | What | Mechanism |
|-------|------|-----------|
| **Global** | All yfinance calls | 1.5s min gap via `rate_limiter` |
| **Live Prices** | `fetch_live_price` | 120s in-memory cache |
| **Fundamentals** | `fetch_yf_fundamentals` | 6-hour in-memory cache |
| **Option OI** | `fetch_option_oi_metrics` | 30-min in-memory cache |
| **Indices** | `fetch_index_data` | 120s in-memory cache |
| **Market Regime** | `calculate_market_regime` | 300s in-memory cache |
| **Scanner** | Trading loop | Sequential scan, 5s between symbols |
| **Aggregator** | `aggregate_all_watchlist` | Sequential, 2s between symbols |

> [!IMPORTANT]
> **Trade-off**: Data will be slightly less "real-time" (2-min stale at worst for prices, 30-min for OI). But since your scan cycle is every 10 minutes anyway, this has **zero impact on trading decisions** while completely eliminating rate limiting.

## Open Questions

> [!NOTE]
> 1. Your `CACHE_TTL_SECONDS` is currently 60s for live prices. Is **120s** acceptable, or do you want to keep it at 60s? (The rate limiter alone would likely fix the issue even at 60s.)
> 2. Do you want to add a **disk/DB-backed cache** for fundamentals so they survive restarts, or is in-memory (6hr TTL) fine?

## Verification Plan

### Manual Verification
- Run the trading cycle manually and confirm:
  - No "Too Many Requests" errors in logs
  - All 10 symbols scan successfully
  - Prices, fundamentals, and OI data are populated correctly
  - Second cycle reuses cache (check for `Using cached...` log messages)
