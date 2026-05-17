# Phase 4 — AI Decision Engine & Agent Integration

> **Goal:** Build the core AI comparison engine. Each of the 4 LLMs (ChatGPT, Gemini, Claude, Grok) receives the exact same market data, at the exact same time, and must return a strict JSON trading decision. This phase handles prompt construction, API calls, response parsing, validation, and fairness enforcement.

---

## 4.1 Architecture Overview

```
  Scanned Opportunities (from Phase 3)
  + Market Context
  + Portfolio State
          │
          ▼
  ┌──────────────────────────┐
  │    Prompt Builder        │
  │  (agents/prompt_builder) │
  │                          │
  │  Builds IDENTICAL JSON   │
  │  payload for all 4 AIs   │
  └──────────┬───────────────┘
             │
    ┌────────┼────────┬────────────┐
    ▼        ▼        ▼            ▼
 ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐
 │ GPT  │ │Gemini│ │Claude│ │   Grok   │
 │ 4o   │ │ Pro  │ │3.5   │ │    2     │
 └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘
    │        │        │           │
    ▼        ▼        ▼           ▼
  ┌──────────────────────────────────┐
  │     Response Validator           │
  │  (Parse JSON, validate fields)   │
  └──────────────┬───────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────┐
  │  4 Independent Decisions         │
  │  (one per AI, same data)         │
  └──────────────────────────────────┘
```

---

## 4.2 Base Agent — `agents/base_agent.py`

Abstract base class that all 4 agents inherit from. Ensures consistency.

```python
from abc import ABC, abstractmethod
from datetime import datetime
import time
import json

class BaseAgent(ABC):
    """
    Every AI agent must implement this interface.
    This guarantees:
    - Same input format
    - Same output format
    - Standardized error handling
    - Latency tracking
    """

    def __init__(self, agent_name: str, provider: str, model_name: str):
        self.agent_name = agent_name       # "ChatGPT", "Gemini", etc.
        self.provider = provider           # "openai", "google", etc.
        self.model_name = model_name       # "gpt-4o", "gemini-1.5-pro", etc.

    @abstractmethod
    async def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """
        Each agent implements its own API call.
        Returns raw text response from the LLM.
        """
        pass

    async def make_decision(self, payload: dict) -> dict:
        """
        Public method called by the trading loop.

        Steps:
        1. Build the prompt from the payload
        2. Call the AI API
        3. Parse the response
        4. Validate the response
        5. Return the structured decision (or error)

        Returns:
        {
            "agent": "ChatGPT",
            "symbol": "RELIANCE.NS",
            "decision": "BUY",
            "trade_type": "INTRADAY",
            "position": "LONG",
            "quantity": 15,
            "entry_price": 2890,
            "stop_loss": 2850,
            "target": 2975,
            "confidence": 81,
            "reasoning": "Strong breakout with volume confirmation...",
            "latency_ms": 1250,
            "is_valid": true,
            "raw_response": "...",
            "timestamp": "2026-05-16T10:30:00+05:30"
        }
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(payload)

        start_time = time.time()

        try:
            raw_response = await self._call_api(system_prompt, user_prompt)
            latency_ms = int((time.time() - start_time) * 1000)

            parsed = self._parse_response(raw_response)
            is_valid = self._validate_decision(parsed, payload)

            return {
                "agent": self.agent_name,
                "symbol": payload["stock"]["symbol"],
                "decision": parsed.get("decision", "HOLD"),
                "trade_type": parsed.get("trade_type", "INTRADAY"),
                "position": parsed.get("position", "LONG"),
                "quantity": parsed.get("quantity", 0),
                "entry_price": parsed.get("entry_price", 0),
                "stop_loss": parsed.get("stop_loss", 0),
                "target": parsed.get("target", 0),
                "confidence": parsed.get("confidence", 0),
                "reasoning": parsed.get("reasoning", ""),
                "latency_ms": latency_ms,
                "is_valid": is_valid,
                "raw_response": raw_response,
                "error_message": None,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "agent": self.agent_name,
                "symbol": payload["stock"]["symbol"],
                "decision": "HOLD",
                "is_valid": False,
                "error_message": str(e),
                "latency_ms": latency_ms,
                "timestamp": datetime.now().isoformat()
            }
```

---

## 4.3 Prompt Builder — `agents/prompt_builder.py`

### 4.3.1 System Prompt (Role Definition)

This is the same for all AIs. It defines who they are and how they must respond.

