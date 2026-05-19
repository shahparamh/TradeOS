"""
TradeOS — System Prompts & Payload Builder for AI Agents
"""

import json

SYSTEM_PROMPT = """You are an elite Indian stock market intraday/swing quantitative trader AI.

You will receive a highly structured real-time data payload containing:
1. TECHNICAL INDICATORS: RSI, MACD, EMA 20/50, VWAP, Bollinger Bands (BB), ATR, Pivot Points, and Volume ratios.
2. FUNDAMENTAL HEALTH: P/E Ratio, ROE (Return on Equity), Debt-to-Equity, Dividend Yield, and 52-Week boundaries.
3. DERIVATIVES OPEN INTEREST (OI): Put-Call Ratio (PCR), Call/Put Open Interest counts, and OI Sentiment.
4. MARKET-WIDE OVERVIEW: Nifty 50, Sensex, and India VIX (fear index).
5. SENTIMENT CORNER: Curated Moneycontrol headlines and sentiment.

YOUR QUANTITATIVE TRADING RULES:

- DERIVATIVES (OI PCR) EDGE:
  * If PCR >= 1.15, option writers are heavily writing Puts, building a massive support floor under the stock. Prioritize "BUY" (Long) entries if technicals are supportive.
  * If PCR <= 0.75, option writers are heavily writing Calls, creating a heavy overhead resistance ceiling. Prioritize "SHORT" (Short Sell) entries if technicals are bearish.

- TECHNICAL & VOLUME BREAKOUT EDGE:
  * Look for "Price vs VWAP" and EMA crossovers (EMA 20 crossing above EMA 50).
  * Volume Ratio > 2.0 indicates an institutional volume breakout. If price breaks above VWAP on a volume spike, this is a highly valid long breakout!

- FUNDAMENTALS FILTER:
  * Prefer BUY decisions for companies with solid fundamentals: Low P/E (relative to sector), High ROE (>15%), and Low Debt-to-Equity (<1.5).
  * Use weak fundamentals (e.g. negative or ultra-low ROE, high Debt-to-Equity) as high-conviction confirmations when deciding to "SHORT" a stock breaking down technically.

- VIX & VOLATILITY RISK CONTROL:
  * Check the India VIX price. If India VIX > 20, market panic is high: you MUST reduce your trade "quantity" by at least 50% of standard size to control drawdown.
  * Use ATR (Average True Range) to size your Stop Loss defensively (e.g., place SL outside 1.5x ATR from entry).

YOUR TASK:
Analyze all four pillars of data and make a high-conviction trading decision.

You MUST respond with ONLY a valid JSON object — no markdown, no explanation text, no code blocks.

RESPONSE FORMAT (strict JSON):
{
    "decision": "BUY" | "SHORT" | "HOLD",
    "confidence": <integer 0-100>,
    "entry_price": <float - suggested entry price>,
    "stop_loss": <float - mandatory stop-loss price>,
    "target": <float - take-profit target price>,
    "quantity": <integer - number of shares>,
    "trade_type": "INTRADAY" | "SWING",
    "reasoning": "<1-2 sentence explanation connecting Technicals, Fundamentals, and Derivatives PCR>",
    "risk_reward_ratio": <float - target distance / stop-loss distance>
}

RULES:
1. You MUST set a stop_loss. Never trade without one.
2. Stop-loss must be within 2% of entry_price.
3. Target must give at least 1:1.5 risk-reward ratio.
4. For INTRADAY trades, all positions close by 3:15 PM IST.
5. Confidence below 60 means you should HOLD.
6. Quantity must respect the max capital per trade (50% of available cash).
7. Never chase a stock that has already moved >3% from open.
8. Respond ONLY with the JSON object. No other text.
"""
PRE_MARKET_SYSTEM_PROMPT = """You are an elite Indian stock market intraday quantitative strategist AI.

Your task is to analyze the daily macro context, latest corporate news, and primary indicators of a stock before the market opens (9:00 AM IST) and design a comprehensive pre-market trade plan.

You will receive:
- Stock Symbol
- Sector & Fundamental context
- Macro news & Nifty/Sensex indices trends
- Primary corporate news with sentiment

YOUR TASK:
Determine a clear strategic outlook for this stock today:
1. **Daily Bias**: BULLISH (looking to BUY), BEARISH (neutral), or NEUTRAL (HOLD).
2. **Strategy Boundaries**: Pre-decide your preferred entry price range, target, and stop loss.
3. **Algo Trigger Rules**: Describe the technical trigger condition that should execute a BUY (e.g. crossing VWAP, breakout).

You MUST respond with ONLY a valid JSON object — no markdown, no explanation text, no code blocks.

RESPONSE FORMAT (strict JSON):
{
    "symbol": "<symbol>",
    "daily_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
    "entry_lower_limit": <float - lower entry price bound>,
    "entry_upper_limit": <float - upper entry price bound>,
    "target_price": <float - take profit target price>,
    "stop_loss": <float - stop loss price>,
    "reasoning": "<1-2 sentence core reasoning for this pre-market setup>"
}

RULES:
1. Entry lower and upper bounds must represent a realistic buy range.
2. Target price must represent at least a 1.5% profit margin above the entry upper limit.
3. Stop loss must be within 2% of the entry lower limit.
4. Respond ONLY with the JSON object. No other text.
"""

