"""
TradeOS — Grok AI Agent (xAI)
Uses the OpenAI-compatible API endpoint at api.x.ai
Grok uses the same request format as OpenAI, just a different base URL and model name.
"""

import time
import httpx
from config import settings
from agents.prompts import SYSTEM_PROMPT, parse_ai_response
from utils.logger import setup_logger

logger = setup_logger("agent_grok")

GROK_API_URL = "https://api.x.ai/v1/chat/completions"


async def query_grok(payload: str) -> dict:
    """
    Sends market data payload to Grok and returns a parsed trading decision.
    Uses the OpenAI-compatible chat completions endpoint.
    """
    start_time = time.time()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.XAI_API_KEY}",
    }

    body = {
        "model": settings.GROK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": payload},
        ],
        "temperature": 0.3,
        "max_tokens": 500,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(GROK_API_URL, headers=headers, json=body)

        latency_ms = int((time.time() - start_time) * 1000)

        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Grok API error ({response.status_code}): {error_text}")
            return {
                "agent": "Grok",
                "provider": "xai",
                "decision": "HOLD",
                "confidence": 0,
                "reasoning": f"API error {response.status_code}: {error_text[:200]}",
                "is_valid": False,
                "latency_ms": latency_ms,
                "raw_response": error_text,
            }

        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]

        logger.info(f"Grok responded in {latency_ms}ms")

        parsed = parse_ai_response(raw_text)
        parsed["agent"] = "Grok"
        parsed["provider"] = "xai"
        parsed["latency_ms"] = latency_ms
        parsed["raw_response"] = raw_text

        return parsed

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Grok error: {str(e)}")
        return {
            "agent": "Grok",
            "provider": "xai",
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": f"API error: {str(e)}",
            "is_valid": False,
            "latency_ms": latency_ms,
            "raw_response": str(e),
        }
