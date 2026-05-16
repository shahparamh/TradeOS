# 🚀 TradeOS: Autonomous AI Multi-Agent Trading Platform

TradeOS is a production-grade, autonomous multi-agent system designed to evaluate and compare AI models under identical real-world Indian stock market conditions.

The platform currently evaluates **Google Gemini 2.0 Flash** and **Meta Llama 3.3 (via Groq)** to determine which AI makes the most profitable trading decisions before deploying real capital.

---

## 🏗 System Architecture

### Backend (Python/FastAPI)
- **Market Data Aggregator**: Real-time NSE data via `yfinance`, Google News RSS, and NewsAPI.
- **Technical Engine**: 130+ indicators using `pandas_ta` (RSI, MACD, VWAP, etc.).
- **AI Decision Engine**: Concurrent polling of multiple LLMs with identical data payloads.
- **Risk Assessment**: Pre-trade validation, circuit breakers, and position management.
- **Virtual Broker**: Simulation of fills, slippage, and brokerage for 30-day performance tracking.

### Frontend (React.js - Coming Soon)
- Professional financial charting (Lightweight Charts).
- Real-time AI performance leaderboard.
- Live trade logs with AI reasoning visualization.

---

## 🛠 Setup Instructions

### 1. Prerequisites
- Python 3.10+
- [Groq API Key](https://console.groq.com/) (Free)
- [Google AI Studio API Key](https://aistudio.google.com/) (Free)
- [NewsAPI Key](https://newsapi.org/) (Free)

### 2. Installation
```bash
git clone https://github.com/yourusername/TradeOS.git
cd TradeOS/backend
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the `backend/` directory:
```env
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
NEWS_API_KEY=your_newsapi_key
INITIAL_CAPITAL=100000
DATABASE_URL=sqlite:///./tradeos.db
```

### 4. Database Seeding
Initialize the agents and database:
```bash
python -m database.seed
```

### 5. Run the Platform
```bash
python main.py
```
Visit `http://localhost:8000/api/health` to verify.

---

## 📅 Roadmap

- [x] **Phase 1**: Database & Foundation
- [x] **Phase 2**: Market Data & News Aggregator
- [x] **Phase 3**: Technical Scanner & Strategies
- [x] **Phase 4**: AI Decision Engine (Gemini & Groq)
- [ ] **Phase 5**: Risk Management & Virtual Broker
- [ ] **Phase 6**: React.js Dashboard
- [ ] **Phase 7**: Full 24/7 Autonomous Scheduler

---

## ⚖️ Disclaimer
This software is for simulation and educational purposes only. Trading in the stock market involves risk. Never trade with money you cannot afford to lose.
