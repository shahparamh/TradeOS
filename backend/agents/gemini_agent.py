"""
TradeOS — Gemini AI Agent (Google)
Uses the google-generativeai SDK to query Gemini 1.5 Pro.
"""

import time
import google.generativeai as genai
from config import settings
from agents.prompts import SYSTEM_PROMPT, parse_ai_response
from utils.logger import setup_logger

logger = setup_logger("agent_gemini")

# Keep track of the active working key index at the module level
_current_key_index = 0

async def query_gemini(payload: str) -> dict:
    """
    Sends market data payload to Gemini and returns a parsed trading decision.
    Uses stateful API key rotation to bypass rate limits gracefully.
    """
    global _current_key_index
    keys = settings.GEMINI_API_KEYS
    if not keys:
        keys = [settings.GEMINI_API_KEY]
        
    start_time = time.time()
    num_keys = len(keys)
    
    # Try all keys starting from our last known working key index
    for attempt in range(num_keys):
        current_idx = (_current_key_index + attempt) % num_keys
        api_key = keys[current_idx]
        
        try:
            # Dynamically configure the Gemini SDK with the active key
            genai.configure(api_key=api_key)
            
            model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                system_instruction=SYSTEM_PROMPT,
            )

            response = model.generate_content(
                payload,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=500,
                ),
            )

            raw_text = response.text
            latency_ms = int((time.time() - start_time) * 1000)

            # Success! Save the index of the working key!
            _current_key_index = current_idx
            
            logger.info(f"Gemini responded in {latency_ms}ms (using key index {current_idx})")

            parsed = parse_ai_response(raw_text)
            parsed["agent"] = "Gemini"
            parsed["provider"] = "google"
            parsed["latency_ms"] = latency_ms
            parsed["raw_response"] = raw_text

            return parsed

        except Exception as e:
            err_msg = str(e)
            masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "unknown"
            
            # Check for Rate Limit / Quota errors
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                logger.warning(f"Gemini API key {masked_key} rate-limited/exhausted. Trying next key...")
                continue
                
            logger.error(f"Gemini API key {masked_key} error: {err_msg}")
            continue

    # If all keys failed or exhausted
    latency_ms = int((time.time() - start_time) * 1000)
    logger.error("All Gemini API keys have been exhausted or failed.")
    return {
        "agent": "Gemini",
        "provider": "google",
        "decision": "HOLD",
        "confidence": 0,
        "reasoning": "All Gemini API keys are exhausted or offline.",
        "is_valid": False,
        "latency_ms": latency_ms,
        "raw_response": "All keys failed.",
    }
