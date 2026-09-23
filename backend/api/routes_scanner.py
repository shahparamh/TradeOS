from fastapi import APIRouter
from scanner.opportunity_scanner import OpportunityScanner
from data.data_aggregator import aggregate_all_watchlist, aggregate_market_context

router = APIRouter(prefix="/scanner", tags=["Scanner"])
scanner = OpportunityScanner()

@router.get("/run")
async def run_scanner():
    """
    Manually triggers the scanner across the watchlist.
    Fetches live data, calculates indicators, and returns opportunities.
    """
    # 1. Fetch live data
    watchlist_data = await aggregate_all_watchlist()
    
    # Extract news & fundamentals from the aggregated data
    # (Since data_aggregator returns them nested)
    news_data = {}
    fundamentals = {}
    indicators_list = []
    
    from scanner.technical_engine import calculate_all_indicators, generate_indicator_summary
    import pandas as pd
    
    for stock in watchlist_data:
        if "error" in stock:
            continue
            
        symbol = stock["symbol"]
        news_data[symbol] = stock["news"]
        fundamentals[symbol] = stock["fundamentals"]
        
        # Convert candles dict list to DataFrame for technical analysis
        candles_list = stock["candles"]
        if candles_list:
            df = pd.DataFrame(candles_list)
            # rename for pandas_ta if needed
            df.rename(columns={"datetime": "Datetime", "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
            df["Datetime"] = pd.to_datetime(df["Datetime"])
            df.set_index("Datetime", inplace=True)
            
            # Calculate indicators
            enriched_df = calculate_all_indicators(df)
            summary = generate_indicator_summary(enriched_df, symbol)
            
            # Merge live price from data_aggregator into summary if needed
            summary["price"] = stock["price_data"].get("price", summary.get("price"))
            indicators_list.append(summary)

    # 2. Scan for opportunities
    opportunities = scanner.scan_all(indicators_list, news_data, fundamentals)
    
    return {
        "status": "success",
        "opportunities_found": len(opportunities),
        "opportunities": opportunities
    }


@router.get("/analyze/{symbol}")
async def analyze_stock_manually(symbol: str, market: str = "IN"):
    """
    Performs an instant ad-hoc technical and AI agent analysis on any stock symbol in the
    given market. Fetches live data, processes indicators, and queries all active agents
    concurrently. Does NOT execute trades in the database to prevent polluting simulation
    records.
    """
    from market_data.market_config import normalize_market
    from market_data.factory import get_provider
    from market_data.base import MarketDataError

    try:
        m = normalize_market(market)
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    symbol = symbol.upper()
    if m == "IN" and not symbol.endswith(".NS") and "." not in symbol:
        symbol = f"{symbol}.NS"

    try:
        import asyncio
        from scanner.technical_engine import calculate_all_indicators, generate_indicator_summary
        from data.data_aggregator import aggregate_market_context
        from data.news_fetcher import fetch_all_news_for_stock
        from data.fundamentals_fetcher import fetch_yf_fundamentals
        from agents.agent_executor import execute_all_agents

        provider = get_provider(m)

        # 1. Fetch intraday candles (5d window so the chart has enough history to be useful,
        # not just today's session). Must run in a thread — a blocking provider call would
        # otherwise freeze the single-threaded event loop and stall every other request.
        try:
            candles_df = await asyncio.to_thread(provider.get_intraday_candles, symbol, "5m", "5d")
        except MarketDataError as e:
            return {"status": "error", "message": e.message, "error_code": e.code}
        if candles_df.empty:
            return {"status": "error", "message": f"Could not fetch candle data for {symbol}."}

        # 2. Fetch live price
        try:
            price_res = await asyncio.to_thread(provider.get_quote, symbol)
        except MarketDataError as e:
            return {"status": "error", "message": e.message, "error_code": e.code}
        current_price = (price_res or {}).get("price", candles_df["Close"].iloc[-1])

        # 3. Calculate technical indicators
        enriched_df = calculate_all_indicators(candles_df)
        indicators = generate_indicator_summary(enriched_df, symbol)
        indicators["price"] = current_price

        # 4. Fetch Market Context (Index performance etc.), real news, and fundamentals concurrently.
        # fundamentals is REQUIRED — execute_all_agents() silently returns [] with no fundamentals
        # in the opportunity payload, which was quietly breaking every AI decision from this endpoint.
        # News/fundamentals fetchers are Indian-market-specific (NSE company map, yfinance) —
        # for US symbols skip them rather than sending India-shaped noise into the AI payload.
        if m == "IN":
            market_context, news, fundamentals = await asyncio.gather(
                aggregate_market_context(),
                asyncio.to_thread(fetch_all_news_for_stock, symbol),
                asyncio.to_thread(fetch_yf_fundamentals, symbol),
            )
        else:
            market_context, news, fundamentals = {}, [], {"symbol": symbol}
        news = news or []

        # 5. Build manual check payload — news and fundamentals are now part of both the AI payload and the response
        opportunity = {
            "symbol": symbol,
            "signal_type": "MANUAL_CHECK",
            "indicators": indicators,
            "fundamentals": fundamentals,
        }

        # 6. Execute all active agents concurrently (execute_trades=False is critical!)
        ai_decisions = await execute_all_agents(
            market_context=market_context,
            opportunity=opportunity,
            news=news,
            execute_trades=False
        )

        # 7. Format candles for the frontend chart (same shape as GET /market/candles/{symbol})
        candles = []
        df_reset = candles_df.reset_index()
        date_col = "Datetime" if "Datetime" in df_reset.columns else "Date"
        for _, row in df_reset.iterrows():
            candles.append({
                "datetime": str(row[date_col]),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })

        return {
            "status": "success",
            "symbol": symbol,
            "price": current_price,
            "technical_summary": indicators,
            "ai_decisions": ai_decisions,
            "news": news,
            "candles": candles,
        }

    except Exception as e:
        return {"status": "error", "message": f"Analysis failed: {str(e)}"}

