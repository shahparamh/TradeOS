from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database.connection import SessionLocal
from database.models import Agent, DailyPerformance, Trade, Position, AIResponse
from agents.agent_executor import execute_all_agents
from data.data_aggregator import aggregate_market_context
from data.market_fetcher import fetch_intraday_candles
from scanner.technical_engine import calculate_all_indicators, generate_indicator_summary
from broker.position_monitor import PositionMonitor
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
        # 1. Pre-Market Strategy Planner - At 9:00 AM IST
        self.scheduler.add_job(
            self.run_pre_market_session,
            CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone="Asia/Kolkata"),
            id="pre_market_strategy",
            name="Pre-Market Strategy Planner",
            replace_existing=True
        )

        # 2. Main Trading Loop - Every 10 mins (9:15 AM - 3:30 PM IST)
        self.scheduler.add_job(
            self.run_trading_cycle,
            CronTrigger(day_of_week="mon-fri", hour="9-15", minute="*/10", timezone="Asia/Kolkata"),
            id="trading_loop",
            name="Main Trading Cycle",
            replace_existing=True
        )

        # 3. Position Monitor - Every 2 mins
        self.scheduler.add_job(
            self.run_monitor_cycle,
            "interval",
            minutes=2,
            id="monitor_loop",
            name="Position Monitor",
            replace_existing=True
        )

        # 4. End of Day - 3:45 PM IST
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
            from broker.virtual_broker import VirtualBroker
            from config import settings
            broker = VirtualBroker(settings)
            monitor = PositionMonitor(broker)
            exits = await monitor.check_all_positions(db)
            if exits:
                for ex in exits:
                    logger.info(f"Monitor Exit: {ex['agent']} | {ex['symbol']} | {ex.get('reason', 'UNKNOWN')} | PnL: {ex.get('pnl', 0.0)}")
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
                
                # Dynamic news fetch if enabled in system rules
                from database.models import SystemRule
                enable_news = db.query(SystemRule).filter(SystemRule.key == "enable_news_sentiment").first()
                enable_news_bool = enable_news.bool_value if enable_news else True
                
                news_payload = []
                if enable_news_bool:
                    try:
                        from data.news_fetcher import fetch_all_news_for_stock
                        news_payload = fetch_all_news_for_stock(symbol) or []
                    except Exception as e:
                        logger.error(f"Failed to fetch news for {symbol}: {e}")
                
                # Logic inside execute_all_agents handles calling AIs and executing trades via VirtualBroker
                await execute_all_agents(market_context, opportunity, news_payload)
                
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

    async def run_pre_market_session(self):
        """Pre-market planner job: Decides bias, limits, targets, and stops before open (9:00 AM IST)."""
        db = SessionLocal()
        logger.info("=== PRE-MARKET STRATEGY SESSION START ===")
        try:
            # 1. Market Context
            market_context = await aggregate_market_context()
            
            # 2. Active Agents
            agents = db.query(Agent).filter(Agent.is_active == True).all()
            if not agents:
                logger.info("No active agents found for pre-market planning.")
                return
                
            # 3. Watchlist
            symbols = WATCHLIST
            
            from agents.prompts import PRE_MARKET_SYSTEM_PROMPT, build_pre_market_payload
            from data.news_fetcher import fetch_all_news_for_stock
            from database.models import AgentDailyStrategy
            from datetime import date
            
            # Importing agent clients dynamically to avoid circular references
            from agents.gemini_agent import query_gemini
            from agents.groq_agent import query_groq
            from agents.openrouter_agent import query_openrouter_free
            from agents.deepseek_agent import query_deepseek
            from agents.ollama_agent import query_ollama
            
            for symbol in symbols:
                # Fetch recent news to pass into LLM context
                news = []
                try:
                    news = fetch_all_news_for_stock(symbol)
                except Exception as ne:
                    logger.warning(f"Failed to fetch news for {symbol}: {ne}")
                    
                fundamentals = {"symbol": symbol, "desc": "NSE Watchlist Stock"}
                payload_str = build_pre_market_payload(symbol, market_context, news, fundamentals)
                
                for agent in agents:
                    # Skip if strategy already generated for today
                    existing = db.query(AgentDailyStrategy).filter(
                        AgentDailyStrategy.agent_id == agent.id,
                        AgentDailyStrategy.symbol == symbol,
                        AgentDailyStrategy.date == date.today()
                    ).first()
                    
                    if existing:
                        logger.info(f"Strategy already exists for {agent.name} on {symbol} today.")
                        continue
                        
                    decision_data = None
                    try:
                        if agent.provider == "google":
                            decision_data = await query_gemini(payload_str, system_prompt=PRE_MARKET_SYSTEM_PROMPT)
                        elif agent.provider == "groq":
                            decision_data = await query_groq(payload_str, system_prompt=PRE_MARKET_SYSTEM_PROMPT)
                        elif agent.provider == "openrouter":
                            import json
                            payload_dict = json.loads(payload_str)
                            decision_data = await query_openrouter_free(payload_dict, system_prompt=PRE_MARKET_SYSTEM_PROMPT)
                        elif agent.provider == "deepseek":
                            import json
                            payload_dict = json.loads(payload_str)
                            decision_data = await query_deepseek(payload_dict, system_prompt=PRE_MARKET_SYSTEM_PROMPT)
                        elif agent.provider == "ollama":
                            decision_data = await query_ollama(payload_str, system_prompt=PRE_MARKET_SYSTEM_PROMPT)
                    except Exception as ex:
                        logger.error(f"Error querying {agent.name} pre-market: {ex}")
                        continue
                        
                    if decision_data and isinstance(decision_data, dict):
                        bias = decision_data.get("daily_bias", "NEUTRAL").upper()
                        lower_lim = decision_data.get("entry_lower_limit")
                        upper_lim = decision_data.get("entry_upper_limit")
                        target = decision_data.get("target_price")
                        sl = decision_data.get("stop_loss")
                        reason = decision_data.get("reasoning", "Pre-market bias set.")
                        
                        strategy_record = AgentDailyStrategy(
                            agent_id=agent.id,
                            date=date.today(),
                            symbol=symbol,
                            daily_bias=bias,
                            entry_lower_limit=float(lower_lim) if lower_lim else None,
                            entry_upper_limit=float(upper_lim) if upper_lim else None,
                            target_price=float(target) if target else None,
                            stop_loss=float(sl) if sl else None,
                            reasoning=reason
                        )
                        db.add(strategy_record)
                        logger.info(f"Seeded pre-market setup for {agent.name} | {symbol} | Bias: {bias}")
                db.commit()
                await asyncio.sleep(1) # Kind to APIs
        except Exception as e:
            logger.error(f"Pre-market strategy session failed: {e}")
            db.rollback()
        finally:
            db.close()
            logger.info("=== PRE-MARKET STRATEGY SESSION END ===")
