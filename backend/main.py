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
from scheduler.trading_loop import TradingScheduler

# Initialize scheduler
trading_scheduler = TradingScheduler()

# Create all tables on startup
Base.metadata.create_all(bind=engine)

def seed_db():
    db = SessionLocal()
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

# Include routers
app.include_router(market_router, prefix="/api")
app.include_router(scanner_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(broker_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
