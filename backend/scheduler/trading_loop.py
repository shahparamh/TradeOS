from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database.connection import SessionLocal
from database.models import Agent, DailyPerformance, Trade, Position, AIResponse
from agents.agent_executor import execute_all_agents
from data.data_aggregator import aggregate_market_context
from data.market_fetcher import fetch_intraday_candles
from scanner.technical_engine import calculate_all_indicators, generate_indicator_summary
from scheduler.monitor import PositionMonitor
from utils.logger import setup_logger
from utils.constants import WATCHLIST
from datetime import datetime, date
import asyncio

logger = setup_logger("trading_scheduler")

class TradingScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
        self.is_running_cycle = False

    def start(self):
        """Starts the scheduler and registers jobs."""
        # 1. Main Trading Loop - Every 10 mins (9:15 AM - 3:30 PM IST)
        self.scheduler.add_job(
            self.run_trading_cycle,
            CronTrigger(day_of_week="mon-fri", hour="9-15", minute="*/10", timezone="Asia/Kolkata"),
            id="trading_loop",
            name="Main Trading Cycle",
            replace_existing=True
        )

        # 2. Position Monitor - Every 2 mins
        self.scheduler.add_job(
            self.run_monitor_cycle,
            "interval",
            minutes=2,
            id="monitor_loop",
            name="Position Monitor",
            replace_existing=True
        )

        # 3. End of Day - 3:45 PM IST
        self.scheduler.add_job(
            self.run_end_of_day,
            CronTrigger(day_of_week="mon-fri", hour=15, minute=45, timezone="Asia/Kolkata"),
            id="eod_job",
            name="End of Day Processor",
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("TradeOS Scheduler started.")

    async def run_monitor_cycle(self):
        """Runs the position monitor to check for SL/TP hits."""
        db = SessionLocal()
        try:
            monitor = PositionMonitor(db)
            exits = await monitor.check_all_positions()
            if exits:
                for ex in exits:
                    logger.info(f"Monitor Exit: {ex['agent']} | {ex['symbol']} | {ex['exit_reason']} | PnL: {ex['pnl']}")
        except Exception as e:
            logger.error(f"Monitor cycle error: {e}")
        finally:
            db.close()

    async def run_trading_cycle(self):
        """Executes the full trading pipeline."""
        if self.is_running_cycle:
            logger.warning("Cycle already in progress, skipping...")
            return
            
        from datetime import datetime, timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist)
        
        # 1. Market Days Check (0=Mon, 4=Fri)
        if now.weekday() > 4:
            logger.info("Market is closed (Weekend). Skipping trading cycle to save API keys.")
            return
            
        # 2. Market Hours Check (9:15 AM to 3:15 PM)
        market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=15, second=0, microsecond=0)
        
        if now < market_start or now > market_end:
            logger.info(f"Market is closed (Time: {now.strftime('%I:%M %p')}). Skipping trading cycle to save API keys.")
            return
            
        self.is_running_cycle = True
        db = SessionLocal()
        logger.info("=== TRADING CYCLE START ===")
        
        try:
            # 1. Market Context
            market_context = await aggregate_market_context()
            
            # 2. Get active agents
            agents = db.query(Agent).filter(Agent.is_active == True).all()
            
            # 3. Watchlist symbols (Loaded dynamically from constants)
            symbols = WATCHLIST
            
            for symbol in symbols:
                # Cooldown check: Skip stocks analyzed in the last 5 minutes
                from datetime import datetime, timedelta
                five_mins_ago = datetime.utcnow() - timedelta(minutes=15)
                recent_scan = db.query(AIResponse).filter(
                    AIResponse.symbol == symbol,
                    AIResponse.created_at >= five_mins_ago
                ).first()
                
                if recent_scan:
                    logger.info(f"Skipping {symbol} scan - recently analyzed in the last 5 minutes.")
                    continue
                    
                logger.info(f"Scanning {symbol}...")
                candles_df = fetch_intraday_candles(symbol, "5m", "5d")
                if candles_df.empty: continue
                
                indicators = generate_indicator_summary(calculate_all_indicators(candles_df), symbol)
                opportunity = {
                    "symbol": symbol,
                    "signal_type": "AUTOMATIC_SCAN",
                    "indicators": indicators
                }
                
                # Logic inside execute_all_agents handles calling AIs and executing trades via VirtualBroker
                await execute_all_agents(market_context, opportunity, [])
                
                # Small sleep to be kind to APIs
                await asyncio.sleep(10)
                
        except Exception as e:
            logger.error(f"Trading cycle error: {e}")
        finally:
            db.close()
            self.is_running_cycle = False
            logger.info("=== TRADING CYCLE END ===")

    async def run_end_of_day(self):
        """Calculates daily performance for all agents."""
        db = SessionLocal()
        today = date.today()
        logger.info(f"Running EOD Processing for {today}...")
        
        try:
            agents = db.query(Agent).all()
            for agent in agents:
                # Calculate daily stats
                trades_today = db.query(Trade).filter(
                    Trade.agent_id == agent.id,
                    Trade.exit_time >= datetime.combine(today, datetime.min.time())
                ).all()
                
                wins = [t for t in trades_today if (t.pnl or 0) > 0]
                losses = [t for t in trades_today if (t.pnl or 0) <= 0]
                
                realized_pnl = sum(t.pnl for t in trades_today if t.pnl)
                
                # Fetch open positions for unrealized pnl
                positions = db.query(Position).filter(Position.agent_id == agent.id).all()
                unrealized_pnl = sum(p.unrealized_pnl for p in positions)
                
                perf = DailyPerformance(
                    agent_id=agent.id,
                    date=today,
                    starting_capital=agent.cash_balance - realized_pnl, # Rough estimate
                    ending_capital=agent.cash_balance,
                    realized_pnl=realized_pnl,
                    unrealized_pnl=unrealized_pnl,
                    total_trades=len(trades_today),
                    winning_trades=len(wins),
                    losing_trades=len(losses),
                    win_rate=(len(wins)/len(trades_today)*100) if trades_today else 0
                )
                db.add(perf)
            
            db.commit()
            logger.info("EOD Processing complete.")
        except Exception as e:
            logger.error(f"EOD Processing error: {e}")
            db.rollback()
        finally:
            db.close()
