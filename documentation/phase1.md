# Phase 1 — Project Foundation & Database Architecture

> **Goal:** Set up the entire project skeleton, install all dependencies, configure environment variables, design the complete database schema, and build the foundational utility modules that every other phase depends on.

---

## 1.1 Project Directory Structure

Create the following folder hierarchy inside `TradeOS/`:

```
TradeOS/
├── backend/
│   ├── main.py                      # FastAPI entry point
│   ├── config.py                    # All configuration constants
│   ├── requirements.txt             # Python dependencies
│   ├── .env                         # API keys (NEVER commit this)
│   ├── .env.example                 # Template for .env
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py            # SQLAlchemy engine & session factory
│   │   ├── models.py                # All ORM table models
│   │   └── seed.py                  # Seed initial data (agents, watchlist)
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── market_fetcher.py        # yfinance + NSE data fetcher
│   │   ├── news_fetcher.py          # Google RSS + NewsAPI
│   │   ├── fundamentals_fetcher.py  # Screener.in + yfinance fundamentals
│   │   └── data_aggregator.py       # Combines all data into unified format
│   │
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── technical_engine.py      # pandas_ta indicator calculations
│   │   └── opportunity_scanner.py   # Filters opportunities from indicators
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py            # Abstract base class for all agents
│   │   ├── chatgpt_agent.py         # OpenAI GPT-4o integration
│   │   ├── gemini_agent.py          # Google Gemini integration
│   │   ├── claude_agent.py          # Anthropic Claude integration
│   │   ├── grok_agent.py            # xAI Grok integration
│   │   └── prompt_builder.py        # Builds standardized prompt + JSON
│   │
│   ├── broker/
│   │   ├── __init__.py
│   │   ├── virtual_broker.py        # Simulated trade execution engine
│   │   ├── risk_manager.py          # All risk validation rules
│   │   └── position_monitor.py      # Monitors SL/TP for open positions
│   │
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── trading_loop.py          # APScheduler orchestration
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_dashboard.py      # REST endpoints for dashboard
│   │   ├── routes_agents.py         # REST endpoints for agent data
│   │   ├── routes_trades.py         # REST endpoints for trade history
│   │   └── routes_market.py         # REST endpoints for market data
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py                # Centralized logging
│       ├── helpers.py               # Date/time helpers, IST conversions
│       └── constants.py             # Watchlist, market hours, etc.
│
├── frontend/                        # React.js (Vite) dashboard
│   └── (initialized in Phase 6)
│
├── todo.md
├── phase1.md
├── phase2.md
├── ...
└── README.md
```

---

## 1.2 Python Environment Setup

### Step 1: Create a Virtual Environment

```bash
cd TradeOS/backend
python -m venv venv
```

### Step 2: Activate the Virtual Environment

```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Step 3: Create `requirements.txt`

```txt
# === Core Framework ===
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.9.0
python-dotenv==1.0.1

# === Database ===
sqlalchemy==2.0.35
aiosqlite==0.20.0

# === Market Data ===
yfinance==0.2.43
pandas==2.2.2
numpy==1.26.4

# === Technical Indicators ===
pandas-ta==0.3.14b

# === News & Scraping ===
requests==2.32.3
beautifulsoup4==4.12.3
feedparser==6.0.11
lxml==5.3.0

# === AI Agent SDKs ===
openai==1.51.0
google-generativeai==0.8.0
anthropic==0.34.0

# === Scheduling ===
apscheduler==3.10.4

# === Data Visualization (API side) ===
plotly==5.24.0

# === Utilities ===
httpx==0.27.2
python-dateutil==2.9.0
pytz==2024.2
```

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 1.3 Environment Configuration

### Step 1: Create `.env.example`

This is the template file that we commit to git. The actual `.env` file with real keys is never committed.

```env
# ========================================
# TradeOS — Environment Configuration
# ========================================

# --- LLM API Keys ---
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxx
XAI_API_KEY=xai-xxxxxxxxxxxxxxxxxxxxxxxx

# --- News APIs ---
NEWS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# --- Database ---
DATABASE_URL=sqlite:///./tradeos.db

# --- Trading Config ---
INITIAL_CAPITAL=100000
MAX_CAPITAL_PER_TRADE=0.20
MAX_OPEN_POSITIONS=5
MAX_INTRADAY_TRADES=3
AUTO_SQUARE_OFF_TIME=15:15
DAILY_DRAWDOWN_LIMIT=-0.05