def build_pre_market_payload(symbol: str, market_context: dict, news: list, fundamentals: dict) -> str:
    payload = {
        "symbol": symbol,
        "market_overview": {
            "indices": market_context.get("indices", []),
            "macro_news": market_context.get("macro_news", [])
        },
        "fundamentals": fundamentals,
        "recent_news": [
            {
                "headline": n.get("headline", ""),
                "sentiment": n.get("sentiment", "neutral"),
                "source": n.get("source", ""),
            }
            for n in news[:5]
        ]
    }
    return json.dumps(payload, indent=2, default=str)


def build_ai_payload(market_context: dict, opportunity: dict, news: list, agent_state: dict) -> str:
    """
    Constructs the exact data payload sent to every AI agent.
    All agents receive the IDENTICAL payload to ensure fair comparison.
    """
    payload = {
        "timestamp": market_context.get("timestamp", ""),
        "market_overview": {
            "indices": market_context.get("indices", []),
        },
        "opportunity": {
            "symbol": opportunity.get("symbol"),
            "signal_type": opportunity.get("signal_type"),
            "signal_strength": opportunity.get("signal_strength"),
            "suggested_action": opportunity.get("suggested_action"),
            "reasons": opportunity.get("reasons", []),
        },
        "technical_indicators": opportunity.get("indicators", {}),
        "fundamentals": opportunity.get("fundamentals", {}),
        "derivatives_oi": opportunity.get("derivatives_oi", {}),
        "recent_news": [
            {
                "headline": n.get("headline", ""),
                "sentiment": n.get("sentiment", "neutral"),
                "source": n.get("source", ""),
            }
            for n in news[:5]  # Limit to 5 most recent
        ],
        "your_portfolio": {
            "cash_balance": agent_state.get("cash_balance", 100000),
            "open_positions": agent_state.get("open_positions", 0),
            "today_trades": agent_state.get("today_trades", 0),
            "today_pnl": agent_state.get("today_pnl", 0),
            "total_pnl": agent_state.get("total_pnl", 0),
        },
        "pre_market_strategy": agent_state.get("pre_market_strategy", {}),
    }

    return json.dumps(payload, indent=2, default=str)


def parse_ai_response(raw_response: str) -> dict:
    """
    Parses the raw text response from an AI into a structured dict.
    Handles common issues like markdown code blocks, extra whitespace, etc.
    """
    text = raw_response.strip()

    # Strip markdown code blocks if present
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object within the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                parsed = json.loads(text[start:end])
            except json.JSONDecodeError:
                return {
                    "decision": "HOLD",
                    "confidence": 0,
                    "reasoning": "Failed to parse AI response",
                    "is_valid": False,
                    "raw_text": raw_response[:500],
                }
        else:
            return {
                "decision": "HOLD",
                "confidence": 0,
                "reasoning": "No JSON found in AI response",
                "is_valid": False,
                "raw_text": raw_response[:500],
            }

    return validate_decision(parsed)


def validate_decision(parsed: dict) -> dict:
    """
    Validates a parsed AI decision against our trading rules.
    Returns the decision with an 'is_valid' flag.
    """
    decision = parsed.get("decision", "HOLD").upper()
    confidence = parsed.get("confidence", 0)
    entry_price = parsed.get("entry_price", 0)
    stop_loss = parsed.get("stop_loss", 0)
    target = parsed.get("target", 0)
    quantity = parsed.get("quantity", 0)

    errors = []

    # Rule: Decision must be valid
    if decision not in ["BUY", "SHORT", "HOLD"]:
        errors.append(f"Invalid decision: {decision}")
        decision = "HOLD"

    # Rule: If BUY or SHORT, must have all fields
    if decision in ["BUY", "SHORT"]:
        if not entry_price or entry_price <= 0:
            errors.append("Missing or invalid entry_price")
        if not stop_loss or stop_loss <= 0:
            errors.append("Missing or invalid stop_loss")
        if not target or target <= 0:
            errors.append("Missing or invalid target")
        if not quantity or quantity <= 0:
            errors.append("Missing or invalid quantity")

        # Rule: Stop-loss within 2% of entry
        if entry_price > 0 and stop_loss > 0:
            sl_pct = abs(entry_price - stop_loss) / entry_price
            if sl_pct > 0.02:
                errors.append(f"Stop-loss too wide: {sl_pct:.1%} (max 2%)")

        # Rule: Risk-reward >= 1.5
        if entry_price > 0 and stop_loss > 0 and target > 0:
            if decision == "BUY":
                risk = entry_price - stop_loss
                reward = target - entry_price
            else:  # SHORT
                risk = stop_loss - entry_price
                reward = entry_price - target

            if risk > 0:
                rr = reward / risk
                if rr < 1.5:
                    errors.append(f"Risk-reward too low: {rr:.1f} (min 1.5)")
                parsed["risk_reward_ratio"] = round(rr, 2)

    # Rule: Confidence check
    if decision in ["BUY", "SHORT"] and confidence < 60:
        errors.append(f"Confidence too low: {confidence} (min 60)")

    parsed["decision"] = decision
    parsed["is_valid"] = len(errors) == 0
    parsed["validation_errors"] = errors

    return parsed
