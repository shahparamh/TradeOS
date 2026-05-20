"""
TradeOS — Agent Executor
Runs all AI agents concurrently with identical data for fair comparison.
"""

import asyncio
import json
from datetime import datetime
from agents.gemini_agent import query_gemini
from agents.groq_agent import query_groq
from agents.github_agent import query_github
from agents.huggingface_agent import query_huggingface
from agents.prompts import build_ai_payload
from database.connection import SessionLocal
from database.models import Agent, AIResponse
from utils.logger import setup_logger

from agents.ollama_agent import query_ollama

logger = setup_logger("agent_executor")

async def query_agent_pipeline(agent, payload_dict: dict, opportunity: dict) -> dict:
    """Sequentially executes Call 1 (Analyst) and Call 2 (Devil's Advocate) for Layer 5 multi-model validation."""
    payload_str = json.dumps(payload_dict, default=str)
    
    # 1. CALL 1: Analyst Decision
    decision = {"decision": "HOLD", "confidence": 0, "reasoning": "Failed to query analyst."}
    try:
        if agent.provider == "google":
            decision = await query_gemini(payload_str)
        elif agent.provider == "groq":
            decision = await query_groq(payload_str)
        elif agent.provider == "github":
            decision = await query_github(payload_str)
        elif agent.provider == "huggingface":
            decision = await query_huggingface(payload_str)
        elif agent.provider == "ollama":
            import os
            if os.getenv("RENDER"):
                return {"decision": "HOLD", "confidence": 0, "reasoning": "Ollama disabled in cloud."}
            decision = await query_ollama(payload_str)
    except Exception as ex:
        logger.error(f"Analyst Call 1 failed for {agent.name}: {ex}")
        return {"decision": "HOLD", "confidence": 0, "reasoning": f"Analyst query error: {ex}"}
        
    # Standardize output contract parameters (Layer 3)
    decision["trailing_stop"] = decision.get("trailing_stop", 0.01)
    decision["partial_exit_1"] = decision.get("partial_exit_1", {"price": None, "qty_pct": 50})
    decision["invalidation_condition"] = decision.get("invalidation_condition", "Close below VWAP")
    decision["signal_expiry"] = decision.get("signal_expiry", "14:00")
    decision["checklist"] = decision.get("checklist", {
        "no_earnings_within_3_days": True,
        "volume_ratio_confirmed": True,
        "vix_within_limit": True,
        "not_chasing_3pct_move": True
    })
    
    # 2. CALL 2: Devil's Advocate (Multi-Model Validation - Layer 5)
    if decision.get("decision") in ["BUY", "SHORT"] and decision.get("confidence", 0) >= 65:
        logger.info(f"Initiating Devil's Advocate check for {agent.name} on {opportunity.get('symbol')}...")
        objection_prompt = f"""You are the Devil's Advocate for TradeOS.
Your sole job is to criticize the following proposed trade decision and find every reason it could fail.

PROPOSED DECISION:
{json.dumps(decision, indent=2, default=str)}

TECHNICAL, FUNDAMENTAL & DERIVATIVES PAYLOAD:
{payload_str}

CRITIQUE REQUIREMENTS:
1. Rate your disagreement with this trade on a scale from 0 to 10 (where 0 means perfect agreement, and 10 means extremely dangerous/terrible idea).
2. List 2-3 specific technical, fundamental, or derivatives objections.

You MUST respond with ONLY a valid JSON object — no markdown, no explanation text, no code blocks.

RESPONSE FORMAT (strict JSON):
{{
    "disagreement_score": <integer 0-10>,
    "objections": ["<objection 1>", "<objection 2>"]
}}
"""
        from database.models import SystemRule
        da_db = SessionLocal()
        threshold = 8.0
        try:
            rule = da_db.query(SystemRule).filter(SystemRule.key == "devils_advocate_veto_threshold").first()
            if rule and rule.numeric_value is not None:
                threshold = float(rule.numeric_value)
        except Exception as dbe:
            logger.warning(f"Failed to query devils_advocate_veto_threshold: {dbe}")
        finally:
            da_db.close()

        try:
            critique = {"disagreement_score": 0, "objections": []}
            if agent.provider == "google":
                critique = await query_gemini(objection_prompt)
            elif agent.provider == "groq":
                critique = await query_groq(objection_prompt)
            elif agent.provider == "github":
                critique = await query_github(objection_prompt)
            elif agent.provider == "huggingface":
                critique = await query_huggingface(objection_prompt)
            elif agent.provider == "ollama":
                critique = await query_ollama(objection_prompt)
                
            score = critique.get("disagreement_score", 0) if isinstance(critique, dict) else 0
            objections = critique.get("objections", []) if isinstance(critique, dict) else []
            
            logger.info(f"Devil's Advocate Disagreement Score for {agent.name}: {score}/10")
            if score >= threshold:
                logger.warning(f"Devil's Advocate OVERRIDE for {agent.name} due to score {score} >= {threshold}. Objections: {objections}")
                decision["decision"] = "HOLD"
                decision["confidence"] = 40
                decision["reasoning"] = f"OVERRULED by Devil's Advocate (Disagreement {score}/10): " + "; ".join(objections)
        except Exception as ex:
            logger.warning(f"Devil's Advocate call failed: {ex}. Proceeding with original decision.")
            
    return decision





