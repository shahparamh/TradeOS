"""
TradeOS — Survival Arena Debate Pipeline
TradingAgents-style multi-role decision pipeline for a single survival agent/symbol:
Analyst Team (parallel) -> Bull/Bear Researcher debate -> Trader -> Risk Team -> Portfolio Manager
-> deterministic Survival Risk Engine (the only layer with real veto power).
"""

import asyncio
import json
from agents.gemini_agent import query_gemini
from agents.groq_agent import query_groq
from agents.ollama_agent import query_ollama
from agents.prompts import (
    ARENA_TECHNICAL_ANALYST_PROMPT,
    ARENA_FUNDAMENTALS_ANALYST_PROMPT,
    ARENA_SENTIMENT_ANALYST_PROMPT,
    ARENA_BULL_RESEARCHER_PROMPT,
    ARENA_BEAR_RESEARCHER_PROMPT,
    ARENA_TRADER_PROMPT,
    ARENA_RISK_ANALYST_PROMPT_TEMPLATE,
    ARENA_PORTFOLIO_MANAGER_PROMPT,
    build_arena_analyst_payload,
    build_arena_trader_payload,
    build_arena_portfolio_manager_payload,
)
from datetime import datetime
from broker.survival_risk_manager import SurvivalRiskManager
from database.models import ArenaDebateLog, ArenaReflection, Trade
from utils.logger import setup_logger
from utils.helpers import generate_cycle_id, get_ist_now

logger = setup_logger("arena_debate")

_PROVIDER_DISPATCH = {
    "google": query_gemini,
    "groq": query_groq,
    "ollama": query_ollama,
}


_HOUSEKEEPING_KEYS = {"raw_response", "agent", "provider", "latency_ms", "is_valid", "validation_errors"}


def _clean(d: dict) -> dict:
    """Every provider client always routes through parse_ai_response()/validate_decision(),
    which injects trade-decision housekeeping fields (raw_response, is_valid, ...) even onto
    non-trade role responses (analyst reports, bull/bear arguments). Strip that noise before
    storing/forwarding a role's output — keeps prompts smaller and keeps ArenaDebateLog JSON
    limited to what the UI actually renders."""
    if not isinstance(d, dict):
        return d
    return {k: v for k, v in d.items() if k not in _HOUSEKEEPING_KEYS}


async def _ask(provider: str, payload: str, system_prompt: str) -> dict:
    """Every provider client (query_gemini/query_groq/...) already parses its raw text
    response into a dict via parse_ai_response before returning, so the result here is
    ready to use directly — no need to re-parse raw_response."""
    fn = _PROVIDER_DISPATCH.get(provider)
    if not fn:
        return {"error": f"Unknown provider {provider}"}
    try:
        result = await fn(payload, system_prompt=system_prompt)
        return _clean(result)
    except Exception as e:
        logger.error(f"Arena role call failed for provider {provider}: {e}")
        return {"error": str(e)}


def _today_realized_pnl(db, agent_id: int) -> float:
    """Shared with SurvivalRiskManager's daily kill-switch check, but reuses the caller's
    session instead of opening a new one — safe to call twice per debate since it's a cheap
    read, and keeps the PM's view of today's P&L consistent with what the risk engine sees."""
    today_start = datetime.combine(get_ist_now().date(), datetime.min.time())
    trades_today = db.query(Trade).filter(
        Trade.agent_id == agent_id,
        Trade.exit_time >= today_start,
    ).all()
    return sum(t.pnl for t in trades_today if t.pnl)


def _recent_reflections(db, agent_id: int, limit: int = 5) -> list:
    rows = (
        db.query(ArenaReflection)
        .filter(ArenaReflection.agent_id == agent_id)
        .order_by(ArenaReflection.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "realized_pnl": r.realized_pnl,
            "realized_return_pct": r.realized_return_pct,
            "reflection": r.reflection_text,
        }
        for r in rows
    ]


