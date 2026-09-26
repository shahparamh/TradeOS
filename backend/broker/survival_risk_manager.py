"""
TradeOS — Survival Arena Risk Manager
Deterministic, non-negotiable risk rules for AgentZero-style survival agents.
Unlike the fleet's RiskManager, these numbers are hardcoded constants (not DB-tunable
SystemRules) — the AI must never be able to loosen its own risk envelope.
"""

import math
from datetime import datetime, date
from utils.logger import setup_logger
from utils.helpers import get_ist_now, is_market_open

logger = setup_logger("survival_risk_manager")


class SurvivalRiskManager:
    MAX_RISK_PER_TRADE_PCT = 0.01      # 1% of current equity risked per trade
    HARD_STOP_LOSS_PCT = 0.06          # 6% max stop distance from entry
    MIN_RISK_REWARD_RATIO = 2.0        # reward/risk must be at least this, computed against
                                        # the FINAL (possibly 6%-clamped) stop -- the single
                                        # authoritative R:R gate; Trader may weigh R:R
                                        # qualitatively but does not enforce it, and PM is
                                        # explicitly barred from re-litigating it
    MAX_OPEN_POSITIONS = 6                 # raised from 2 so larger accounts (e.g. a $200K
                                            # game) can actually diversify across the watchlist
                                            # instead of parking most of their capital idle
                                            # after just two positions
    MAX_CAPITAL_PER_POSITION_PCT = 0.20     # no single position's notional may exceed this
                                            # share of equity, independent of risk-based sizing
    DAILY_LOSS_KILL_SWITCH_PCT = -0.05  # -5% of starting capital in one day halts new entries
    MAX_TOTAL_DRAWDOWN_PCT = -0.30      # -30% of starting capital is the outer drawdown guard
    ENABLE_SHORT_SELLING = False
    ENABLE_LEVERAGE = False
    ENABLE_OPTIONS = False

    def validate_and_size(self, decision: dict, agent, agent_state: dict, db) -> dict:
        """
        Runs every survival guardrail against a Portfolio Manager proposal.
        On approval, OVERWRITES decision['quantity'] and decision['stop_loss'] with the
        deterministically computed values — the AI's proposed quantity is never trusted directly.
        Returns {"approved": bool, "rejection_reason": str|None, "decision": dict}
        """
        checks = [
            self._check_market_hours(decision),
            self._check_options_leverage_short(decision),
            self._check_death_threshold(agent, agent_state),
            self._check_daily_kill_switch(agent, agent_state),
            self._check_total_drawdown(agent, agent_state),
            self._check_position_limit(agent_state),
            self._check_duplicate_position(decision, agent_state),
        ]
        for check in checks:
            if not check["passed"]:
                logger.warning(f"Survival trade REJECTED for {agent.name}: {check['reason']}")
                return {"approved": False, "rejection_reason": check["reason"], "decision": decision}

        # Clamp stop-loss to the hard 6% cap before sizing off it
        entry = decision.get("entry_price") or decision.get("price")
        stop_loss = decision.get("stop_loss")
        target = decision.get("target")
        if not entry or not stop_loss or not target:
            return {"approved": False, "rejection_reason": "Missing entry price, stop loss, or target", "decision": decision}

        # Log both sides of the clamp unconditionally (whether or not it actually fires) so
        # downstream diagnostics can quantify how often/how much it changes the Trader's
        # intended stop, without changing the clamp's behavior itself.
        proposed_stop_loss = stop_loss
        proposed_stop_distance_pct = round(abs(entry - stop_loss) / entry, 4)
        decision["proposed_stop_loss"] = proposed_stop_loss
        decision["proposed_stop_distance_pct"] = proposed_stop_distance_pct

        sl_distance_pct = abs(entry - stop_loss) / entry
        if sl_distance_pct > self.HARD_STOP_LOSS_PCT:
            # NOTE: this silently TIGHTENS an excessively wide stop rather than rejecting the
            # trade outright. Left exactly as-is for this patch (flagged separately for later
            # review) -- tightening an AI-proposed technical stop can change what the setup
            # actually means and can artificially inflate the R:R computed just below against
            # this clamped value. Not addressed here to avoid mixing two policy changes.
            direction = 1 if decision.get("decision") == "BUY" else -1
            stop_loss = entry * (1 - direction * self.HARD_STOP_LOSS_PCT)
            decision["stop_loss"] = round(stop_loss, 2)
            sl_distance_pct = self.HARD_STOP_LOSS_PCT

        final_stop = decision["stop_loss"]
        decision["final_stop_loss"] = final_stop
        decision["final_stop_distance_pct"] = round(abs(entry - final_stop) / entry, 4)

        # Long-only geometry sanity check, ahead of the R:R math below -- a malformed
        # stop/target (on the wrong side of entry) makes risk/reward undefined or negative.
        if final_stop >= entry:
            return {"approved": False, "rejection_reason": f"INVALID_GEOMETRY: Stop-loss {final_stop} is not below entry {entry} for a long position.", "decision": decision}
        if target <= entry:
            return {"approved": False, "rejection_reason": f"INVALID_GEOMETRY: Target {target} is not above entry {entry} for a long position.", "decision": decision}

        risk = entry - final_stop
        reward = target - entry
        if risk <= 0 or reward <= 0:
            return {"approved": False, "rejection_reason": f"INVALID_GEOMETRY: Non-positive risk ({risk}) or reward ({reward}).", "decision": decision}

        # Deterministic, authoritative R:R gate -- the Trader may weigh R:R qualitatively and
        # the Portfolio Manager is explicitly barred from re-litigating it; this is the one
        # place it is actually enforced, computed against the final (post-clamp) stop.
        computed_rr = round(reward / risk, 2)
        decision["risk_reward_ratio"] = computed_rr
        if computed_rr < self.MIN_RISK_REWARD_RATIO:
            return {
                "approved": False,
                "rejection_reason": f"RISK_REWARD_REJECTED: Risk-reward {computed_rr:.2f} below minimum {self.MIN_RISK_REWARD_RATIO:.2f}.",
                "decision": decision,
            }

        # Deterministic position sizing: risk_amount / stop_distance — the AI's proposed
        # quantity is discarded entirely in favor of this formula (spec section 13).
        equity = agent_state["cash_balance"]
        risk_amount = equity * self.MAX_RISK_PER_TRADE_PCT
        stop_distance = abs(entry - decision["stop_loss"])
        if stop_distance <= 0:
            return {"approved": False, "rejection_reason": "Stop distance is zero", "decision": decision}

        qty = math.floor(risk_amount / stop_distance)
        if qty < 1:
            return {
                "approved": False,
                "rejection_reason": f"Computed position size is below 1 share (risk budget ₹{risk_amount:.2f} / stop distance ₹{stop_distance:.2f}).",
                "decision": decision,
            }

        # Pure risk-based sizing (risk_amount / stop_distance) has no ceiling on notional —
        # a tight stop relative to price (common on lower-volatility large caps) can size a
        # "1%-risk" trade into most of the account's cash in one symbol, defeating
        # MAX_OPEN_POSITIONS entirely since there's nothing left to diversify with. Cap any
        # single position's notional so a larger account can actually spread across multiple
        # names instead of parking most of its capital in the first idea that clears R:R.
        max_position_notional = equity * self.MAX_CAPITAL_PER_POSITION_PCT
        max_qty_by_concentration = math.floor(max_position_notional / entry)
        qty = min(qty, max_qty_by_concentration)
        if qty < 1:
            return {"approved": False, "rejection_reason": "Computed position size is below 1 share after the per-position concentration cap.", "decision": decision}

        # Never spend more cash than available on hand
        max_affordable = math.floor(agent_state["cash_balance"] / entry)
        qty = min(qty, max_affordable)
        if qty < 1:
            return {"approved": False, "rejection_reason": "Insufficient cash for even 1 share.", "decision": decision}

        decision["quantity"] = qty
        return {"approved": True, "rejection_reason": None, "decision": decision}

    def _check_market_hours(self, decision: dict) -> dict:
        if decision.get("ignore_hours"):
            return {"passed": True}
        market = decision.get("market", "IN")
        if market == "IN":
            if not is_market_open():
                return {"passed": False, "reason": "Market is closed"}
            return {"passed": True}
        # Non-IN markets: the scheduler only invokes run_arena_cycle during that market's
        # own regular session (see trading_loop.py), so by the time a decision reaches here
        # the session is already known-open. This check exists only to preserve NSE-hours
        # behavior unchanged for IN; it does not gate other markets.
        return {"passed": True}

    def _check_options_leverage_short(self, decision: dict) -> dict:
        trade_type = decision.get("trade_type", "INTRADAY")
        if trade_type in ["FUTURES", "OPTIONS"] and not self.ENABLE_OPTIONS:
            return {"passed": False, "reason": "OPTIONS_DISABLED: Survival agents may only trade cash equity."}
        if decision.get("decision") == "SHORT" and not self.ENABLE_SHORT_SELLING:
            return {"passed": False, "reason": "SHORT_SELLING_DISABLED: Survival agents are long-only."}
        return {"passed": True}

    def _check_death_threshold(self, agent, agent_state: dict) -> dict:
        if agent.is_dead:
            return {"passed": False, "reason": "AGENT_DEAD: This agent has already been terminated."}
        equity = agent_state["cash_balance"] + agent_state.get("open_positions_value", 0.0)
        if agent.death_threshold is not None and equity <= agent.death_threshold:
            return {"passed": False, "reason": f"DEATH_THRESHOLD: Equity ₹{equity:.2f} is at or below death threshold ₹{agent.death_threshold:.2f}."}
        return {"passed": True}

    def _check_daily_kill_switch(self, agent, agent_state: dict) -> dict:
        from database.connection import SessionLocal
        from database.models import Trade

        starting_capital = agent.starting_capital or agent_state.get("cash_balance", 1)
        db = SessionLocal()
        try:
            today_start = datetime.combine(get_ist_now().date(), datetime.min.time())
            trades_today = db.query(Trade).filter(
                Trade.agent_id == agent.id,
                Trade.exit_time >= today_start,
            ).all()
            today_pnl = sum(t.pnl for t in trades_today if t.pnl)
            drawdown_pct = today_pnl / starting_capital if starting_capital else 0
            if drawdown_pct <= self.DAILY_LOSS_KILL_SWITCH_PCT:
                return {
                    "passed": False,
                    "reason": f"DAILY_KILL_SWITCH: Daily loss {drawdown_pct:.1%} has hit the -5% limit. No new entries until tomorrow.",
                }
        finally:
            db.close()
        return {"passed": True}

    def _check_total_drawdown(self, agent, agent_state: dict) -> dict:
        starting_capital = agent.starting_capital or agent_state.get("cash_balance", 1)
        equity = agent_state["cash_balance"] + agent_state.get("open_positions_value", 0.0)
        drawdown_pct = (equity - starting_capital) / starting_capital if starting_capital else 0
        if drawdown_pct <= self.MAX_TOTAL_DRAWDOWN_PCT:
            return {
                "passed": False,
                "reason": f"MAX_DRAWDOWN_EXCEEDED: Total drawdown {drawdown_pct:.1%} has breached the -30% survival limit.",
            }
        return {"passed": True}

    def _check_position_limit(self, agent_state: dict) -> dict:
        if agent_state.get("positions_count", 0) >= self.MAX_OPEN_POSITIONS:
            return {"passed": False, "reason": f"Max open positions reached ({self.MAX_OPEN_POSITIONS})"}
        return {"passed": True}

    def _check_duplicate_position(self, decision: dict, agent_state: dict) -> dict:
        symbol = decision.get("symbol", "")
        if symbol in agent_state.get("open_symbols", []):
            return {"passed": False, "reason": f"Already have an open position in {symbol}"}
        return {"passed": True}
