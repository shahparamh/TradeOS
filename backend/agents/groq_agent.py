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


# Keep track of the active working key index at the module level
_current_key_index = 0

async def query_groq(payload: str, system_prompt: str = SYSTEM_PROMPT) -> dict:
    """
    Sends market data payload to Groq (Llama 3.3 70B) and returns a parsed trading decision.
    Uses stateful API key rotation to bypass rate limits gracefully.
    """
    global _current_key_index
    keys = [k.strip() for k in settings.GROQ_API_KEYS if k and k.strip()]
    if not keys:
        keys = [k.strip() for k in [settings.GROQ_API_KEY] if k and k.strip()]
        
    if not keys:
        logger.error("No valid Groq API Keys found!")
        return {
            "agent": "Groq-Llama",
            "provider": "groq",
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": "Groq API Key not provided. Please add GROQ_API_KEY in your backend/.env file.",
            "is_valid": False,
            "latency_ms": 0,
            "raw_response": "Missing API Keys",
        }
        
    start_time = time.time()
    num_keys = len(keys)
    
    # Try all keys starting from our last known working key index
    for attempt in range(num_keys):
        current_idx = (_current_key_index + attempt) % num_keys
        api_key = keys[current_idx]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        body = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload},
            ],
            "temperature": 0.3,
            "max_tokens": 500,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(GROQ_API_URL, headers=headers, json=body)

            latency_ms = int((time.time() - start_time) * 1000)

            # If we get rate limited (429), try next key
            if response.status_code == 429:
                masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "unknown"
                logger.warning(f"Groq API key {masked_key} rate-limited (429). Trying next key...")
                continue
                
            if response.status_code != 200:
                error_text = response.text
                masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "unknown"
                logger.error(f"Groq API key {masked_key} failed (status {response.status_code}): {error_text}")
                if response.status_code >= 500:
                    continue
                
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

            # Success!
            _current_key_index = current_idx  # Save the index of the working key!
            
            data = response.json()
            raw_text = data["choices"][0]["message"]["content"]

            logger.info(f"Groq (Llama 3.3) responded in {latency_ms}ms (using key index {current_idx})")

            parsed = parse_ai_response(raw_text)
            parsed["agent"] = "Groq-Llama"
            parsed["provider"] = "groq"
            parsed["latency_ms"] = latency_ms
            parsed["raw_response"] = raw_text

            return parsed

        except Exception as e:
            logger.warning(f"Exception using Groq key index {current_idx}: {str(e)}")
            continue
            
    # If all keys failed or exhausted
    latency_ms = int((time.time() - start_time) * 1000)
    logger.error("All Groq API keys have been exhausted or failed.")
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
