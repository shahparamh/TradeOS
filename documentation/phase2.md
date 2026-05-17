# Phase 2 — Market Data & News Aggregation Engine

> **Goal:** Build the complete data collection layer that fetches real-time price data, historical OHLCV, live indices, news headlines, and fundamental metrics from multiple free sources. Normalize everything into clean, unified formats that the Scanner and AI agents can consume.

---

## 2.1 Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                   DATA AGGREGATOR                        │
│          (data/data_aggregator.py)                        │
│                                                          │
│   ┌────────────────┐  ┌──────────────┐  ┌─────────────┐ │
│   │ Market Fetcher │  │ News Fetcher │  │ Fundamental │ │
│   │ (yfinance +    │  │ (RSS + API + │  │ Fetcher     │ │
│   │  NSE scraper)  │  │  scraping)   │  │ (screener)  │ │
│   └───────┬────────┘  └──────┬───────┘  └──────┬──────┘ │
│           │                  │                  │        │
│           └──────────────────┴──────────────────┘        │
│                          │                               │
│                    Unified JSON                           │
│                   (per symbol)                            │
└──────────────────────────────────────────────────────────┘
```

---

## 2.2 Market Data Fetcher — `data/market_fetcher.py`

This is the **primary data source** for all price and volume information.

### 2.2.1 Yahoo Finance Integration (yfinance)

#### Functions to Implement:

**`fetch_live_price(symbol: str) → dict`**

Fetches the latest price data for a single stock.

```python
import yfinance as yf

def fetch_live_price(symbol: str) -> dict:
    """
    Returns:
    {
        "symbol": "RELIANCE.NS",
        "price": 2890.50,
        "open": 2875.00,
        "high": 2910.00,
        "low": 2860.00,
        "volume": 12500000,
        "prev_close": 2870.00,
        "change_pct": 0.71,
        "timestamp": "2026-05-16T10:30:00+05:30"
    }
    """
    ticker = yf.Ticker(symbol)
    info = ticker.fast_info
    # Extract and return structured data
```

**`fetch_intraday_candles(symbol: str, interval: str = "5m", period: str = "1d") → pd.DataFrame`**

Fetches intraday OHLCV candles for technical analysis.

```python
def fetch_intraday_candles(symbol: str, interval: str = "5m", period: str = "1d"):
    """
    Returns DataFrame with columns:
    | Datetime | Open | High | Low | Close | Volume |

    Supported intervals: "1m", "5m", "15m"
    Note: yfinance limits 1m data to last 7 days, 5m to last 60 days.
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    return df
```

**`fetch_historical_data(symbol: str, period: str = "6mo", interval: str = "1d") → pd.DataFrame`**

Fetches daily historical data for longer-term trend analysis.

```python
def fetch_historical_data(symbol: str, period: str = "6mo", interval: str = "1d"):
    """
    Used for:
    - Calculating 50-day EMA, 200-day SMA
    - Identifying support/resistance levels
    - Drawing historical trend lines on dashboard charts
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    return df
```

**`fetch_index_data() → dict`**

Fetches Nifty 50, Sensex, and India VIX — essential for market context.

```python
def fetch_index_data() -> dict:
    """
    Returns:
    {
        "nifty50": {
            "value": 24500.50,
            "change_pct": 0.45,
            "trend": "bullish"  # Based on whether above/below 20 EMA
        },
        "sensex": {
            "value": 80200.00,
            "change_pct": 0.38
        },
        "india_vix": {
            "value": 14.2,
            "status": "low"  # < 15 = low, 15-20 = moderate, > 20 = high
        }
    }
    """
```

**`fetch_bulk_prices(symbols: list) → dict`**

Fetches prices for the entire watchlist in one efficient call.

```python
def fetch_bulk_prices(symbols: list) -> dict:
    """
    Uses yf.download() for batch efficiency.
    Returns dict keyed by symbol with price data.

    Example:
    data = yf.download(symbols, period="1d", interval="5m", group_by="ticker")
    """
```

### 2.2.2 NSE India Scraper (Backup & Verification)

Used to cross-verify `yfinance` data and fetch NSE-specific information.

**`fetch_nse_market_status() → dict`**

```python
def fetch_nse_market_status() -> dict:
    """
    Scrapes NSE India website for:
    - Market breadth (advances vs declines)
    - Top 5 gainers
    - Top 5 losers
    - FII/DII data (if available)

    Returns:
    {
        "advances": 1250,
        "declines": 780,
        "unchanged": 120,
        "breadth_ratio": 1.60,
        "top_gainers": [...],
        "top_losers": [...]
    }
    """