async def run_arena_debate(agent, opportunity: dict, agent_state: dict, db) -> dict:
    """
    Runs the full multi-role debate for one agent/symbol candidate and, if approved,
    returns the final sized decision ready for VirtualBroker. Always writes one
    ArenaDebateLog row regardless of outcome.
    """
    symbol = opportunity["symbol"]
    market = opportunity.get("market", "IN")
    provider = agent.provider
    cycle_id = generate_cycle_id()

    indicators = opportunity.get("indicators", {})
    fundamentals = opportunity.get("fundamentals", {})
    news = opportunity.get("news", [])

    analyst_payload = build_arena_analyst_payload(symbol, indicators, fundamentals, news, market=market)

    # 1. Analyst Team — parallel
    technical_report, fundamentals_report, sentiment_report = await asyncio.gather(
        _ask(provider, analyst_payload, ARENA_TECHNICAL_ANALYST_PROMPT),
        _ask(provider, analyst_payload, ARENA_FUNDAMENTALS_ANALYST_PROMPT),
        _ask(provider, analyst_payload, ARENA_SENTIMENT_ANALYST_PROMPT),
    )
    analyst_reports = {
        "technical": technical_report,
        "fundamentals": fundamentals_report,
        "sentiment": sentiment_report,
    }

    # 2. Researcher Team — 1 round: Bull then Bear (bear sees the bull argument)
    bull_payload = json.dumps({"symbol": symbol, "analyst_reports": analyst_reports}, default=str)
    bull_argument = await _ask(provider, bull_payload, ARENA_BULL_RESEARCHER_PROMPT)

    bear_payload = json.dumps({"symbol": symbol, "analyst_reports": analyst_reports, "bull_argument": bull_argument}, default=str)
    bear_argument = await _ask(provider, bear_payload, ARENA_BEAR_RESEARCHER_PROMPT)

    # 3. Trader
    reflections = _recent_reflections(db, agent.id)
    trader_payload = build_arena_trader_payload(symbol, analyst_reports, bull_argument, bear_argument, agent_state, reflections)
    trader_proposal = await _ask(provider, trader_payload, ARENA_TRADER_PROMPT)

    log = ArenaDebateLog(
        agent_id=agent.id,
        symbol=symbol,
        market=market,
        cycle_id=cycle_id,
        analyst_reports=json.dumps(analyst_reports, default=str),
        bull_argument=json.dumps(bull_argument, default=str),
        bear_argument=json.dumps(bear_argument, default=str),
        debate_rounds=1,
        trader_proposal=json.dumps(trader_proposal, default=str),
        indicators_snapshot=json.dumps(indicators, default=str),
    )

    if trader_proposal.get("decision") != "BUY":
        log.risk_team_debate = None
        log.portfolio_manager_decision = None
        log.risk_engine_result = json.dumps({"approved": False, "rejection_reason": "Trader did not propose BUY"})
        log.final_action = "HOLD"
        db.add(log)
        db.commit()
        return {"decision": "HOLD", "reasoning": trader_proposal.get("reasoning", "Trader proposed HOLD.")}

    # 4. Risk Management Team — conservative + aggressive perspectives
    conservative_prompt = ARENA_RISK_ANALYST_PROMPT_TEMPLATE.format(
        stance="conservative",
        stance_instruction="Weigh capital preservation heavily. Flag anything that could threaten the account's survival.",
    )
    aggressive_prompt = ARENA_RISK_ANALYST_PROMPT_TEMPLATE.format(
        stance="aggressive",
        stance_instruction="Weigh missed opportunity cost. Only object if the setup is genuinely weak.",
    )
    risk_payload = json.dumps({"symbol": symbol, "trader_proposal": trader_proposal, "bull_case": bull_argument, "bear_case": bear_argument}, default=str)
    conservative_review, aggressive_review = await asyncio.gather(
        _ask(provider, risk_payload, conservative_prompt),
        _ask(provider, risk_payload, aggressive_prompt),
    )
    risk_reviews = [conservative_review, aggressive_review]
    log.risk_team_debate = json.dumps(risk_reviews, default=str)

    # 5. Portfolio Manager — receives real portfolio state so it can check portfolio fit
    # instead of re-litigating the setup's technicals. Only fields we can actually populate
    # today (no sector/correlation data exists in the schema) are included, so the prompt
    # can't be asked to weigh concerns it was never given data for.
    portfolio_state = {
        "cash_balance": agent_state.get("cash_balance"),
        "open_positions_count": agent_state.get("positions_count", 0),
        "max_open_positions": SurvivalRiskManager.MAX_OPEN_POSITIONS,
        "open_symbols": agent_state.get("open_symbols", []),
        "exposure_value": agent_state.get("open_positions_value", 0.0),
        "today_realized_pnl": _today_realized_pnl(db, agent.id),
        "daily_loss_kill_switch_pct": SurvivalRiskManager.DAILY_LOSS_KILL_SWITCH_PCT,
    }
    pm_payload = build_arena_portfolio_manager_payload(symbol, trader_proposal, risk_reviews, portfolio_state)
    pm_decision = await _ask(provider, pm_payload, ARENA_PORTFOLIO_MANAGER_PROMPT)
    pm_decision["symbol"] = symbol
    pm_decision["agent_id"] = agent.id
    pm_decision["market"] = market
    log.portfolio_manager_decision = json.dumps(pm_decision, default=str)

    if pm_decision.get("decision") != "BUY":
        log.risk_engine_result = json.dumps({"approved": False, "rejection_reason": "Portfolio Manager overrode to HOLD"})
        log.final_action = "HOLD"
        db.add(log)
        db.commit()
        return {"decision": "HOLD", "reasoning": pm_decision.get("reasoning", "Portfolio Manager held.")}

    # 6. Deterministic Survival Risk Engine — final, non-negotiable gate
    risk_manager = SurvivalRiskManager()
    result = risk_manager.validate_and_size(pm_decision, agent, agent_state, db)
    log.risk_engine_result = json.dumps({
        "approved": result["approved"],
        "rejection_reason": result["rejection_reason"],
        "quantity": result["decision"].get("quantity"),
        # SurvivalRiskManager now computes this deterministically (against the final,
        # post-6%-clamp stop) whenever it gets far enough to check R:R -- lets diagnostics
        # distinguish a RISK_REWARD_REJECTED rejection from sizing/cash/stop/position-limit/
        # kill-switch rejections by their reason string, and see the ratio either way.
        "risk_reward_ratio": result["decision"].get("risk_reward_ratio"),
        # Both sides of the 6% stop clamp, logged whether or not it actually fired, so we can
        # later measure how often/how much it changes the Trader's intended invalidation level
        # -- purely observational, the clamp's own behavior is unchanged.
        "proposed_stop_loss": result["decision"].get("proposed_stop_loss"),
        "final_stop_loss": result["decision"].get("final_stop_loss"),
        "proposed_stop_distance_pct": result["decision"].get("proposed_stop_distance_pct"),
        "final_stop_distance_pct": result["decision"].get("final_stop_distance_pct"),
    }, default=str)
    log.final_action = "BUY" if result["approved"] else "REJECTED"
    db.add(log)
    db.commit()

    if not result["approved"]:
        return {"decision": "HOLD", "reasoning": f"Risk Engine rejected: {result['rejection_reason']}"}

    final_decision = result["decision"]
    final_decision["decision"] = "BUY"
    final_decision["symbol"] = symbol
    final_decision["agent_id"] = agent.id
    return final_decision


