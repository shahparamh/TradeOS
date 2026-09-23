from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json
import asyncio

from database.connection import get_db
from database.models import Agent, Trade, Position, ArenaDebateLog, ArenaReflection, SystemRule
from api.routes_auth import get_current_user
from utils.constants import ARENA_WATCHLIST
from utils.helpers import get_ist_now

router = APIRouter(prefix="/arena", tags=["Survival Arena"])


def _agent_equity(agent: Agent, db: Session) -> float:
    positions = db.query(Position).filter(Position.agent_id == agent.id).all()
    return agent.cash_balance + sum(p.unrealized_pnl or 0.0 for p in positions)


@router.get("/agents")
def list_arena_agents(db: Session = Depends(get_db)):
    agents = db.query(Agent).filter(Agent.mode == "SURVIVAL").all()
    result = []
    for agent in agents:
        equity = _agent_equity(agent, db)
        starting_capital = agent.starting_capital or 1
        survival_days = None
        if agent.created_at:
            end = agent.died_at or get_ist_now().replace(tzinfo=None)
            survival_days = max(0, (end - agent.created_at).days)
        result.append({
            "id": agent.id,
            "name": agent.name,
            "model_name": agent.model_name,
            "provider": agent.provider,
            "starting_capital": starting_capital,
            "cash_balance": float(agent.cash_balance or 0),
            "equity": round(equity, 2),
            "return_pct": round(((equity - starting_capital) / starting_capital) * 100, 2) if starting_capital else 0,
            "status": "Dead" if agent.is_dead else "Alive",
            "is_dead": agent.is_dead,
            "is_active": agent.is_active,
            "died_at": agent.died_at.isoformat() if agent.died_at else None,
            "survival_days": survival_days,
            "death_threshold": agent.death_threshold,
        })
    return result