# --- Broker Simulation ---
BROKERAGE_PERCENT=0.0003
SLIPPAGE_PERCENT=0.0005

# --- Scheduler ---
SCAN_INTERVAL_MINUTES=10
```

### Step 2: Create `config.py`

This file reads `.env` and exposes typed configuration to all modules.

```python
# backend/config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # LLM Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")

    # News
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./tradeos.db")

    # Trading
    INITIAL_CAPITAL: float = float(os.getenv("INITIAL_CAPITAL", 100000))
    MAX_CAPITAL_PER_TRADE: float = float(os.getenv("MAX_CAPITAL_PER_TRADE", 0.20))
    MAX_OPEN_POSITIONS: int = int(os.getenv("MAX_OPEN_POSITIONS", 5))
    MAX_INTRADAY_TRADES: int = int(os.getenv("MAX_INTRADAY_TRADES", 3))
    AUTO_SQUARE_OFF_TIME: str = os.getenv("AUTO_SQUARE_OFF_TIME", "15:15")
    DAILY_DRAWDOWN_LIMIT: float = float(os.getenv("DAILY_DRAWDOWN_LIMIT", -0.05))

    # Broker
    BROKERAGE_PERCENT: float = float(os.getenv("BROKERAGE_PERCENT", 0.0003))
    SLIPPAGE_PERCENT: float = float(os.getenv("SLIPPAGE_PERCENT", 0.0005))

    # Scheduler
    SCAN_INTERVAL_MINUTES: int = int(os.getenv("SCAN_INTERVAL_MINUTES", 10))

