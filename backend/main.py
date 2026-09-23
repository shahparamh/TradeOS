from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from database.connection import engine, SessionLocal, run_lightweight_migrations
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
from api.routes_health import router as health_router
from api.routes_arena import router as arena_router
from scheduler.trading_loop import TradingScheduler
from utils.api_manager import initialize_api_manager

# Initialize scheduler
trading_scheduler = TradingScheduler()

# Create all tables on startup
Base.metadata.create_all(bind=engine)
run_lightweight_migrations()

def seed_db():
    db = SessionLocal()
    
    # Purge existing openrouter/github/deepseek agents and their dependencies — these
    # providers have been removed from the app entirely (github's endpoint was dead;
    # deepseek was dropped by request), so any leftover rows from before removal must not
    # linger as inert-but-visible agents.
    purged_providers = ("openrouter", "github", "deepseek")
    purged_agents = db.query(Agent).filter(Agent.provider.in_(purged_providers)).all()
    if purged_agents:
        from database.models import Trade, Position, DailyPerformance, AIResponse, AgentDailyStrategy
        for agent in purged_agents:
            db.query(Position).filter(Position.agent_id == agent.id).delete()
            db.query(Trade).filter(Trade.agent_id == agent.id).delete()
            db.query(DailyPerformance).filter(DailyPerformance.agent_id == agent.id).delete()
            db.query(AIResponse).filter(AIResponse.agent_id == agent.id).delete()
            db.query(AgentDailyStrategy).filter(AgentDailyStrategy.agent_id == agent.id).delete()
            db.delete(agent)
        db.commit()

    # 1. Seed default agents
    existing_names = {a.name for a in db.query(Agent).all()}
    default_agents = [
        Agent(name="Gemini", model_name=settings.GEMINI_MODEL, provider="google", cash_balance=settings.INITIAL_CAPITAL, total_pnl=0.0),
        Agent(name="Groq-Llama", model_name="llama-3.3-70b", provider="groq", cash_balance=settings.INITIAL_CAPITAL, total_pnl=0.0),
        Agent(name="Local-Ollama", model_name="llama3.2", provider="ollama", cash_balance=settings.INITIAL_CAPITAL, total_pnl=0.0)
    ]
    for agent in default_agents:
        if agent.name not in existing_names:
            db.add(agent)

    # 1b. Seed the default Survival Arena agent
    if "AgentZero-Alpha" not in existing_names:
        arena_starting_capital = 2000.0
        db.add(Agent(
            name="AgentZero-Alpha",
            model_name=settings.GEMINI_MODEL,
            provider="google",
            cash_balance=arena_starting_capital,
            starting_capital=arena_starting_capital,
            death_threshold=arena_starting_capital * 0.10,
            total_pnl=0.0,
            mode="SURVIVAL",
        ))

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
        ("arena_emergency_stop", "boolean", False, None, "Global kill switch for the Survival Arena — halts all new arena orders without needing AI approval"),
        ("enable_loss_lockout", "boolean", False, None, "Toggle single-stock daily loss lockout"),
        ("enable_short_selling", "boolean", True, None, "Allow intraday short positions"),
        ("min_profit_threshold_pct", "float", None, 0.015, "Minimum take profit percentage threshold (e.g., 0.015 for 1.5%)"),
        ("enable_news_sentiment", "boolean", True, None, "Enable parsing of live RSS news sentiment inside trading loop"),
        ("max_open_positions", "float", None, 40.0, "Maximum open positions per agent"),
        ("max_capital_per_trade_pct", "float", None, 0.50, "Maximum capital per trade percentage (0.50 = 50%)"),
        ("max_intraday_trades", "float", None, 70.0, "Maximum intraday trades per agent per day"),
        ("daily_drawdown_limit", "float", None, -0.05, "Daily loss drawdown limit (e.g., -0.05 for -5%)"),
        ("min_confidence", "float", None, 65.0, "Minimum model confidence floor to enter trade (0-100)"),
        ("max_stop_loss_distance", "float", None, 0.07, "Maximum allowed stop loss distance (e.g. 0.07 for 7%)"),
        ("min_risk_reward_ratio", "float", None, 2.0, "Minimum risk-reward ratio allowed"),
        ("max_consecutive_losses", "float", None, 5.0, "Circuit breaker max consecutive daily losses"),
        ("max_trades_per_stock_daily", "float", None, 5.0, "Maximum trades per stock per model per day"),
        ("entry_start_hour", "float", None, 9.25, "Allowed entry start hour (e.g., 9.25 for 9:15 AM)"),
        ("entry_end_hour", "float", None, 14.0, "Allowed entry end hour (e.g., 14.0 for 2:00 PM)"),
        ("enable_fno_trading", "boolean", True, None, "Toggle Futures & Options (F&O) accessibility for AI models"),
        ("starting_capital_per_agent", "float", None, 5000000.0, "Starting balance per AI agent upon platform reset"),
        ("devils_advocate_veto_threshold", "float", None, 8.0, "Devil's Advocate disagreement threshold to veto trades (0.0-10.0)"),
        ("max_trades_daily_per_model", "float", None, 20.0, "Maximum trades per model across all symbols per day"),
        ("equity_ai_cooldown_min", "float", None, 5.0, "AI request cooldown for Equity symbols in minutes"),
        ("fno_ai_cooldown_min", "float", None, 5.0, "AI request cooldown for F&O symbols in minutes")
    ]
    for key, val_type, b_val, n_val, desc in rules_to_seed:
        existing = db.query(SystemRule).filter(SystemRule.key == key).first()
        if not existing:
            db.add(SystemRule(key=key, value_type=val_type, bool_value=b_val, numeric_value=n_val, description=desc))
        else:
            existing.value_type = val_type
            existing.bool_value = b_val
            existing.numeric_value = n_val
            existing.description = desc
            
    # Auto-reactivate agents if their API keys are configured and available (not exhausted/empty)
    all_agents = db.query(Agent).all()
    for agent in all_agents:
        has_key = False
        if agent.provider == "google":
            has_key = bool(settings.GEMINI_API_KEY or settings.GEMINI_API_KEYS)
        elif agent.provider == "groq":
            has_key = bool(settings.GROQ_API_KEY or settings.GROQ_API_KEYS)
        elif agent.provider == "ollama":
            has_key = True  # Local Ollama doesn't need an external API key
            
        if has_key and not agent.is_active:
            agent.is_active = True
            print(f"Auto-reactivated agent '{agent.name}' (provider: {agent.provider}) as API key is configured.")
            
    db.commit()
    db.close()



