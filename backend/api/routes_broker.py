from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from database.connection import get_db
from database.models import Trade, Position, Agent, DailyPerformance
from data.market_fetcher import fetch_live_price
from utils.helpers import get_ist_now
from config import settings

router = APIRouter(prefix="/broker", tags=["Broker & Risk"])


@router.get("/trades", response_model=None)
def get_all_trades(db: Session = Depends(get_db)):
    trades = db.query(Trade).options(joinedload(Trade.agent)).order_by(Trade.entry_time.desc()).all()
    result = []

    def _is_bullish_position(position_type: str | None) -> bool:
        return (position_type or "").upper() in ["LONG", "BUY_CE", "SELL_PE"]

    def _estimate_exit_market_price(trade: Trade):
        if trade.exit_price is None:
            return None

        slip = float(settings.SLIPPAGE_PERCENT or 0)
        if slip <= 0:
            return round(float(trade.exit_price), 2)

        if _is_bullish_position(trade.position_type):
            # Bullish exits sell/close slightly below market due to slippage.
            estimated_market = float(trade.exit_price) / (1 - slip)
        else:
            # Bearish exits cover slightly above market due to slippage.
            estimated_market = float(trade.exit_price) / (1 + slip)

        return round(estimated_market, 2)

    for t in trades:
        result.append({
            "id": t.id,
            "agent_id": t.agent_id,
            "agent_name": t.agent.name if t.agent else "Unknown",
            "symbol": t.symbol,
            "action": t.action,
            "trade_type": t.trade_type or "INTRADAY",
            "position_type": t.position_type,
            "quantity": t.quantity,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "exit_market_price": _estimate_exit_market_price(t),
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
    positions = db.query(Position).options(joinedload(Position.agent)).all()
    position_trade_ids = {p.trade_id for p in positions if p.trade_id is not None}

    # Defensive fallback: if an OPEN trade lost its Position row unexpectedly,
    # surface it in live positions instead of hiding it from the UI.
    orphan_open_trades = db.query(Trade).options(joinedload(Trade.agent)).filter(
        Trade.status == "OPEN",
        Trade.exit_time.is_(None),
        ~Trade.id.in_(position_trade_ids) if position_trade_ids else True,
    ).all()

    result = []
    for pos in positions:
        # Load the last known price directly from the database to prevent Yahoo Finance timeout!
        current_price = pos.current_price

        unrealized = 0.0
        if pos.position_type == "LONG":
            unrealized = (current_price - pos.entry_price) * pos.quantity
        elif pos.position_type == "SHORT":
            unrealized = (pos.entry_price - current_price) * pos.quantity

        result.append({
            "id": pos.id,
            "agent_id": pos.agent_id,
            "agent_name": pos.agent.name if pos.agent else "Unknown",
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

    for trade in orphan_open_trades:
        current_price = trade.entry_price
        if trade.position_type in ["LONG", "BUY_CE", "SELL_PE"]:
            unrealized = (current_price - trade.entry_price) * trade.quantity
        else:
            unrealized = (trade.entry_price - current_price) * trade.quantity

        result.append({
            "id": f"orphan-{trade.id}",
            "agent_id": trade.agent_id,
            "agent_name": trade.agent.name if trade.agent else "Unknown",
            "trade_id": trade.id,
            "symbol": trade.symbol,
            "trade_type": trade.trade_type or "INTRADAY",
            "position_type": trade.position_type or ("LONG" if trade.action == "BUY" else "SHORT"),
            "quantity": trade.quantity,
            "entry_price": trade.entry_price,
            "current_price": round(current_price, 2),
            "stop_loss": trade.stop_loss,
            "target_price": trade.target_price,
            "unrealized_pnl": round(unrealized, 2),
            "opened_at": trade.entry_time.isoformat() if trade.entry_time else None,
        })

    return result


@router.get("/leaderboard")
def get_leaderboard(db: Session = Depends(get_db)):
    try:
        agents = db.query(Agent).options(joinedload(Agent.trades)).all()
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
            if t.entry_time and t.entry_time.date() == get_ist_now().date()
        ])
    }


@router.get("/performance/daily", response_model=None)
def get_daily_performance(db: Session = Depends(get_db)):
    return db.query(DailyPerformance).order_by(DailyPerformance.date.desc()).all()


from pydantic import BaseModel

class ManualTradeRequest(BaseModel):
    agent_id: int
    symbol: str
    action: str
    quantity: int
    trade_type: str
    position_type: str
    stop_loss: float
    target_price: float

@router.post("/trade/manual")
def place_manual_trade(req: ManualTradeRequest, db: Session = Depends(get_db)):
    from config import settings
    from broker.virtual_broker import VirtualBroker

    agent = db.query(Agent).get(req.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    symbol = req.symbol.upper().strip()
    if not symbol.endswith(".NS") and symbol not in ["^NSEI", "^NSEBANK", "NIFTY", "BANKNIFTY", "FINNIFTY"]:
        # Auto-append .NS for Indian equities if it's not indices or derivative contracts
        if not any(char in symbol for char in ["-", "^"]):
            symbol = f"{symbol}.NS"

    try:
        price_data = fetch_live_price(symbol)
        live_price = price_data.get("price")
        if not live_price or live_price <= 0:
            raise ValueError(f"Invalid live price fetched for {symbol}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch live price for symbol '{symbol}': {str(e)}")

    broker = VirtualBroker(settings)

    try:
        if req.action.upper() == "BUY":
            res = broker.buy(
                agent=agent,
                symbol=symbol,
                quantity=req.quantity,
                market_price=live_price,
                stop_loss=req.stop_loss,
                target=req.target_price,
                confidence=100,
                trade_type=req.trade_type,
                db_session=db,
                position_type=req.position_type
            )
        else:
            res = broker.short_sell(
                agent=agent,
                symbol=symbol,
                quantity=req.quantity,
                market_price=live_price,
                stop_loss=req.stop_loss,
                target=req.target_price,
                confidence=100,
                db_session=db,
                trade_type=req.trade_type,
                position_type=req.position_type
            )

        if not res.get("success"):
            raise HTTPException(status_code=400, detail=res.get("error", "Failed to place manual trade"))

        db.commit()
        return {
            "status": "success",
            "message": f"Manual trade executed: {req.action} {req.quantity} {symbol} @ ₹{res.get('fill_price'):.2f}"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

