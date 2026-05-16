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

logger = setup_logger("agent_executor")


async def execute_all_agents(
    market_context: dict,
    opportunity: dict,
    news: list,
) -> list[dict]:
    """
    Sends the IDENTICAL payload to all active AI agents concurrently.
    Returns a list of parsed decisions from each agent.
    """
    db = SessionLocal()

    try:
        # Get agent states from DB
        agents = db.query(Agent).filter(Agent.is_active == True).all()

        if not agents:
            logger.warning("No active agents found in database.")
            return []

        # Build the single payload that ALL agents receive
        # Use the first agent's state as a template — each agent gets their own state
        agent_states = {}
        for agent in agents:
            open_positions = len([p for p in agent.positions])
            today_trades = len([
                t for t in agent.trades
                if t.entry_time and t.entry_time.date() == datetime.utcnow().date()
            ])

            agent_states[agent.name] = {
                "cash_balance": agent.cash_balance,
                "open_positions": open_positions,
                "today_trades": today_trades,
                "today_pnl": 0,  # Will calculate from daily_performance later
                "total_pnl": agent.total_pnl,
            }

        # Create tasks — each agent gets the same market data but their own portfolio state
        tasks = []
        agent_names = []

        for agent in agents:
            payload = build_ai_payload(
                market_context=market_context,
                opportunity=opportunity,
                news=news,
                agent_state=agent_states[agent.name],
            )

            if agent.provider == "google":
                tasks.append(query_gemini(payload))
                agent_names.append(("Gemini", agent.id, payload))
            elif agent.provider == "groq":
                tasks.append(query_groq(payload))
                agent_names.append(("Groq-Llama", agent.id, payload))
            else:
                logger.warning(f"Unknown provider {agent.provider} for agent {agent.name}, skipping.")

        if not tasks:
            logger.warning("No tasks to execute.")
            return []

        # Execute ALL agents concurrently — this is the fairness guarantee
        logger.info(f"Querying {len(tasks)} AI agents concurrently...")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and save to DB
        decisions = []
        for i, result in enumerate(results):
            agent_name, agent_id, input_payload = agent_names[i]

            if isinstance(result, Exception):
                logger.error(f"{agent_name} raised exception: {result}")
                decision = {
                    "agent": agent_name,
                    "decision": "HOLD",
                    "confidence": 0,
                    "reasoning": f"Exception: {str(result)}",
                    "is_valid": False,
                    "latency_ms": 0,
                    "raw_response": str(result),
                }
            else:
                decision = result

            decision["agent_id"] = agent_id

            # Save AI response to database
            ai_response = AIResponse(
                agent_id=agent_id,
                cycle_id=market_context.get("cycle_id", "manual"),
                symbol=opportunity.get("symbol", "UNKNOWN"),
                input_payload=input_payload[:5000],  # Truncate for DB
                raw_response=decision.get("raw_response", "")[:5000],
                parsed_decision=json.dumps(decision, default=str)[:5000],
                decision=decision.get("decision", "HOLD"),
                confidence=decision.get("confidence", 0),
                latency_ms=decision.get("latency_ms", 0),
                is_valid=decision.get("is_valid", False),
                error_message="; ".join(decision.get("validation_errors", []))[:500] if decision.get("validation_errors") else None,
            )
            db.add(ai_response)

            decisions.append(decision)
            logger.info(
                f"  [{agent_name}]: {decision.get('decision')} "
                f"(confidence: {decision.get('confidence', 'N/A')}, "
                f"valid: {decision.get('is_valid')}, "
                f"latency: {decision.get('latency_ms')}ms)"
            )

        db.commit()
        return decisions

    except Exception as e:
        logger.error(f"Agent executor error: {str(e)}", exc_info=True)
        db.rollback()
        return []
    finally:
        db.close()
