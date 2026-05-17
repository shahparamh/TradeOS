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
async def analyze_stock_manually(symbol: str):
    """
    Performs an instant ad-hoc technical and AI agent analysis on any NSE stock symbol.
    Fetches live data, processes indicators, and queries all active agents concurrently.
    Does NOT execute trades in the database to prevent polluting simulation records.
    """
    symbol = symbol.upper()
    if not symbol.endswith(".NS") and "." not in symbol:
        symbol = f"{symbol}.NS"
        
    try:
        import pandas as pd
        from data.market_fetcher import fetch_intraday_candles, fetch_live_price
        from scanner.technical_engine import calculate_all_indicators, generate_indicator_summary
        from data.data_aggregator import aggregate_market_context
        from agents.agent_executor import execute_all_agents
        
        # 1. Fetch intraday candles
        candles_df = fetch_intraday_candles(symbol, "5m", "1d")
        if candles_df.empty:
            return {"status": "error", "message": f"Could not fetch candle data for {symbol}."}
            
        # 2. Fetch live price
        price_res = fetch_live_price(symbol)
        current_price = price_res.get("price", candles_df["Close"].iloc[-1])
        
        # 3. Calculate technical indicators
        enriched_df = calculate_all_indicators(candles_df)
        indicators = generate_indicator_summary(enriched_df, symbol)
        indicators["price"] = current_price
        
        # 4. Fetch Market Context (Index performance etc.)
        market_context = await aggregate_market_context()
        
        # 5. Build manual check payload
        opportunity = {
            "symbol": symbol,
            "signal_type": "MANUAL_CHECK",
            "indicators": indicators
        }
        
        # 6. Execute all active agents concurrently (execute_trades=False is critical!)
        ai_decisions = await execute_all_agents(
            market_context=market_context,
            opportunity=opportunity,
            news=[],
            execute_trades=False
        )
        
        return {
            "status": "success",
            "symbol": symbol,
            "price": current_price,
            "technical_summary": indicators,
            "ai_decisions": ai_decisions
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Analysis failed: {str(e)}"}

