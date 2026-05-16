# Phase 5 — Risk Management & Virtual Broker Execution Engine

> **Goal:** Build the risk management guardrails that protect capital and the virtual broker that executes trades. The risk manager validates every AI decision before execution. The virtual broker simulates realistic trade fills with slippage and brokerage. The position monitor actively watches open positions for stop-loss hits, target hits, and intraday square-off.

---

## 5.1 Architecture Overview

```
  AI Decisions (from Phase 4)
          │
          ▼
  ┌────────────────────────┐
  │   Risk Manager         │
  │                        │
  │   Validates:           │
  │   - Capital limits     │
  │   - Position limits    │
  │   - Drawdown checks    │
  │   - Circuit breakers   │
  └──────────┬─────────────┘
             │
         APPROVED / REJECTED
             │
             ▼
  ┌────────────────────────┐
  │   Virtual Broker       │
  │                        │
  │   Executes:            │
  │   - buy()              │
  │   - sell()             │
  │   - short_sell()       │
  │   - cover()            │
  │                        │
  │   Applies:             │
  │   - Slippage           │
  │   - Brokerage          │
  └──────────┬─────────────┘
             │
             ▼
  ┌────────────────────────┐
  │   Position Monitor     │
  │   (Runs every cycle)   │
  │                        │
  │   Monitors:            │
  │   - Stop-loss hit?     │
  │   - Target hit?        │
  │   - 3:15 PM square-off │
  │   - AI EXIT signals    │
  └────────────────────────┘
```

---

## 5.2 Risk Manager — `broker/risk_manager.py`

### 5.2.1 Pre-Trade Validation

Every AI decision passes through the risk manager BEFORE execution.

```python
class RiskManager:
    """
    The guardian of capital. No trade gets executed without passing
    through every rule in this class.
    """

    def __init__(self, settings):
        self.max_capital_per_trade = settings.MAX_CAPITAL_PER_TRADE     # 0.20 (20%)
        self.max_open_positions = settings.MAX_OPEN_POSITIONS           # 5
        self.max_intraday_trades = settings.MAX_INTRADAY_TRADES         # 3
        self.daily_drawdown_limit = settings.DAILY_DRAWDOWN_LIMIT       # -0.05 (-5%)
        self.auto_square_off_time = settings.AUTO_SQUARE_OFF_TIME       # "15:15"

    def validate_trade(self, decision: dict, agent_state: dict) -> dict:
        """
        Runs ALL risk checks on a proposed trade.

        Parameters:
        - decision: The AI's parsed decision (from Phase 4)
        - agent_state: Current state of the agent's portfolio

        agent_state = {
            "agent_id": 1,
            "agent_name": "ChatGPT",
            "cash_balance": 82000,
            "initial_capital": 100000,
            "open_positions": [...],
            "positions_count": 1,
            "today_trades_count": 1,
            "today_pnl": -320,
            "consecutive_losses": 0,
            "peak_capital": 100000
        }

        Returns:
        {
            "approved": True/False,
            "rejection_reason": "..." (if rejected),
            "adjusted_quantity": <int> (if quantity was too large),
            "warnings": [...]
        }
        """
        checks = [
            self._check_circuit_breaker(agent_state),
            self._check_capital_limit(decision, agent_state),
            self._check_position_limit(agent_state),
            self._check_intraday_trade_limit(decision, agent_state),
            self._check_stop_loss_distance(decision),
            self._check_risk_reward_ratio(decision),
            self._check_market_hours(decision),
            self._check_duplicate_position(decision, agent_state),
        ]

        for check in checks:
            if not check["passed"]:
                return {
                    "approved": False,
                    "rejection_reason": check["reason"]
                }

        return {"approved": True, "warnings": []}
```

### 5.2.2 Individual Risk Checks

**Check 1: Circuit Breaker**