```

### 2.2.3 Data Validation

Every price fetch must go through validation:

```python
def validate_price_data(data: dict) -> bool:
    """
    Checks:
    1. Price is not None or 0
    2. Price is within 20% of previous close (circuit breaker detection)
    3. Volume is not negative
    4. Timestamp is from today (not stale data)
    """
```

### 2.2.4 Error Handling & Fallback

```python
# Priority chain:
# 1. Try yfinance first
# 2. If yfinance fails → try NSE scraper
# 3. If both fail → log error, skip this symbol for this cycle
# NEVER use stale data without flagging it
```

---

## 2.3 News Fetcher — `data/news_fetcher.py`

Aggregates news from multiple free sources for each stock and for the broader market.

### 2.3.1 Google News RSS Parser

The most reliable and completely free news source.

**`fetch_google_news(query: str, max_results: int = 5) → list[dict]`**

```python
import feedparser
from datetime import datetime

def fetch_google_news(query: str, max_results: int = 5) -> list:
    """
    Fetches news from Google News RSS feed.

    URL pattern:
    https://news.google.com/rss/search?q={query}+stock+India&hl=en-IN&gl=IN&ceid=IN:en

    Returns:
    [
        {
            "headline": "Reliance Q4 profit surges 12%",
            "source": "google_rss",
            "url": "https://...",
            "published_at": "2026-05-16T08:30:00",
            "query": "Reliance"
        },
        ...
    ]
    """
    url = f"https://news.google.com/rss/search?q={query}+stock+India&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)

    articles = []
    for entry in feed.entries[:max_results]:
        articles.append({
            "headline": entry.title,
            "source": "google_rss",
            "url": entry.link,
            "published_at": entry.published,
            "query": query
        })
    return articles
```

**`fetch_market_news() → list[dict]`**

Fetches broad Indian market news (RBI, Nifty, economic events).

```python
def fetch_market_news() -> list:
    """
    Searches for:
    - "Indian stock market today"
    - "RBI policy"
    - "Nifty 50"
    - "FII DII activity India"

    Returns combined list of macro market news.
    """
```

### 2.3.2 NewsAPI Integration

Backup source with better structured data.

**`fetch_newsapi_headlines(query: str, max_results: int = 5) → list[dict]`**

```python
import requests
from config import settings

def fetch_newsapi_headlines(query: str, max_results: int = 5) -> list:
    """
    Uses NewsAPI.org free tier.
    Free tier limit: 100 requests/day — use sparingly.

    Endpoint: https://newsapi.org/v2/everything
    Params:
        q: query
        language: en
        sortBy: publishedAt
        pageSize: max_results
        apiKey: NEWS_API_KEY

    Returns same format as Google RSS for consistency.
    """
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": max_results,
        "apiKey": settings.NEWS_API_KEY
    }
    response = requests.get(url, params=params)
    data = response.json()
    # Parse and return
```

### 2.3.3 Moneycontrol Scraper

For specific earnings reports and breaking market news.

**`scrape_moneycontrol_news(symbol_name: str) → list[dict]`**

```python
from bs4 import BeautifulSoup
import requests

def scrape_moneycontrol_news(symbol_name: str) -> list:
    """
    Scrapes moneycontrol.com for company-specific news.

    Strategy:
    1. Search: https://www.moneycontrol.com/news/tags/{company_name}.html
    2. Parse headline, date, and link from each article card
    3. Return top 3-5 articles

    IMPORTANT:
    - Add User-Agent header to avoid blocking
    - Add 1-2 second delay between requests (rate limiting)
    - Cache results in news_cache table to avoid re-fetching
    """
```

### 2.3.4 Economic Times Markets Scraper

For macro events and RBI news.

**`scrape_et_markets() → list[dict]`**

```python
def scrape_et_markets() -> list:
    """
    Scrapes Economic Times Markets section for:
    - RBI monetary policy updates
    - Global market impact on India
    - Sector rotation news
    - Government policy announcements

    URL: https://economictimes.indiatimes.com/markets
    """
```

### 2.3.5 Basic Sentiment Tagging

Simple keyword-based sentiment until we add NLP in future phases.

```python
def tag_sentiment(headline: str) -> str:
    """
    Simple keyword-based sentiment analysis.

    Positive keywords: "surge", "profit", "beat", "upgrade", "bullish", "record high",
                       "growth", "strong", "outperform", "expansion"

    Negative keywords: "crash", "loss", "downgrade", "bearish", "selloff", "decline",
                       "weak", "miss", "fraud", "default", "debt"

    Returns: "positive", "negative", or "neutral"
    """
    headline_lower = headline.lower()
    positive_words = ["surge", "profit", "beat", "upgrade", "bullish", "record",
                      "growth", "strong", "outperform", "expansion", "rally"]
    negative_words = ["crash", "loss", "downgrade", "bearish", "selloff", "decline",
                      "weak", "miss", "fraud", "default", "slump", "fall"]

    pos_count = sum(1 for word in positive_words if word in headline_lower)
    neg_count = sum(1 for word in negative_words if word in headline_lower)

    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"