settings = Settings()
```

---

## 1.4 Database Schema (SQLAlchemy ORM)

### Full Schema Design

We need 7 core tables. Here is the detailed schema for each:

---

### Table 1: `agents`

Stores metadata about each AI agent.

| Column       | Type         | Description                       |
|--------------|--------------|-----------------------------------|
| id           | Integer (PK) | Auto-increment                    |
| name         | String(50)   | "ChatGPT", "Gemini", "Claude", "Grok" |
| provider     | String(50)   | "openai", "google", "anthropic", "xai" |
| model_name   | String(100)  | "gpt-4o", "gemini-1.5-pro", etc.  |
| cash_balance | Float        | Current available capital          |
| total_pnl    | Float        | Cumulative realized PnL           |
| is_active    | Boolean      | Can this agent trade?             |
| created_at   | DateTime     | When agent was registered          |

---

### Table 2: `trades`

Every single trade ever executed by any agent.

| Column         | Type         | Description                                   |
|----------------|--------------|-----------------------------------------------|
| id             | Integer (PK) | Auto-increment                                |
| agent_id       | Integer (FK) | References `agents.id`                        |
| symbol         | String(30)   | e.g. "RELIANCE.NS"                            |
| action         | String(20)   | "BUY", "SELL", "SHORT", "COVER"               |
| trade_type     | String(20)   | "INTRADAY" or "SWING"                         |
| position_type  | String(10)   | "LONG" or "SHORT"                             |
| quantity       | Integer      | Number of shares                              |
| entry_price    | Float        | Price at which trade was entered               |
| exit_price     | Float        | Price at which trade was closed (nullable)     |
| stop_loss      | Float        | AI-defined stop loss price                    |
| target_price   | Float        | AI-defined take profit price                  |
| brokerage      | Float        | Brokerage cost for this trade                 |
| slippage       | Float        | Slippage cost for this trade                  |
| pnl            | Float        | Realized profit/loss (nullable until closed)  |
| status         | String(20)   | "OPEN", "CLOSED", "SL_HIT", "TARGET_HIT", "SQUARED_OFF" |
| confidence     | Integer      | AI confidence score (0-100)                   |
| entry_time     | DateTime     | When trade was opened                         |
| exit_time      | DateTime     | When trade was closed (nullable)              |
| created_at     | DateTime     | Record creation timestamp                     |

---

### Table 3: `positions`

Currently open positions across all agents. This is a live view.

| Column          | Type         | Description                              |
|-----------------|--------------|------------------------------------------|
| id              | Integer (PK) | Auto-increment                           |
| agent_id        | Integer (FK) | References `agents.id`                   |
| trade_id        | Integer (FK) | References `trades.id`                   |
| symbol          | String(30)   | e.g. "INFY.NS"                          |
| position_type   | String(10)   | "LONG" or "SHORT"                        |
| quantity        | Integer      | Number of shares                         |
| entry_price     | Float        | Entry price                              |
| current_price   | Float        | Latest market price                      |
| stop_loss       | Float        | Stop loss level                          |
| target_price    | Float        | Take profit level                        |
| unrealized_pnl  | Float        | Current floating PnL                     |
| opened_at       | DateTime     | When position was opened                 |

---

### Table 4: `daily_performance`

End-of-day snapshot for each agent. Used for equity curves and analytics.

| Column              | Type         | Description                              |
|---------------------|--------------|------------------------------------------|
| id                  | Integer (PK) | Auto-increment                           |
| agent_id            | Integer (FK) | References `agents.id`                   |
| date                | Date         | Trading date                             |
| starting_capital    | Float        | Capital at market open                   |
| ending_capital      | Float        | Capital at market close                  |
| realized_pnl        | Float        | PnL from closed trades today             |
| unrealized_pnl      | Float        | PnL from open positions at EOD           |
| total_trades        | Integer      | Number of trades executed today           |
| winning_trades      | Integer      | Trades closed in profit                  |
| losing_trades       | Integer      | Trades closed in loss                    |
| max_drawdown        | Float        | Worst peak-to-trough today               |
| win_rate            | Float        | winning / total (percentage)             |

---

### Table 5: `market_snapshots`

Periodic market state captures. Useful for debugging and replay.

| Column         | Type         | Description                               |
|----------------|--------------|-------------------------------------------|
| id             | Integer (PK) | Auto-increment                            |
| symbol         | String(30)   | e.g. "RELIANCE.NS" or "^NSEI"            |
| open           | Float        | Open price                                |
| high           | Float        | High price                                |
| low            | Float        | Low price                                 |
| close          | Float        | Close / LTP                               |
| volume         | BigInteger   | Volume traded                             |
| rsi            | Float        | RSI at this snapshot                      |
| macd_signal    | String(10)   | "bullish" or "bearish"                    |
| ema_20         | Float        | 20-period EMA                             |
| ema_50         | Float        | 50-period EMA                             |
| vwap           | Float        | VWAP value                                |
| atr            | Float        | ATR value                                 |
| captured_at    | DateTime     | When this snapshot was taken               |

---

### Table 6: `news_cache`

Cached news articles to avoid re-fetching and for AI context.

| Column       | Type          | Description                              |
|--------------|---------------|------------------------------------------|
| id           | Integer (PK)  | Auto-increment                           |
| symbol       | String(30)    | Related stock symbol (nullable for macro) |
| headline     | String(500)   | News headline                            |
| source       | String(100)   | "google_rss", "newsapi", "moneycontrol"  |
| url          | String(500)   | Link to original article                 |
| sentiment    | String(20)    | "positive", "negative", "neutral"        |
| published_at | DateTime      | When the article was published           |
| fetched_at   | DateTime      | When we fetched it                       |

---

### Table 7: `ai_responses`

Raw AI responses for every decision cycle. Critical for debugging and AI personality analysis.

| Column          | Type          | Description                              |
|-----------------|---------------|------------------------------------------|
| id              | Integer (PK)  | Auto-increment                           |
| agent_id        | Integer (FK)  | References `agents.id`                   |
| cycle_id        | String(50)    | Unique ID for this scan cycle            |
| symbol          | String(30)    | Stock being evaluated                    |
| input_payload   | Text (JSON)   | Exact JSON sent to the AI                |
| raw_response    | Text          | Raw text response from the AI            |
| parsed_decision | Text (JSON)   | Parsed structured decision               |
| decision        | String(20)    | "BUY", "SELL", "HOLD", "EXIT"            |
| confidence      | Integer       | AI confidence score                      |
| latency_ms      | Integer       | Response time in milliseconds            |
| is_valid        | Boolean       | Did the response parse correctly?        |
| error_message   | String(500)   | Error details if parsing failed          |
| created_at      | DateTime      | Timestamp                                |

---

## 1.5 Database Connection & ORM Implementation

### Step 1: Create `database/connection.py`

```python
# Sets up SQLAlchemy engine and session factory.
# Uses SQLite for development, can be swapped to PostgreSQL via DATABASE_URL.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    """Dependency injection for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Step 2: Create `database/models.py`

Implement all 7 tables as SQLAlchemy ORM models using the schema definitions above. Each model class maps to one table. Define proper relationships:
- `Agent` → has many `Trade` objects
- `Trade` → has one `Position` (if open)
- `Agent` → has many `DailyPerformance` records
- `Agent` → has many `AIResponse` records

### Step 3: Create `database/seed.py`

