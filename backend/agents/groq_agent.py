"""
TradeOS — Groq AI Agent (via Groq Cloud)
Uses Groq's OpenAI-compatible API for ultra-fast free inference.
Model is configured via settings.GROQ_MODEL (see config.py).
"""

import time
import httpx
from config import settings
from agents.prompts import SYSTEM_PROMPT, parse_ai_response
from utils.logger import setup_logger
from utils.api_manager import api_key_manager

logger = setup_logger("agent_groq")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

GROQ_STRATEGY_OVERLAY = """
MODEL-SPECIFIC STRATEGY LOCK (Groq-Llama):
- Follow one stable trend-confluence framework throughout the day; do not frequently switch strategy style.
- Prioritize momentum continuation only when VWAP and EMA structure agree; otherwise HOLD.
- For mean-reversion, require explicit Bollinger or RSI extreme plus reversal confirmation.
- If confidence drops, lower size first instead of changing the underlying strategy logic.
- Enforce high-quality trade selection: confidence >= 70, risk-reward >= 2.0, and expected target move >= 1.5%.
- Do not force trades in choppy structure; HOLD is preferred when confluence is weak.
"""


async def query_groq(payload: str, system_prompt: str = SYSTEM_PROMPT) -> dict:
    """
    Sends market data payload to Groq and returns parsed trading decision.
    """
    api_key = api_key_manager.get_key("groq")
    if not api_key:
        logger.error("All Groq API Keys are exhausted or missing!")
        return {
            "agent": "Groq-Llama",
            "provider": "groq",
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": "Groq API Keys exhausted or not provided.",
            "is_valid": False,
            "latency_ms": 0,
            "raw_response": "Missing or exhausted API Keys",
        }

    start_time = time.time()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    effective_prompt = f"{system_prompt}\n\n{GROQ_STRATEGY_OVERLAY}"

    body = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": effective_prompt},
            {"role": "user", "content": payload},
        ],
        "temperature": 0.3,
        # gpt-oss is a reasoning model — its internal reasoning tokens count against this
        # budget before any JSON content is emitted. Too small a value (verified: even 10
        # tokens) burns the whole budget on reasoning and returns EMPTY content.
        "max_tokens": 2000,
    }

    try:
        api_key_manager.record_usage("groq", api_key)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(GROQ_API_URL, headers=headers, json=body)

        latency_ms = int((time.time() - start_time) * 1000)

        if response.status_code == 429:
            masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "unknown"
            logger.warning(f"Groq API key {masked_key} rate-limited (429). Marking exhausted.")
            api_key_manager.mark_exhausted("groq", api_key)
            return {
                "agent": "Groq-Llama",
                "provider": "groq",
                "decision": "HOLD",
                "confidence": 0,
                "reasoning": "Rate limited (429).",
                "is_valid": False,
                "latency_ms": latency_ms,
                "raw_response": "Rate limit",
            }

        if response.status_code != 200:
            error_text = response.text
            masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "unknown"
            logger.error(f"Groq API key {masked_key} failed (status {response.status_code}): {error_text}")

            return {
                "agent": "Groq-Llama",
                "provider": "groq",
                "decision": "HOLD",
                "confidence": 0,
                "reasoning": f"API error {response.status_code}: {error_text[:200]}",
                "is_valid": False,
                "latency_ms": latency_ms,
                "raw_response": error_text,
            }

        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]

        logger.info(f"Groq ({settings.GROQ_MODEL}) responded in {latency_ms}ms")

        parsed = parse_ai_response(raw_text)
        parsed["agent"] = "Groq-Llama"
        parsed["provider"] = "groq"
        parsed["latency_ms"] = latency_ms
        parsed["raw_response"] = raw_text

        return parsed

    except Exception as e:
        logger.warning(f"Exception using Groq key: {str(e)}")

    # If all keys failed or exhausted
    latency_ms = int((time.time() - start_time) * 1000)
    logger.error("All Groq API keys have been exhausted or failed. Auto-deactivating Groq agent in the database.")
    try:
        from database.connection import SessionLocal
        from database.models import Agent
        db = SessionLocal()
        agent_db = db.query(Agent).filter(Agent.provider == "groq").first()
        if agent_db and agent_db.is_active:
            agent_db.is_active = False
            db.commit()
            logger.info("Successfully auto-deactivated agent Groq-Llama in the database.")
    except Exception as db_ex:
        logger.error(f"Error auto-deactivating Groq agent in database: {db_ex}")

    return {
        "agent": "Groq-Llama",
        "provider": "groq",
        "decision": "HOLD",
        "confidence": 0,
        "reasoning": "All Groq API keys are exhausted or offline.",
        "is_valid": False,
        "latency_ms": latency_ms,
        "raw_response": "All keys failed.",
    }

