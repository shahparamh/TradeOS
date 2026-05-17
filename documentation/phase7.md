# Phase 7 — Automation, Scheduling & 30-Day Live Simulation

> **Goal:** Wire the entire system together into a fully autonomous trading loop. The scheduler runs every 10 minutes during Indian market hours, executing the complete pipeline: fetch data → calculate indicators → scan opportunities → query all 4 AIs → validate decisions → execute trades → monitor positions → update dashboard. Then launch the official 30-day live-market simulation.

---

## 7.1 Architecture Overview — The Master Loop

```
                    ┌─────────────────────────────┐
                    │     APScheduler Engine       │
                    │     (Every 10 minutes)       │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  STEP 1: Is Market Open?     │
                    │  (9:15 AM - 3:30 PM IST)     │
                    └──────────────┬──────────────┘
                           YES     │     NO
                    ┌──────────────▼──┐   ┌──────────────────┐
                    │ TRADING LOOP    │   │ OFF-HOURS LOOP   │
                    │                 │   │ - Fetch news     │
                    │ Step 2: Fetch   │   │ - Update watchlist│
                    │   market data   │   │ - Analyze trends │
                    │                 │   └──────────────────┘
                    │ Step 3: Fetch   │
                    │   news          │
                    │                 │
                    │ Step 4: Calc    │
                    │   indicators    │
                    │                 │
                    │ Step 5: Scan    │
                    │   opportunities │
                    │                 │
                    │ Step 6: Monitor │
                    │   open positions│
                    │   (SL/TP check) │
                    │                 │
                    │ Step 7: Query   │
                    │   all 4 AIs     │
                    │   (concurrent)  │
                    │                 │
                    │ Step 8: Risk    │
                    │   validation    │
                    │                 │
                    │ Step 9: Execute │
                    │   trades        │
                    │                 │
                    │ Step 10: Save   │
                    │   to database   │
                    └─────────────────┘
```

---

## 7.2 Scheduler Setup — `scheduler/trading_loop.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from utils.helpers import is_market_open, get_ist_now
from utils.logger import setup_logger

logger = setup_logger("scheduler")

class TradingScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

    def start(self):
        """
        Registers all scheduled jobs and starts the scheduler.

        Jobs:
        1. Trading Loop       — Every 10 min, Mon-Fri, 9:15 AM - 3:30 PM IST
        2. Position Monitor   — Every 5 min, Mon-Fri, 9:15 AM - 3:30 PM IST
        3. End-of-Day Process — Once at 3:35 PM IST, Mon-Fri
        4. Pre-Market Prep    — Once at 9:00 AM IST, Mon-Fri
        5. News Crawler       — Every 30 min, 24/7
        """

        # Main trading loop — runs every 10 minutes during market hours
        self.scheduler.add_job(
            self.run_trading_cycle,
            CronTrigger(
                day_of_week="mon-fri",
                hour="9-15",
                minute="*/10",
                timezone="Asia/Kolkata"
            ),
            id="trading_loop",
            name="Main Trading Cycle",
            max_instances=1,                  # Prevent overlap
            misfire_grace_time=60             # Allow 60s late execution
        )

        # Position monitor — checks SL/TP every 5 minutes
        self.scheduler.add_job(
            self.run_position_monitor,
            CronTrigger(
                day_of_week="mon-fri",
                hour="9-15",
                minute="*/5",
                timezone="Asia/Kolkata"
            ),
            id="position_monitor",
            name="Position Monitor",
            max_instances=1
        )

        # End-of-day processing — runs once at 3:35 PM
        self.scheduler.add_job(
            self.run_end_of_day,
            CronTrigger(
                day_of_week="mon-fri",
                hour=15,
                minute=35,
                timezone="Asia/Kolkata"
            ),
            id="eod_processing",
            name="End of Day Processing"
        )

        # Pre-market preparation — runs at 9:00 AM
        self.scheduler.add_job(
            self.run_pre_market,
            CronTrigger(
                day_of_week="mon-fri",
                hour=9,
                minute=0,
                timezone="Asia/Kolkata"
            ),
            id="pre_market",
            name="Pre-Market Preparation"
        )

        # News crawler — runs every 30 minutes, 24/7
        self.scheduler.add_job(
            self.run_news_crawler,
            IntervalTrigger(minutes=30),
            id="news_crawler",
            name="News Crawler"
        )

        self.scheduler.start()
        logger.info("TradeOS Scheduler started — all jobs registered")
