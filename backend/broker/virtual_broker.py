"""
TradeOS — Virtual Broker
Simulates trade execution with slippage and brokerage costs.
"""

from datetime import datetime
from database.models import Trade, Position, Agent
from utils.logger import setup_logger
from utils.helpers import get_ist_now

logger = setup_logger("virtual_broker")

class VirtualBroker:
    def __init__(self, settings):
        self.brokerage_pct = settings.BROKERAGE_PERCENT    # 0.0003
        self.slippage_pct = settings.SLIPPAGE_PERCENT      # 0.0005

    def buy(self, agent, symbol: str, quantity: int, market_price: float, 
            stop_loss: float, target: float, confidence: int, 
            trade_type: str, db_session) -> dict:
        """Executes a LONG entry."""
        # 1. Apply slippage (buy higher)
        fill_price = market_price * (1 + self.slippage_pct)
        
        # 2. Calculate brokerage
        brokerage = fill_price * quantity * self.brokerage_pct
        total_cost = (fill_price * quantity) + brokerage
        
        if agent.cash_balance < total_cost:
             return {"success": False, "error": "Insufficient cash balance"}

        # 3. Deduct cash
        agent.cash_balance -= total_cost
        
        # 4. Create Trade record
        trade = Trade(
            agent_id=agent.id,
            symbol=symbol,
            action="BUY",
            trade_type=trade_type,
            position_type="LONG",
            quantity=quantity,
            entry_price=round(fill_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            brokerage=round(brokerage, 2),
            slippage=round(fill_price - market_price, 2),
            status="OPEN",
            confidence=confidence,
            entry_time=get_ist_now()
        )
        db_session.add(trade)
        db_session.flush() # Get trade.id

        # 5. Create Position record
        position = Position(
            agent_id=agent.id,
            trade_id=trade.id,
            symbol=symbol,
            trade_type=trade_type,
            position_type="LONG",
            quantity=quantity,
            entry_price=round(fill_price, 2),
            current_price=round(fill_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            opened_at=get_ist_now()
        )
        db_session.add(position)
        
        logger.info(f"LONG Position opened for agent {agent.name}: {quantity} {symbol} @ {fill_price:.2f}")
        return {
            "success": True,
            "trade_id": trade.id,
            "fill_price": fill_price,
            "total_cost": total_cost,
            "brokerage": brokerage
        }

    def sell(self, agent, trade, current_market_price: float, exit_reason: str, db_session) -> dict:
        """Closes a LONG position."""
        # 1. Apply slippage (sell lower)
        fill_price = current_market_price * (1 - self.slippage_pct)
        
        # 2. Calculate exit brokerage
        exit_brokerage = fill_price * trade.quantity * self.brokerage_pct
        
        # 3. Calculate PnL
        gross_pnl = (fill_price - trade.entry_price) * trade.quantity
        net_pnl = gross_pnl - trade.brokerage - exit_brokerage
        
        # 4. Add proceeds to cash
        proceeds = (fill_price * trade.quantity) - exit_brokerage
        agent.cash_balance += proceeds
        agent.total_pnl += net_pnl
        
        # 5. Update Trade record
        trade.exit_price = round(fill_price, 2)
        trade.pnl = round(net_pnl, 2)
        trade.status = exit_reason
        trade.exit_time = get_ist_now()
        
        # 6. Delete Position
        position = db_session.query(Position).filter(Position.trade_id == trade.id).first()
        if position:
            db_session.delete(position)
            
        logger.info(f"LONG Position closed for agent {agent.name}: {trade.symbol} @ {fill_price:.2f} (Reason: {exit_reason}, PnL: {net_pnl:.2f})")
        return {
            "success": True,
            "net_pnl": net_pnl,
            "fill_price": fill_price
        }

    def short_sell(self, agent, symbol: str, quantity: int, market_price: float, 
                   stop_loss: float, target: float, confidence: int, db_session) -> dict:
        """Executes a SHORT entry."""
        # 1. Apply slippage (sell lower)
        fill_price = market_price * (1 - self.slippage_pct)
        
        # 2. Calculate brokerage
        brokerage = fill_price * quantity * self.brokerage_pct
        margin_required = fill_price * quantity
        
        if agent.cash_balance < (margin_required + brokerage):
             return {"success": False, "error": "Insufficient margin"}

        # 3. Deduct margin (fully blocked for simulation)
        agent.cash_balance -= (margin_required + brokerage)
        
        # 4. Create Trade record
        trade = Trade(
            agent_id=agent.id,
            symbol=symbol,
            action="SELL",
            trade_type="INTRADAY",
            position_type="SHORT",
            quantity=quantity,
            entry_price=round(fill_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            brokerage=round(brokerage, 2),
            slippage=round(market_price - fill_price, 2),
            status="OPEN",
            confidence=confidence,
            entry_time=get_ist_now()
        )
        db_session.add(trade)
        db_session.flush()

        # 5. Create Position record
        position = Position(
            agent_id=agent.id,
            trade_id=trade.id,
            symbol=symbol,
            trade_type="INTRADAY",
            position_type="SHORT",
            quantity=quantity,
            entry_price=round(fill_price, 2),
            current_price=round(fill_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            opened_at=get_ist_now()
        )
        db_session.add(position)
        
        logger.info(f"SHORT Position opened for agent {agent.name}: {quantity} {symbol} @ {fill_price:.2f}")
        return {"success": True, "trade_id": trade.id, "fill_price": fill_price}

    def cover(self, agent, trade, current_market_price: float, exit_reason: str, db_session) -> dict:
        """Closes a SHORT position."""
        # 1. Apply slippage (buy higher)
        fill_price = current_market_price * (1 + self.slippage_pct)
        
        # 2. Calculate exit brokerage
        exit_brokerage = fill_price * trade.quantity * self.brokerage_pct
        
        # 3. Calculate PnL
        gross_pnl = (trade.entry_price - fill_price) * trade.quantity
        net_pnl = gross_pnl - trade.brokerage - exit_brokerage
        
        # 4. Release margin and add PnL
        margin_released = trade.entry_price * trade.quantity
        agent.cash_balance += (margin_released + net_pnl)
        agent.total_pnl += net_pnl
        
        # 5. Update Trade record
        trade.exit_price = round(fill_price, 2)
        trade.pnl = round(net_pnl, 2)
        trade.status = exit_reason
        trade.exit_time = get_ist_now()
        
        # 6. Delete Position
        position = db_session.query(Position).filter(Position.trade_id == trade.id).first()
        if position:
            db_session.delete(position)
            
        logger.info(f"SHORT Position closed for agent {agent.name}: {trade.symbol} @ {fill_price:.2f} (Reason: {exit_reason}, PnL: {net_pnl:.2f})")
        return {"success": True, "net_pnl": net_pnl, "fill_price": fill_price}
