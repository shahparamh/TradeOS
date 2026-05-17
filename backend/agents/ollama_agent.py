"""
TradeOS — Local Ollama AI Agent (Llama 3.2 3B)
Queries the local Ollama server running on macOS at http://localhost:11434.
"""

import time
import httpx
import json
from agents.prompts import SYSTEM_PROMPT, parse_ai_response
from utils.logger import setup_logger

logger = setup_logger("agent_ollama")

OLLAMA_API_URL = "http://localhost:11434/api/chat"

async def query_ollama(payload: str) -> dict:
    """
    Sends market data payload to local Ollama (Llama 3.2 3B) and returns parsed trading decision.
    """
    start_time = time.time()

    body = {
        "model": "llama3.2",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": payload},
        ],
        "stream": False,
        "options": {
            "temperature": 0.3
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(OLLAMA_API_URL, json=body)

        latency_ms = int((time.time() - start_time) * 1000)

        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Ollama API error ({response.status_code}): {error_text}")
            return {
                "agent": "Local-Ollama",
                "provider": "ollama",
                "decision": "HOLD",
                "confidence": 0,
                "reasoning": f"Local Ollama error {response.status_code}: {error_text[:200]}",
                "is_valid": False,
                "latency_ms": latency_ms,
                "raw_response": error_text,
            }

        data = response.json()
        raw_text = data["message"]["content"]

        logger.info(f"Local Ollama (Llama 3.2) responded in {latency_ms}ms")

        parsed = parse_ai_response(raw_text)
        parsed["agent"] = "Local-Ollama"
        parsed["provider"] = "ollama"
        parsed["latency_ms"] = latency_ms
        parsed["raw_response"] = raw_text

        return parsed

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Ollama error: {str(e)}")
        return {
            "agent": "Local-Ollama",
            "provider": "ollama",
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": f"Local Ollama is offline or busy. Exception: {str(e)}",
            "is_valid": False,
            "latency_ms": latency_ms,
            "raw_response": str(e),
        }
