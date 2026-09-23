"""
TradeOS — Position Monitor
Actively watches open positions for stop-loss, target, and intraday square-off.
"""

from database.models import Position, Trade, Agent
from data.market_fetcher import fetch_bulk_prices_cached
from market_data.factory import get_provider
from market_data.base import MarketDataError
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

        if not positions:
            return actions

        # Batch-fetch current prices per market — IN via the existing yfinance-backed
        # cache, US via the Alpaca provider — instead of one round trip per open position.
        by_market: dict[str, list] = {}
        for pos in positions:
            by_market.setdefault(getattr(pos, "market", "IN") or "IN", []).append(pos)

        prices = {}
        in_symbols = tuple(sorted({p.symbol for p in by_market.get("IN", [])}))
        if in_symbols:
            prices.update(fetch_bulk_prices_cached(in_symbols))

        us_symbols = tuple(sorted({p.symbol for p in by_market.get("US", [])}))
        if us_symbols:
            try:
                us_quotes = get_provider("US").get_bulk_quotes(us_symbols)
                for sym, q in us_quotes.items():
                    if q.get("price") is not None:
                        prices[sym] = {"price": q["price"], "volume": q.get("volume", 0)}
            except MarketDataError as e:
                logger.warning(f"US position monitor price fetch skipped: {e.code} {e.message}")

        for pos in positions:
            try:
                # 1. Look up the batch-fetched live price of the underlying asset
                price_data = prices.get(pos.symbol)
                if not price_data:
                    continue

                current_price = price_data["price"]
                
                # 2. Evaluate exit conditions based on underlying price
                exit_reason = self._evaluate_exit(pos, current_price)
                
                if exit_reason:
                    # 3. Execute closure
                    agent = db_session.query(Agent).get(pos.agent_id)
                    trade = db_session.query(Trade).get(pos.trade_id)
                    
                    result = self.broker.close_position(agent, trade, current_price, exit_reason, db_session)
                    
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
        """Determines if a position should be closed based on dynamic SL/Target rules."""
        now = get_ist_now()
        position_market = getattr(position, "market", "IN") or "IN"

        # 1. Intraday Square-off (3:15 PM IST) — IN only. US intraday square-off would need
        # its own America/New_York cutoff; not wired up yet, so US INTRADAY positions are
        # only closed by SL/target below until that's added.
        if position.trade_type == "INTRADAY" and position_market == "IN":
            # Only trigger intraday square-off if the position was opened before 3:15 PM
            # and current time is past 3:15 PM. This allows testing positions created during off-hours.
            if position.opened_at:
                import pytz
                from utils.helpers import IST
                opened_at_utc = pytz.utc.localize(position.opened_at) if position.opened_at.tzinfo is None else position.opened_at.astimezone(pytz.utc)
                opened_at_ist = opened_at_utc.astimezone(IST)
                opened_after_cutoff = opened_at_ist.hour > 15 or (opened_at_ist.hour == 15 and opened_at_ist.minute >= 15)
                is_today = opened_at_ist.date() == now.date()
                if (now.hour == 15 and now.minute >= 15) or now.hour > 15:
                    if not (is_today and opened_after_cutoff):
                        return "SQUARED_OFF"
            else:
                if (now.hour == 15 and now.minute >= 15) or now.hour > 15:
                    return "SQUARED_OFF"

        # 2. Bullish positions (LONG, BUY_CE, SELL_PE)
        is_bullish = position.position_type in ["LONG", "BUY_CE", "SELL_PE"]
        
        if is_bullish:
            if position.target_price > 0 and current_price >= position.target_price:
                return "TARGET_HIT"
            if position.stop_loss > 0 and current_price <= position.stop_loss:
                return "SL_HIT"
        # 3. Bearish positions (SHORT, BUY_PE, SELL_CE)
        else:
            if position.target_price > 0 and current_price <= position.target_price:
                return "TARGET_HIT"
            if position.stop_loss > 0 and current_price >= position.stop_loss:
                return "SL_HIT"

        return None

    def _update_unrealized_pnl(self, position, current_price: float):
        """Updates the unrealized PnL in the database based on F&O contract math."""
        trade_type = position.trade_type
        position_type = position.position_type
        symbol = position.symbol
        quantity = position.quantity
        
        # Determine lot size
        lot_size = 1
        if trade_type in ["FUTURES", "OPTIONS"]:
            from broker.virtual_broker import get_lot_size
            lot_size = get_lot_size(symbol)
            
        if trade_type == "OPTIONS":
            entry_prem = position.entry_price * 0.02
            
            if position_type == "BUY_CE":
                exit_prem = max(0.0, entry_prem + (current_price - position.entry_price) * 0.5)
                position.unrealized_pnl = (exit_prem - entry_prem) * lot_size * quantity
            elif position_type == "BUY_PE":
                exit_prem = max(0.0, entry_prem + (position.entry_price - current_price) * 0.5)
                position.unrealized_pnl = (exit_prem - entry_prem) * lot_size * quantity
            elif position_type == "SELL_CE":
                exit_prem = max(0.0, entry_prem + (current_price - position.entry_price) * 0.5)
                position.unrealized_pnl = (entry_prem - exit_prem) * lot_size * quantity
            elif position_type == "SELL_PE":
                exit_prem = max(0.0, entry_prem + (position.entry_price - current_price) * 0.5)
                position.unrealized_pnl = (entry_prem - exit_prem) * lot_size * quantity
                
        elif trade_type == "FUTURES":
            if position_type == "LONG":
                position.unrealized_pnl = (current_price - position.entry_price) * lot_size * quantity
            else:  # SHORT
                position.unrealized_pnl = (position.entry_price - current_price) * lot_size * quantity
                
        else:  # Equity
            if position_type == "LONG":
                position.unrealized_pnl = (current_price - position.entry_price) * quantity
            else:
                position.unrealized_pnl = (position.entry_price - current_price) * quantity
        
        position.current_price = current_price