```

---

## 7.3 The Main Trading Cycle — Step by Step

```python
async def run_trading_cycle(self):
    """
    The MASTER function. Runs the complete trading pipeline.
    Called every 10 minutes during market hours.
    """
    cycle_id = generate_cycle_id()
    logger.info(f"═══ TRADING CYCLE START: {cycle_id} ═══")

    db = SessionLocal()

    try:
        # ──────────────────────────────────────────
        # STEP 1: Verify market is open
        # ──────────────────────────────────────────
        if not is_market_open():
            logger.info("Market is closed. Skipping trading cycle.")
            return

        # ──────────────────────────────────────────
        # STEP 2: Fetch market data for all watchlist stocks
        # ──────────────────────────────────────────
        logger.info("[Step 2] Fetching market data...")
        market_context = await aggregate_market_context()
        watchlist_data = await aggregate_all_watchlist()
        logger.info(f"  → Fetched data for {len(watchlist_data)} stocks")
        logger.info(f"  → Nifty: {market_context['nifty50']['value']} ({market_context['nifty50']['change_pct']}%)")

        # ──────────────────────────────────────────
        # STEP 3: Fetch latest news
        # ──────────────────────────────────────────
        logger.info("[Step 3] Fetching news...")
        news_data = await fetch_all_news_for_watchlist()
        logger.info(f"  → Fetched {sum(len(v) for v in news_data.values())} news articles")

        # ──────────────────────────────────────────
        # STEP 4: Calculate technical indicators
        # ──────────────────────────────────────────
        logger.info("[Step 4] Calculating indicators...")
        enriched_data = []
        for stock in watchlist_data:
            candles = await fetch_intraday_candles(stock["symbol"])
            if len(candles) >= 50:
                indicators = calculate_all_indicators(candles)
                summary = generate_indicator_summary(indicators, stock["symbol"])
                enriched_data.append(summary)
        logger.info(f"  → Calculated indicators for {len(enriched_data)} stocks")

        # ──────────────────────────────────────────
        # STEP 5: Scan for opportunities
        # ──────────────────────────────────────────
        logger.info("[Step 5] Scanning for opportunities...")
        scanner = OpportunityScanner()
        opportunities = scanner.scan_all(enriched_data, news_data, fundamentals={})
        logger.info(f"  → Found {len(opportunities)} opportunities")

        for opp in opportunities:
            logger.info(f"    📊 {opp['symbol']}: {opp['signal_type']} ({opp['signal_strength']})")

        # ──────────────────────────────────────────
        # STEP 6: Monitor existing positions (SL/TP)
        # ──────────────────────────────────────────
        logger.info("[Step 6] Monitoring open positions...")
        monitor = PositionMonitor(broker)
        position_actions = await monitor.check_all_positions(db)
        for action in position_actions:
            logger.info(f"    ⚡ {action['agent']}: {action['symbol']} → {action['exit_reason']} (PnL: ₹{action['pnl']})")

        # ──────────────────────────────────────────
        # STEP 7: Send opportunities to all 4 AIs
        # ──────────────────────────────────────────
        if len(opportunities) > 0:
            logger.info("[Step 7] Querying AI agents...")

            for opportunity in opportunities[:5]:  # Max 5 per cycle
                payload = build_full_payload(
                    cycle_id=cycle_id,
                    market_context=market_context,
                    opportunity=opportunity,
                    news=news_data.get(opportunity["symbol"], [])
                )

                # All 4 AIs get IDENTICAL data at the SAME time
                decisions = await execute_all_agents(payload)

                for decision in decisions:
                    logger.info(f"    🤖 {decision['agent']}: {decision['decision']} "
                              f"(confidence: {decision.get('confidence', 'N/A')})")

                    # ──────────────────────────────────────
                    # STEP 8: Risk validation per agent
                    # ──────────────────────────────────────
                    if decision["decision"] in ["BUY", "SHORT"] and decision["is_valid"]:
                        agent_state = get_agent_state(decision["agent"], db)
                        risk_check = risk_manager.validate_trade(decision, agent_state)

                        if risk_check["approved"]:
                            # ──────────────────────────────
                            # STEP 9: Execute trade
                            # ──────────────────────────────
                            if decision["decision"] == "BUY":
                                result = broker.buy(
                                    agent_id=agent_state["agent_id"],
                                    symbol=opportunity["symbol"],
                                    quantity=decision["quantity"],
                                    market_price=decision["entry_price"],
                                    stop_loss=decision["stop_loss"],
                                    target=decision["target"],
                                    confidence=decision["confidence"],
                                    trade_type=decision["trade_type"],
                                    db_session=db
                                )
                                logger.info(f"    ✅ {decision['agent']}: BOUGHT {opportunity['symbol']} "
                                          f"x{decision['quantity']} @ ₹{result['fill_price']}")

                            elif decision["decision"] == "SHORT":
                                result = broker.short_sell(
                                    agent_id=agent_state["agent_id"],
                                    symbol=opportunity["symbol"],
                                    quantity=decision["quantity"],
                                    market_price=decision["entry_price"],
                                    stop_loss=decision["stop_loss"],
                                    target=decision["target"],
                                    confidence=decision["confidence"],
                                    db_session=db
                                )
                                logger.info(f"    ✅ {decision['agent']}: SHORTED {opportunity['symbol']} "
                                          f"x{decision['quantity']} @ ₹{result['fill_price']}")
                        else:
                            logger.info(f"    ❌ {decision['agent']}: REJECTED — {risk_check['rejection_reason']}")

                    # ──────────────────────────────────────
                    # STEP 10: Save AI response to database
                    # ──────────────────────────────────────
                    save_ai_response(db, decision, cycle_id, opportunity["symbol"])

        else:
            logger.info("[Step 7] No opportunities found. AIs will not be queried.")

        # Save market snapshots
        for stock in enriched_data:
            save_market_snapshot(db, stock)

        db.commit()

    except Exception as e:
        logger.error(f"Trading cycle failed: {str(e)}", exc_info=True)
        db.rollback()
    finally:
        db.close()

    logger.info(f"═══ TRADING CYCLE END: {cycle_id} ═══\n")