Seed script that:
1. Creates all tables if they don't exist (`Base.metadata.create_all(engine)`).
2. Inserts the 4 agent records:
   - ChatGPT (openai, gpt-4o)
   - Gemini (google, gemini-1.5-pro)
   - Claude (anthropic, claude-3.5-sonnet)
   - Grok (xai, grok-2)
3. Each agent gets `INITIAL_CAPITAL` (₹1,00,000) as starting cash balance.

---

## 1.6 FastAPI Server Setup

### `main.py` — The Entry Point

```python
# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.connection import engine
from database.models import Base

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TradeOS API",
    description="Autonomous AI Trading Evaluation Platform",
    version="1.0.0"
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/api/health")
def health_check():
    return {"status": "alive", "platform": "TradeOS"}

# Include routers (added in later phases)
# app.include_router(dashboard_router, prefix="/api")
# app.include_router(agents_router, prefix="/api")
# app.include_router(trades_router, prefix="/api")
# app.include_router(market_router, prefix="/api")
```

Run with:

```bash
uvicorn main:app --reload --port 8000
```

---

## 1.7 Utility Modules

### `utils/constants.py`

```python
# Watchlist — Liquid NSE stocks for initial simulation
WATCHLIST = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "LT.NS",
    "AXISBANK.NS",
    "ITC.NS",
    "BHARTIARTL.NS",
    "BEL.NS",
    "TATAMOTORS.NS",
]

# Indian market indices
NIFTY_50 = "^NSEI"
SENSEX = "^BSESN"
INDIA_VIX = "^INDIAVIX"

# Market hours (IST)
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"

# AI Agent names
AGENT_NAMES = ["ChatGPT", "Gemini", "Claude", "Grok"]
```

### `utils/logger.py`

```python
# Centralized logging with file + console output
# Logs every trade decision, API call, and error
# Format: [2026-05-16 10:30:00] [INFO] [scanner] Opportunity found: RELIANCE.NS

import logging
import os
from datetime import datetime

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # File handler — one log file per day
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(os.path.join(log_dir, f"tradeos_{today}.log"))
    file_handler.setLevel(logging.DEBUG)

    # Format
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
```

### `utils/helpers.py`

```python
# Helper functions:
# - get_ist_now()        → returns current datetime in IST timezone
# - is_market_open()     → checks if current time is within 9:15 AM - 3:30 PM IST
# - generate_cycle_id()  → creates unique ID for each scan cycle (e.g., "CYC-20260516-103000")
# - format_currency(amt) → formats ₹1,00,000 style
# - parse_ist_time(t)    → parses "HH:MM" string to IST-aware time object

import pytz
from datetime import datetime
import uuid

IST = pytz.timezone("Asia/Kolkata")

def get_ist_now():
    return datetime.now(IST)

def is_market_open():
    now = get_ist_now()
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close and now.weekday() < 5

def generate_cycle_id():
    now = get_ist_now()
    return f"CYC-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

def format_currency(amount):
    return f"₹{amount:,.2f}"
```

---

## 1.8 `.gitignore`

Create a `.gitignore` at the project root:

```
# Environment
.env
venv/
__pycache__/

# Database
*.db

# Logs
logs/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Node (for frontend)
node_modules/
dist/
```

---

## 1.9 Phase 1 Completion Checklist

| #  | Task                                         | Status |
|----|----------------------------------------------|--------|
| 1  | Create full directory structure               | ☐      |
| 2  | Initialize Python virtual environment         | ☐      |
| 3  | Install all packages from requirements.txt    | ☐      |
| 4  | Create `.env` and `.env.example`              | ☐      |
| 5  | Create `config.py` with all settings          | ☐      |
| 6  | Define all 7 database tables in `models.py`   | ☐      |
| 7  | Create `connection.py` (engine + session)     | ☐      |
| 8  | Create `seed.py` (insert agents + watchlist)  | ☐      |
| 9  | Set up `main.py` with FastAPI + CORS          | ☐      |
| 10 | Create `constants.py`, `logger.py`, `helpers.py` | ☐  |
| 11 | Create `.gitignore`                           | ☐      |
| 12 | Run `uvicorn main:app` and verify `/api/health` | ☐   |
| 13 | Run seed script and verify DB has 4 agents    | ☐      |

---

> **Phase 1 is COMPLETE when:** The FastAPI server starts, the database is created with all 7 tables, 4 AI agents are seeded with ₹1,00,000 each, and the `/api/health` endpoint returns a valid response.

> **Next →** [Phase 2: Market Data & News Aggregation Engine](./phase2.md)
