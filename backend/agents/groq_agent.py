"""
TradeOS — Groq AI Agent (Llama 3.3 70B via Groq Cloud)
Uses Groq's OpenAI-compatible API for ultra-fast free inference.
Groq provides free access to open-source models like Llama 3.3 70B.
"""

import time
import httpx
from config import settings
from agents.prompts import SYSTEM_PROMPT, parse_ai_response
from utils.logger import setup_logger

logger = setup_logger("agent_groq")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


async def query_groq(payload: str) -> dict:
    """
    Sends market data payload to Groq (Llama 3.3 70B) and returns a parsed trading decision.
    Uses OpenAI-compatible chat completions endpoint.
    """
    start_time = time.time()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
    }

    body = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": payload},
        ],
        "temperature": 0.3,
        "max_tokens": 500,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(GROQ_API_URL, headers=headers, json=body)

        latency_ms = int((time.time() - start_time) * 1000)

        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Groq API error ({response.status_code}): {error_text}")
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

        logger.info(f"Groq (Llama 3.3) responded in {latency_ms}ms")

        parsed = parse_ai_response(raw_text)
        parsed["agent"] = "Groq-Llama"
        parsed["provider"] = "groq"
        parsed["latency_ms"] = latency_ms
        parsed["raw_response"] = raw_text

        return parsed

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Groq error: {str(e)}")
        return {
            "agent": "Groq-Llama",
            "provider": "groq",
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": f"API error: {str(e)}",
            "is_valid": False,
            "latency_ms": latency_ms,
            "raw_response": str(e),
        }