```

---

## 7.4 Pre-Market Preparation (9:00 AM IST)

```python
async def run_pre_market(self):
    """
    Runs at 9:00 AM before market opens.

    Tasks:
    1. Reset daily counters for all agents (today_trades, consecutive_losses)
    2. Fetch overnight news for all watchlist stocks
    3. Fetch global market cues (US markets, Asian markets)
    4. Pre-calculate support/resistance from previous day
    5. Generate pre-market watchlist priorities
    6. Log pre-market summary
    """
```

---

## 7.5 End-of-Day Processing (3:35 PM IST)

```python
async def run_end_of_day(self):
    """
    Runs at 3:35 PM after market close.

    Tasks:
    1. Force-close any remaining intraday positions (should be done by 3:15)
    2. For each agent, calculate:
       - Starting capital vs ending capital
       - Realized PnL for the day
       - Unrealized PnL on swing positions
       - Win rate (wins / total trades today)
       - Max drawdown for the day
    3. Insert daily_performance record for each agent
    4. Update leaderboard rankings
    5. Generate daily summary report
    6. Log end-of-day results
    """
```

---

## 7.6 FastAPI Integration — Starting the Scheduler

```python
# backend/main.py — Add scheduler startup

from contextlib import asynccontextmanager
from scheduler.trading_loop import TradingScheduler

trading_scheduler = TradingScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    trading_scheduler.start()
    yield
    # Shutdown
    trading_scheduler.scheduler.shutdown()

app = FastAPI(lifespan=lifespan, title="TradeOS API")

# Add scheduler status endpoint
@app.get("/api/scheduler/status")
def scheduler_status():
    jobs = trading_scheduler.scheduler.get_jobs()
    return {
        "running": trading_scheduler.scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time),
                "trigger": str(job.trigger)
            }
            for job in jobs
        ]
    }

@app.post("/api/scheduler/trigger")
async def manual_trigger():
    """Manually trigger a trading cycle (for testing)."""
    await trading_scheduler.run_trading_cycle()
    return {"status": "cycle_completed"}
