"""
TradeOS — End of Day Processor
Handles daily cleanup, performance tracking, and agent resets.
"""

from datetime import datetime
from database.models import Agent, Trade, Position, DailyPerformance
from utils.logger import setup_logger
from utils.helpers import get_ist_now

logger = setup_logger("eod_processor")

async def run_end_of_day(db_session):
    """
    Runs at 3:30 PM IST to finalize the day's results.
    """
    logger.info("Starting End-of-Day (EOD) processing...")
    
    agents = db_session.query(Agent).all()
    today = get_ist_now().date()
    
    for agent in agents:
        # 1. Calculate daily metrics
        today_trades = [t for t in agent.trades if t.entry_time and t.entry_time.date() == today]
        winning_trades = [t for t in today_trades if (t.pnl or 0) > 0]
        losing_trades = [t for t in today_trades if (t.pnl or 0) < 0]
        
        realized_pnl = sum(t.pnl or 0 for t in today_trades)
        unrealized_pnl = sum(p.unrealized_pnl or 0 for p in agent.positions)
        
        win_rate = (len(winning_trades) / len(today_trades)) if today_trades else 0
        
        # 2. Create performance snapshot
        perf = DailyPerformance(
            agent_id=agent.id,
            date=today,
            starting_capital=agent.cash_balance - realized_pnl, # Rough estimate
            ending_capital=agent.cash_balance,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_trades=len(today_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=round(win_rate, 2),
            max_drawdown=0.0 # To be implemented with high-water mark logic
        )
        db_session.add(perf)
        
        # 3. Reset daily counters if needed (consecutive losses reset only on profit)
        if realized_pnl > 0:
             # This would require adding consecutive_losses to Agent model if we want it persistent
             pass
             
        logger.info(f"EOD for {agent.name}: PnL={realized_pnl:.2f}, Trades={len(today_trades)}")

    db_session.commit()
    logger.info("EOD processing complete.")
