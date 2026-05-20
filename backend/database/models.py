from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from .connection import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True)
    provider = Column(String(50))
    model_name = Column(String(100))
    cash_balance = Column(Float)
    total_pnl = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    trades = relationship("Trade", back_populates="agent")
    positions = relationship("Position", back_populates="agent")
    daily_performance = relationship("DailyPerformance", back_populates="agent")
    ai_responses = relationship("AIResponse", back_populates="agent")

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    symbol = Column(String(30))
    action = Column(String(20))
    trade_type = Column(String(20))
    position_type = Column(String(10))
    quantity = Column(Integer)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float)
    target_price = Column(Float)
    brokerage = Column(Float, default=0.0)
    slippage = Column(Float, default=0.0)
    pnl = Column(Float, nullable=True)
    status = Column(String(20)) # OPEN, CLOSED, SL_HIT, TARGET_HIT, SQUARED_OFF
    confidence = Column(Integer)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="trades")
    position = relationship("Position", back_populates="trade", uselist=False)

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    trade_id = Column(Integer, ForeignKey("trades.id"))
    symbol = Column(String(30))
    trade_type = Column(String(20))
    position_type = Column(String(10))
    quantity = Column(Integer)
    entry_price = Column(Float)
    current_price = Column(Float)
    stop_loss = Column(Float)
    target_price = Column(Float)
    unrealized_pnl = Column(Float, default=0.0)
    opened_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="positions")
    trade = relationship("Trade", back_populates="position")

class DailyPerformance(Base):
    __tablename__ = "daily_performance"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    date = Column(Date, default=datetime.utcnow().date())
    starting_capital = Column(Float)
    ending_capital = Column(Float)
    realized_pnl = Column(Float)
    unrealized_pnl = Column(Float)
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    max_drawdown = Column(Float)
    win_rate = Column(Float)

    agent = relationship("Agent", back_populates="daily_performance")

class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(30))
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)
    rsi = Column(Float, nullable=True)
    macd_signal = Column(String(10), nullable=True)
    ema_20 = Column(Float, nullable=True)
    ema_50 = Column(Float, nullable=True)
    vwap = Column(Float, nullable=True)
    atr = Column(Float, nullable=True)
    captured_at = Column(DateTime, default=datetime.utcnow)

class NewsCache(Base):
    __tablename__ = "news_cache"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(30), nullable=True)
    headline = Column(String(500))
    source = Column(String(100))
    url = Column(String(500), unique=True)
    sentiment = Column(String(20))
    published_at = Column(DateTime)
    fetched_at = Column(DateTime, default=datetime.utcnow)

class AIResponse(Base):
    __tablename__ = "ai_responses"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    cycle_id = Column(String(50))
    symbol = Column(String(30))
    input_payload = Column(Text)
    raw_response = Column(Text)
    parsed_decision = Column(Text)
    decision = Column(String(20))
    confidence = Column(Integer)
    latency_ms = Column(Integer)
    is_valid = Column(Boolean)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="ai_responses")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    role = Column(String(20), default="trader") # 'admin', 'trader'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AgentDailyStrategy(Base):
    __tablename__ = "agent_daily_strategies"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    date = Column(Date, default=datetime.utcnow().date())
    symbol = Column(String(30))
    daily_bias = Column(String(20)) # BULLISH, BEARISH, NEUTRAL
    entry_lower_limit = Column(Float)
    entry_upper_limit = Column(Float)
    target_price = Column(Float)
    stop_loss = Column(Float)
    reasoning = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent")

class SystemRule(Base):
    __tablename__ = "system_rules"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, index=True, nullable=False) # e.g. 'enable_loss_lockout'
    value_type = Column(String(10), default="boolean") # 'boolean', 'float', 'int'
    bool_value = Column(Boolean, nullable=True)
    numeric_value = Column(Float, nullable=True)
    description = Column(String(250))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class APIUsageLog(Base):
    """Tracks per-key API usage for all external providers."""
    __tablename__ = "api_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)   # e.g. "gemini", "groq", "newsapi"
    key_hash = Column(String(32), nullable=False)               # First 16 chars of SHA-256 hash
    requests_today = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0, nullable=True)
    last_reset = Column(DateTime, default=datetime.utcnow)
    is_exhausted = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