```python
SYSTEM_PROMPT = """
You are an expert Indian stock market trader and analyst. You operate as an autonomous trading agent for the Indian equity market (NSE/BSE).

YOUR ROLE:
- Analyze the provided market data, technical indicators, news, and fundamentals.
- Make a precise trading decision based on the confluence of all available information.
- You must be disciplined — only trade when there is a clear edge.

TRADING RULES YOU MUST FOLLOW:
1. You can only trade stocks from the provided watchlist.
2. Maximum 20% of available capital per trade.
3. Maximum 5 open positions at any time.
4. For SHORT positions: INTRADAY only (must close before 3:15 PM IST).
5. Always define a stop_loss and target for every trade.
6. Stop loss must be within 3% of entry price.
7. Target must provide at least 1:1.5 risk-reward ratio.
8. If confidence is below 60, you MUST choose HOLD.
9. Never chase a stock that has already moved more than 5% today.

RESPONSE FORMAT:
You MUST respond with ONLY a valid JSON object. No explanations outside the JSON.
No markdown formatting. No code blocks. Just raw JSON.

{
    "decision": "BUY" | "SELL" | "SHORT" | "HOLD" | "EXIT",
    "trade_type": "INTRADAY" | "SWING",
    "position": "LONG" | "SHORT",
    "quantity": <integer>,
    "entry_price": <float>,
    "stop_loss": <float>,
    "target": <float>,
    "confidence": <integer 0-100>,
    "reasoning": "<1-2 sentence explanation>"
}

If you decide not to trade, respond:
{
    "decision": "HOLD",
    "confidence": <integer>,
    "reasoning": "<why you are not trading>"
}
"""
```

### 4.3.2 User Prompt (Market Data Payload)

This is the dynamic part — contains the actual market data.

```python
def build_user_prompt(payload: dict) -> str:
    """
    Constructs the user prompt from the aggregated payload.

    The payload structure:
    {
        "cycle_id": "CYC-20260516-103000-a1b2c3",
        "timestamp": "2026-05-16T10:30:00+05:30",

        "market_context": {
            "nifty50": {"value": 24500, "change_pct": 0.45, "trend": "bullish"},
            "india_vix": {"value": 14.2, "status": "low"},
            "market_breadth": {"advances": 1250, "declines": 780, "ratio": 1.60},
            "macro_news": ["RBI keeps repo rate unchanged at 6.5%"]
        },

        "opportunity": {
            "symbol": "RELIANCE.NS",
            "signal_type": "bullish_breakout",
            "signal_strength": "strong",
            "reasons": ["Price above 20 EMA", "Volume 3.2x", "RSI 61"]
        },

        "stock": {
            "symbol": "RELIANCE.NS",
            "price": 2890.50,
            "open": 2875.00,
            "high": 2910.00,
            "low": 2860.00,
            "volume": 12500000,
            "change_pct": 0.71,
            "rsi": 61.3,
            "macd": "bullish",
            "ema_20": 2870.00,
            "ema_50": 2845.00,
            "vwap": 2882.00,
            "volume_ratio": 3.2,
            "atr": 35.50,
            "bb_position": "upper_half",
            "support_1": 2855.00,
            "resistance_1": 2910.00,
            "trend": "strong_bullish"
        },

        "news": [
            {"headline": "Reliance Q4 profit surges 12%", "sentiment": "positive"},
            {"headline": "Jio subscriber adds beat estimates", "sentiment": "positive"}
        ],

        "fundamentals": {
            "pe_ratio": 28.5,
            "revenue_growth": 15.2,
            "profit_growth": 22.8,
            "roe": 18.5,
            "debt_to_equity": 0.45,
            "promoter_holding": 50.3
        },

        "portfolio": {
            "cash_balance": 82000,
            "total_capital": 100000,
            "open_positions": [
                {
                    "symbol": "INFY.NS",
                    "type": "LONG",
                    "quantity": 20,
                    "entry_price": 1480,
                    "current_price": 1505,
                    "unrealized_pnl": 500,
                    "stop_loss": 1450,
                    "target": 1550
                }
            ],
            "today_trades": 1,
            "today_pnl": 320,
            "positions_count": 1
        }
    }
    """
    return json.dumps(payload, indent=2)
```

---

## 4.4 Agent Implementations

### 4.4.1 ChatGPT Agent — `agents/chatgpt_agent.py`

```python
from openai import AsyncOpenAI
from agents.base_agent import BaseAgent
from config import settings

class ChatGPTAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="ChatGPT",
            provider="openai",
            model_name="gpt-4o"
        )
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,        # Low temperature for consistent decisions
            max_tokens=500,          # Enough for JSON response
            response_format={"type": "json_object"}  # Force JSON output
        )
        return response.choices[0].message.content
```

### 4.4.2 Gemini Agent — `agents/gemini_agent.py`

```python
import google.generativeai as genai
from agents.base_agent import BaseAgent
from config import settings

class GeminiAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="Gemini",
            provider="google",
            model_name="gemini-1.5-pro"
        )
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            self.model_name,
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=500,
                response_mime_type="application/json"  # Force JSON
            )
        )

    async def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        response = await self.model.generate_content_async(full_prompt)
        return response.text
```