```python
def _check_circuit_breaker(self, agent_state: dict) -> dict:
    """
    STOPS ALL TRADING if:

    Condition 1: Daily drawdown exceeds limit
    ─────────────────────────────────────────
    If the agent has lost more than 5% of initial capital TODAY,
    halt all trading for the rest of the day.

    Formula:
    drawdown = today_pnl / initial_capital
    If drawdown < -0.05 → STOP

    Example:
    Initial capital: ₹1,00,000
    Today PnL: -₹5,500
    Drawdown: -5.5% → CIRCUIT BREAKER TRIGGERED

    Condition 2: Consecutive losses
    ────────────────────────────────
    If the agent has 3 consecutive losing trades,
    halt trading until next day.

    This prevents:
    - Tilt trading (emotional revenge trades)
    - Compounding losses in a bad market
    """
    # Check daily drawdown
    drawdown = agent_state["today_pnl"] / agent_state["initial_capital"]
    if drawdown < self.daily_drawdown_limit:
        return {
            "passed": False,
            "reason": f"CIRCUIT BREAKER: Daily drawdown {drawdown:.1%} exceeds limit {self.daily_drawdown_limit:.1%}"
        }

    # Check consecutive losses
    if agent_state["consecutive_losses"] >= 3:
        return {
            "passed": False,
            "reason": f"CIRCUIT BREAKER: {agent_state['consecutive_losses']} consecutive losses"
        }

    return {"passed": True}
```

**Check 2: Capital Per Trade Limit**

```python
def _check_capital_limit(self, decision: dict, agent_state: dict) -> dict:
    """
    Ensures no single trade risks more than 20% of available capital.

    Formula:
    trade_value = quantity × entry_price
    max_allowed = cash_balance × MAX_CAPITAL_PER_TRADE

    If trade_value > max_allowed:
    → Adjust quantity down to fit within limit
    → Or reject if even 1 share exceeds limit

    Example:
    Cash: ₹82,000
    Max per trade: ₹16,400 (20%)
    AI wants: 15 shares × ₹2,890 = ₹43,350 → REJECTED
    Adjusted: 5 shares × ₹2,890 = ₹14,450 → APPROVED
    """
    trade_value = decision["quantity"] * decision["entry_price"]
    max_allowed = agent_state["cash_balance"] * self.max_capital_per_trade

    if trade_value > max_allowed:
        # Try to adjust quantity
        adjusted_qty = int(max_allowed / decision["entry_price"])
        if adjusted_qty < 1:
            return {
                "passed": False,
                "reason": f"Insufficient capital. Trade: ₹{trade_value:,.0f}, Max: ₹{max_allowed:,.0f}"
            }
        decision["quantity"] = adjusted_qty
        return {"passed": True, "warning": f"Quantity adjusted from {decision['quantity']} to {adjusted_qty}"}

    return {"passed": True}
```

**Check 3: Position Limit**

```python
def _check_position_limit(self, agent_state: dict) -> dict:
    """
    Maximum 5 open positions at any time.
    This prevents over-diversification and capital dilution.
    """
    if agent_state["positions_count"] >= self.max_open_positions:
        return {
            "passed": False,
            "reason": f"Max open positions reached ({self.max_open_positions})"
        }
    return {"passed": True}
```

**Check 4: Intraday Trade Limit**

```python
def _check_intraday_trade_limit(self, decision: dict, agent_state: dict) -> dict:
    """
    Maximum 3 intraday trades per day.
    Prevents overtrading and excessive brokerage costs.
    """
    if decision.get("trade_type") == "INTRADAY":
        if agent_state["today_trades_count"] >= self.max_intraday_trades:
            return {
                "passed": False,
                "reason": f"Max intraday trades reached ({self.max_intraday_trades})"
            }
    return {"passed": True}
```

**Check 5: Stop Loss Distance**

