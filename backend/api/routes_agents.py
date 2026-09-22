from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from database.connection import get_db
from database.models import Agent, Trade
from datetime import datetime

router = APIRouter(prefix="/agents", tags=["AI Agents"])


@router.get("/")
def get_all_agents(db: Session = Depends(get_db)):
    # Fleet mode only — Survival Arena agents have their own /api/arena/agents endpoint
    agents = db.query(Agent).options(joinedload(Agent.trades)).filter(Agent.mode != "SURVIVAL").all()
    result = []
    for agent in agents:
        all_trades = agent.trades or []
        closed = [t for t in all_trades if t.pnl is not None]
        wins = [t for t in closed if t.pnl > 0]
        result.append({
            "id": agent.id,
            "name": agent.name,
            "model_name": agent.model_name,
            "provider": agent.provider,
            "cash_balance": float(agent.cash_balance or 0),
            "total_pnl": float(agent.total_pnl or 0),
            "is_active": agent.is_active,
            "trades_count": len(all_trades),
            "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        })
    return result


@router.get("/{agent_id}")
def get_agent_detail(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.mode != "SURVIVAL").first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    all_trades = agent.trades or []
    closed = [t for t in all_trades if t.pnl is not None]
    wins = [t for t in closed if t.pnl > 0]
    from utils.helpers import get_ist_now
    today = get_ist_now().date()
    today_trades = [t for t in all_trades if t.entry_time and t.entry_time.date() == today]

    return {
        "id": agent.id,
        "name": agent.name,
        "model_name": agent.model_name,
        "provider": agent.provider,
        "cash_balance": float(agent.cash_balance or 0),
        "total_pnl": float(agent.total_pnl or 0),
        "is_active": agent.is_active,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "stats": {
            "total_trades": len(all_trades),
            "closed_trades": len(closed),
            "open_positions": len(agent.positions),
            "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
            "total_wins": len(wins),
            "total_losses": len(closed) - len(wins),
            "today_trades": len(today_trades),
            "avg_pnl": round(sum(t.pnl for t in closed) / len(closed), 2) if closed else 0,
            "best_trade": max((t.pnl for t in closed), default=0),
            "worst_trade": min((t.pnl for t in closed), default=0),
        }
    }


@router.get("/{agent_id}/trades")
def get_agent_trades(agent_id: int, db: Session = Depends(get_db)):
    trades = db.query(Trade).filter(Trade.agent_id == agent_id).order_by(Trade.entry_time.desc()).all()
    return [{
        "id": t.id,
        "symbol": t.symbol,
        "action": t.action,
        "position_type": t.position_type,
        "quantity": t.quantity,
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "pnl": t.pnl,
        "status": t.status,
        "confidence": t.confidence,
        "entry_time": t.entry_time.isoformat() if t.entry_time else None,
        "exit_time": t.exit_time.isoformat() if t.exit_time else None,
    } for t in trades]


@router.post("/{agent_id}/scan/{symbol}")
async def trigger_agent_scan(agent_id: int, symbol: str, db: Session = Depends(get_db)):
    """Manually trigger a scan for a specific agent on a symbol."""
    from agents.agent_executor import execute_all_agents
    from data.data_aggregator import aggregate_market_context
    from data.market_fetcher import fetch_intraday_candles
    from scanner.technical_engine import calculate_all_indicators, generate_indicator_summary

    market_context = await aggregate_market_context()
    candles_df = fetch_intraday_candles(symbol, "5m", "1d")
    if candles_df.empty:
        raise HTTPException(status_code=400, detail=f"No data for {symbol}")

    indicators = generate_indicator_summary(calculate_all_indicators(candles_df), symbol)
    opportunity = {"symbol": symbol, "signal_type": "MANUAL_TRIGGER", "indicators": indicators}

    decisions = await execute_all_agents(market_context, opportunity, [])
    return {"status": "success", "symbol": symbol, "decisions": decisions}


@router.post("/{agent_id}/toggle")
def toggle_agent_status(agent_id: int, db: Session = Depends(get_db)):
    """Manually toggle an agent's active status."""
    agent = db.query(Agent).get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.is_active = not agent.is_active
    db.commit()
    return {
        "status": "success",
        "is_active": agent.is_active,
        "message": f"Agent {agent.name} is now {'active' if agent.is_active else 'paused'}."
    }

