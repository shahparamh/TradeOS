"""
TradeOS — Agent Executor
Runs all AI agents concurrently with identical data for fair comparison.
"""

import asyncio
import json
from datetime import datetime
from agents.gemini_agent import query_gemini
from agents.groq_agent import query_groq
from agents.prompts import build_ai_payload
from database.connection import SessionLocal
from database.models import Agent, AIResponse
from utils.logger import setup_logger

from agents.openrouter_agent import query_openrouter_free
from agents.deepseek_agent import query_deepseek
from agents.ollama_agent import query_ollama

logger = setup_logger("agent_executor")





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

        agent_states = {}
        for agent in agents:
            from database.models import AgentDailyStrategy
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

            agent_states[agent.name] = {
                "agent_name": agent.name,
                "cash_balance": agent.cash_balance,
                "initial_capital": settings.INITIAL_CAPITAL,
                "positions_count": len(agent.positions),
                "today_trades_count": len([
                    t for t in agent.trades
                    if t.entry_time and t.entry_time.date() == datetime.utcnow().date()
                ]),
                "today_pnl": 0.0, # Simplified for now
                "total_pnl": agent.total_pnl,
                "open_symbols": [p.symbol for p in agent.positions],
                "pre_market_strategy": pre_market_data
            }

        tasks = []
        agent_names = []
        for agent in agents:
            payload = build_ai_payload(market_context, opportunity, news, agent_states[agent.name])
            if agent.provider == "google":
                tasks.append(query_gemini(payload))
                agent_names.append(("Gemini", agent.id, payload))
            elif agent.provider == "groq":
                tasks.append(query_groq(payload))
                agent_names.append(("Groq-Llama", agent.id, payload))
            elif agent.provider == "openrouter":
                tasks.append(query_openrouter_free(payload))
                agent_names.append((agent.name, agent.id, payload))
            elif agent.provider == "deepseek":
                tasks.append(query_deepseek(payload))
                agent_names.append((agent.name, agent.id, payload))
            elif agent.provider == "ollama":
                tasks.append(query_ollama(payload))
                agent_names.append((agent.name, agent.id, payload))




        if not tasks: return []
        results = await asyncio.gather(*tasks, return_exceptions=True)

        decisions = []
        for i, result in enumerate(results):
            agent_name, agent_id, input_payload = agent_names[i]
            decision = result if not isinstance(result, Exception) else {"decision": "HOLD", "reasoning": str(result)}
            decision["agent_id"] = agent_id
            decision["agent"] = agent_name


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

                    if decision["decision"] == "BUY":
                        broker.buy(agent, opportunity["symbol"], decision["quantity"], 
                                   current_price, decision["stop_loss"], 
                                   decision["target"], decision["confidence"], "INTRADAY", db)
                    elif decision["decision"] == "SHORT":
                        broker.short_sell(agent, opportunity["symbol"], decision["quantity"], 
                                          current_price, decision["stop_loss"], 
                                          decision["target"], decision["confidence"], db)
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

