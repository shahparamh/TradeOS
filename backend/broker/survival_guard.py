"""
TradeOS — Survival Guard
Watches Survival Arena agents for the death threshold and force-closes them when hit.
Runs as part of the existing position-monitor cadence (every 2 minutes).
"""

from datetime import datetime
from database.models import Agent, Position, Trade
from utils.logger import setup_logger
from utils.helpers import get_ist_now

logger = setup_logger("survival_guard")


def check_deaths(db, broker) -> list[dict]:
    """Marks any Survival Arena agent whose equity has hit its death threshold as dead,
    force-closing all of its open positions first. Returns a list of death events."""
    events = []
    agents = db.query(Agent).filter(
        Agent.mode == "SURVIVAL",
        Agent.is_dead == False,  # noqa: E712
    ).all()

    for agent in agents:
        if agent.death_threshold is None:
            continue

        positions = db.query(Position).filter(Position.agent_id == agent.id).all()
        equity = agent.cash_balance + sum(p.unrealized_pnl or 0.0 for p in positions)

        if equity > agent.death_threshold:
            continue

        logger.warning(f"AGENT DEATH: {agent.name} equity ₹{equity:.2f} <= death threshold ₹{agent.death_threshold:.2f}. Force-closing all positions.")

        for pos in positions:
            trade = db.query(Trade).get(pos.trade_id)
            if not trade:
                continue
            try:
                broker.close_position(agent, trade, pos.current_price or pos.entry_price, "AGENT_DEATH", db)
            except Exception as e:
                logger.error(f"Failed to force-close position {pos.symbol} for dying agent {agent.name}: {e}")

        agent.is_dead = True
        agent.died_at = get_ist_now()
        events.append({"agent": agent.name, "agent_id": agent.id, "final_equity": equity})

    if events:
        db.commit()

    return events