@router.post("/agents/{agent_id}/toggle")
def toggle_arena_agent(agent_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Pauses/resumes a Survival agent — a deactivated agent is skipped by the next arena
    cycle (run_arena_cycle filters on is_active fresh from the DB each run, so this takes
    effect immediately with no restart needed) but keeps its equity/trade history intact."""
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to control Arena agents.")

    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.mode == "SURVIVAL").first()
    if not agent:
        raise HTTPException(status_code=404, detail="Survival agent not found")

    agent.is_active = not agent.is_active
    db.commit()
    return {
        "status": "success",
        "is_active": agent.is_active,
        "message": f"{agent.name} is now {'active' if agent.is_active else 'paused'}.",
    }


@router.get("/agents/{agent_id}")
def get_arena_agent_detail(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.mode == "SURVIVAL").first()
    if not agent:
        raise HTTPException(status_code=404, detail="Survival agent not found")

    trades = db.query(Trade).filter(Trade.agent_id == agent_id).order_by(Trade.entry_time.desc()).all()
    positions = db.query(Position).filter(Position.agent_id == agent_id).all()
    closed = [t for t in trades if t.pnl is not None]
    wins = [t for t in closed if t.pnl > 0]
    equity = _agent_equity(agent, db)
    starting_capital = agent.starting_capital or 1

    debate_logs = db.query(ArenaDebateLog).filter(ArenaDebateLog.agent_id == agent_id).order_by(ArenaDebateLog.created_at.desc()).limit(50).all()
    reflections = db.query(ArenaReflection).filter(ArenaReflection.agent_id == agent_id).order_by(ArenaReflection.created_at.desc()).limit(20).all()

    def _safe_json(text):
        if not text:
            return None
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    return {
        "id": agent.id,
        "name": agent.name,
        "model_name": agent.model_name,
        "provider": agent.provider,
        "starting_capital": starting_capital,
        "cash_balance": float(agent.cash_balance or 0),
        "equity": round(equity, 2),
        "return_pct": round(((equity - starting_capital) / starting_capital) * 100, 2) if starting_capital else 0,
        "status": "Dead" if agent.is_dead else "Alive",
        "death_threshold": agent.death_threshold,
        "died_at": agent.died_at.isoformat() if agent.died_at else None,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "stats": {
            "total_trades": len(trades),
            "closed_trades": len(closed),
            "open_positions": len(positions),
            "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
            "best_trade": max((t.pnl for t in closed), default=0),
            "worst_trade": min((t.pnl for t in closed), default=0),
            "max_drawdown_pct": round(min((r.realized_return_pct for r in reflections if r.realized_return_pct is not None), default=0), 2),
        },
        "positions": [{
            "symbol": p.symbol, "quantity": p.quantity, "entry_price": p.entry_price,
            "current_price": p.current_price, "stop_loss": p.stop_loss, "target_price": p.target_price,
            "unrealized_pnl": p.unrealized_pnl,
        } for p in positions],
        "trades": [{
            "id": t.id, "symbol": t.symbol, "action": t.action, "quantity": t.quantity,
            "entry_price": t.entry_price, "exit_price": t.exit_price, "pnl": t.pnl,
            "status": t.status, "entry_time": t.entry_time.isoformat() if t.entry_time else None,
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
        } for t in trades],
        "debate_transcripts": [{
            "id": d.id, "symbol": d.symbol, "cycle_id": d.cycle_id,
            "analyst_reports": _safe_json(d.analyst_reports),
            "bull_argument": _safe_json(d.bull_argument),
            "bear_argument": _safe_json(d.bear_argument),
            "trader_proposal": _safe_json(d.trader_proposal),
            "risk_team_debate": _safe_json(d.risk_team_debate),
            "portfolio_manager_decision": _safe_json(d.portfolio_manager_decision),
            "risk_engine_result": _safe_json(d.risk_engine_result),
            "final_action": d.final_action,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        } for d in debate_logs],
        "reflections": [{
            "trade_id": r.trade_id, "realized_pnl": r.realized_pnl,
            "realized_return_pct": r.realized_return_pct, "benchmark_return_pct": r.benchmark_return_pct,
            "reflection_text": r.reflection_text, "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in reflections],
    }


class CreateArenaAgent(BaseModel):
    model_config = {"protected_namespaces": ()}

    name: str
    provider: str
    model_name: str
    starting_capital: float = 2000.0
    death_threshold: Optional[float] = None


@router.post("/agents")
def create_arena_agent(payload: CreateArenaAgent, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to create arena agents.")

    existing = db.query(Agent).filter(Agent.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"An agent named '{payload.name}' already exists.")

    death_threshold = payload.death_threshold if payload.death_threshold is not None else payload.starting_capital * 0.10

    agent = Agent(
        name=payload.name,
        provider=payload.provider,
        model_name=payload.model_name,
        cash_balance=payload.starting_capital,
        starting_capital=payload.starting_capital,
        death_threshold=death_threshold,
        total_pnl=0.0,
        is_active=True,
        mode="SURVIVAL",
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return {"status": "success", "agent_id": agent.id}


@router.post("/emergency-stop")
def emergency_stop(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to control the Arena.")
    rule = db.query(SystemRule).filter(SystemRule.key == "arena_emergency_stop").first()
    if not rule:
        rule = SystemRule(key="arena_emergency_stop", value_type="boolean", bool_value=True, description="Global kill switch for the Survival Arena")
        db.add(rule)
    else:
        rule.bool_value = True
    db.commit()
    return {"status": "success", "message": "Survival Arena EMERGENCY STOP engaged. No new orders will be placed."}


@router.post("/resume")
def resume_arena(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to control the Arena.")
    rule = db.query(SystemRule).filter(SystemRule.key == "arena_emergency_stop").first()
    if rule:
        rule.bool_value = False
        db.commit()
    return {"status": "success", "message": "Survival Arena resumed."}


@router.get("/status")
def arena_status(db: Session = Depends(get_db)):
    rule = db.query(SystemRule).filter(SystemRule.key == "arena_emergency_stop").first()
    return {"emergency_stop": bool(rule.bool_value) if rule else False, "watchlist": ARENA_WATCHLIST}


@router.get("/market")
def arena_market(db: Session = Depends(get_db)):
    # One batched yfinance call for the whole watchlist instead of one rate-limited
    # round trip per symbol (each of which would otherwise queue behind the global
    # 3s-minimum gap between yfinance calls — 11 symbols serialized is 30s+ on a cold cache).
    from data.market_fetcher import fetch_bulk_quotes
    quotes = fetch_bulk_quotes(tuple(ARENA_WATCHLIST))
    return [quotes[s] for s in ARENA_WATCHLIST if s in quotes]


@router.post("/cycle-trigger")
async def trigger_arena_cycle_manually():
    from main import trading_scheduler
    asyncio.create_task(trading_scheduler.run_arena_cycle(ignore_hours=True))
    return {"status": "triggered", "message": "Survival Arena cycle started in background"}


def _safe_json(text):
    if not text:
        return {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


# Keyword heuristics for classifying WHY a debate didn't result in a trade — not a precise
# parse of the LLM's reasoning, just enough to separate "never got to R:R because fundamentals/
# volume killed it first" from "got to R:R and failed that specific bar", which is exactly the
# distinction needed to tell a genuine policy-calibration question (is 2:1 realistic for this
# symbol's volatility?) apart from a symbol that never had a shot regardless of R:R.
_FUNDAMENTAL_KEYWORDS = ("p/e", "pe ratio", "valuation", "leverage", "debt", "revenue", "earnings", "fundamental", "growth")
_VOLUME_KEYWORDS = ("volume", "conviction", "liquidity", "participation")
_RR_KEYWORDS = ("risk-reward", "risk reward", "r:r", "reward-to-risk", "reward to risk")


def _classify_blocker(trader: dict, pm: dict, risk_engine: dict) -> str:
    if trader.get("decision") != "BUY":
        reasoning = (trader.get("reasoning") or "").lower()
        if any(k in reasoning for k in _RR_KEYWORDS):
            return "risk_reward_gate (trader)"
        if any(k in reasoning for k in _FUNDAMENTAL_KEYWORDS):
            return "fundamentals_gate (trader)"
        if any(k in reasoning for k in _VOLUME_KEYWORDS):
            return "volume_conviction_gate (trader)"
        return "trader_hold_other"

    if pm and pm.get("decision") != "BUY":
        reasoning = (pm.get("reasoning") or "").lower()
        if any(k in reasoning for k in _RR_KEYWORDS):
            return "risk_reward_gate (portfolio_manager)"
        if any(k in reasoning for k in _VOLUME_KEYWORDS):
            return "volume_conviction_gate (portfolio_manager)"
        if any(k in reasoning for k in _FUNDAMENTAL_KEYWORDS):
            return "fundamentals_gate (portfolio_manager)"
        return "pm_override_other"

    if risk_engine and not risk_engine.get("approved"):
        return f"risk_engine_gate: {risk_engine.get('rejection_reason')}"

    return "approved"


@router.get("/diagnostics")
def arena_diagnostics(agent_id: Optional[int] = None, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Self-serve version of the manual debate-log analysis: for every stored debate, shows
    what the trader actually proposed (entry/stop/target/R:R when it got that far) and
    classifies WHY it didn't result in a trade — so a symbol that never reaches the R:R
    question (killed by fundamentals/volume first) is visibly distinct from one that reaches
    R:R and fails that specific bar. Aggregates per symbol so volatility-vs-policy questions
    (e.g. "is 2:1 R:R realistic for this symbol?") can be answered from real accumulated data
    instead of manually re-reading transcripts each time."""
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view Arena diagnostics.")

    query = db.query(ArenaDebateLog).order_by(ArenaDebateLog.created_at.desc())
    if agent_id is not None:
        query = query.filter(ArenaDebateLog.agent_id == agent_id)
    logs = query.limit(1000).all()

    per_symbol: dict[str, dict] = {}
    rows = []

    for log in logs:
        trader = _safe_json(log.trader_proposal)
        pm = _safe_json(log.portfolio_manager_decision)
        risk_engine = _safe_json(log.risk_engine_result)
        blocker = _classify_blocker(trader, pm, risk_engine)

        entry = trader.get("entry_price")
        sl = trader.get("stop_loss")
        target = trader.get("target")
        rr = trader.get("risk_reward_ratio")
        if rr is None and entry and sl and target:
            stop_distance = abs(entry - sl)
            if stop_distance > 0:
                rr = round(abs(target - entry) / stop_distance, 2)

        rows.append({
            "agent_id": log.agent_id,
            "symbol": log.symbol,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "trader_decision": trader.get("decision"),
            "entry_price": entry,
            "stop_loss": sl,
            "target": target,
            "risk_reward_ratio": rr,
            "blocker": blocker,
            "final_action": log.final_action,
        })

        bucket = per_symbol.setdefault(log.symbol, {
            "symbol": log.symbol,
            "total_debates": 0,
            "buy_proposals": 0,
            "reached_pm": 0,
            "approved_trades": 0,
            "risk_reward_ratios": [],
            "blocker_counts": {},
        })
        bucket["total_debates"] += 1
        if trader.get("decision") == "BUY":
            bucket["buy_proposals"] += 1
            if rr is not None:
                bucket["risk_reward_ratios"].append(rr)
        if pm:
            bucket["reached_pm"] += 1
        if blocker == "approved":
            bucket["approved_trades"] += 1
        bucket["blocker_counts"][blocker] = bucket["blocker_counts"].get(blocker, 0) + 1

    summary = []
    for bucket in per_symbol.values():
        rrs = bucket.pop("risk_reward_ratios")
        bucket["avg_risk_reward_when_proposed"] = round(sum(rrs) / len(rrs), 2) if rrs else None
        bucket["min_risk_reward_when_proposed"] = min(rrs) if rrs else None
        bucket["max_risk_reward_when_proposed"] = max(rrs) if rrs else None
        summary.append(bucket)
    summary.sort(key=lambda b: b["buy_proposals"], reverse=True)

    return {
        "total_debates_analyzed": len(logs),
        "per_symbol_summary": summary,
        "debates": rows,
    }
