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


# Ordered so the FIRST matching category (by earliest string position in the reasoning
# text) becomes the "primary" reason and any other categories found become "secondary" —
# a rough proxy for which concern the model led with vs mentioned in passing.
_REASON_CATEGORIES = {
    "low_volume": ("volume", "conviction", "liquidity", "participation"),
    "valuation": ("p/e", "pe ratio", "valuation", "premium"),
    "leverage": ("debt-to-equity", "leverage", "debt "),
    "growth": ("revenue", "earnings growth", "profit contraction", "revenue contraction", "growth"),
    "technical_momentum": ("macd", "rsi", "overbought", "oversold", "resistance", "support", "bull trap", "reversion", "divergence"),
    "risk_reward": ("risk-reward", "risk reward", "r:r", "reward-to-risk"),
    "data_unavailable": ("unavailable", "offline", "lack of data", "no data"),
}

# Best-effort numeric extraction straight out of the LLM's own narrative — it routinely
# cites the specific number it read (e.g. "RSI at 71.2", "P/E 86.59"), so pull those out
# instead of re-deriving indicators from scratch.
import re as _re
_NUM_PATTERNS = {
    "rsi": _re.compile(r"RSI[^\d]{0,10}(\d{1,3}(?:\.\d+)?)", _re.IGNORECASE),
    "pe_ratio": _re.compile(r"P/E[^\d]{0,10}(\d{1,4}(?:\.\d+)?)", _re.IGNORECASE),
}


def _classify_reasons(text: str) -> dict:
    text_l = (text or "").lower()
    hits = []
    for category, keywords in _REASON_CATEGORIES.items():
        positions = [text_l.find(kw) for kw in keywords if kw in text_l]
        if positions:
            hits.append((min(positions), category))
    hits.sort(key=lambda x: x[0])
    categories = [c for _, c in hits]
    # de-dupe while preserving first-seen order
    seen = []
    for c in categories:
        if c not in seen:
            seen.append(c)
    return {
        "primary_reason": seen[0] if seen else None,
        "secondary_reasons": seen[1:] if len(seen) > 1 else [],
    }


def _extract_numeric_mentions(text: str) -> dict:
    text = text or ""
    out = {}
    for key, pattern in _NUM_PATTERNS.items():
        m = pattern.search(text)
        if m:
            try:
                out[key] = float(m.group(1))
            except ValueError:
                pass
    return out


