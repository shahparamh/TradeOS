from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from database.connection import engine, SessionLocal
from database.models import Base, Agent
import asyncio
from contextlib import asynccontextmanager
from config import settings

# Routers
from api.routes_market import router as market_router
from api.routes_scanner import router as scanner_router
from api.routes_agents import router as agents_router
from api.routes_broker import router as broker_router
from api.routes_auth import router as auth_router
from api.routes_settings import router as settings_router
from scheduler.trading_loop import TradingScheduler

# Initialize scheduler
trading_scheduler = TradingScheduler()

# Create all tables on startup
Base.metadata.create_all(bind=engine)

def seed_db():
    db = SessionLocal()
    
    # 1. Seed default agents
    existing_names = {a.name for a in db.query(Agent).all()}
    default_agents = [
        Agent(name="Gemini", model_name=settings.GEMINI_MODEL, provider="google", cash_balance=100000.0, total_pnl=0.0),
        Agent(name="Groq-Llama", model_name="llama-3.3-70b", provider="groq", cash_balance=100000.0, total_pnl=0.0),
        Agent(name="Qwen-Free", model_name="qwen-2.5-72b", provider="openrouter", cash_balance=100000.0, total_pnl=0.0),
        Agent(name="DeepSeek-R1", model_name="deepseek-reasoning", provider="deepseek", cash_balance=100000.0, total_pnl=0.0),
        Agent(name="Local-Ollama", model_name="llama3.2", provider="ollama", cash_balance=100000.0, total_pnl=0.0)
    ]
    for agent in default_agents:
        if agent.name not in existing_names:
            db.add(agent)

    # 2. Seed default admin user
    from database.models import User
    from api.routes_auth import hash_password
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        db.add(User(
            username="admin",
            email="admin@tradeos.ai",
            hashed_password=hash_password("admin1234"),
            role="admin",
            is_active=True
        ))
    else:
        admin_user.hashed_password = hash_password("admin1234")

    # 3. Seed default trading rules
    from database.models import SystemRule
    rules_to_seed = [
        ("enable_loss_lockout", "boolean", True, None, "Toggle single-stock daily loss lockout"),
        ("enable_short_selling", "boolean", False, None, "Allow intraday short positions"),
        ("min_profit_threshold_pct", "float", None, 0.015, "Minimum take profit percentage threshold (e.g., 0.015 for 1.5%)"),
        ("enable_news_sentiment", "boolean", True, None, "Enable parsing of live RSS news sentiment inside trading loop")
    ]
    for key, val_type, b_val, n_val, desc in rules_to_seed:
        existing = db.query(SystemRule).filter(SystemRule.key == key).first()
        if not existing:
            db.add(SystemRule(key=key, value_type=val_type, bool_value=b_val, numeric_value=n_val, description=desc))
            
    db.commit()
    db.close()


seed_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the scheduler
    trading_scheduler.start()
    yield
    # Shutdown: Stop the scheduler
    trading_scheduler.scheduler.shutdown()

app = FastAPI(
    title="TradeOS API",
    description="Autonomous AI Trading Evaluation Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/api/health")
def health_check():
    return {"status": "alive", "platform": "TradeOS"}

# Scheduler Controls
@app.get("/api/scheduler/status")
def get_scheduler_status():
    jobs = trading_scheduler.scheduler.get_jobs()
    return {
        "is_running": trading_scheduler.scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time),
                "trigger": str(job.trigger)
            } for job in jobs
        ]
    }

@app.post("/api/scheduler/trigger")
async def trigger_cycle_manually():
    # Trigger in background so request doesn't timeout
    asyncio.create_task(trading_scheduler.run_trading_cycle())
    return {"status": "triggered", "message": "Trading cycle started in background"}

@app.post("/api/scheduler/monitor")
async def trigger_monitor_manually():
    await trading_scheduler.run_monitor_cycle()
    return {"status": "completed", "message": "Position monitor check completed"}

@app.post("/api/scheduler/pre-market")
async def trigger_pre_market_manually():
    asyncio.create_task(trading_scheduler.run_pre_market_session())
    return {"status": "triggered", "message": "Pre-market strategy planning started in background"}

@app.get("/api/scheduler/pre-market/today")
def get_today_pre_market_strategy():
    from database.connection import SessionLocal
    from database.models import AgentDailyStrategy
    from datetime import date
    
    db = SessionLocal()
    try:
        today = date.today()
        # Query strategies for today
        strategies = db.query(AgentDailyStrategy).filter(AgentDailyStrategy.date == today).all()
        
        result = []
        for s in strategies:
            agent_name = s.agent.name if s.agent else f"Agent #{s.agent_id}"
            result.append({
                "id": s.id,
                "agent_id": s.agent_id,
                "agent_name": agent_name,
                "date": str(s.date),
                "symbol": s.symbol,
                "daily_bias": s.daily_bias,
                "entry_lower_limit": s.entry_lower_limit,
                "entry_upper_limit": s.entry_upper_limit,
                "target_price": s.target_price,
                "stop_loss": s.stop_loss,
                "reasoning": s.reasoning,
                "created_at": str(s.created_at)
            })
        return result
    finally:
        db.close()

# Include routers
app.include_router(market_router, prefix="/api")
app.include_router(scanner_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(broker_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(settings_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)


# --- REAL-TIME WEBSOCKET STATE BROADCASTER (Matching React Endpoint /api/ws/market) ---
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import asyncio
import random
from utils.constants import WATCHLIST
from data.market_fetcher import fetch_live_price

class WebSocketConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

ws_manager = WebSocketConnectionManager()

@app.websocket("/api/ws/market")
async def websocket_market_endpoint(websocket: WebSocket):
    """Establishes secure production real-time tick stream connection at /api/ws/market."""
    await ws_manager.connect(websocket)
    try:
        while True:
            symbol = random.choice(WATCHLIST)
            try:
                price_data = fetch_live_price(symbol)
                base_price = price_data.get("price", 100.0)
                
                # Realistic micro-fluctuations (0.01% - 0.05%)
                fluctuation = random.uniform(-0.0005, 0.0005)
                live_price = base_price * (1 + fluctuation)
                
                tick_data = {
                    "type": "MARKET_TICK",
                    "data": {
                        "symbol": symbol,
                        "price": round(live_price, 2),
                        "change_pct": round(fluctuation * 100, 2),
                        "change": round(live_price - base_price, 2),
                        "volume": random.randint(1000, 50000),
                        "time": str(datetime.utcnow())
                    }
                }
                await websocket.send_json(tick_data)
            except Exception:
                pass
            # 0.5s ticks
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