```python
def _check_stop_loss_distance(self, decision: dict) -> dict:
    """
    Stop loss must be within 3% of entry price.
    Too wide a stop loss = too much capital at risk.

    For LONG: (entry - stop_loss) / entry <= 0.03
    For SHORT: (stop_loss - entry) / entry <= 0.03
    """
    entry = decision["entry_price"]
    sl = decision["stop_loss"]
    sl_distance = abs(entry - sl) / entry

    if sl_distance > 0.03:
        return {
            "passed": False,
            "reason": f"Stop loss too wide: {sl_distance:.1%} (max 3%)"
        }
    return {"passed": True}
```

**Check 6: Risk-Reward Ratio**

```python
def _check_risk_reward_ratio(self, decision: dict) -> dict:
    """
    Minimum risk-reward ratio of 1:1.5.
    We should never risk more than we stand to gain.

    Formula:
    risk = |entry - stop_loss|
    reward = |target - entry|
    ratio = reward / risk >= 1.5
    """
    entry = decision["entry_price"]
    sl = decision["stop_loss"]
    target = decision["target"]

    risk = abs(entry - sl)
    reward = abs(target - entry)

    if risk == 0:
        return {"passed": False, "reason": "Risk is zero (stop loss = entry)"}

    rr_ratio = reward / risk
    if rr_ratio < 1.5:
        return {
            "passed": False,
            "reason": f"Risk-reward ratio too low: 1:{rr_ratio:.1f} (min 1:1.5)"
        }
    return {"passed": True}
```

**Check 7: Market Hours**

```python
def _check_market_hours(self, decision: dict) -> dict:
    """
    - No new trades after 3:00 PM IST (to allow time for intraday square-off).
    - SHORT trades are only allowed during market hours.
    - No trades on weekends or holidays.
    """
    from utils.helpers import get_ist_now, is_market_open

    now = get_ist_now()
    if not is_market_open():
        return {"passed": False, "reason": "Market is closed"}

    # No new trades after 3:00 PM
    if now.hour >= 15:
        return {"passed": False, "reason": "Too late for new trades (after 3:00 PM)"}

    return {"passed": True}
```

**Check 8: Duplicate Position Check**

```python
def _check_duplicate_position(self, decision: dict, agent_state: dict) -> dict:
    """
    Prevents opening a duplicate position in the same stock.
    An agent should not BUY RELIANCE if they already have an open LONG position in RELIANCE.
    """
    symbol = decision.get("symbol", "")
    for pos in agent_state.get("open_positions", []):
        if pos["symbol"] == symbol:
            return {
                "passed": False,
                "reason": f"Already have open position in {symbol}"
            }
    return {"passed": True}
```

---

## 5.3 Virtual Broker — `broker/virtual_broker.py`

### 5.3.1 The Execution Engine

```python
class VirtualBroker:
    """
    Simulates a real broker. Executes trades against live market prices
    with realistic slippage and brokerage costs.

    This module is designed to be SWAPPABLE.
    After the 1-month simulation, replace this with a real broker API
    (Dhan, Upstox, Zerodha) by implementing the same interface.
    """

    def __init__(self, settings):
        self.brokerage_pct = settings.BROKERAGE_PERCENT    # 0.0003 (0.03%)
        self.slippage_pct = settings.SLIPPAGE_PERCENT      # 0.0005 (0.05%)
```

### 5.3.2 Buy (LONG Entry)

```python
def buy(self, agent_id: int, symbol: str, quantity: int,
        market_price: float, stop_loss: float, target: float,
        confidence: int, trade_type: str, db_session) -> dict:
    """
    Executes a BUY order for a LONG position.

    Steps:
    1. Apply slippage to market price (buy slightly higher)
       fill_price = market_price × (1 + SLIPPAGE_PERCENT)

    2. Calculate brokerage
       brokerage = fill_price × quantity × BROKERAGE_PERCENT

    3. Calculate total cost
       total_cost = (fill_price × quantity) + brokerage

    4. Deduct from agent's cash balance
       agent.cash_balance -= total_cost

    5. Create TRADE record (status = "OPEN")
    6. Create POSITION record
    7. Log the execution

    Returns:
    {
        "success": True,
        "trade_id": 42,
        "fill_price": 2891.95,        # Market price + slippage
        "total_cost": 43529.25,
        "brokerage": 13.01,
        "slippage_cost": 21.67
    }

    Example:
    Market price: ₹2,890.00
    Slippage (0.05%): ₹1.45
    Fill price: ₹2,891.45
    Quantity: 15
    Trade value: ₹43,371.75
    Brokerage (0.03%): ₹13.01
    Total cost: ₹43,384.76
    """
```

