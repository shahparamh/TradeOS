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
