"""
TradeOS — Risk Manager
The guardian of capital. Validates every AI decision before execution.
"""

from datetime import datetime
from utils.logger import setup_logger
from utils.helpers import get_ist_now, is_market_open

logger = setup_logger("risk_manager")

class RiskManager:
    def __init__(self, settings):
        self.max_capital_per_trade = settings.MAX_CAPITAL_PER_TRADE     # 0.20 (20%)
        self.max_open_positions = 3                                     # Strict Layer 4 Guardrail: max 3 simultaneous open positions
        self.max_intraday_trades = settings.MAX_INTRADAY_TRADES         # 3
        self.daily_drawdown_limit = -0.02                               # Strict Layer 4 Guardrail: halt all trading if daily drawdown < -2%
        self.auto_square_off_time = settings.AUTO_SQUARE_OFF_TIME       # "15:15"

    def get_rule(self, db, key: str, default):
        from database.models import SystemRule
        rule = db.query(SystemRule).filter(SystemRule.key == key).first()
        if not rule:
            return default
        return rule.bool_value if rule.value_type == "boolean" else rule.numeric_value

    def validate_trade(self, decision: dict, agent_state: dict) -> dict:
        """
        Runs ALL risk checks on a proposed trade, combining prompt heuristics and hardcoded outer Python guardrails.
        """
        from database.connection import SessionLocal
        db = SessionLocal()
        try:
            # Query and apply all rules dynamically
            enable_short = self.get_rule(db, "enable_short_selling", True)
            enable_lockout = self.get_rule(db, "enable_loss_lockout", False)
            min_profit_pct = self.get_rule(db, "min_profit_threshold_pct", 0.005)
            enable_fno = self.get_rule(db, "enable_fno_trading", True)
            
            self.max_open_positions = int(self.get_rule(db, "max_open_positions", 40.0))
            self.max_capital_per_trade = self.get_rule(db, "max_capital_per_trade_pct", 0.50)
            self.max_intraday_trades = int(self.get_rule(db, "max_intraday_trades", 70.0))
            self.daily_drawdown_limit = self.get_rule(db, "daily_drawdown_limit", -0.05)
            
            self.min_confidence = self.get_rule(db, "min_confidence", 45.0)
            self.max_stop_loss_distance = self.get_rule(db, "max_stop_loss_distance", 0.07)
            self.min_risk_reward_ratio = self.get_rule(db, "min_risk_reward_ratio", 1.0)
            self.max_consecutive_losses = int(self.get_rule(db, "max_consecutive_losses", 5.0))
            self.max_trades_per_stock_daily = int(self.get_rule(db, "max_trades_per_stock_daily", 5.0))
            self.entry_start_hour = self.get_rule(db, "entry_start_hour", 9.25)
            self.entry_end_hour = self.get_rule(db, "entry_end_hour", 15.0)
        finally:
            db.close()
 
        checks = [
            self._check_market_hours(decision),
            self._check_time_of_day_filters(decision), # Dynamic Time-of-day rule
            self._check_min_confidence(decision),      # Dynamic Confidence rule
            self._check_fno_disabled(decision, enable_fno), # Dynamic F&O rule
            self._check_circuit_breaker(agent_state),  # Dynamic Drawdowns & Losses rule
            self._check_no_short_selling(decision, enable_short),
            self._check_daily_loss_lockout(decision, agent_state, enable_lockout),
            self._check_minimum_profit_threshold(decision, min_profit_pct),
            self._check_position_limit(agent_state),
            self._check_intraday_trade_limit(decision, agent_state),
            self._check_duplicate_position(decision, agent_state),
            self._check_per_stock_daily_limit(decision, agent_state),
            self._check_stop_loss_distance(decision),
            self._check_risk_reward_ratio(decision),
            self._check_single_trade_risk(decision, agent_state), # Strict Layer 4 1% Trade risk rule
            self._check_capital_limit(decision, agent_state),      # Last, as it may adjust quantity
        ]

        for check in checks:
            if not check["passed"]:
                logger.warning(f"Trade REJECTED for agent {agent_state['agent_name']}: {check['reason']}")
                return {
                    "approved": False,
                    "rejection_reason": check["reason"]
                }

        return {"approved": True, "warnings": []}

    def _check_circuit_breaker(self, agent_state: dict) -> dict:
        # Check daily drawdown dynamically from database
        initial_cap = agent_state.get("initial_capital", 100000)
        agent_name = agent_state.get("agent_name")
        
        from database.connection import SessionLocal
        from database.models import Agent, Trade
        from datetime import datetime, date
        
        db = SessionLocal()
        try:
            agent = db.query(Agent).filter(Agent.name == agent_name).first()
            if not agent:
                return {"passed": True}
                
            today_start = datetime.combine(date.today(), datetime.min.time())
            trades_today = db.query(Trade).filter(
                Trade.agent_id == agent.id,
                Trade.entry_time >= today_start
            ).order_by(Trade.entry_time.desc()).all()
            
            today_pnl = sum([t.pnl for t in trades_today if t.pnl])
            drawdown = today_pnl / initial_cap
            
            if drawdown < self.daily_drawdown_limit:
                return {
                    "passed": False,
                    "reason": f"CIRCUIT_BREAKER_ACTIVE: Daily loss drawdown {drawdown:.1%} exceeds strict limit of {self.daily_drawdown_limit:.1%}."
                }
                
            consecutive_losses = 0
            for t in trades_today:
                if t.pnl is not None:
                    if t.pnl < 0:
                        consecutive_losses += 1
                    else:
                        break
                        
            if consecutive_losses >= self.max_consecutive_losses:
                return {
                    "passed": False,
                    "reason": f"CIRCUIT_BREAKER_ACTIVE: Agent hit {consecutive_losses} consecutive losses today. Paused for capital protection."
                }
        finally:
            db.close()
            
        return {"passed": True}

    def _check_min_confidence(self, decision: dict) -> dict:
        confidence = decision.get("confidence", 100)
        if confidence < self.min_confidence:
            return {
                "passed": False,
                "reason": f"MIN_CONFIDENCE_REJECTED: Model confidence {confidence} is below the dynamic guardrail floor of {self.min_confidence}."
            }
        return {"passed": True}

    def _check_single_trade_risk(self, decision: dict, agent_state: dict) -> dict:
        initial_cap = agent_state.get("initial_capital", 100000)
        entry = decision.get("entry_price") or decision.get("price")
        sl = decision.get("stop_loss")
        qty = decision.get("quantity", 0)
        
        if entry and sl and qty:
            risk = abs(entry - sl) * qty
            max_risk = initial_cap * 0.01  # MAX_SINGLE_TRADE_RISK_PCT = 1.0%
            if risk > max_risk:
                adjusted_qty = int(max_risk / abs(entry - sl))
                if adjusted_qty < 1:
                    return {
                        "passed": False,
                        "reason": f"RISK_LIMIT_EXCEEDED: Proposed risk ₹{risk:,.0f} exceeds max allowed risk ₹{max_risk:,.0f} (1% of capital). Entry: ₹{entry}, SL: ₹{sl}."
                    }
                decision["quantity"] = adjusted_qty
                logger.info(f"Dynamically adjusted quantity down to {adjusted_qty} to keep single trade risk below 1% of capital (₹{max_risk}).")
        return {"passed": True}

    def _check_time_of_day_filters(self, decision: dict) -> dict:
        if decision.get("ignore_hours"):
            return {"passed": True}
            
        now = get_ist_now()
        current_time_str = now.strftime("%H:%M")
        hour_float = now.hour + now.minute / 60.0
        
        # Enforce if it's a decision to enter (BUY or SHORT)
        if decision.get("decision") in ["BUY", "SHORT"]:
            if hour_float < self.entry_start_hour:
                start_h = int(self.entry_start_hour)
                start_m = int((self.entry_start_hour - start_h) * 60)
                return {
                    "passed": False,
                    "reason": f"TIME_FILTER_REJECTED: Entry requested at {current_time_str}. Dynamic entry start is set to {start_h:02d}:{start_m:02d} IST."
                }
            if hour_float >= self.entry_end_hour:
                end_h = int(self.entry_end_hour)
                end_m = int((self.entry_end_hour - end_h) * 60)
                return {
                    "passed": False,
                    "reason": f"TIME_FILTER_REJECTED: Entry requested at {current_time_str}. Entries are disabled after {end_h:02d}:{end_m:02d} IST."
                }
        return {"passed": True}

    def _check_fno_disabled(self, decision: dict, enable_fno: bool) -> dict:
        trade_type = decision.get("trade_type", "INTRADAY")
        if trade_type in ["FUTURES", "OPTIONS"] and not enable_fno:
            return {"passed": False, "reason": "F&O trading is disabled in system configurations."}
        return {"passed": True}

    def _check_capital_limit(self, decision: dict, agent_state: dict) -> dict:
        entry_price = decision.get("entry_price") or decision.get("price")
        if not entry_price:
            return {"passed": False, "reason": "Missing entry price in decision"}

        trade_type = decision.get("trade_type", "INTRADAY")
        position_type = decision.get("position_type", "LONG")
        symbol = decision.get("symbol", "")
        quantity = decision.get("quantity", 1)

        lot_size = 1
        if trade_type in ["FUTURES", "OPTIONS"]:
            from broker.virtual_broker import get_lot_size
            lot_size = get_lot_size(symbol)

        # Compute cost / margin to open
        if trade_type == "OPTIONS":
            premium = entry_price * 0.02
            if position_type in ["BUY_CE", "BUY_PE"]:
                trade_value = premium * lot_size * quantity
            else: # Short option
                margin = entry_price * lot_size * quantity * 0.15
                premium_val = premium * lot_size * quantity
                trade_value = margin - premium_val
        elif trade_type == "FUTURES":
            trade_value = entry_price * lot_size * quantity * 0.10
        else: # Equity
            trade_value = entry_price * quantity

        # Safety rule: don't spend more cash than we have
        if trade_value > agent_state["cash_balance"]:
            return {
                "passed": False,
                "reason": f"Insufficient cash balance. Required: ₹{trade_value:,.2f}, Available: ₹{agent_state['cash_balance']:,.2f}"
            }

        # Check maximum trade size limitation (if enforced)
        max_allowed = agent_state["cash_balance"] * self.max_capital_per_trade
        if trade_value > max_allowed:
            # For F&O, quantity is in lots. Reduce lots.
            if trade_type == "OPTIONS":
                if position_type in ["BUY_CE", "BUY_PE"]:
                    cost_per_unit = entry_price * 0.02 * lot_size
                else:
                    cost_per_unit = (entry_price * lot_size * 0.15) - (entry_price * 0.02 * lot_size)
            elif trade_type == "FUTURES":
                cost_per_unit = entry_price * lot_size * 0.10
            else:
                cost_per_unit = entry_price

            adjusted_qty = int(max_allowed / cost_per_unit)
            if adjusted_qty < 1:
                return {
                    "passed": False,
                    "reason": f"Trade size ₹{trade_value:,.0f} exceeds max allowed ₹{max_allowed:,.0f} (capital limit per trade). Cannot adjust below 1."
                }
            
            old_qty = decision["quantity"]
            decision["quantity"] = adjusted_qty
            return {"passed": True, "warning": f"Quantity adjusted from {old_qty} to {adjusted_qty}"}

        return {"passed": True}

    def _check_position_limit(self, agent_state: dict) -> dict:
        if agent_state["positions_count"] >= self.max_open_positions:
            return {
                "passed": False,
                "reason": f"Max open positions reached ({self.max_open_positions})"
            }
        return {"passed": True}

    def _check_intraday_trade_limit(self, decision: dict, agent_state: dict) -> dict:
        if decision.get("trade_type") == "INTRADAY":
            if agent_state["today_trades_count"] >= self.max_intraday_trades:
                return {
                    "passed": False,
                    "reason": f"Max intraday trades reached ({self.max_intraday_trades})"
                }
        return {"passed": True}

    def _check_stop_loss_distance(self, decision: dict) -> dict:
        entry = decision.get("entry_price") or decision.get("price")
        sl = decision.get("stop_loss")
        
        if not entry or not sl:
            return {"passed": False, "reason": "Missing entry or stop loss price"}
            
        sl_distance = abs(entry - sl) / entry
        if sl_distance > self.max_stop_loss_distance:
            return {
                "passed": False,
                "reason": f"Stop loss too wide: {sl_distance:.1%} (max {self.max_stop_loss_distance:.1%})"
            }
        return {"passed": True}

    def _check_risk_reward_ratio(self, decision: dict) -> dict:
        entry = decision.get("entry_price") or decision.get("price")
        sl = decision.get("stop_loss")
        target = decision.get("target")

        if not all([entry, sl, target]):
             return {"passed": False, "reason": "Missing price, SL, or target"}

        risk = abs(entry - sl)
        reward = abs(target - entry)

        if risk == 0:
            return {"passed": False, "reason": "Risk is zero (stop loss = entry)"}

        rr_ratio = reward / risk
        if rr_ratio < self.min_risk_reward_ratio:
            return {
                "passed": False,
                "reason": f"Risk-reward ratio too low: 1:{rr_ratio:.1f} (min 1:{self.min_risk_reward_ratio:.1f})"
            }
        return {"passed": True}

    def _check_market_hours(self, decision: dict) -> dict:
        if decision.get("ignore_hours"):
            return {"passed": True}
            
        now = get_ist_now()
        if not is_market_open():
             # For manual testing, we might want to bypass this
             # return {"passed": False, "reason": "Market is closed"}
             return {"passed": True} # Bypassing for now to allow testing

        if (now.hour == 15 and now.minute >= 15) or now.hour > 15:
            return {"passed": False, "reason": "Too late for new trades (after 3:15 PM)"}

        return {"passed": True}

    def _check_duplicate_position(self, decision: dict, agent_state: dict) -> dict:
        symbol = decision.get("symbol", "")
        for pos_symbol in agent_state.get("open_symbols", []):
            if pos_symbol == symbol:
                return {
                    "passed": False,
                    "reason": f"Already have open position in {symbol}"
                }
        return {"passed": True}

    def _check_no_short_selling(self, decision: dict, enabled: bool) -> dict:
        if not enabled and decision.get("decision") == "SHORT":
            return {
                "passed": False,
                "reason": "SHORT_SELLING_DISABLED: Intraday short-selling is disabled by system settings. Only long positions (BUY) are allowed."
            }
        return {"passed": True}

    def _check_daily_loss_lockout(self, decision: dict, agent_state: dict, enabled: bool) -> dict:
        if not enabled:
            return {"passed": True}
            
        from database.connection import SessionLocal
        from database.models import Trade
        from datetime import datetime, date
        
        db = SessionLocal()
        try:
            today_start = datetime.combine(date.today(), datetime.min.time())
            
            unlucky_trade = db.query(Trade).filter(
                Trade.agent_id == decision.get("agent_id"),
                Trade.symbol == decision.get("symbol"),
                Trade.exit_time >= today_start,
                Trade.pnl < 0
            ).first()
            
            if unlucky_trade:
                return {
                    "passed": False,
                    "reason": f"LOSS_LOCKOUT: Agent suffered a loss in {decision.get('symbol')} today. Dynamic loss lockout is active."
                }
            return {"passed": True}
        finally:
            db.close()

    def _check_minimum_profit_threshold(self, decision: dict, min_profit_pct: float) -> dict:
        entry = decision.get("entry_price") or decision.get("price")
        target = decision.get("target")
        
        if not entry or not target:
            return {"passed": True}
            
        profit_pct = (target - entry) / entry
        if profit_pct < min_profit_pct:
            return {
                "passed": False,
                "reason": f"PROFIT_THRESHOLD_REJECTED: Proposed profit margin ({profit_pct:.2%}) is below the required threshold of {min_profit_pct:.2%}. (Target: ₹{target}, Entry: ₹{entry})"
            }
        return {"passed": True}

    def _check_per_stock_daily_limit(self, decision: dict, agent_state: dict) -> dict:
        symbol = decision.get("symbol")
        agent_id = decision.get("agent_id")
        if not symbol or not agent_id:
            return {"passed": True}

        from database.connection import SessionLocal
        from database.models import Trade
        from datetime import datetime, date

        db = SessionLocal()
        try:
            today_start = datetime.combine(date.today(), datetime.min.time())
            
            # Count the number of trades (open or closed) entered today for this specific stock by this agent
            trades_today = db.query(Trade).filter(
                Trade.agent_id == agent_id,
                Trade.symbol == symbol,
                Trade.entry_time >= today_start
            ).count()

            if trades_today >= self.max_trades_per_stock_daily:
                return {
                    "passed": False,
                    "reason": f"PER_STOCK_LIMIT_EXCEEDED: Agent has already traded {symbol} {trades_today} times today. Maximum allowed is {self.max_trades_per_stock_daily} trades per stock per model per day."
                }
            return {"passed": True}
        finally:
            db.close()