@router.get("/diagnostics/outcomes")
def arena_diagnostics_outcomes(
    symbol: Optional[str] = None,
    agent_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """For every stored (mostly-HOLD) debate, reconstructs what actually happened to the
    stock afterward — forward returns at +5/+15/+30/+60 min from the decision timestamp,
    plus max favorable/adverse excursion over that hour — using real intraday candles, not
    the day's overall move. Also splits WHY the debate didn't result in a trade into a
    primary reason (whichever concern the model's reasoning led with) and secondary reasons
    (mentioned but not the lead), so "is low volume the real bottleneck vs fundamentals"
    can be answered from accumulated data instead of re-reading transcripts by hand."""
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view Arena diagnostics.")

    logs = _fetch_debate_logs(db, agent_id, symbol, limit)
    results = _compute_outcome_rows(logs)

    # Quick aggregate: of the debates where we could measure a 60-min outcome, how often
    # would staying out (HOLD) have been correct (price fell or stayed flat) vs a missed
    # opportunity (price kept running)?
    measured = [r for r in results if r["forward_returns_pct"].get("+60m") is not None]
    missed_opportunity = sum(1 for r in measured if r["trader_decision"] != "BUY" and r["forward_returns_pct"]["+60m"] > 0.5)
    avoided_drawdown = sum(1 for r in measured if r["trader_decision"] != "BUY" and r["forward_returns_pct"]["+60m"] < -0.5)

    return {
        "total_analyzed": len(results),
        "outcomes_measured": len(measured),
        "of_holds_missed_opportunity_gt_0.5pct": missed_opportunity,
        "of_holds_avoided_drawdown_gt_0.5pct": avoided_drawdown,
        "debates": results,
    }


def _fetch_debate_logs(db: Session, agent_id: Optional[int], symbol: Optional[str], limit: int):
    query = db.query(ArenaDebateLog).order_by(ArenaDebateLog.created_at.desc())
    if agent_id is not None:
        query = query.filter(ArenaDebateLog.agent_id == agent_id)
    if symbol is not None:
        query = query.filter(ArenaDebateLog.symbol == symbol)
    return query.limit(limit).all()


def _volume_ratio_bucket(vr) -> Optional[str]:
    if vr is None:
        return None
    if vr < 0.7:
        return "low (<0.7x)"
    if vr < 1.3:
        return "normal (0.7-1.3x)"
    return "high (>=1.3x)"


def _rr_bucket(rr) -> Optional[str]:
    if rr is None:
        return None
    if rr < 1.0:
        return "<1.0"
    if rr < 1.5:
        return "1.0-1.5"
    if rr < 2.0:
        return "1.5-2.0"
    return ">=2.0"


def _text_bias(text: str, positive_kw: tuple, negative_kw: tuple, unavailable_kw: tuple = ()) -> str:
    text_l = (text or "").lower()
    if any(k in text_l for k in unavailable_kw):
        return "unavailable"
    pos_hit = any(k in text_l for k in positive_kw)
    neg_hit = any(k in text_l for k in negative_kw)
    if pos_hit and not neg_hit:
        return "bullish"
    if neg_hit and not pos_hit:
        return "bearish"
    if pos_hit and neg_hit:
        return "mixed"
    return "neutral"


def _compute_outcome_rows(logs: list) -> list:
    """Shared by /diagnostics/outcomes and /diagnostics/summary — one debate log in,
    one enriched row out (reasoning classification + real forward-price outcome)."""
    from datetime import timezone as _tz, timedelta as _td
    from data.market_fetcher import fetch_intraday_candles

    IST = _tz(_td(hours=5, minutes=30))

    by_symbol: dict[str, list] = {}
    for log in logs:
        by_symbol.setdefault(log.symbol, []).append(log)

    results = []
    for sym, sym_logs in by_symbol.items():
        try:
            candles = fetch_intraday_candles(sym, "5m", "5d")
        except Exception:
            candles = None

        for log in sym_logs:
            trader = _safe_json(log.trader_proposal)
            pm = _safe_json(log.portfolio_manager_decision)
            reports = _safe_json(log.analyst_reports)
            indicators = _safe_json(log.indicators_snapshot) if getattr(log, "indicators_snapshot", None) else {}
            tech = reports.get("technical", {}) if isinstance(reports, dict) else {}
            fund = reports.get("fundamentals", {}) if isinstance(reports, dict) else {}
            sent = reports.get("sentiment", {}) if isinstance(reports, dict) else {}

            reasoning_source = pm.get("reasoning") if (trader.get("decision") == "BUY" and pm) else trader.get("reasoning")
            reason_split = _classify_reasons(reasoning_source)

            entry = trader.get("entry_price")
            sl = trader.get("stop_loss")
            target = trader.get("target")
            rr = trader.get("risk_reward_ratio")
            if rr is None and entry and sl and target:
                stop_distance = abs(entry - sl)
                rr = round(abs(target - entry) / stop_distance, 2) if stop_distance > 0 else None

            volume_ratio = indicators.get("volume_ratio") if isinstance(indicators, dict) else None
            technical_bias = _text_bias(tech.get("summary"), ("bullish", "constructive", "strong"), ("bearish", "weak", "breakdown"))
            fundamentals_bias = _text_bias(
                fund.get("summary"),
                ("strong", "solid", "robust", "pristine", "attractive"),
                ("precarious", "risk", "extreme", "compromised", "stretched", "leverage"),
                ("unavailable",),
            )
            combo_key = f"{reason_split['primary_reason']} | tech={technical_bias} | fund={fundamentals_bias}"

            outcome = {"decision_price": None, "forward_returns_pct": {}, "mfe_pct": None, "mae_pct": None, "note": None}
            if candles is not None and not candles.empty and log.created_at:
                decision_time_ist = log.created_at.replace(tzinfo=_tz.utc).astimezone(IST)
                prior = candles[candles.index <= decision_time_ist]
                if not prior.empty:
                    decision_price = float(prior.iloc[-1]["Close"])
                    outcome["decision_price"] = round(decision_price, 2)

                    window_end = decision_time_ist + _td(minutes=60)
                    window = candles[(candles.index > decision_time_ist) & (candles.index <= window_end)]

                    for horizon in (5, 15, 30, 60):
                        target_time = decision_time_ist + _td(minutes=horizon)
                        at_or_after = candles[candles.index >= target_time]
                        if not at_or_after.empty and decision_price:
                            price_then = float(at_or_after.iloc[0]["Close"])
                            outcome["forward_returns_pct"][f"+{horizon}m"] = round((price_then - decision_price) / decision_price * 100, 2)
                        else:
                            outcome["forward_returns_pct"][f"+{horizon}m"] = None

                    if not window.empty and decision_price:
                        outcome["mfe_pct"] = round((float(window["High"].max()) - decision_price) / decision_price * 100, 2)
                        outcome["mae_pct"] = round((float(window["Low"].min()) - decision_price) / decision_price * 100, 2)
                    else:
                        outcome["note"] = "Not enough time has passed since this decision to measure a 60-min outcome yet."
                else:
                    outcome["note"] = "No candle found at or before the decision timestamp (outside available history)."
            else:
                outcome["note"] = "Candle data unavailable for this symbol."

            results.append({
                "symbol": sym,
                "agent_id": log.agent_id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "trader_decision": trader.get("decision"),
                "final_action": log.final_action,
                "primary_reason": reason_split["primary_reason"],
                "secondary_reasons": reason_split["secondary_reasons"],
                "numeric_mentions": _extract_numeric_mentions(reasoning_source),
                "volume_ratio": volume_ratio,
                "volume_ratio_bucket": _volume_ratio_bucket(volume_ratio),
                "technical_bias": technical_bias,
                "fundamentals_bias": fundamentals_bias,
                "combo_key": combo_key,
                "technical_summary": tech.get("summary"),
                "fundamentals_summary": fund.get("summary"),
                "sentiment_summary": sent.get("summary"),
                "proposed_entry": entry,
                "proposed_stop_loss": sl,
                "proposed_target": target,
                "risk_reward_ratio": rr,
                "risk_reward_bucket": _rr_bucket(rr),
                **outcome,
            })

    return results


def _rollup(rows: list, key_fn) -> list:
    """Groups outcome rows by key_fn and computes the standard set of rollup stats:
    sample size, missed-opportunity rate, avoided-drawdown rate, avg MFE/MAE."""
    groups: dict = {}
    for r in rows:
        key = key_fn(r)
        if key is None:
            continue
        groups.setdefault(key, []).append(r)

    out = []
    for key, group_rows in groups.items():
        measured = [r for r in group_rows if r["forward_returns_pct"].get("+60m") is not None]
        holds = [r for r in measured if r["trader_decision"] != "BUY"]
        missed = sum(1 for r in holds if r["forward_returns_pct"]["+60m"] > 0.5)
        avoided = sum(1 for r in holds if r["forward_returns_pct"]["+60m"] < -0.5)
        mfe_vals = [r["mfe_pct"] for r in group_rows if r["mfe_pct"] is not None]
        mae_vals = [r["mae_pct"] for r in group_rows if r["mae_pct"] is not None]
        out.append({
            "key": key,
            "sample_size": len(group_rows),
            "outcomes_measured": len(measured),
            "holds_measured": len(holds),
            "missed_opportunity_rate": round(missed / len(holds), 2) if holds else None,
            "avoided_drawdown_rate": round(avoided / len(holds), 2) if holds else None,
            "avg_mfe_pct": round(sum(mfe_vals) / len(mfe_vals), 2) if mfe_vals else None,
            "avg_mae_pct": round(sum(mae_vals) / len(mae_vals), 2) if mae_vals else None,
        })
    out.sort(key=lambda g: g["sample_size"], reverse=True)
    return out


@router.get("/diagnostics/summary")
def arena_diagnostics_summary(agent_id: Optional[int] = None, limit: int = 500, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Rollup view over /diagnostics/outcomes: the same enriched rows, pre-grouped by the
    dimensions that matter for the volume-vs-fundamentals-vs-R:R calibration question —
    by primary rejection reason, by symbol, by R:R bucket, by volume-ratio bucket, and by
    the (reason, technical bias, fundamentals bias) combination. Each group reports sample
    size, missed-opportunity rate, avoided-drawdown rate, and avg MFE/MAE, so which layer is
    actually too conservative can be read off directly once enough sessions accumulate."""
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view Arena diagnostics.")

    logs = _fetch_debate_logs(db, agent_id, None, limit)
    rows = _compute_outcome_rows(logs)

    return {
        "total_debates": len(rows),
        "by_primary_reason": _rollup(rows, lambda r: r["primary_reason"]),
        "by_symbol": _rollup(rows, lambda r: r["symbol"]),
        "by_risk_reward_bucket": _rollup(rows, lambda r: r["risk_reward_bucket"]),
        "by_volume_ratio_bucket": _rollup(rows, lambda r: r["volume_ratio_bucket"]),
        "by_reason_and_bias_combo": _rollup(rows, lambda r: r["combo_key"]),
    }


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


_FUNNEL_ORDER = ["evaluated", "trader_buy_proposed", "pm_approved", "risk_engine_approved"]


@router.get("/diagnostics/funnel")
def arena_diagnostics_funnel(agent_id: Optional[int] = None, limit: int = 1000, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Answers "why isn't this converting to trades" directly, instead of describing
    rejection quality in isolation:
    - overall + per-symbol conversion funnel (evaluated -> trader BUY -> PM keeps it ->
      risk engine approves), so you can see exactly which stage kills the most candidates
    - near-miss analysis: HOLDs blocked by exactly ONE reason (no stacking) that went on to
      show positive MFE — the closest available proxy for "would this have worked if that
      one filter were relaxed"
    - stacking check: does missed-opportunity rate rise as the number of cited reasons goes
      up, i.e. are multiple conservative filters compounding into an effectively stricter bar
      than any single one intends
    - per-reason "protectiveness": avg MAE avoided vs avg MFE missed, so a reason that mostly
      just suppresses frequency (small MAE, real MFE missed) reads differently from one that's
      genuinely catching real drawdowns (large negative MAE)."""
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view Arena diagnostics.")

    logs = _fetch_debate_logs(db, agent_id, None, limit)
    rows = _compute_outcome_rows(logs)

    # --- Overall + per-symbol funnel ---
    def _build_funnel(subset: list) -> dict:
        total = len(subset)
        stage_counts = {s: 0 for s in _FUNNEL_ORDER}
        executed = 0
        for r in subset:
            # final_action reflects what actually happened after the risk engine
            stage = "evaluated"
            if r["trader_decision"] == "BUY":
                stage = "trader_buy_proposed"
                if r["final_action"] == "BUY":
                    stage = "risk_engine_approved"
                    executed += 1
                elif r["final_action"] == "REJECTED":
                    # PM kept it as BUY but the deterministic risk engine vetoed it
                    stage = "pm_approved"
                # else final_action == "HOLD": PM itself overrode -> stays at trader_buy_proposed
            stage_counts[stage] += 1
        # Cumulative "reached at least this stage" counts (funnel-style, not just terminal stage)
        cumulative = {}
        remaining = total
        for s in _FUNNEL_ORDER:
            cumulative[s] = remaining
            remaining -= stage_counts[s]
        return {
            "total_evaluated": total,
            "reached_stage_counts": stage_counts,
            "cumulative_reached": cumulative,
            "conversion_pct": {
                s: (round(cumulative[s] / total * 100, 1) if total else None) for s in _FUNNEL_ORDER
            },
            "executed_trades": executed,
            "overall_conversion_pct": round(executed / total * 100, 2) if total else None,
        }

    overall_funnel = _build_funnel(rows)
    by_symbol_funnel = {}
    for sym in sorted({r["symbol"] for r in rows}):
        by_symbol_funnel[sym] = _build_funnel([r for r in rows if r["symbol"] == sym])
    # Symbols that basically never get past the trader's own judgment
    dead_symbols = sorted(
        by_symbol_funnel.items(),
        key=lambda kv: kv[1]["conversion_pct"]["trader_buy_proposed"] or 0,
    )
    never_reaches_buy = [sym for sym, f in dead_symbols if (f["conversion_pct"]["trader_buy_proposed"] or 0) == 0]

    # --- Near-miss analysis: single-reason HOLDs with a subsequently positive MFE ---
    near_misses = []
    for r in rows:
        if r["trader_decision"] == "BUY":
            continue
        reason_count = (1 if r["primary_reason"] else 0) + len(r["secondary_reasons"])
        if reason_count == 1 and r["mfe_pct"] is not None and r["mfe_pct"] > 0.5:
            near_misses.append({
                "symbol": r["symbol"],
                "created_at": r["created_at"],
                "sole_reason": r["primary_reason"],
                "mfe_pct": r["mfe_pct"],
                "mae_pct": r["mae_pct"],
                "forward_60m_pct": r["forward_returns_pct"].get("+60m"),
            })
    near_misses.sort(key=lambda x: x["mfe_pct"], reverse=True)

    # --- Stacking check: does missed-opportunity rate rise with reason count? ---
    by_reason_count: dict[int, list] = {}
    for r in rows:
        if r["trader_decision"] == "BUY":
            continue
        reason_count = (1 if r["primary_reason"] else 0) + len(r["secondary_reasons"])
        by_reason_count.setdefault(reason_count, []).append(r)
    stacking = []
    for count, group in sorted(by_reason_count.items()):
        measured = [r for r in group if r["forward_returns_pct"].get("+60m") is not None]
        missed = sum(1 for r in measured if r["forward_returns_pct"]["+60m"] > 0.5)
        avoided = sum(1 for r in measured if r["forward_returns_pct"]["+60m"] < -0.5)
        stacking.append({
            "reason_count": count,
            "sample_size": len(group),
            "outcomes_measured": len(measured),
            "missed_opportunity_rate": round(missed / len(measured), 2) if measured else None,
            "avoided_drawdown_rate": round(avoided / len(measured), 2) if measured else None,
        })

    # --- Per-reason protectiveness: avg MAE avoided vs avg MFE missed ---
    protectiveness = _rollup(rows, lambda r: r["primary_reason"])
    for p in protectiveness:
        mfe = p["avg_mfe_pct"] or 0
        mae = p["avg_mae_pct"] or 0
        # Positive score = mostly suppressing frequency (missing upside, not avoiding much
        # downside); negative score = genuinely protective (avoiding real downside).
        p["net_suppression_score"] = round(mfe + mae, 2) if (p["avg_mfe_pct"] is not None and p["avg_mae_pct"] is not None) else None
    protectiveness.sort(key=lambda p: p["net_suppression_score"] if p["net_suppression_score"] is not None else -999, reverse=True)

    # --- Overall trade-vs-hold rate straight from final_action ---
    final_actions = {}
    for r in rows:
        fa = r["final_action"] or "UNKNOWN"
        final_actions[fa] = final_actions.get(fa, 0) + 1

    return {
        "total_debates": len(rows),
        "final_action_breakdown": final_actions,
        "overall_funnel": overall_funnel,
        "symbols_that_never_reach_buy_proposal": never_reaches_buy,
        "by_symbol_funnel": by_symbol_funnel,
        "near_miss_single_reason_positive_mfe": near_misses,
        "stacking_by_reason_count": stacking,
        "reason_protectiveness_ranked": protectiveness,
        "_notes": {
            "funnel_stages": "evaluated -> trader_buy_proposed -> pm_approved -> risk_engine_approved. "
                              "There is no separate sequential fundamentals/technicals/volume gate in the "
                              "actual pipeline — the Trader synthesizes all three holistically in one judgment "
                              "call. primary_reason (from /diagnostics/summary) is the closest available proxy "
                              "for 'which factor it led with', not a hard pass/fail stage.",
            "net_suppression_score": "avg_mfe_pct + avg_mae_pct for that reason's HOLDs. Positive = mostly "
                                      "missing upside without avoiding much downside (frequency-suppressing). "
                                      "Negative = genuinely avoiding real drawdown (protective).",
        },
    }