### 5.3.3 Sell (LONG Exit)

```python
def sell(self, agent_id: int, trade_id: int, market_price: float,
         exit_reason: str, db_session) -> dict:
    """
    Closes a LONG position by selling.

    Steps:
    1. Apply slippage (sell slightly lower)
       fill_price = market_price × (1 - SLIPPAGE_PERCENT)

    2. Calculate brokerage on exit
    3. Calculate realized PnL:
       gross_pnl = (fill_price - entry_price) × quantity
       net_pnl = gross_pnl - entry_brokerage - exit_brokerage

    4. Add proceeds to agent's cash balance:
       agent.cash_balance += (fill_price × quantity) - exit_brokerage

    5. Update TRADE record:
       - exit_price = fill_price
       - pnl = net_pnl
       - status = exit_reason ("CLOSED", "SL_HIT", "TARGET_HIT", "SQUARED_OFF")
       - exit_time = now

    6. Delete POSITION record (no longer open)
    7. Update agent's total_pnl

    Returns:
    {
        "success": True,
        "trade_id": 42,
        "fill_price": 2974.01,
        "gross_pnl": 1230.90,
        "net_pnl": 1204.88,
        "exit_reason": "TARGET_HIT"
    }
    """
```

### 5.3.4 Short Sell (SHORT Entry)

```python
def short_sell(self, agent_id: int, symbol: str, quantity: int,
               market_price: float, stop_loss: float, target: float,
               confidence: int, db_session) -> dict:
    """
    Opens a SHORT position (sell first, buy later).

    RULES:
    - INTRADAY ONLY (must close before 3:15 PM)
    - No overnight shorts
    - Slippage works in reverse (fill slightly lower than expected)

    Steps:
    1. Apply slippage:
       fill_price = market_price × (1 - SLIPPAGE_PERCENT)

    2. Calculate margin required (full value of trade):
       margin = fill_price × quantity

    3. Block margin from cash balance:
       agent.cash_balance -= margin

    4. Create TRADE record (position_type = "SHORT", trade_type = "INTRADAY")
    5. Create POSITION record
    """
```

### 5.3.5 Cover (SHORT Exit)

```python
def cover(self, agent_id: int, trade_id: int, market_price: float,
          exit_reason: str, db_session) -> dict:
    """
    Closes a SHORT position by buying back.

    Steps:
    1. Apply slippage (buy back slightly higher):
       fill_price = market_price × (1 + SLIPPAGE_PERCENT)

    2. Calculate PnL:
       gross_pnl = (entry_price - fill_price) × quantity  # Profit if price dropped
       net_pnl = gross_pnl - entry_brokerage - exit_brokerage

    3. Release blocked margin and add PnL:
       agent.cash_balance += margin + net_pnl

    4. Update TRADE record (status, exit_price, pnl)
    5. Delete POSITION record
    """
```

---

## 5.4 Position Monitor — `broker/position_monitor.py`

Runs every cycle to check if any open positions need to be closed.

### 5.4.1 The Monitor Loop

