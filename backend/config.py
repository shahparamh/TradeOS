import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # LLM Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEYS: list = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()] or [os.getenv("GEMINI_API_KEY", "")]
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")



    # News
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    NEWS_API_KEYS: list = [k.strip() for k in os.getenv("NEWS_API_KEYS", "").split(",") if k.strip()] or [os.getenv("NEWS_API_KEY", "")]

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./tradeos.db")

    # Trading
    INITIAL_CAPITAL: float = float(os.getenv("INITIAL_CAPITAL", 5000000.0))
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

    # Agent Models
    GROK_MODEL: str = "grok-4.20-reasoning"  # Updated based on user input
    GROQ_API_KEYS: list = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()] or [os.getenv("GROQ_API_KEY", "")]
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"  # Free tier on Groq
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")

settings = Settings()