### 4.4.3 Claude Agent — `agents/claude_agent.py`

```python
from anthropic import AsyncAnthropic
from agents.base_agent import BaseAgent
from config import settings

class ClaudeAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="Claude",
            provider="anthropic",
            model_name="claude-sonnet-4-20250514"
        )
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.messages.create(
            model=self.model_name,
            max_tokens=500,
            temperature=0.3,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.content[0].text
```

### 4.4.4 Grok Agent — `agents/grok_agent.py`

```python
from openai import AsyncOpenAI
from agents.base_agent import BaseAgent
from config import settings

class GrokAgent(BaseAgent):
    """
    xAI's Grok uses an OpenAI-compatible API.
    We use the OpenAI SDK with a custom base URL.
    """
    def __init__(self):
        super().__init__(
            agent_name="Grok",
            provider="xai",
            model_name="grok-2"
        )
        self.client = AsyncOpenAI(
            api_key=settings.XAI_API_KEY,
            base_url="https://api.x.ai/v1"   # xAI API endpoint
        )

    async def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content
```

---

## 4.5 Response Parser & Validator

### 4.5.1 Response Parsing

```python
def parse_ai_response(raw_response: str) -> dict:
    """
    Parses the raw text response from any AI into a structured dict.

    Handles edge cases:
    1. Response wrapped in ```json ... ``` code blocks → strip them
    2. Response has trailing text after JSON → extract JSON only
    3. Response has leading text before JSON → find first { and last }
    4. Response is valid JSON → parse directly

    Returns parsed dict or raises ValueError.
    """
    # Strip markdown code blocks
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    # Find JSON object boundaries
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in response: {raw_response[:200]}")

    json_str = cleaned[start:end]
    return json.loads(json_str)
```

### 4.5.2 Decision Validation

```python
def validate_decision(decision: dict, payload: dict) -> bool:
    """
    Validates that the AI's decision is sane and follows the rules.

    Checks:
    1. 'decision' is one of: BUY, SELL, SHORT, HOLD, EXIT
    2. If BUY/SHORT:
       a. quantity > 0
       b. entry_price > 0
       c. stop_loss > 0
       d. target > 0
       e. confidence >= 0 and <= 100
       f. For BUY: stop_loss < entry_price < target
       g. For SHORT: target < entry_price < stop_loss
       h. Stop loss within 3% of entry price
       i. Risk-reward ratio >= 1:1.5
       j. Trade value (quantity * entry_price) <= 20% of available capital
       k. Current open positions < MAX_OPEN_POSITIONS
    3. If HOLD: confidence field exists
    4. If EXIT: must reference an existing open position

    Returns True if valid, False otherwise.
    """
    valid_actions = ["BUY", "SELL", "SHORT", "HOLD", "EXIT"]

    action = decision.get("decision", "").upper()
    if action not in valid_actions:
        return False

    if action in ["BUY", "SHORT"]:
        required_fields = ["quantity", "entry_price", "stop_loss", "target", "confidence"]
        for field in required_fields:
            if field not in decision or decision[field] is None:
                return False

        entry = decision["entry_price"]
        sl = decision["stop_loss"]
        target = decision["target"]
        qty = decision["quantity"]
        confidence = decision["confidence"]

        # Confidence check
        if confidence < 60:
            return False  # AI should have returned HOLD

        # Price logic check
        if action == "BUY":
            if not (sl < entry < target):
                return False
        elif action == "SHORT":
            if not (target < entry < sl):
                return False

        # Stop loss within 3%
        sl_pct = abs(entry - sl) / entry
        if sl_pct > 0.03:
            return False

        # Risk-reward >= 1:1.5
        risk = abs(entry - sl)
        reward = abs(target - entry)
        if risk > 0 and (reward / risk) < 1.5:
            return False

        # Capital check
        trade_value = qty * entry
        available_cash = payload["portfolio"]["cash_balance"]
        max_trade_value = available_cash * 0.20
        if trade_value > max_trade_value:
            return False

    return True
```

---

## 4.6 Concurrent AI Execution

**CRITICAL for fair comparison:** All 4 AIs must receive data at the same time.

```python
import asyncio

async def execute_all_agents(payload: dict) -> list[dict]:
    """
    Sends the IDENTICAL payload to all 4 AIs simultaneously.
    Uses asyncio.gather() for true concurrent execution.

    This ensures:
    1. All AIs get the same data
    2. All AIs get data at the same timestamp
    3. No AI has an information advantage
    4. We can measure latency differences

    Returns list of 4 decision dicts (one per agent).
    """
    agents = [
        ChatGPTAgent(),
        GeminiAgent(),
        ClaudeAgent(),
        GrokAgent()
    ]

    # Each agent gets its OWN portfolio state (they have independent balances)
    tasks = []
    for agent in agents:
        agent_payload = payload.copy()
        agent_payload["portfolio"] = get_agent_portfolio(agent.agent_name)
        tasks.append(agent.make_decision(agent_payload))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    decisions = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            decisions.append({
                "agent": agents[i].agent_name,
                "decision": "HOLD",
                "is_valid": False,
                "error_message": str(result)
            })
        else:
            decisions.append(result)

    return decisions
```

