from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Trade, Position, Agent, DailyPerformance
from data.market_fetcher import fetch_live_price

router = APIRouter(prefix="/broker", tags=["Broker & Risk"])


@router.get("/trades", response_model=None)
def get_all_trades(db: Session = Depends(get_db)):
    trades = db.query(Trade).order_by(Trade.entry_time.desc()).all()
    result = []
    for t in trades:
        agent = db.query(Agent).get(t.agent_id)
        result.append({
            "id": t.id,
            "agent_id": t.agent_id,
            "agent_name": agent.name if agent else "Unknown",
            "symbol": t.symbol,
            "action": t.action,
            "trade_type": t.trade_type or "INTRADAY",
            "position_type": t.position_type,
            "quantity": t.quantity,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "stop_loss": t.stop_loss,
            "target_price": t.target_price,
            "pnl": t.pnl,
            "status": t.status,
            "confidence": t.confidence,
            "entry_time": t.entry_time.isoformat() if t.entry_time else None,
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            "brokerage": t.brokerage,
        })
    return result


@router.get("/positions", response_model=None)
def get_all_positions(db: Session = Depends(get_db)):
    positions = db.query(Position).all()
    result = []
    for pos in positions:
        agent = db.query(Agent).get(pos.agent_id)
        # Try to get live price to update unrealized PnL
        try:
            price_data = fetch_live_price(pos.symbol)
            current_price = price_data.get("price", pos.current_price)
        except Exception:
            current_price = pos.current_price

        unrealized = 0.0
        if pos.position_type == "LONG":
            unrealized = (current_price - pos.entry_price) * pos.quantity
        elif pos.position_type == "SHORT":
            unrealized = (pos.entry_price - current_price) * pos.quantity

        result.append({
            "id": pos.id,
            "agent_id": pos.agent_id,
            "agent_name": agent.name if agent else "Unknown",
            "trade_id": pos.trade_id,
            "symbol": pos.symbol,
            "trade_type": pos.trade_type or "INTRADAY",
            "position_type": pos.position_type,
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "current_price": round(current_price, 2),
            "stop_loss": pos.stop_loss,
            "target_price": pos.target_price,
            "unrealized_pnl": round(unrealized, 2),
            "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
        })
    return result


@router.get("/leaderboard")
def get_leaderboard(db: Session = Depends(get_db)):
    try:
        agents = db.query(Agent).all()
        leaderboard = []
        COLOR_MAP = {
            "gemini": "var(--color-gemini)",
            "groq": "var(--color-groq)",
            "gpt": "var(--color-chatgpt)",
            "claude": "var(--color-claude)",
            "grok": "var(--color-grok)",
            "qwen": "var(--accent-cyan)",
            "deepseek": "var(--accent-purple)",
            "local": "var(--green-profit)",
            "ollama": "var(--green-profit)",
        }


        for agent in agents:
            all_trades = agent.trades or []
            closed = [t for t in all_trades if t.pnl is not None]
            wins = [t for t in closed if t.pnl > 0]

            color_key = agent.name.lower().split('-')[0] if agent.name else "gemini"
            color = COLOR_MAP.get(color_key, "var(--accent-blue)")

            leaderboard.append({
                "id": agent.id,
                "name": agent.name or "Unknown",
                "model_name": agent.model_name or "N/A",
                "provider": agent.provider or "N/A",
                "cash_balance": float(agent.cash_balance or 0),
                "total_pnl": float(agent.total_pnl or 0),
                "win_rate": f"{(len(wins)/len(closed)*100):.0f}%" if closed else "0%",
                "trades_count": len(all_trades),
                "closed_count": len(closed),
                "color": color,
                "is_active": agent.is_active,
            })

        leaderboard.sort(key=lambda x: x["total_pnl"], reverse=True)
        return leaderboard
    except Exception as e:
        print(f"Leaderboard error: {e}")
        return []


@router.post("/positions/{position_id}/close")
def manual_close_position(position_id: int, db: Session = Depends(get_db)):
    from config import settings
    from broker.virtual_broker import VirtualBroker

    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    trade = db.query(Trade).get(position.trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade record not found")

    agent = db.query(Agent).get(position.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get live price for square-off
    try:
        price_data = fetch_live_price(position.symbol)
        current_price = price_data.get("price", position.current_price)
    except Exception:
        current_price = position.current_price

    broker = VirtualBroker(settings)

    try:
        if position.position_type == "LONG":
            result = broker.sell(agent, trade, current_price, "SQUARED_OFF", db)
        else:
            result = broker.cover(agent, trade, current_price, "SQUARED_OFF", db)

        db.commit()
        return {
            "status": "success",
            "symbol": position.symbol,
            "fill_price": result.get("fill_price"),
            "net_pnl": result.get("net_pnl"),
            "message": f"Position in {position.symbol} squared off at ₹{result.get('fill_price', current_price):.2f}"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}/status", response_model=None)
def get_agent_status(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "name": agent.name,
        "cash_balance": agent.cash_balance,
        "total_pnl": agent.total_pnl,
        "open_positions_count": len(agent.positions),
        "today_trades_count": len([
            t for t in agent.trades
            if t.entry_time and t.entry_time.date() == datetime.utcnow().date()
        ])
    }


@router.get("/performance/daily", response_model=None)
def get_daily_performance(db: Session = Depends(get_db)):
    return db.query(DailyPerformance).order_by(DailyPerformance.date.desc()).all()
