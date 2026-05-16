from fastapi import APIRouter
from agents.agent_executor import execute_all_agents
from data.data_aggregator import aggregate_market_context
from data.market_fetcher import fetch_intraday_candles
from data.news_fetcher import fetch_all_news_for_stock
from scanner.technical_engine import calculate_all_indicators, generate_indicator_summary
from scanner.opportunity_scanner import OpportunityScanner
import pandas as pd

router = APIRouter(prefix="/agents", tags=["AI Agents"])
scanner = OpportunityScanner()


@router.get("/test/{symbol}")
async def test_agents_on_symbol(symbol: str):
    """
    Manually test both AI agents on a specific stock symbol.
    This endpoint:
    1. Fetches live market data for the given symbol
    2. Calculates technical indicators
    3. Scans for opportunities
    4. Sends the data to Gemini & Grok concurrently
    5. Returns both AI decisions side-by-side
    """

    # 1. Fetch market context (indices, VIX)
    market_context = await aggregate_market_context()

    # 2. Fetch candles + indicators for the symbol
    candles_df = fetch_intraday_candles(symbol, "5m", "5d")
    if candles_df.empty:
        return {"error": f"No candle data found for {symbol}"}

    enriched_df = calculate_all_indicators(candles_df)
    indicators = generate_indicator_summary(enriched_df, symbol)

    # 3. Fetch news
    news = fetch_all_news_for_stock(symbol)

    # 4. Build a synthetic opportunity from the indicators
    # (In the real loop, OpportunityScanner would find this automatically)
    opportunity = {
        "symbol": symbol,
        "signal_type": "manual_test",
        "signal_strength": "moderate",
        "suggested_action": "ANALYZE",
        "reasons": ["Manual test trigger — AI should analyze independently"],
        "indicators": indicators,
    }

    # 5. Execute all agents
    decisions = await execute_all_agents(
        market_context=market_context,
        opportunity=opportunity,
        news=news,
    )

    return {
        "status": "success",
        "symbol": symbol,
        "indicators_summary": indicators,
        "news_count": len(news),
        "ai_decisions": [
            {
                "agent": d.get("agent"),
                "decision": d.get("decision"),
                "confidence": d.get("confidence"),
                "entry_price": d.get("entry_price"),
                "stop_loss": d.get("stop_loss"),
                "target": d.get("target"),
                "quantity": d.get("quantity"),
                "trade_type": d.get("trade_type"),
                "reasoning": d.get("reasoning"),
                "risk_reward_ratio": d.get("risk_reward_ratio"),
                "is_valid": d.get("is_valid"),
                "validation_errors": d.get("validation_errors", []),
                "latency_ms": d.get("latency_ms"),
            }
            for d in decisions
        ],
    }
