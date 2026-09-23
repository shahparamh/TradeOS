from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database.connection import SessionLocal
from database.models import Agent, DailyPerformance, Trade, Position, AIResponse
from agents.agent_executor import execute_all_agents
from data.data_aggregator import aggregate_market_context
from data.market_fetcher import fetch_intraday_candles_batch
from scanner.technical_engine import calculate_all_indicators, generate_indicator_summary
from broker.position_monitor import PositionMonitor
from utils.logger import setup_logger
from utils.constants import WATCHLIST, ARENA_WATCHLIST
from market_data.market_config import get_watchlist, MARKET_META, normalize_market
from market_data.factory import get_provider
from market_data.base import MarketDataError
from datetime import datetime, date
import asyncio

logger = setup_logger("trading_scheduler")


def _validate_data_integrity(symbol: str, indicators: dict, fundamentals: dict) -> tuple[bool, str]:
    """
    Validates that critical data is present and non-null before sending to agents.
    Returns (is_valid, reason_if_invalid)
    """
    # 1. Check indicators have values
    critical_indicators = ["rsi", "macd", "volume_ratio", "ema_20", "ema_50", "vwap"]
    for ind in critical_indicators:
        val = indicators.get(ind)
        if val is None or (isinstance(val, float) and val != val):  # NaN check
            return False, f"Missing or null indicator: {ind}"
    
    # 2. Check for reasonable indicator ranges
    rsi = indicators.get("rsi", 50)
    if not (0 <= rsi <= 100):
        return False, f"Invalid RSI value: {rsi}"
    
    volume_ratio = indicators.get("volume_ratio", 1.0)
    if volume_ratio <= 0:
        return False, f"Invalid volume ratio: {volume_ratio}"
    
    # 3. Check price data exists
    price_related = ["price", "ema_20", "ema_50", "vwap"]
    for field in price_related:
        val = indicators.get(field)
        if val is None or val <= 0:
            return False, f"Invalid or missing price field: {field}"
    
    # 4. Fundamentals can be minimal, but shouldn't be completely empty
    # (It's okay if market_cap is None, but at least "symbol" should exist)
    if not fundamentals.get("symbol"):
        return False, "Fundamentals missing symbol"
    
    # 5. Ensure we have at least candlestick pattern
    pattern = indicators.get("candlestick_pattern")
    if pattern is None:
        return False, "Missing candlestick pattern"
    
    return True, ""

class TradingScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
        self.is_running_cycle = False
        self.cycle_start_time = None

    def start(self):
        """Starts the scheduler and registers jobs."""
        # 0. Daily Fundamentals Refresh - 1:00 AM IST
        self.scheduler.add_job(
            self.run_fundamentals_refresh,
            CronTrigger(hour=1, minute=0, timezone="Asia/Kolkata"),
            id="daily_fundamentals_refresh",
            name="Daily Fundamentals Refresh",
            replace_existing=True
        )
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

        # 2b. Survival Arena Cycle - Every 10 mins, offset 5 min from the Fleet cycle above
        # (9:05/9:15/9:25/... vs 9:00/9:10/9:20/...) so the two cycles never fire in the same
        # minute. Both hit the same global yfinance rate limiter and LLM providers; firing
        # together was causing each cycle to queue behind the other's calls, turning a
        # ~7-8 min cycle into 30-40+ min gaps under real concurrent load.
        self.scheduler.add_job(
            self.run_arena_cycle,
            CronTrigger(day_of_week="mon-fri", hour="9-15", minute="5-59/10", timezone="Asia/Kolkata"),
            id="arena_loop",
            name="Survival Arena Cycle (India)",
            replace_existing=True,
            kwargs={"market": "IN"},
        )

        # 2c. Survival Arena Cycle — US market, regular session only (9:30 AM - 4:00 PM ET).
        # Runs on the US exchange's own timezone/hours rather than IST — never assume NSE
        # hours apply here. Offset 5 minutes into each 10-minute window for the same
        # rate-limiter/provider-contention reason as the IN cycle above.
        self.scheduler.add_job(
            self.run_arena_cycle,
            CronTrigger(day_of_week="mon-fri", hour="9-15", minute="5-59/10", timezone="America/New_York"),
            id="arena_loop_us",
            name="Survival Arena Cycle (US)",
            replace_existing=True,
            kwargs={"market": "US"},
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

        # 5. Render Keep-Alive - Every 2 mins (only if BACKEND_URL is set)
        from config import settings
        from datetime import datetime
        if settings.BACKEND_URL:
            self.scheduler.add_job(
                self.ping_self,
                "interval",
                minutes=2,
                next_run_time=datetime.now(),
                id="keep_alive_job",
                name="Keep Render App Alive",
                replace_existing=True
            )
            logger.info(f"Scheduled keep-alive ping for backend every 2 mins: {settings.BACKEND_URL}")

        self.scheduler.start()
        logger.info("TradeOS Scheduler started.")

    async def ping_self(self):
        """Pings own health endpoint externally to keep the Render container awake."""
        from config import settings
        import httpx
        if not settings.BACKEND_URL:
            return
        url = f"{settings.BACKEND_URL.rstrip('/')}/api/health"
        headers = {"User-Agent": "TradeOS-KeepAlive/1.0"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)
                if response.status_code == 200:
                    logger.info(f"[Keep-Alive] Self-ping successful: {response.json()}")
                else:
                    logger.warning(f"[Keep-Alive] Self-ping returned status code: {response.status_code}")
        except Exception as e:
            logger.error(f"[Keep-Alive] Self-ping failed: {e}")

    async def run_monitor_cycle(self, ignore_hours: bool = False):
        """Runs the position monitor to check for SL/TP hits. Skips only when NEITHER
        market is currently in its regular session — IN and US run on independent
        timezones/hours, so an IN-hours gate alone would starve US position monitoring."""
        if not ignore_hours:
            from datetime import datetime, timezone, timedelta
            from utils.market_calendar import is_market_holiday
            ist = timezone(timedelta(hours=5, minutes=30))
            now = datetime.now(ist)

            in_open = False
            if not is_market_holiday(now.date()):
                market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
                market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
                in_open = market_start <= now <= market_end

            us_open = False
            try:
                # Alpaca's clock check is a synchronous `requests` call — must run off the
                # event loop thread. Without to_thread, this blocks EVERY coroutine on the
                # single-worker server (including unrelated health checks) for up to the
                # request timeout, every 2 minutes.
                us_status = await asyncio.to_thread(get_provider("US").get_market_status)
                us_open = us_status.get("is_open", False)
            except MarketDataError:
                pass

            if not in_open and not us_open:
                return

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

            # Survival Arena bookkeeping: reflection memory for closed arena trades, then death check.
            from database.models import Agent as AgentModel, Trade as TradeModel
            from agents.arena_debate import record_reflection
            for ex in exits:
                agent_row = db.query(AgentModel).filter(AgentModel.name == ex.get("agent")).first()
                if agent_row and agent_row.mode == "SURVIVAL":
                    trades = db.query(TradeModel).filter(
                        TradeModel.agent_id == agent_row.id,
                        TradeModel.symbol == ex.get("symbol"),
                        TradeModel.status.isnot(None),
                    ).order_by(TradeModel.exit_time.desc()).first()
                    if trades:
                        record_reflection(db, agent_row, trades)
            if exits:
                db.commit()

            from broker import survival_guard
            death_events = survival_guard.check_deaths(db, broker)
            for ev in death_events:
                logger.warning(f"ARENA DEATH: {ev['agent']} (id={ev['agent_id']}) died with final equity ₹{ev['final_equity']:.2f}")
        except Exception as e:
            logger.error(f"Monitor cycle error: {e}")
        finally:
            db.close()

    async def run_fundamentals_refresh(self):
        """Refreshes fundamentals cache once per day during IST night window."""
        try:
            from data.fundamentals_fetcher import refresh_daily_fundamentals
            await asyncio.to_thread(refresh_daily_fundamentals, WATCHLIST)
        except Exception as e:
            logger.error(f"Daily fundamentals refresh error: {e}")

    async def run_trading_cycle(self, ignore_hours: bool = False):
        """Executes the full trading pipeline."""
        from datetime import datetime, timezone, timedelta
        
        if self.is_running_cycle:
            if self.cycle_start_time and (datetime.now() - self.cycle_start_time).total_seconds() > 300:
                logger.warning("Previous cycle timed out (5 mins exceeded). Forcing new cycle.")
                self.is_running_cycle = False
            else:
                logger.warning("Cycle already in progress, skipping...")
                return
            
        ist = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist)
        
        if not ignore_hours:
            # 1. Market Days & Holiday Check
            from utils.market_calendar import is_market_holiday
            if is_market_holiday(now.date()):
                logger.info("Market is closed (Weekend or Holiday). Skipping trading cycle to save API keys.")
                return
                
            # 2. Market Hours Check (9:15 AM to 3:15 PM)
            market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
            market_end = now.replace(hour=15, minute=15, second=0, microsecond=0)
            
            if now < market_start or now > market_end:
                logger.info(f"Market is closed (Time: {now.strftime('%I:%M %p')}). Skipping trading cycle to save API keys.")
                return
            
        self.is_running_cycle = True
        self.cycle_start_time = datetime.now()
        db = SessionLocal()
        logger.info("=== TRADING CYCLE START ===")
        
        try:
            # 1. Market Context
            market_context = await aggregate_market_context()
            
            # 2. Get active agents (Fleet mode only — Survival Arena agents run through run_arena_cycle)
            agents = db.query(Agent).filter(Agent.is_active == True, Agent.mode != "SURVIVAL").all()

            # 3. Watchlist symbols (Loaded dynamically from constants)
            symbols = WATCHLIST

            # Fetch rules for category switches and cooldowns
            from database.models import SystemRule
            enable_equity = db.query(SystemRule).filter(SystemRule.key == "enable_equity_trading").first()
            enable_equity_bool = enable_equity.bool_value if enable_equity else True

            enable_fno = db.query(SystemRule).filter(SystemRule.key == "enable_fno_trading").first()
            enable_fno_bool = False # Temporarily disabled FNO trading

            equity_cooldown = db.query(SystemRule).filter(SystemRule.key == "equity_ai_cooldown_min").first()
            equity_cooldown_min = float(equity_cooldown.numeric_value) if equity_cooldown else 30.0

            fno_cooldown = db.query(SystemRule).filter(SystemRule.key == "fno_ai_cooldown_min").first()
            fno_cooldown_min = float(fno_cooldown.numeric_value) if fno_cooldown else 30.0

            # Batch-fetch intraday candles for the whole watchlist in one yfinance call
            # instead of one rate-limited round trip per symbol (see fetch_intraday_candles_batch).
            batch_candles = await asyncio.to_thread(fetch_intraday_candles_batch, tuple(symbols), "5m", "5d")

            # Scan symbols sequentially to prevent rate limits and overloading the APIs
            for symbol in symbols:
                # 1. Category check
                is_fno = symbol.startswith("^") or symbol in ["^NSEI", "^NSEBANK", "NIFTY", "BANKNIFTY", "FINNIFTY"]
                if is_fno and not enable_fno_bool:
                    logger.info(f"Skipping {symbol} scan - F&O trading is disabled.")
                    continue
                if not is_fno and not enable_equity_bool:
                    logger.info(f"Skipping {symbol} scan - Equity trading is disabled.")
                    continue
                
                local_db = SessionLocal()
                try:
                    # 2. Cooldown check: Skip stocks analyzed within the cooldown window (30 mins default)
                    from datetime import datetime, timedelta
                    cooldown_min = fno_cooldown_min if is_fno else equity_cooldown_min
                    cooldown_start = datetime.utcnow() - timedelta(minutes=cooldown_min)
                    
                    recent_scan = local_db.query(AIResponse).filter(
                        AIResponse.symbol == symbol,
                        AIResponse.created_at >= cooldown_start
                    ).first()
                    
                    if not ignore_hours and recent_scan:
                        logger.info(f"Skipping {symbol} scan - recently analyzed in the last {cooldown_min} minutes.")
                        continue
                        
                    logger.info(f"Scanning {symbol}...")
                    candles_df = batch_candles.get(symbol)
                    if candles_df is None or candles_df.empty:
                        continue

                    indicators = generate_indicator_summary(calculate_all_indicators(candles_df), symbol)

                    # PRE-FILTER 1: Extreme Indecision + Ultra-low Volume Filter
                    # Only skip if RSI is highly indecisive (45-55) AND volume is extremely low (<1.0x average)
                    rsi = indicators.get("rsi", 50.0)
                    vol_ratio = indicators.get("volume_ratio", 1.0)
                    pattern = indicators.get("candlestick_pattern", "None")
                    
                    if not ignore_hours and (45 <= rsi <= 55) and vol_ratio < 0.8:
                        logger.info(f"Skipping {symbol} - Extreme indecision (RSI: {rsi}, Vol: {vol_ratio}x).")
                        continue
                    
                    # Fetch stock-specific fundamental metrics (P/E, ROE, 52W High/Low, Sector)
                    from data.fundamentals_fetcher import fetch_yf_fundamentals
                    fundamentals = await asyncio.to_thread(fetch_yf_fundamentals, symbol)
                    
                    # Fetch Derivatives Option Chain Open Interest (OI) & PCR (Put-Call Ratio)
                    # If OI fetch fails due to rate limiting, scanner will still work with other indicators
                    from data.market_fetcher import fetch_option_oi_metrics
                    oi_metrics = await asyncio.to_thread(fetch_option_oi_metrics, symbol)
                    if not oi_metrics.get("total_call_oi", 0) and not oi_metrics.get("total_put_oi", 0):
                        logger.debug(f"No OI data for {symbol}—proceeding without derivatives metrics.")
                    
                    # Dynamic news fetch if enabled in system rules
                    from database.models import SystemRule
                    enable_news = local_db.query(SystemRule).filter(SystemRule.key == "enable_news_sentiment").first()
                    enable_news_bool = enable_news.bool_value if enable_news else True
                    
                    news_payload = []
                    if enable_news_bool:
                        try:
                            from data.news_fetcher import fetch_all_news_for_stock
                            news_payload = await asyncio.to_thread(fetch_all_news_for_stock, symbol) or []
                        except Exception as e:
                            logger.error(f"Failed to fetch news for {symbol}: {e}")
                            
                    # PRE-FILTER 2: Full Opportunity Scanner
                    from scanner.opportunity_scanner import OpportunityScanner
                    scanner = OpportunityScanner()
                    opps = scanner.scan_all([indicators], {symbol: news_payload}, {symbol: fundamentals}, {symbol: oi_metrics})
                    
                    if not ignore_hours and not opps:
                        logger.info(f"Skipping {symbol} - No scanner opportunities found.")
                        continue
                    
                    # PRE-FILTER 3: Data Integrity Validation
                    # Ensure all critical data is present before sending to AI agents
                    is_valid, validation_error = _validate_data_integrity(symbol, indicators, fundamentals)
                    if not is_valid:
                        logger.warning(f"Skipping {symbol} - Data integrity check failed: {validation_error}")
                        continue
                        
                    scanner_signals = [o["signal_type"] for o in opps] if opps else []
                    
                    opportunity = {
                        "symbol": symbol,
                        "signal_type": "AUTOMATIC_SCAN",
                        "scanner_signals": scanner_signals,
                        "indicators": indicators,
                        "fundamentals": fundamentals,
                        "derivatives_oi": oi_metrics,
                        "ignore_hours": ignore_hours
                    }
                    
                    # Logic inside execute_all_agents handles calling AIs and executing trades via VirtualBroker
                    await execute_all_agents(market_context, opportunity, news_payload)
                    
                    # Inter-symbol delay of 10 seconds to prevent rate limit hammering
                    # Global rate limiter is 3.0s, but we need breathing room for API response times
                    await asyncio.sleep(10)
                    
                except Exception as inner_ex:
                    logger.error(f"Failed to process scan for {symbol}: {inner_ex}")
                finally:
                    try:
                        local_db.close()
                    except Exception as ex:
                        logger.error(f"Error closing local db for {symbol}: {ex}")
                
        except Exception as e:
            logger.error(f"Trading cycle error: {e}")
        finally:
            try:
                db.close()
            except Exception as e:
                logger.error(f"Error closing main db session: {e}")
            self.is_running_cycle = False
            logger.info("=== TRADING CYCLE END ===")

    async def run_arena_cycle(self, ignore_hours: bool = False, market: str = "IN"):
        """Survival Arena pipeline: scans the given market's watchlist and runs the
        multi-role debate pipeline for every non-dead SURVIVAL agent in that market.
        Mirrors run_trading_cycle's structure but is intentionally simpler — cash equity
        only, no F&O/derivatives context. `market` selects both the watchlist/provider AND
        which agents participate (agents are scoped to one market via Agent.market)."""
        from database.models import Agent, SystemRule
        import pytz

        market = normalize_market(market)
        meta = MARKET_META[market]
        tz = pytz.timezone(meta["timezone"])
        now = datetime.now(tz)

        if not ignore_hours:
            if market == "IN":
                from utils.market_calendar import is_market_holiday
                if is_market_holiday(now.date()):
                    return
                market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
                market_end = now.replace(hour=15, minute=15, second=0, microsecond=0)
                if now < market_start or now > market_end or now.weekday() >= 5:
                    return
            else:
                # US regular session only (9:30 AM - 4:00 PM ET, Mon-Fri). No pre-market/
                # after-hours candles get fed into this strategy.
                try:
                    status_ = await asyncio.to_thread(get_provider("US").get_market_status)
                    if not status_.get("is_open"):
                        return
                except MarketDataError:
                    logger.warning("[Arena/US] Could not check Alpaca market clock; skipping cycle.")
                    return

        db = SessionLocal()
        try:
            stop_rule = db.query(SystemRule).filter(SystemRule.key == "arena_emergency_stop").first()
            if stop_rule and stop_rule.bool_value:
                logger.info("Survival Arena is paused (emergency stop active). Skipping cycle.")
                return

            agents = db.query(Agent).filter(
                Agent.mode == "SURVIVAL",
                Agent.is_active == True,
                Agent.is_dead == False,
                Agent.market == market,
            ).all()
            if not agents:
                return

            market_context = await aggregate_market_context() if market == "IN" else {}

            from broker.virtual_broker import VirtualBroker
            from broker.survival_risk_manager import SurvivalRiskManager
            from agents.arena_debate import run_arena_debate
            from database.models import Position, Trade
            from config import settings
            broker = VirtualBroker(settings)

            watchlist = get_watchlist(market)
            provider = get_provider(market)

            # Batch-fetch intraday candles for the whole arena watchlist in one provider call.
            batch_candles = await asyncio.to_thread(provider.get_intraday_candles_batch, tuple(watchlist), "5m", "5d")

            for symbol in watchlist:
                local_db = SessionLocal()
                try:
                    candles_df = batch_candles.get(symbol)
                    if candles_df is None or candles_df.empty:
                        continue
                    indicators = generate_indicator_summary(calculate_all_indicators(candles_df), symbol)

                    # News/fundamentals fetchers are Indian-market-specific (NSE company map,
                    # yfinance) — not wired up for US symbols yet. Feed the analyst team a
                    # minimal, explicitly-labeled stub instead of India-shaped data.
                    if market == "IN":
                        from data.fundamentals_fetcher import fetch_yf_fundamentals
                        fundamentals = await asyncio.to_thread(fetch_yf_fundamentals, symbol)

                        from data.news_fetcher import fetch_all_news_for_stock
                        news_payload = await asyncio.to_thread(fetch_all_news_for_stock, symbol) or []
                    else:
                        fundamentals = {"symbol": symbol, "note": "US fundamentals not yet integrated"}
                        news_payload = []

                    is_valid, validation_error = _validate_data_integrity(symbol, indicators, fundamentals)
                    if not is_valid:
                        logger.warning(f"[Arena] Skipping {symbol} - {validation_error}")
                        continue

                    opportunity = {
                        "symbol": symbol,
                        "market": market,
                        "indicators": indicators,
                        "fundamentals": fundamentals,
                        "news": news_payload,
                        "ignore_hours": ignore_hours,
                    }

                    for agent in agents:
                        agent_row = local_db.query(Agent).get(agent.id)
                        if not agent_row or agent_row.is_dead:
                            continue

                        positions = local_db.query(Position).filter(Position.agent_id == agent_row.id).all()
                        if any(p.symbol == symbol for p in positions):
                            continue
                        if len(positions) >= SurvivalRiskManager.MAX_OPEN_POSITIONS:
                            continue

                        agent_state = {
                            "cash_balance": agent_row.cash_balance,
                            "starting_capital": agent_row.starting_capital,
                            "open_positions_value": sum(p.unrealized_pnl or 0.0 for p in positions),
                            "positions_count": len(positions),
                            "open_symbols": [p.symbol for p in positions],
                            "is_dead": agent_row.is_dead,
                        }

                        decision = await run_arena_debate(agent_row, opportunity, agent_state, local_db)

                        if decision.get("decision") == "BUY":
                            current_price = indicators.get("price")
                            result = broker.buy(
                                agent_row, symbol, decision["quantity"], current_price,
                                decision["stop_loss"], decision["target"], decision.get("confidence", 0),
                                "INTRADAY", local_db, "LONG",
                            )
                            if result.get("success"):
                                local_db.commit()
                                logger.info(f"[Arena] {agent_row.name} bought {decision['quantity']} {symbol} @ {result['fill_price']}")
                            else:
                                logger.warning(f"[Arena] Buy failed for {agent_row.name} on {symbol}: {result.get('error')}")

                        await asyncio.sleep(5)

                except Exception as inner_ex:
                    logger.error(f"[Arena] Failed to process {symbol}: {inner_ex}")
                finally:
                    local_db.close()

        except Exception as e:
            logger.error(f"Arena cycle error: {e}")
        finally:
            db.close()

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
            
            # 2. Active Agents (Fleet mode only)
            agents = db.query(Agent).filter(Agent.is_active == True, Agent.mode != "SURVIVAL").all()
            if not agents:
                logger.info("No active agents found for pre-market planning.")
                return
                
            # 3. Watchlist
            symbols = WATCHLIST
            
            # Fetch rules for category switches
            from database.models import SystemRule
            enable_equity = db.query(SystemRule).filter(SystemRule.key == "enable_equity_trading").first()
            enable_equity_bool = enable_equity.bool_value if enable_equity else True
            
            enable_fno = db.query(SystemRule).filter(SystemRule.key == "enable_fno_trading").first()
            enable_fno_bool = False # Temporarily disabled FNO trading
            
            from agents.prompts import PRE_MARKET_SYSTEM_PROMPT, build_pre_market_payload
            from data.news_fetcher import fetch_all_news_for_stock
            from database.models import AgentDailyStrategy
            from datetime import date
            
            # Importing agent clients dynamically to avoid circular references
            from agents.gemini_agent import query_gemini
            from agents.groq_agent import query_groq
            from agents.ollama_agent import query_ollama
            
            for symbol in symbols:
                # Category check
                is_fno = symbol.startswith("^") or symbol in ["^NSEI", "^NSEBANK", "NIFTY", "BANKNIFTY", "FINNIFTY"]
                if is_fno and not enable_fno_bool:
                    logger.info(f"Skipping pre-market planning for {symbol} - F&O trading is disabled.")
                    continue
                if not is_fno and not enable_equity_bool:
                    logger.info(f"Skipping pre-market planning for {symbol} - Equity trading is disabled.")
                    continue
                # Fetch recent news to pass into LLM context
                news = []
                try:
                    news = await asyncio.to_thread(fetch_all_news_for_stock, symbol)
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
                        elif agent.provider == "ollama":
                            import os
                            if os.getenv("RENDER"):
                                logger.info("Skipping local Ollama pre-market setup in Render cloud.")
                                continue
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