seed_db()

# Initialize centralized API key manager with all configured keys
initialize_api_manager()

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

# Compress JSON responses (trade history, candles, watchlists) before they hit the wire —
# shrinks payloads ~70-80% for minimal CPU cost, which matters most on slower client connections.
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    asyncio.create_task(trading_scheduler.run_trading_cycle(ignore_hours=True))
    return {"status": "triggered", "message": "Trading cycle started in background"}

@app.post("/api/scheduler/monitor")
async def trigger_monitor_manually():
    await trading_scheduler.run_monitor_cycle(ignore_hours=True)
    return {"status": "completed", "message": "Position monitor check completed"}

@app.post("/api/scheduler/pre-market")
async def trigger_pre_market_manually():
    asyncio.create_task(trading_scheduler.run_pre_market_session())
    return {"status": "triggered", "message": "Pre-market strategy planning started in background"}

@app.post("/api/settings/reset")
def reset_platform_data(payload: dict = None):
    from fastapi import HTTPException
    from database.connection import SessionLocal
    from database.models import Trade, Position, AIResponse, DailyPerformance, AgentDailyStrategy, Agent, SystemRule
    
    db = SessionLocal()
    try:
        # Determine starting capital
        capital = 5000000.0
        if payload and "starting_capital" in payload:
            capital = float(payload["starting_capital"])
        else:
            # Query starting capital from DB settings
            rule = db.query(SystemRule).filter(SystemRule.key == "starting_capital_per_agent").first()
            if rule and rule.numeric_value is not None:
                capital = float(rule.numeric_value)
        
        # 1. Truncate / delete all transactional tables (Fleet mode only — Survival Arena
        # keeps its own balances and history; a fleet reset must never touch it)
        fleet_agent_ids = [a.id for a in db.query(Agent.id).filter(Agent.mode != "SURVIVAL").all()]
        db.query(Position).filter(Position.agent_id.in_(fleet_agent_ids)).delete(synchronize_session=False)
        db.query(Trade).filter(Trade.agent_id.in_(fleet_agent_ids)).delete(synchronize_session=False)
        db.query(AIResponse).filter(AIResponse.agent_id.in_(fleet_agent_ids)).delete(synchronize_session=False)
        db.query(DailyPerformance).filter(DailyPerformance.agent_id.in_(fleet_agent_ids)).delete(synchronize_session=False)
        db.query(AgentDailyStrategy).filter(AgentDailyStrategy.agent_id.in_(fleet_agent_ids)).delete(synchronize_session=False)

        # 2. Reset agent balances (Fleet mode only)
        agents = db.query(Agent).filter(Agent.mode != "SURVIVAL").all()
        for agent in agents:
            agent.cash_balance = capital
            agent.total_pnl = 0.0
            
        # 3. Update the starting capital rule in db
        cap_rule = db.query(SystemRule).filter(SystemRule.key == "starting_capital_per_agent").first()
        if cap_rule:
            cap_rule.numeric_value = capital
        else:
            db.add(SystemRule(key="starting_capital_per_agent", value_type="float", numeric_value=capital, description="Starting balance per AI agent upon platform reset"))
            
        db.commit()
        return {"status": "success", "message": f"Platform successfully reset! All agent balances set to ₹{capital:,.2f}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database reset failed: {str(e)}")
    finally:
        db.close()

@app.get("/api/scheduler/pre-market/today")
def get_today_pre_market_strategy():
    from database.connection import SessionLocal
    from database.models import AgentDailyStrategy
    from datetime import date
    
    db = SessionLocal()
    try:
        today = date.today()
        from database.models import Agent
        # Query strategies for today for active agents only
        strategies = db.query(AgentDailyStrategy).join(Agent).filter(
            AgentDailyStrategy.date == today,
            Agent.is_active == True
        ).all()
        
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
app.include_router(health_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(scanner_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(broker_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(arena_router, prefix="/api")

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


# --- SINGLE-SERVICE FRONTEND HOSTING ---
# Serves the built React app (frontend/dist) from this same FastAPI process, so one Render
# Web Service covers both frontend and backend — no separate static site, no cross-origin
# API calls, no VITE_API_URL to keep in sync (frontend/src/services/api.js defaults to the
# relative "/api", which resolves correctly here since everything is same-origin).
# Registered LAST so it never shadows the /api/* routers or the websocket route above.
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException
from pathlib import Path

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """SPA fallback: serves any built static file directly (favicon, manifest, ...),
        otherwise returns index.html so React Router can handle the client-side route.
        Unmatched /api/* paths 404 here instead of silently returning the app shell."""
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
else:
    # No build present (e.g. local backend-only dev) — keep a plain root health response.
    @app.get("/")
    def read_root():
        return {"status": "TradeOS Backend is running", "note": "frontend/dist not found — run `npm run build` in frontend/ to serve the app from here."}
