# Watchlist — Liquid NSE stocks for initial simulation
WATCHLIST = [
    "^NSEI",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "SBIN.NS",
    "INFY.NS",
    "TCS.NS",
    "HCLTECH.NS",
    "WIPRO.NS",
    "CIPLA.NS",
    "VEDL.NS",
    "DIVISLAB.NS",
    "VBL.NS",
]


# Survival Arena watchlist — liquid NSE equities only (no index/F&O, options/leverage disabled for Arena agents)
ARENA_WATCHLIST = [s for s in WATCHLIST if not s.startswith("^")]


# Indian market indices
NIFTY_50 = "^NSEI"
SENSEX = "^BSESN"
INDIA_VIX = "^INDIAVIX"

# Market hours (IST)
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"

# AI Agent names
AGENT_NAMES = ["Gemini", "Groq-Llama", "Local-Ollama"]

# US watchlist and per-market watchlist map — kept in market_data/market_config.py to avoid
# a circular import (market_config imports WATCHLIST from here). Re-exported here too for
# convenience: `from utils.constants import WATCHLISTS`.
from market_data.market_config import WATCHLISTS, US_WATCHLIST  # noqa: E402,F401
