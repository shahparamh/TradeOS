from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.connection import engine
from database.models import Base

# Create all tables on startup (simple approach for now)
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

from api.routes_market import router as market_router
from api.routes_scanner import router as scanner_router
from api.routes_agents import router as agents_router

# Include routers
app.include_router(market_router, prefix="/api")
app.include_router(scanner_router, prefix="/api")
app.include_router(agents_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