```python
class PositionMonitor:
    """
    Actively monitors all open positions across all agents.
    Runs every cycle (every 5-15 minutes during market hours).
    """

    def __init__(self, broker: VirtualBroker):
        self.broker = broker

    async def check_all_positions(self, db_session) -> list[dict]:
        """
        For each open position:
        1. Fetch current market price
        2. Check if stop-loss has been hit
        3. Check if target has been hit
        4. Check if it's time for intraday square-off
        5. Execute closure if any condition is met
        6. Update unrealized PnL if position remains open

        Returns list of actions taken.
        """
        positions = db_session.query(Position).all()
        actions = []

        for pos in positions:
            current_price = await fetch_live_price(pos.symbol)
            action = self._evaluate_position(pos, current_price)

            if action:
                result = self._execute_closure(pos, current_price, action, db_session)
                actions.append(result)
            else:
                # Update unrealized PnL
                self._update_unrealized_pnl(pos, current_price, db_session)

        return actions
```

### 5.4.2 Stop-Loss & Target Detection

```python
def _evaluate_position(self, position, current_price: float) -> str | None:
    """
    Checks if any exit condition is met.

    For LONG positions:
    ─────────────────
    TARGET HIT:  current_price >= target_price
    SL HIT:      current_price <= stop_loss

    For SHORT positions:
    ──────────────────
    TARGET HIT:  current_price <= target_price  (price dropped to target)
    SL HIT:      current_price >= stop_loss     (price rose to stop loss)

    INTRADAY SQUARE-OFF:
    ────────────────────
    current_time >= 15:15 IST AND trade_type == "INTRADAY"
    → Force close regardless of PnL

    Returns:
    - "TARGET_HIT" if target reached
    - "SL_HIT" if stop loss triggered
    - "SQUARED_OFF" if intraday time limit
    - None if position should remain open
    """
    from utils.helpers import get_ist_now

    # Check time-based square-off first (highest priority)
    now = get_ist_now()
    if position.trade_type == "INTRADAY":
        square_off_hour, square_off_min = 15, 15
        if now.hour > square_off_hour or (now.hour == square_off_hour and now.minute >= square_off_min):
            return "SQUARED_OFF"

    # Check LONG positions
    if position.position_type == "LONG":
        if current_price >= position.target_price:
            return "TARGET_HIT"
        if current_price <= position.stop_loss:
            return "SL_HIT"

    # Check SHORT positions
    elif position.position_type == "SHORT":
        if current_price <= position.target_price:
            return "TARGET_HIT"
        if current_price >= position.stop_loss:
            return "SL_HIT"

    return None
```

### 5.4.3 Unrealized PnL Update

```python
def _update_unrealized_pnl(self, position, current_price: float, db_session):
    """
    Updates the floating PnL for open positions.
    This is displayed on the dashboard in real-time.

    For LONG:  unrealized_pnl = (current_price - entry_price) × quantity
    For SHORT: unrealized_pnl = (entry_price - current_price) × quantity
    """
    if position.position_type == "LONG":
        position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
    else:
        position.unrealized_pnl = (position.entry_price - current_price) * position.quantity

    position.current_price = current_price
    db_session.commit()
```

---

## 5.5 Trade Execution Flow — End to End

Here is exactly what happens when an AI says "BUY RELIANCE at ₹2,890":