```

### 2.3.6 News Caching Strategy

```python
# Every fetched news item is saved to the `news_cache` table.
# Before fetching, check if we already have recent news (< 30 minutes old).
# This prevents:
#   1. Hitting API rate limits
#   2. Sending duplicate news to the AIs
#   3. Wasting bandwidth on unchanged data
```

---

## 2.4 Fundamentals Fetcher — `data/fundamentals_fetcher.py`

### 2.4.1 yfinance Fundamentals

**`fetch_yf_fundamentals(symbol: str) → dict`**

```python
def fetch_yf_fundamentals(symbol: str) -> dict:
    """
    Fetches basic fundamental data from Yahoo Finance.

    Returns:
    {
        "symbol": "RELIANCE.NS",
        "market_cap": 1950000000000,
        "pe_ratio": 28.5,
        "pb_ratio": 2.1,
        "dividend_yield": 0.35,
        "eps": 101.5,
        "52_week_high": 3050.00,
        "52_week_low": 2200.00,
        "sector": "Energy",
        "industry": "Oil & Gas Refining"
    }
    """
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
    }
```

### 2.4.2 Screener.in Scraper

The best free source for Indian-specific fundamental metrics.

**`scrape_screener_data(symbol_name: str) → dict`**

```python
def scrape_screener_data(symbol_name: str) -> dict:
    """
    Scrapes screener.in for detailed Indian market fundamentals.

    URL: https://www.screener.in/company/{SYMBOL}/consolidated/

    Data extracted:
    {
        "revenue_growth": 15.2,          # % YoY
        "profit_growth": 22.8,           # % YoY
        "roe": 18.5,                     # Return on Equity %
        "roce": 21.3,                    # Return on Capital Employed %
        "debt_to_equity": 0.45,
        "promoter_holding": 50.3,        # %
        "promoter_holding_change": -0.2, # Quarterly change
        "quarterly_revenue": [           # Last 4 quarters
            {"quarter": "Q1 2026", "revenue": 250000, "profit": 45000},
            ...
        ]
    }

    IMPORTANT:
    - Screener may require login for some data — handle gracefully
    - Cache aggressively (fundamentals don't change intraday)
    - Refresh once per day maximum
    """
```

### 2.4.3 NSE Corporate Filings

**`fetch_nse_filings(symbol: str) → list[dict]`**

```python
def fetch_nse_filings(symbol: str) -> list:
    """
    Fetches recent corporate announcements from NSE.

    Data includes:
    - Quarterly results announcements
    - Board meeting dates
    - Dividend declarations
    - Bonus/split announcements
    - Insider trading disclosures

    Returns:
    [
        {
            "type": "quarterly_results",
            "date": "2026-05-10",
            "description": "Board meeting to consider Q4 FY26 results"
        },
        ...
    ]
    """
```

---

## 2.5 Data Aggregator — `data/data_aggregator.py`

This is the **master module** that combines all data sources into a single unified payload.

### 2.5.1 The Aggregation Function

**`aggregate_stock_data(symbol: str) → dict`**

```python
async def aggregate_stock_data(symbol: str) -> dict:
    """
    The MASTER function that combines all data for a single stock.

    Calls:
    1. market_fetcher.fetch_live_price(symbol)
    2. market_fetcher.fetch_intraday_candles(symbol)
    3. news_fetcher.fetch_all_news(symbol)
    4. fundamentals_fetcher.fetch_yf_fundamentals(symbol)

    Returns unified JSON:
    {
        "symbol": "RELIANCE.NS",
        "timestamp": "2026-05-16T10:30:00+05:30",

        "price_data": {
            "current_price": 2890.50,
            "open": 2875.00,
            "high": 2910.00,
            "low": 2860.00,
            "volume": 12500000,
            "prev_close": 2870.00,
            "change_pct": 0.71
        },

        "candles": [...],  # DataFrame converted to list of dicts

        "fundamentals": {
            "pe_ratio": 28.5,
            "market_cap": 1950000000000,
            "revenue_growth": 15.2,
            "profit_growth": 22.8,
            "roe": 18.5,
            "debt_to_equity": 0.45,
            "promoter_holding": 50.3
        },

        "news": [
            {
                "headline": "Reliance Q4 profit surges 12%",
                "sentiment": "positive",
                "source": "google_rss",
                "published_at": "2026-05-16T08:30:00"
            },
            ...
        ],

        "filings": [...]
    }
    """
