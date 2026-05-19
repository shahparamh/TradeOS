# 🚀 TradeOS: Autonomous AI Multi-Agent Trading Platform

TradeOS is a production-grade, autonomous multi-agent quantitative evaluation engine designed to compare, benchmark, and deploy AI models under identical, live stock market conditions in real-time.

By running diverse cognitive LLMs concurrently with the exact same technical indicator and news streams, TradeOS calculates objective performance metrics, win rates, and drawdowns before deploying simulated or live capital.

---

## ⚡ Key Highlights & Features

*   **Quantitative AI Fleet**:
    *   **Google Gemini 3.1 Flash Lite**: Ultra-fast multi-modal analysis and planning.
    *   **Groq-Llama 3.3 (70B)**: Real-time contrarian/mean-reversion execution.
    *   **Qwen-Free (via OpenRouter)**: High-speed reasoning model.
    *   **Local-Ollama (Llama 3.2 3B)**: **100% private, free, and offline fallback agent** running on your local RAM & GPU (Local Only).
*   **Virtual Broker & Position Monitor**: Simulates fills with slippage, brokerage, and active monitoring for stop-loss, targets, and automatic 3:15 PM IST square-offs.
*   **Derivatives & VIX Integrator**:
    *   **Option Open Interest (OI) & PCR**: Dynamically queries the option chain of the nearest expiry to calculate the **Put-Call Ratio (PCR)** (PCR $\ge$ 1.15 is BULLISH support floor; PCR $\le$ 0.75 is BEARISH overhead resistance).
    *   **India VIX Ingestion**: Monitors `^INDIAVIX` volatility. AI agents automatically scale down trade sizes by 50%+ during high volatility (VIX > 20).
*   **Technicals & yfinance Fundamentals Fusion**: Ingests real-time indicators (RSI, MACD, EMA 20/50, VWAP, Bollinger Bands, ATR, Pivot Points) alongside key stock metrics (P/E Ratio, Market Cap, Debt-to-Equity, ROE) to enable deep quantitative decisions.
*   **Cost-Efficient Pre-emptive API Guard**: Automatically scans database entries before calling LLM APIs. If an agent has already executed 2 trades for that stock today, it pre-emptively skips the API request, **saving 100% of LLM token costs**.
*   **Stunning Dashboard**: Interactive React frontend showing real-time agent leaderboards, trade counts, visual win-rates, active positions, and interactive fluctuating charts.

---

## 🏗️ System Architecture

```
                    ┌────────────────────────┐
                    │   React Dashboard UI   │
                    └───────────┬────────────┘
                                │ HTTP / WebSockets (0.5s Fluctuations)
                    ┌───────────▼────────────┐
                    │  FastAPI Backend Host  │
                    └───────────┬────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Market fetcher   │  │ database         │  │ agent executor   │
│ - Live NSE Prices│  │ - SQLite / Neon  │  │ - Google / Groq  │
│ - Options OI PCR │  │ - Position State │  │ - OpenRouter     │
│ - India VIX      │  │ - Trade History  │  │ - Local Ollama   │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 🛠️ Quick Start Setup

### 1. Prerequisites
*   Python 3.10+ & Node.js (with npm)
*   **Ollama Installed** (Local Only): To power the offline agent (`ollama run llama3.2`)
*   **LLM Credentials**: API Keys for Gemini, Groq, and OpenRouter (linked inside your secure `.env`).

### 2. Launching Locally 🚀
We provide an easy local start routine:
1. **Backend**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```
2. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   *   👉 Backend running on: `http://localhost:8000`
   *   👉 Frontend running on: `http://localhost:5173`

---

## 🦙 Running the Local Ollama Agent (Llama 3.2) - Local Only

To run the completely private, offline **Local-Ollama (Llama 3.2)** agent in your local TradeOS fleet:

1. **Download & Install Ollama**:
   * **macOS**: Download from [ollama.com/download/Ollama-darwin.zip](https://ollama.com/download/Ollama-darwin.zip).
   * **Windows**: Download from [ollama.com/download/OllamaSetup.exe](https://ollama.com/download/OllamaSetup.exe) and run.
2. **Pull the Llama 3.2 Brain**:
   ```bash
   ollama pull llama3.2
   ```
3. **Automatic Cloud Exclusion**: When deployed to Render, the engine automatically detects the cloud environment (`RENDER=true`) and bypasses Ollama execution, avoiding cloud server connection failures while keeping it active locally!

---

## ⚙️ Environment Configuration

Create a `.env` file in the `backend/` directory:
```env
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
OPENROUTER_API_KEY=your_openrouter_key

# Quant settings
INITIAL_CAPITAL=100000
DATABASE_URL=sqlite:///./tradeos.db
```

---

## 📅 Platform Status & Roadmap

| Phase | Title | Focus Area | Status |
| :---: | :--- | :--- | :---: |
| **1** | Database & Foundation | SQLite architecture, models schema & config | ✅ Completed |
| **2** | Market Data & News | Live NSE feeds, RSS news sentiment, indicators | ✅ Completed |
| **3** | Technical Indicator Solver | Moving Averages, RSI, MACD, Bollinger Bands | ✅ Completed |
| **4** | Multi-Agent Core Engine | Parallel execution of AI decision queries | ✅ Completed |
| **5** | Virtual Broker & Risk Manager | Slippage, brokerage, stop-loss, targets, **2-Trade Limit** | ✅ Completed |
| **6** | React Financial Dashboard | Professional charting, leaderboards, logs, **OI PCR & VIX** | ✅ Completed |
| **7** | Autonomous APScheduler | 24/7 autonomous loop & **Pre-emptive API Guard** | ✅ Completed |
| **8** | Portfolio Intelligence & Backtester | Roll back 5 years + Sector Correlation Matrix | 🚀 *Next* |
| **9** | Fleet Expansion & SaaS Database | Multi-user JWT security, BYOK keys portal | 🚀 *Next* |
| **10** | Dynamic Memory Loops & Deployment | AI Self-Learning, Redis cache, Docker, WebSockets | 🚀 *Next* |

---

## ⚖️ Disclaimer
This software is for simulation and educational purposes only. TradeOS does not deploy real financial capital unless explicit real-broker plugins are coded. Trading in financial markets involves high risk. Never trade with capital you cannot afford to lose.
