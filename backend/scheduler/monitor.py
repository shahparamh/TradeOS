from sqlalchemy.orm import Session
from database.models import Position, Trade, Agent
from data.market_fetcher import fetch_live_price
from broker.virtual_broker import VirtualBroker
from config import settings
from utils.logger import setup_logger

logger = setup_logger("position_monitor")

class PositionMonitor:
    def __init__(self, db: Session):
        self.db = db
        self.broker = VirtualBroker(settings)

    async def check_all_positions(self):
        """Checks all open positions against SL/TP levels."""
        positions = self.db.query(Position).all()
        if not positions:
            return []

        results = []
        for pos in positions:
            try:
                # 1. Fetch current price
                price_data = fetch_live_price(pos.symbol)
                current_price = price_data.get("price")
                if not current_price:
                    continue

                # 2. Check exit conditions
                exit_reason = None
                
                if pos.position_type == "LONG":
                    if current_price <= pos.stop_loss:
                        exit_reason = "SL_HIT"
                    elif current_price >= pos.target_price:
                        exit_reason = "TARGET_HIT"
                else: # SHORT
                    if current_price >= pos.stop_loss:
                        exit_reason = "SL_HIT"
                    elif current_price <= pos.target_price:
                        exit_reason = "TARGET_HIT"

                # 3. Execute exit if needed
                if exit_reason:
                    agent = self.db.query(Agent).get(pos.agent_id)
                    trade = self.db.query(Trade).get(pos.trade_id)
                    
                    if exit_reason == "SL_HIT":
                        logger.warning(f"🛑 SL HIT for {pos.symbol} at {current_price}")
                    else:
                        logger.info(f"🎯 TARGET HIT for {pos.symbol} at {current_price}")

                    if pos.position_type == "LONG":
                        res = self.broker.sell(agent, trade, current_price, exit_reason, self.db)
                    else:
                        res = self.broker.cover(agent, trade, current_price, exit_reason, self.db)
                    
                    results.append({
                        "symbol": pos.symbol,
                        "agent": agent.name,
                        "exit_reason": exit_reason,
                        "pnl": res.get("net_pnl")
                    })
                    
                # Update current price in DB for dashboard
                pos.current_price = current_price
                
            except Exception as e:
                logger.error(f"Error monitoring {pos.symbol}: {e}")
        
        self.db.commit()
        return results