async def execute_all_agents(
    market_context: dict,
    opportunity: dict,
    news: list,
    execute_trades: bool = True
) -> list[dict]:
    """
    Sends payload to agents and optionally executes trades through Risk/Broker.
    """
    db = SessionLocal()
    from broker.risk_manager import RiskManager
    from broker.virtual_broker import VirtualBroker
    from config import settings
    
    risk_manager = RiskManager(settings)
    broker = VirtualBroker(settings)

    try:
        agents = db.query(Agent).filter(Agent.is_active == True).all()
        if not agents: return []

        # Dynamic Layer 2 Option Greeks & Net Inflows
        from data.market_fetcher import fetch_option_greeks_and_fii, calculate_market_regime
        options_greeks = fetch_option_greeks_and_fii(opportunity.get("symbol"))
        opportunity["options_greeks"] = options_greeks
        
        # Dynamic Layer 1 Nifty Regime
        market_regime = calculate_market_regime()
        market_context["market_regime"] = market_regime

        agent_states = {}
        for agent in agents:
            from database.models import AgentDailyStrategy, Trade
            from datetime import date
            strategy = db.query(AgentDailyStrategy).filter(
                AgentDailyStrategy.agent_id == agent.id,
                AgentDailyStrategy.symbol == opportunity.get("symbol"),
                AgentDailyStrategy.date == date.today()
            ).first()
            
            pre_market_data = {}
            if strategy:
                pre_market_data = {
                    "daily_bias": strategy.daily_bias,
                    "entry_lower_limit": strategy.entry_lower_limit,
                    "entry_upper_limit": strategy.entry_upper_limit,
                    "target_price": strategy.target_price,
                    "stop_loss": strategy.stop_loss,
                    "reasoning": strategy.reasoning
                }

            # Layer 6: Dynamic Post-trade feedback loops (Last 5 closed trades)
            closed_trades = db.query(Trade).filter(
                Trade.agent_id == agent.id,
                Trade.status == "CLOSED"
            ).order_by(Trade.exit_time.desc()).limit(5).all()
            
            recent_perf_str = ""
            if closed_trades:
                recent_perf_str += "\n\nRECENT PERFORMANCE (last 5 closed trades for your model):\n"
                for t in closed_trades:
                    outcome = "WIN" if (t.pnl and t.pnl > 0) else "LOSS"
                    recent_perf_str += f"- Trade {t.id} on {t.symbol}: {t.decision} at {t.entry_price}, exit at {t.exit_price}. Outcome: {outcome} (PnL: ₹{t.pnl:.2f}).\n"
                recent_perf_str += "Adjust your entry threshold: require higher confluence and PCR support if recent performance is sub-optimal."

            agent_states[agent.name] = {
                "agent_name": agent.name,
                "cash_balance": agent.cash_balance,
                "initial_capital": settings.INITIAL_CAPITAL,
                "positions_count": len(agent.positions),
                "today_trades_count": len([
                    t for t in agent.trades
                    if t.entry_time and t.entry_time.date() == datetime.utcnow().date()
                ]),
                "today_pnl": 0.0,
                "total_pnl": agent.total_pnl,
                "open_symbols": [p.symbol for p in agent.positions],
                "pre_market_strategy": pre_market_data,
                "recent_performance_feedback": recent_perf_str
            }

        tasks = []
        agent_names = []
        ignore_hours = opportunity.get("ignore_hours", False)
        for agent in agents:
            # OPTIMIZATION: If this model has already executed maximum trades for this stock today,
            # skip the LLM API call entirely to save API credits and request limits!
            from database.models import Trade, SystemRule
            from datetime import date
            today_start = datetime.combine(date.today(), datetime.min.time())
            
            stock_trades_today = db.query(Trade).filter(
                Trade.agent_id == agent.id,
                Trade.symbol == opportunity.get("symbol"),
                Trade.entry_time >= today_start
            ).count()
            
            rule = db.query(SystemRule).filter(SystemRule.key == "max_trades_per_stock_daily").first()
            max_stock_trades = int(rule.numeric_value) if rule else 5
            
            if not ignore_hours and stock_trades_today >= max_stock_trades:
                logger.info(f"Skipping LLM API query for {agent.name} on {opportunity.get('symbol')} - already traded {stock_trades_today} today.")
                continue

            payload_dict = json.loads(build_ai_payload(market_context, opportunity, news, agent_states[agent.name]))
            
            # Query Sequential Multi-Model Pipeline (Layer 5)
            tasks.append(query_agent_pipeline(agent, payload_dict, opportunity))
            agent_names.append((agent.name, agent.id, json.dumps(payload_dict)))

        if not tasks: return []
        results = await asyncio.gather(*tasks, return_exceptions=True)

        decisions = []
        for i, result in enumerate(results):
            agent_name, agent_id, input_payload = agent_names[i]
            decision = result if not isinstance(result, Exception) else {"decision": "HOLD", "reasoning": str(result)}
            decision["agent_id"] = agent_id
            decision["agent"] = agent_name
            decision["ignore_hours"] = ignore_hours


            # Save AI response
            ai_response = AIResponse(
                agent_id=agent_id,
                cycle_id=market_context.get("cycle_id", "cycle"),
                symbol=opportunity.get("symbol", "UNKNOWN"),
                input_payload=input_payload[:5000],
                raw_response=json.dumps(decision)[:5000],
                decision=decision.get("decision", "HOLD"),
                confidence=decision.get("confidence", 0),
                is_valid=decision.get("is_valid", False)
            )
            db.add(ai_response)

            # --- EXECUTION LOGIC ---
            if execute_trades and decision.get("decision") in ["BUY", "SHORT"]:
                agent = db.query(Agent).get(agent_id)
                # Risk Validation
                risk_res = risk_manager.validate_trade(decision, agent_states[agent.name])
                if risk_res["approved"]:
                    current_price = opportunity.get("indicators", {}).get("price")
                    if not current_price:
                        # Defensive Fallback: fetch live price
                        from data.market_fetcher import fetch_live_price
                        try:
                            current_price = fetch_live_price(opportunity["symbol"]).get("price")
                        except Exception:
                            current_price = decision.get("entry_price")

                    trade_type = decision.get("trade_type", "INTRADAY")
                    position_type = decision.get("position_type", "LONG" if decision["decision"] == "BUY" else "SHORT")
                    if decision["decision"] == "BUY":
                        broker.buy(agent, opportunity["symbol"], decision["quantity"], 
                                   current_price, decision["stop_loss"], 
                                   decision["target"], decision["confidence"], trade_type, db, position_type)
                    elif decision["decision"] == "SHORT":
                        broker.short_sell(agent, opportunity["symbol"], decision["quantity"], 
                                          current_price, decision["stop_loss"], 
                                          decision["target"], decision["confidence"], db, trade_type, position_type)
                else:
                    logger.warning(f"Trade REJECTED for {agent_name}: {risk_res['rejection_reason']}")

            decisions.append(decision)
        
        db.commit()
        return decisions
    except Exception as e:
        logger.error(f"Executor error: {e}")
        db.rollback()
        return []
    finally:
        db.close()

