"""
TradeOS — Virtual Broker
Simulates trade execution with slippage and brokerage costs. Supports Equity, Futures, and Options.
"""

from datetime import datetime
from database.models import Trade, Position, Agent
from utils.helpers import get_ist_now
from utils.logger import setup_logger

logger = setup_logger("virtual_broker")

def get_lot_size(symbol: str) -> int:
    """Helper to determine standard F&O lot sizes."""
    if "NSEI" in symbol:
        return 50
    elif "NSEBANK" in symbol:
        return 15
    else:
        return 100  # Default stock lot size proxy

class VirtualBroker:
    def __init__(self, settings):
        self.brokerage_pct = settings.BROKERAGE_PERCENT    # 0.0003
        self.slippage_pct = settings.SLIPPAGE_PERCENT      # 0.0005

    def buy(self, agent, symbol: str, quantity: int, market_price: float, 
            stop_loss: float, target: float, confidence: int, 
            trade_type: str, db_session, position_type: str = "LONG") -> dict:
        """Executes a LONG/BUY entry for Equity, Futures, or Options."""
        # 1. Apply slippage (buy higher)
        fill_price = market_price * (1 + self.slippage_pct)
        
        # Get lot size
        lot_size = 1
        if trade_type in ["FUTURES", "OPTIONS"]:
            lot_size = get_lot_size(symbol)
            
        # 2. Calculate entry cost / margin
        entry_price = round(fill_price, 2)
        total_cost = 0.0
        brokerage = 0.0
        
        if trade_type == "OPTIONS":
            # For options, entry_price is the underlying spot price. 
            # Premium is entry_price * 0.02.
            premium = entry_price * 0.02
            brokerage = premium * lot_size * quantity * self.brokerage_pct
            
            if position_type in ["BUY_CE", "BUY_PE"]:
                total_cost = (premium * lot_size * quantity) + brokerage
            elif position_type in ["SELL_CE", "SELL_PE"]:
                margin = entry_price * lot_size * quantity * 0.15
                premium_val = premium * lot_size * quantity
                total_cost = margin - premium_val + brokerage
                
        elif trade_type == "FUTURES":
            margin = entry_price * lot_size * quantity * 0.10
            brokerage = entry_price * lot_size * quantity * self.brokerage_pct
            total_cost = margin + brokerage
            
        else:  # Equity LONG
            brokerage = entry_price * quantity * self.brokerage_pct
            total_cost = (entry_price * quantity) + brokerage
            
        if agent.cash_balance < total_cost:
             return {"success": False, "error": f"Insufficient balance/margin. Required: ₹{total_cost:,.2f}"}

        # 3. Deduct cash
        agent.cash_balance -= total_cost
        
        # 4. Create Trade record
        trade = Trade(
            agent_id=agent.id,
            symbol=symbol,
            action="BUY",
            trade_type=trade_type,
            position_type=position_type,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            brokerage=round(brokerage, 2),
            slippage=round(fill_price - market_price, 2),
            status="OPEN",
            confidence=confidence,
            market=getattr(agent, "market", "IN") or "IN",
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
            position_type=position_type,
            quantity=quantity,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            market=getattr(agent, "market", "IN") or "IN",
            opened_at=get_ist_now()
        )
        db_session.add(position)
        
        logger.info(f"Position opened for agent {agent.name}: {quantity} lots/shares {symbol} ({position_type}) @ {entry_price}")
        return {
            "success": True,
            "trade_id": trade.id,
            "fill_price": entry_price,
            "total_cost": total_cost,
            "brokerage": brokerage
        }

    def short_sell(self, agent, symbol: str, quantity: int, market_price: float, 
                   stop_loss: float, target: float, confidence: int, db_session,
                   trade_type: str = "INTRADAY", position_type: str = "SHORT") -> dict:
        """Executes a SHORT/SELL entry for Equity, Futures, or Options."""
        # 1. Apply slippage (sell lower)
        fill_price = market_price * (1 - self.slippage_pct)
        
        # Get lot size
        lot_size = 1
        if trade_type in ["FUTURES", "OPTIONS"]:
            lot_size = get_lot_size(symbol)
            
        entry_price = round(fill_price, 2)
        total_cost = 0.0
        brokerage = 0.0
        
        if trade_type == "OPTIONS":
            # For options, entry_price is the underlying spot price. 
            # Premium is entry_price * 0.02.
            premium = entry_price * 0.02
            brokerage = premium * lot_size * quantity * self.brokerage_pct
            
            if position_type in ["SELL_CE", "SELL_PE"]:
                margin = entry_price * lot_size * quantity * 0.15
                premium_val = premium * lot_size * quantity
                total_cost = margin - premium_val + brokerage
            elif position_type in ["BUY_CE", "BUY_PE"]:
                total_cost = (premium * lot_size * quantity) + brokerage
                
        elif trade_type == "FUTURES":
            margin = entry_price * lot_size * quantity * 0.10
            brokerage = entry_price * lot_size * quantity * self.brokerage_pct
            total_cost = margin + brokerage
            
        else:  # Equity SHORT
            brokerage = entry_price * quantity * self.brokerage_pct
            margin_required = entry_price * quantity
            total_cost = margin_required + brokerage
            
        if agent.cash_balance < total_cost:
             return {"success": False, "error": f"Insufficient balance/margin. Required: ₹{total_cost:,.2f}"}

        # 3. Deduct cash
        agent.cash_balance -= total_cost
        
        # 4. Create Trade record
        trade = Trade(
            agent_id=agent.id,
            symbol=symbol,
            action="SELL",
            trade_type=trade_type,
            position_type=position_type,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            brokerage=round(brokerage, 2),
            slippage=round(market_price - fill_price, 2),
            status="OPEN",
            confidence=confidence,
            market=getattr(agent, "market", "IN") or "IN",
            entry_time=get_ist_now()
        )
        db_session.add(trade)
        db_session.flush()

        # 5. Create Position record
        position = Position(
            agent_id=agent.id,
            trade_id=trade.id,
            symbol=symbol,
            trade_type=trade_type,
            position_type=position_type,
            quantity=quantity,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=round(stop_loss, 2),
            target_price=round(target, 2),
            market=getattr(agent, "market", "IN") or "IN",
            opened_at=get_ist_now()
        )
        db_session.add(position)
        
        logger.info(f"Position opened for agent {agent.name}: {quantity} lots/shares {symbol} ({position_type}) @ {entry_price}")
        return {"success": True, "trade_id": trade.id, "fill_price": entry_price}

    def close_position(self, agent, trade, current_market_price: float, exit_reason: str, db_session) -> dict:
        """Closes any open position (Equity, Futures, or Options) and computes PnL / refunds cash."""
        trade_type = trade.trade_type or "INTRADAY"
        position_type = trade.position_type or "LONG"
        symbol = trade.symbol
        quantity = trade.quantity
        
        is_bullish = position_type in ["LONG", "BUY_CE", "SELL_PE"]
        if is_bullish:
            fill_price = current_market_price * (1 - self.slippage_pct)
        else:
            fill_price = current_market_price * (1 + self.slippage_pct)

        # Get lot size
        lot_size = 1
        if trade_type in ["FUTURES", "OPTIONS"]:
            lot_size = get_lot_size(symbol)
            
        net_pnl = 0.0
        exit_brokerage = 0.0
        refund_amount = 0.0
        
        if trade_type == "OPTIONS":
            entry_prem = trade.entry_price * 0.02
            
            if position_type == "BUY_CE":
                exit_prem = max(0.0, entry_prem + (fill_price - trade.entry_price) * 0.5)
                exit_brokerage = exit_prem * lot_size * quantity * self.brokerage_pct
                gross_pnl = (exit_prem - entry_prem) * lot_size * quantity
                net_pnl = gross_pnl - trade.brokerage - exit_brokerage
                refund_amount = (exit_prem * lot_size * quantity) - exit_brokerage
                
            elif position_type == "BUY_PE":
                exit_prem = max(0.0, entry_prem + (trade.entry_price - fill_price) * 0.5)
                exit_brokerage = exit_prem * lot_size * quantity * self.brokerage_pct
                gross_pnl = (exit_prem - entry_prem) * lot_size * quantity
                net_pnl = gross_pnl - trade.brokerage - exit_brokerage
                refund_amount = (exit_prem * lot_size * quantity) - exit_brokerage
                
            elif position_type == "SELL_CE":
                exit_prem = max(0.0, entry_prem + (fill_price - trade.entry_price) * 0.5)
                exit_brokerage = exit_prem * lot_size * quantity * self.brokerage_pct
                gross_pnl = (entry_prem - exit_prem) * lot_size * quantity
                net_pnl = gross_pnl - trade.brokerage - exit_brokerage
                margin_released = trade.entry_price * lot_size * quantity * 0.15
                premium_debited = exit_prem * lot_size * quantity
                refund_amount = margin_released - premium_debited - exit_brokerage
                
            elif position_type == "SELL_PE":
                exit_prem = max(0.0, entry_prem + (trade.entry_price - fill_price) * 0.5)
                exit_brokerage = exit_prem * lot_size * quantity * self.brokerage_pct
                gross_pnl = (entry_prem - exit_prem) * lot_size * quantity
                net_pnl = gross_pnl - trade.brokerage - exit_brokerage
                margin_released = trade.entry_price * lot_size * quantity * 0.15
                premium_debited = exit_prem * lot_size * quantity
                refund_amount = margin_released - premium_debited - exit_brokerage
                
        elif trade_type == "FUTURES":
            margin_released = trade.entry_price * lot_size * quantity * 0.10
            exit_brokerage = fill_price * lot_size * quantity * self.brokerage_pct
            
            if position_type == "LONG":
                gross_pnl = (fill_price - trade.entry_price) * lot_size * quantity
            else:  # SHORT
                gross_pnl = (trade.entry_price - fill_price) * lot_size * quantity
                
            net_pnl = gross_pnl - trade.brokerage - exit_brokerage
            refund_amount = margin_released + gross_pnl - exit_brokerage
            
        else:  # Equity
            exit_brokerage = fill_price * quantity * self.brokerage_pct
            if position_type == "LONG":
                gross_pnl = (fill_price - trade.entry_price) * quantity
                net_pnl = gross_pnl - trade.brokerage - exit_brokerage
                refund_amount = (fill_price * quantity) - exit_brokerage
            else:  # SHORT
                gross_pnl = (trade.entry_price - fill_price) * quantity
                net_pnl = gross_pnl - trade.brokerage - exit_brokerage
                margin_released = trade.entry_price * quantity
                refund_amount = margin_released + gross_pnl - exit_brokerage
                
        agent.cash_balance += refund_amount
        agent.total_pnl += net_pnl
        
        # Update Trade record
        trade.exit_price = round(fill_price, 2)
        trade.pnl = round(net_pnl, 2)
        trade.status = exit_reason
        trade.exit_time = get_ist_now()
        
        # Delete Position
        position = db_session.query(Position).filter(Position.trade_id == trade.id).first()
        if position:
            db_session.delete(position)
            
        logger.info(f"Position closed for agent {agent.name}: {trade.symbol} ({position_type}) @ {fill_price:.2f} (Reason: {exit_reason}, PnL: {net_pnl:.2f})")
        return {
            "success": True,
            "net_pnl": net_pnl,
            "fill_price": fill_price
        }

    # Backward compatibility wrappers
    def sell(self, agent, trade, current_market_price: float, exit_reason: str, db_session) -> dict:
        return self.close_position(agent, trade, current_market_price, exit_reason, db_session)
        
    def cover(self, agent, trade, current_market_price: float, exit_reason: str, db_session) -> dict:
        return self.close_position(agent, trade, current_market_price, exit_reason, db_session)