```

---

## 7.7 System Startup — How to Run Everything

### Terminal 1: Backend Server + Scheduler

```bash
cd TradeOS/backend
venv\Scripts\activate
python -m database.seed           # Seed agents + tables (first time only)
uvicorn main:app --reload --port 8000
```

### Terminal 2: Frontend Dashboard

```bash
cd TradeOS/frontend
npm run dev                       # Starts on http://localhost:5173
```

### What Happens Automatically:
```
✓ FastAPI starts on port 8000
✓ Scheduler starts and registers all jobs
✓ At 9:00 AM IST → Pre-market prep runs
✓ At 9:15 AM IST → First trading cycle begins
✓ Every 5 min    → Position monitor checks SL/TP
✓ Every 10 min   → Full trading cycle runs
✓ Every 30 min   → News crawler updates
✓ At 3:15 PM IST → Intraday positions squared off
✓ At 3:35 PM IST → End-of-day processing
✓ React dashboard → Auto-refreshes via polling
```

---

## 7.8 The 30-Day Simulation Protocol

### Rules of Engagement

| Rule | Detail |
|------|--------|
| **Duration** | 30 consecutive trading days (approx. 6 calendar weeks) |
| **Starting Capital** | ₹1,00,000 per AI agent (₹4,00,000 total across 4 agents) |
| **Watchlist** | 12 liquid NSE stocks (fixed for the entire simulation) |
| **Data** | Real live market data from Yahoo Finance + NSE |
| **AI Fairness** | All AIs receive identical data at the same timestamp |
| **Risk Rules** | Enforced identically across all agents — no exceptions |
| **Intervention** | ZERO manual intervention. System is fully autonomous. |
| **Logging** | Every decision, trade, and market snapshot is recorded |

### Success Metrics — Measured at Day 30

| Metric | How to Calculate | Why It Matters |
|--------|-----------------|----------------|
| **Total Return %** | (ending_capital - 100000) / 100000 | Raw profitability |
| **Win Rate** | winning_trades / total_trades | Decision accuracy |
| **Sharpe Ratio** | avg_daily_return / std_daily_return × √252 | Risk-adjusted return |
| **Max Drawdown** | worst peak-to-trough decline | Worst-case loss |
| **Profit Factor** | gross_profits / gross_losses | Reward per unit risk |
| **Avg Trade Duration** | avg(exit_time - entry_time) | Trading style |
| **Long vs Short Accuracy** | win_rate by position type | Directional skill |
| **Avg Confidence** | avg(confidence) across all decisions | Self-awareness |
| **Trade Frequency** | total_trades / trading_days | Activity level |
| **Invalid Response Rate** | invalid_responses / total_responses | Reliability |

### Daily Monitoring

During the simulation, check the dashboard daily for:
- [ ] All 4 agents are making decisions (no agent is stuck)
- [ ] Data feeds are working (prices updating during market hours)
- [ ] Circuit breakers haven't locked out all agents
- [ ] No database errors in logs
- [ ] Scheduler jobs are running on time

---

## 7.9 Post-Simulation: Transition to Real Money

After the 30-day simulation proves the system works:

### Step 1: Analyze Results
- Which AI performed best? (Total return + Sharpe Ratio)
- Which AI is most reliable? (Lowest invalid response rate)
- Are the risk rules too tight or too loose?

### Step 2: Choose a Real Broker API
- **Dhan HQ API** — Free, built for algo trading
- **Upstox API** — Free, well-documented
- **Angel One SmartAPI** — Free, widely used

### Step 3: Swap the Broker Module
Replace `virtual_broker.py` with `real_broker.py`:
```python
# broker/real_broker.py
# Same interface as VirtualBroker (buy, sell, short_sell, cover)
# But calls real broker API instead of simulating fills
```

### Step 4: Start with Minimal Capital
- Begin with ₹25,000-₹50,000
- Only enable the BEST performing AI initially
- Gradually add more capital and more AIs as confidence builds

---

## 7.10 Phase 7 Completion Checklist

| #  | Task                                              | Status |
|----|---------------------------------------------------|--------|
| 1  | Implement `TradingScheduler` with APScheduler      | ☐     |
| 2  | Implement `run_trading_cycle()` master function     | ☐     |
| 3  | Implement `run_position_monitor()` SL/TP checker    | ☐     |
| 4  | Implement `run_pre_market()` preparation            | ☐     |
| 5  | Implement `run_end_of_day()` EOD processing         | ☐     |
| 6  | Implement `run_news_crawler()` background crawler    | ☐     |
| 7  | Wire scheduler into FastAPI lifespan                | ☐     |
| 8  | Add `/api/scheduler/status` and `/trigger` endpoints | ☐    |
| 9  | Run full dry-run test (manual trigger)              | ☐     |
| 10 | Verify all 4 AIs receive identical data             | ☐     |
| 11 | Verify SL/TP auto-triggers work correctly           | ☐     |
| 12 | Verify intraday square-off at 3:15 PM works         | ☐     |
| 13 | Verify EOD processing generates daily_performance   | ☐     |
| 14 | Verify dashboard updates in real-time               | ☐     |
| 15 | Start the official 30-day live-market simulation     | ☐     |
| 16 | Monitor daily for 30 days                           | ☐     |
| 17 | Generate final comparison report at Day 30           | ☐     |

---

> **Phase 7 is COMPLETE when:** The entire system runs autonomously during Indian market hours, all 4 AI agents trade independently with their own portfolios, positions are auto-monitored for SL/TP, the dashboard reflects live state, and the 30-day simulation has been successfully completed.

---

## 🏁 FULL PROJECT COMPLETION

When all 7 phases are done, you will have:

```
✅ Phase 1 — Foundation, database, config
✅ Phase 2 — Market data + news + fundamentals
✅ Phase 3 — Technical indicators + opportunity scanner
✅ Phase 4 — 4 AI agents with fair comparison engine
✅ Phase 5 — Risk management + virtual broker + position monitor
✅ Phase 6 — React dashboard with interactive charts
✅ Phase 7 — Autonomous scheduler + 30-day simulation

= A FULLY AUTONOMOUS AI TRADING EVALUATION PLATFORM
```
