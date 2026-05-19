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
            hashed_password=hash_password("adminpassword"),
            role="admin",
            is_active=True
        ))

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

import base64
import struct
import json
from fastapi import WebSocket, WebSocketDisconnect
from utils.constants import WATCHLIST

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

def decode_yahoo_protobuf(base64_str: str) -> dict:
    try:
        data = base64.b64decode(base64_str)
        i = 0
        limit = len(data)
        result = {}
        
        while i < limit:
            key = data[i]
            tag = key >> 3
            wire_type = key & 0x07
            i += 1
            
            if wire_type == 0:  # Varint
                val = 0
                shift = 0
                while True:
                    b = data[i]
                    val |= (b & 0x7F) << shift
                    i += 1
                    if not (b & 0x80):
                        break
                    shift += 7
                if tag == 3:  # Time
                    result["time"] = val
                elif tag == 9:  # Volume
                    result["volume"] = val
            elif wire_type == 1:  # 64-bit
                i += 8
            elif wire_type == 2:  # Length-delimited
                length = 0
                shift = 0
                while True:
                    b = data[i]
                    length |= (b & 0x7F) << shift
                    i += 1
                    if not (b & 0x80):
                        break
                    shift += 7
                val_bytes = data[i:i+length]
                i += length
                if tag == 1:  # Ticker
                    result["symbol"] = val_bytes.decode('utf-8', errors='ignore')
                elif tag == 4:  # Currency
                    result["currency"] = val_bytes.decode('utf-8', errors='ignore')
                elif tag == 5:  # Exchange
                    result["exchange"] = val_bytes.decode('utf-8', errors='ignore')
            elif wire_type == 5:  # 32-bit float
                val = struct.unpack('<f', data[i:i+4])[0]
                i += 4
                if tag == 2:  # Price
                    result["price"] = val
                elif tag == 8:  # Change Percent
                    result["change_pct"] = val
                elif tag == 12:  # Change
                    result["change"] = val
            else:
                break
        return result
    except Exception:
        return {}

async def start_yahoo_websocket_stream():
    """
    Connects to Yahoo Finance WebSocket Streamer and broadcasts decoded ticks in real-time.
    """
    import websockets
    subscription_payload = {
        "subscribe": list(WATCHLIST)
    }
    
    while True:
        try:
            print("[WebSocket Streamer] Connecting to wss://streamer.finance.yahoo.com...")
            async with websockets.connect("wss://streamer.finance.yahoo.com") as ws:
                await ws.send(json.dumps(subscription_payload))
                print("[WebSocket Streamer] Subscribed to watchlist stocks successfully!")
                
                async for message in ws:
                    decoded = decode_yahoo_protobuf(message)
                    if decoded and "symbol" in decoded:
                        await manager.broadcast({
                            "type": "MARKET_TICK",
                            "data": {
                                "symbol": decoded["symbol"],
                                "price": decoded.get("price"),
                                "change_pct": decoded.get("change_pct"),
                                "change": decoded.get("change"),
                                "volume": decoded.get("volume"),
                                "time": decoded.get("time")
                            }
                        })
        except asyncio.CancelledError:
            print("[WebSocket Streamer] Background task cancelled.")
            break
        except Exception as e:
            print(f"[WebSocket Streamer] Connection error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the scheduler
    trading_scheduler.start()
    
    # Startup: Start the continuous live Yahoo Finance WebSocket streamer
    stream_task = asyncio.create_task(start_yahoo_websocket_stream())
    
    yield
    
    # Shutdown: Stop the scheduler and cancel stream
    trading_scheduler.scheduler.shutdown()
    stream_task.cancel()

app = FastAPI(
    title="TradeOS API",
    description="Autonomous AI Trading Evaluation Platform",
    version="1.0.0",
    lifespan=lifespan
)

@app.websocket("/api/ws/market")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "status": "alive",
        "platform": "TradeOS",
        "message": "TradeOS API is running successfully.",
        "documentation": "/docs",
        "health_check": "/api/health"
    }

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