---

## 4.7 AI Response Storage

Every AI response is logged to the `ai_responses` table for:
- Debugging bad decisions
- Analyzing AI personality over time
- Auditing the fairness of comparison

```python
def save_ai_response(db_session, agent_id: int, cycle_id: str, symbol: str,
                     input_payload: dict, raw_response: str, parsed_decision: dict,
                     decision: str, confidence: int, latency_ms: int,
                     is_valid: bool, error_message: str = None):
    """
    Saves complete AI response record to database.

    Fields saved:
    - Full input payload (what the AI saw)
    - Raw response (what the AI said)
    - Parsed decision (structured version)
    - Validation result
    - Latency
    """
```

---

## 4.8 Handling AI Failures

| Failure Type | Handling |
|-------------|----------|
| API timeout (>10 seconds) | Cancel request, log timeout, default to HOLD |
| Invalid JSON response | Log raw response, default to HOLD, mark is_valid=False |
| Rate limit hit | Wait 60 seconds, retry once. If still failing, skip this cycle. |
| API key invalid/expired | Log error, deactivate agent (is_active=False), alert on dashboard |
| Decision fails validation | Log the invalid decision for analysis, default to HOLD |
| Network error | Retry once after 5 seconds. If still failing, default to HOLD |

---

## 4.9 AI Personality Tracking

Over time, we track each AI's behavioral patterns:

```python
def calculate_personality_metrics(agent_id: int, db_session) -> dict:
    """
    Analyzes historical decisions to build an AI personality profile.

    Metrics:
    {
        "aggressiveness": 0.72,         # % of opportunities where AI chose to trade
        "avg_confidence": 74.5,          # Average confidence score
        "risk_tolerance": "high",        # Based on avg stop_loss distance
        "avg_latency_ms": 1100,          # How fast the AI responds
        "overtrading_tendency": 0.15,    # % of trades that were unnecessary (lost money)
        "long_bias": 0.82,              # % of trades that are LONG
        "short_bias": 0.18,             # % of trades that are SHORT
        "hold_rate": 0.35,              # % of opportunities where AI said HOLD
        "avg_risk_reward": 2.1,         # Average risk-reward ratio of trades
        "decision_consistency": 0.88     # How consistent are decisions given similar data
    }
    """
```

---

## 4.10 API Endpoints

```python
# GET  /api/agents                        → List all agents with status
# GET  /api/agents/{id}                   → Single agent details + personality
# GET  /api/agents/{id}/decisions         → Decision history for one agent
# GET  /api/agents/{id}/personality       → AI personality metrics
# GET  /api/agents/compare                → Side-by-side comparison of all agents
# POST /api/agents/test                   → Send test payload to all agents (debugging)
```

---

## 4.11 Phase 4 Completion Checklist

| #  | Task                                              | Status |
|----|---------------------------------------------------|--------|
| 1  | Implement `base_agent.py` with abstract interface  | ☐     |
| 2  | Implement `prompt_builder.py` (system + user prompt) | ☐  |
| 3  | Implement `chatgpt_agent.py`                       | ☐     |
| 4  | Test ChatGPT agent with sample payload             | ☐     |
| 5  | Implement `gemini_agent.py`                        | ☐     |
| 6  | Test Gemini agent with sample payload              | ☐     |
| 7  | Implement `claude_agent.py`                        | ☐     |
| 8  | Test Claude agent with sample payload              | ☐     |
| 9  | Implement `grok_agent.py`                          | ☐     |
| 10 | Test Grok agent with sample payload                | ☐     |
| 11 | Implement response parser with edge case handling  | ☐     |
| 12 | Implement decision validator with all rules        | ☐     |
| 13 | Implement `execute_all_agents()` concurrent runner | ☐     |
| 14 | Test all 4 agents simultaneously with same data    | ☐     |
| 15 | Implement AI response storage to database          | ☐     |
| 16 | Implement error handling for all failure types      | ☐     |
| 17 | Implement personality tracking metrics             | ☐     |
| 18 | Create `/api/agents/*` endpoints                   | ☐     |

---

> **Phase 4 is COMPLETE when:** All 4 AI agents can receive identical market data concurrently, return valid JSON decisions, have their responses parsed, validated, and stored in the database. Invalid responses are handled gracefully with fallback to HOLD.

> **Next →** [Phase 5: Risk Management & Virtual Broker Execution Engine](./phase5.md)
