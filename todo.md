# TradeOS Simulation - API & Library Checklist

To run this simulation without incurring massive data costs, we will rely on free APIs and Python scraping libraries. 

## 1. Market Data (Price, OHLCV, Volume)
We need multiple sources to cross-verify the data and ensure our simulation reflects reality.

*   [ ] **yfinance (Library)**: The primary engine. It pulls directly from Yahoo Finance for free. Excellent for 1-minute, 5-minute intraday data, and daily historicals. (e.g., `RELIANCE.NS`).
*   [ ] **jugaad-data / nsepython (Library)**: Python libraries built specifically to scrape the official NSE India website. Used to fetch live market depth, top gainers/losers, and verify `yfinance` prices.
*   [ ] **Alpha Vantage (API)**: Has a free tier (25 requests/day). We will use this only as a fallback verification check if Yahoo Finance data looks anomalous.

## 2. News & Sentiment Engine
The AIs need to know what is happening in the world to make informed decisions.

*   [ ] **Google News RSS (Feed)**: `https://news.google.com/rss/search?q={Company}`. Completely free, highly reliable, and updates instantly. We will parse this with Python's `feedparser`.
*   [ ] **NewsAPI.org (API)**: Free developer tier (100 requests/day). Good for grabbing general macroeconomic headlines (e.g., RBI rate changes, Nifty news).
*   [ ] **Moneycontrol & Economic Times (Web Scraping)**: We will write custom scrapers using `BeautifulSoup4` and `requests` to fetch specific corporate announcements and earnings reports.

## 3. Fundamental Data
For the scanner to find "Earnings Momentum" or "Value" plays.

*   [ ] **yfinance (Library)**: Can fetch basic fundamentals like P/E ratio, Market Cap, and basic financials.
*   [ ] **Screener.in (Web Scraping)**: We will parse HTML from Screener to get high-quality Indian market metrics like ROE, Debt-to-Equity, and Quarterly profit growth.

## 4. Large Language Model (LLM) APIs
To get the 4 AIs to make decisions, we need API access. 
*Note: While market data is free, premium AI APIs usually charge per token. Here is the breakdown:*

*   [ ] **Google Gemini API**: **FREE TIER AVAILABLE**. Through Google AI Studio, Gemini 1.5 Pro and Flash offer very generous free tiers (up to 15 requests per minute).
*   [ ] **OpenAI API (ChatGPT-4o)**: Paid (pay-as-you-go). Requires an API key loaded with credits.
*   [ ] **Anthropic API (Claude 3.5 Sonnet)**: Paid (pay-as-you-go). Requires an API key.
*   [ ] **xAI API (Grok)**: Paid. Requires an API key.

*Alternative Free Option for LLMs:* If you want strictly free LLMs for testing before paying for OpenAI/Claude, we can use the **Groq API** (which hosts Llama 3 for free at high speeds) or run models locally using **Ollama**.

## 5. Technical Indicators
*   [ ] **pandas_ta (Library)**: Completely free, runs locally. Converts our raw price data into RSI, MACD, Bollinger Bands, EMA, etc.

## 6. Frontend Dashboard
*   [ ] **React.js & Vite**: Open source and free.
*   [ ] **Lightweight Charts (by TradingView)**: A free, high-performance open-source library for creating professional financial candlestick charts in React.
