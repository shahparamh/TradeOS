"""
TradeOS — Position Monitor
Actively watches open positions for stop-loss, target, and intraday square-off.
"""

from database.models import Position, Trade, Agent
from data.market_fetcher import fetch_live_price
from utils.logger import setup_logger
from utils.helpers import get_ist_now

logger = setup_logger("position_monitor")

class PositionMonitor:
    def __init__(self, broker):
        self.broker = broker

    async def check_all_positions(self, db_session) -> list[dict]:
        """Runs the monitoring loop for all open positions."""
        positions = db_session.query(Position).all()
        actions = []

        for pos in positions:
            try:
                # 1. Fetch live price
                price_data = fetch_live_price(pos.symbol)
                if not price_data:
                    continue
                
                current_price = price_data["price"]
                
                # 2. Evaluate exit conditions
                exit_reason = self._evaluate_exit(pos, current_price)
                
                if exit_reason:
                    # 3. Execute closure
                    agent = db_session.query(Agent).get(pos.agent_id)
                    trade = db_session.query(Trade).get(pos.trade_id)
                    
                    if pos.position_type == "LONG":
                        result = self.broker.sell(agent, trade, current_price, exit_reason, db_session)
                    else:
                        result = self.broker.cover(agent, trade, current_price, exit_reason, db_session)
                    
                    actions.append({
                        "symbol": pos.symbol,
                        "agent": agent.name,
                        "action": "CLOSED",
                        "reason": exit_reason,
                        "pnl": result.get("net_pnl")
                    })
                else:
                    # 4. Update unrealized PnL
                    self._update_unrealized_pnl(pos, current_price)
                    
            except Exception as e:
                logger.error(f"Error monitoring position {pos.symbol} (ID: {pos.id}): {str(e)}")

        if actions:
            db_session.commit()
            
        return actions

    def _evaluate_exit(self, position, current_price: float) -> str | None:
        """Determines if a position should be closed."""
        now = get_ist_now()
        
        # 1. Intraday Square-off (3:15 PM IST)
        if position.trade_type == "INTRADAY" or True: # Force check for all during simulation
            if now.hour >= 15 and now.minute >= 15:
                return "SQUARED_OFF"

        # 2. LONG Position Logic
        if position.position_type == "LONG":
            if current_price >= position.target_price:
                return "TARGET_HIT"
            if current_price <= position.stop_loss:
                return "SL_HIT"

        # 3. SHORT Position Logic
        elif position.position_type == "SHORT":
            if current_price <= position.target_price:
                return "TARGET_HIT"
            if current_price >= position.stop_loss:
                return "SL_HIT"

        return None

    def _update_unrealized_pnl(self, position, current_price: float):
        """Updates the unrealized PnL in the database."""
        if position.position_type == "LONG":
            position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
        else:
            position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
        
        position.current_price = current_price