```

### 2.5.2 Aggregate Market Context

**`aggregate_market_context() → dict`**

```python
async def aggregate_market_context() -> dict:
    """
    Fetches the broader market picture.

    Returns:
    {
        "nifty50": {"value": 24500, "change_pct": 0.45, "trend": "bullish"},
        "sensex": {"value": 80200, "change_pct": 0.38},
        "india_vix": {"value": 14.2, "status": "low"},
        "market_breadth": {"advances": 1250, "declines": 780, "ratio": 1.60},
        "macro_news": [...],
        "timestamp": "2026-05-16T10:30:00+05:30"
    }
    """
```

### 2.5.3 Full Watchlist Aggregation

**`aggregate_all_watchlist() → list[dict]`**

```python
async def aggregate_all_watchlist() -> list:
    """
    Iterates over WATCHLIST and calls aggregate_stock_data() for each.
    Uses asyncio.gather() for parallel execution where possible.

    Returns list of unified stock data objects.

    Rate Limiting:
    - Add 0.5s delay between yfinance calls to avoid throttling
    - Cache results for 5 minutes to avoid redundant calls
    """
```

---

## 2.6 Data Storage — Saving Snapshots to Database

Every scan cycle, we persist market data to the `market_snapshots` and `news_cache` tables.

```python
def save_market_snapshot(db_session, symbol: str, data: dict):
    """
    Saves current market state to market_snapshots table.
    Used for:
    1. Historical replay and debugging
    2. Dashboard charting (plotting past prices)
    3. Verifying AI decisions against market state at decision time
    """

def save_news_to_cache(db_session, articles: list):
    """
    Saves fetched news to news_cache table.
    Skips duplicates (check by URL).
    """
```

---

## 2.7 Data Freshness & Reliability Rules

| Rule | Description |
|------|-------------|
| **Staleness Check** | If price data is older than 2 minutes during market hours, discard and re-fetch. |
| **Source Priority** | yfinance → NSE scraper → skip (never guess). |
| **Cache Duration** | Price: 1-2 min. News: 30 min. Fundamentals: 24 hours. |
| **Rate Limits** | yfinance: 0.5s between calls. NewsAPI: max 100/day. Moneycontrol: 2s between scrapes. |
| **Error Logging** | Every failed fetch is logged with timestamp, source, and error message. |
| **Weekend/Holiday** | During non-market hours, fetch previous close data and focus on news aggregation. |

---

## 2.8 API Endpoints (for Dashboard)

Expose data through FastAPI routes in `api/routes_market.py`:

```python
# GET /api/market/price/{symbol}        → Live price for one stock
# GET /api/market/candles/{symbol}      → Intraday candle data
# GET /api/market/indices               → Nifty, Sensex, VIX
# GET /api/market/news/{symbol}         → Recent news for a stock
# GET /api/market/news/macro            → Broad market news
# GET /api/market/fundamentals/{symbol} → Fundamental data
# GET /api/market/watchlist             → Aggregated data for all watchlist stocks
```

---

## 2.9 Phase 2 Completion Checklist

| #  | Task                                              | Status |
|----|---------------------------------------------------|--------|
| 1  | Implement `market_fetcher.py` with all functions   | ☐      |
| 2  | Test yfinance fetching for all 12 watchlist stocks | ☐      |
| 3  | Implement `news_fetcher.py` (RSS + NewsAPI + scraping) | ☐  |
| 4  | Test Google RSS returns relevant Indian stock news | ☐      |
| 5  | Implement `fundamentals_fetcher.py`                | ☐      |
| 6  | Test Screener.in scraper returns valid data        | ☐      |
| 7  | Implement `data_aggregator.py` master function     | ☐      |
| 8  | Test full aggregation for one stock end-to-end     | ☐      |
| 9  | Implement data validation and error handling       | ☐      |
| 10 | Implement caching and rate limiting                | ☐      |
| 11 | Save snapshots and news to database                | ☐      |
| 12 | Create `/api/market/*` endpoints in FastAPI        | ☐      |
| 13 | Test all API endpoints return valid JSON            | ☐      |

---

> **Phase 2 is COMPLETE when:** The system can fetch live price data, news, and fundamentals for all 12 watchlist stocks, combine them into a unified JSON payload, save snapshots to the database, and serve the data through REST endpoints.

> **Next →** [Phase 3: Technical Analysis & Opportunity Scanner](./phase3.md)
