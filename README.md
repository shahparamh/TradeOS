# 🚀 TradeOS: Autonomous AI Multi-Agent Trading Platform

TradeOS is a production-grade, autonomous multi-agent quantitative evaluation engine designed to compare, benchmark, and deploy AI models under identical, live stock market conditions in real-time.

By running diverse cognitive LLMs concurrently with the exact same technical indicator and news streams, TradeOS calculates objective performance metrics, win rates, and drawdowns before deploying simulated or live capital.

---

## ⚡ Key Highlights & Features

*   **5-Agent AI Fleet**:
    *   **Google Gemini 2.0 Flash**: Ultra-fast multi-modal analysis.
    *   **Groq-Llama 3.3 (70B)**: Real-time contrarian/mean-reversion execution.
    *   **Qwen-Free (via OpenRouter)**: High-speed reasoning model.
    *   **DeepSeek-R1**: Full chain-of-thought `<think>` logic tracing before placement.
    *   **Local-Ollama (Llama 3.2 3B)**: **100% private, free, and offline fallback agent** running on your MacBook's RAM & GPU!
*   **Virtual Broker & Position Monitor**: Simulates fills with slippage, brokerage, and active monitoring for stop-loss, targets, and automatic 3:15 PM IST square-offs.
*   **Mathematical Risk Guardrails**: Real-time capital limits, maximum intraday trade caps, and drawdown circuit-breakers.
*   **Stunning Dashboard**: Interactive React frontend showing real-time agent leaderboards, trade counts, visual win-rates, active positions, and interactive charts.

---

## 🏗️ System Architecture

```
                    ┌────────────────────────┐
                    │   React Dashboard UI   │
                    └───────────┬────────────┘
                                │ HTTP / WebSockets
                    ┌───────────▼────────────┐
                    │  FastAPI Backend Host  │
                    └───────────┬────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Market fetcher   │  │ database         │  │ agent executor   │
│ - Live NSE Prices│  │ - SQLite (Seed)  │  │ - Google / Groq  │
│ - pandas_ta Ind. │  │ - Position State │  │ - DeepSeek / Qwen│
│ - News RSS Feeds │  │ - Trade History  │  │ - Local Ollama   │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 🛠️ Quick Start Setup

### 1. Prerequisites
*   Python 3.10+ & Node.js (with npm)
*   **Ollama Installed**: To power the offline agent (`ollama run llama3.2`)
*   **LLM Credentials**: Free API Keys for Gemini, Groq, OpenRouter, and DeepSeek (linked inside your secure `.env`).

### 2. The One-Command Launcher 🚀
No need to open multiple terminal windows manually. We have provided a custom multi-tab macOS launch script:
```bash
# In the TradeOS project root:
chmod +x start.sh
./start.sh
```
*Choose **Choice 1** to automatically spin up Backend and Frontend in separate live Apple Terminal windows!*
*   👉 Backend running on: `http://localhost:8000`
*   👉 Frontend running on: `http://localhost:5173` (or `5174`)

---

## 🦙 Running the Local Ollama Agent (Llama 3.2)

To run the completely private, offline **Local-Ollama (Llama 3.2)** agent in your TradeOS fleet:

1. **Download & Install Ollama**:
   * **macOS**: Download from [ollama.com/download/Ollama-darwin.zip](https://ollama.com/download/Ollama-darwin.zip). Unzip and run `Ollama.app`.
   * **Windows**: Download the installer from [ollama.com/download/OllamaSetup.exe](https://ollama.com/download/OllamaSetup.exe) and run it.
2. **Pull the Llama 3.2 Brain**:
   Open a terminal and download the model:
   ```bash
   ollama pull llama3.2
   ```
3. **Launch & Verify**:
   Ensure the Ollama helper icon is running in your menu bar, and launch TradeOS using `./start.sh`. The system will automatically direct concurrent queries to your local offline brain!

---


## ⚙️ Manual Configuration

If you prefer to configure manually:

### 1. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
Create a `.env` file in the `backend/` directory:
```env
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
OPENROUTER_API_KEY=your_openrouter_key
DEEPSEEK_API_KEY=your_deepseek_key
GITHUB_API_KEY=your_github_models_pat

INITIAL_CAPITAL=100000
DATABASE_URL=sqlite:///./tradeos.db
```
Start backend:
```bash
python main.py
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## 📅 The Consolidated 10-Phase Roadmap

| Phase | Title | Focus Area | Status |
| :---: | :--- | :--- | :---: |
| **1** | Database & Foundation | SQLite architecture, models schema & config | ✅ Completed |
| **2** | Market Data & News | Live NSE feeds, RSS news sentiment, indicators | ✅ Completed |
| **3** | Technical Indicator Solver | Moving Averages, RSI, MACD, Bollinger Bands | ✅ Completed |
| **4** | Multi-Agent Core Engine | Parallel execution of AI decision queries | ✅ Completed |
| **5** | Virtual Broker & Risk Manager | Slippage, brokerage, stop-loss, targets | ✅ Completed |
| **6** | React Financial Dashboard | Professional charting, leaderboards, logs | ✅ Completed |
| **7** | Autonomous APScheduler | 24/7 autonomous loop & 30-day live simulation | ✅ Completed |
| **8** | Portfolio Intelligence & Backtester | Roll back 5 years + Sector Correlation Matrix | 🚀 *Next* |
| **9** | Fleet Expansion & SaaS Database | Multi-user JWT security, BYOK keys portal | 🚀 *Next* |
| **10** | Dynamic Memory Loops & Deployment | AI Self-Learning, Redis cache, Docker, WebSockets | 🚀 *Next* |

---

## ⚖️ Disclaimer
This software is for simulation and educational purposes only. TradeOS does not deploy real financial capital unless explicit real-broker plugins are coded. Trading in financial markets involves high risk. Never trade with capital you cannot afford to lose.