```
Step 1: AI Decision Received
         {"decision": "BUY", "symbol": "RELIANCE.NS", "quantity": 15, ...}
              │
              ▼
Step 2: Risk Manager Validation
         ├── Circuit breaker check     → PASS
         ├── Capital limit check       → PASS (₹43,350 < ₹16,400? → FAIL → adjust to 5 shares)
         ├── Position limit check      → PASS (1/5 positions used)
         ├── Intraday trade limit      → PASS (1/3 used)
         ├── Stop loss distance        → PASS (1.4% < 3%)
         ├── Risk-reward ratio         → PASS (1:2.1)
         ├── Market hours              → PASS (10:30 AM IST)
         └── Duplicate position        → PASS (no existing RELIANCE position)
              │
              ▼
Step 3: Virtual Broker Execution
         ├── Market price: ₹2,890.00
         ├── Slippage (+0.05%): +₹1.45
         ├── Fill price: ₹2,891.45
         ├── Quantity: 5 (adjusted by risk manager)
         ├── Trade value: ₹14,457.25
         ├── Brokerage (0.03%): ₹4.34
         ├── Total cost: ₹14,461.59
         └── Cash deducted: ₹82,000 → ₹67,538.41
              │
              ▼
Step 4: Database Updates
         ├── INSERT into trades (status = "OPEN")
         ├── INSERT into positions
         ├── UPDATE agents (cash_balance)
         └── INSERT into ai_responses (full decision log)
              │
              ▼
Step 5: Position Monitoring (ongoing)
         ├── Every cycle: check current price vs SL/TP
         ├── Price hits ₹2,975 → sell() → "TARGET_HIT" → PnL: +₹417.75
         ├── Price hits ₹2,850 → sell() → "SL_HIT" → PnL: -₹207.25
         └── 3:15 PM → sell() → "SQUARED_OFF" → PnL: varies
```

---

## 5.6 Daily End-of-Day Processing

```python
async def end_of_day_processing(db_session):
    """
    Runs at 3:30 PM IST every trading day.

    Steps:
    1. Force-close any remaining intraday positions (should be done by 3:15)
    2. Calculate daily performance for each agent:
       - Starting vs ending capital
       - Realized PnL
       - Unrealized PnL (for swing positions)
       - Win rate
       - Max drawdown
    3. Insert into daily_performance table
    4. Reset daily counters (today_trades, consecutive_losses if day was profitable)
    5. Log daily summary
    """
```

---

## 5.7 API Endpoints

```python
# GET  /api/trades                       → All trades across all agents
# GET  /api/trades/{agent_id}            → Trades for one agent
# GET  /api/trades/{id}/detail           → Full trade detail with AI reasoning
# GET  /api/positions                    → All open positions
# GET  /api/positions/{agent_id}         → Open positions for one agent
# GET  /api/risk/status                  → Current risk status for all agents
# GET  /api/risk/{agent_id}/circuit      → Circuit breaker status for one agent
# GET  /api/performance/daily            → Daily performance snapshots
# GET  /api/performance/{agent_id}/equity → Equity curve data for charting
```

---

## 5.8 Phase 5 Completion Checklist

| #  | Task                                              | Status |
|----|---------------------------------------------------|--------|
| 1  | Implement `risk_manager.py` with all 8 checks     | ☐     |
| 2  | Test circuit breaker triggers correctly            | ☐     |
| 3  | Test capital limit adjusts quantity properly       | ☐     |
| 4  | Test position and intraday limits                  | ☐     |
| 5  | Implement `virtual_broker.py` — buy()              | ☐     |
| 6  | Implement `virtual_broker.py` — sell()             | ☐     |
| 7  | Implement `virtual_broker.py` — short_sell()       | ☐     |
| 8  | Implement `virtual_broker.py` — cover()            | ☐     |
| 9  | Verify slippage and brokerage calculations         | ☐     |
| 10 | Implement `position_monitor.py` — SL/TP detection  | ☐     |
| 11 | Test stop-loss auto-triggers on price movement     | ☐     |
| 12 | Test target auto-triggers on price movement        | ☐     |
| 13 | Test intraday square-off at 3:15 PM                | ☐     |
| 14 | Implement end-of-day processing                    | ☐     |
| 15 | Test full flow: AI decision → risk → broker → DB   | ☐     |
| 16 | Create `/api/trades/*`, `/api/positions/*`, `/api/risk/*` endpoints | ☐ |

---

> **Phase 5 is COMPLETE when:** Every AI decision is validated through the risk manager, executed through the virtual broker with realistic costs, and monitored for automatic stop-loss/target/square-off. The full trade lifecycle (open → monitor → close) works end-to-end for all 4 agents independently.

> **Next →** [Phase 6: React.js Dashboard & Interactive Charting](./phase6.md)