def record_reflection(db, agent, trade):
    """Writes a post-trade reflection for a closed Survival Arena trade, folded into future
    Trader/Portfolio-Manager prompts via _recent_reflections(). Templated for the MVP — the
    text is generated deterministically, not via an extra LLM call, to keep the loop cheap."""
    if trade.pnl is None or not trade.entry_price:
        return

    realized_return_pct = (trade.pnl / (trade.entry_price * trade.quantity)) * 100 if trade.entry_price and trade.quantity else 0.0

    # Approximate benchmark: today's index move at reflection time, not a precise
    # entry->exit window match. IN uses Nifty; US benchmarking isn't wired up yet.
    benchmark_return_pct = None
    if getattr(trade, "market", "IN") == "IN":
        try:
            from data.market_fetcher import fetch_live_price
            nifty = fetch_live_price("^NSEI")
            benchmark_return_pct = nifty.get("change_pct")
        except Exception:
            pass

    outcome = "won" if trade.pnl > 0 else "lost"
    currency_symbol = "$" if getattr(trade, "market", "IN") == "US" else "₹"
    reflection_text = (
        f"Trade on {trade.symbol} ({trade.entry_time.date() if trade.entry_time else 'N/A'}) {outcome} "
        f"{currency_symbol}{trade.pnl:.2f} ({realized_return_pct:+.2f}%), exit reason: {trade.status}. "
        f"{'Consider requiring stronger confluence before re-entering similar setups.' if trade.pnl < 0 else 'This setup type worked — note the entry conditions.'}"
    )

    reflection = ArenaReflection(
        agent_id=agent.id,
        trade_id=trade.id,
        realized_pnl=trade.pnl,
        realized_return_pct=realized_return_pct,
        benchmark_return_pct=benchmark_return_pct,
        reflection_text=reflection_text,
    )
    db.add(reflection)
