"""
TradeOS — Gemini AI Agent (Google)
Uses the google-generativeai SDK to query Gemini 1.5 Pro.
"""

import time
import google.generativeai as genai
from config import settings
from agents.prompts import SYSTEM_PROMPT, parse_ai_response
from utils.logger import setup_logger
from utils.api_manager import api_key_manager
from utils.llm_rate_limiter import pace

logger = setup_logger("agent_gemini")

async def query_gemini(payload: str, system_prompt: str = SYSTEM_PROMPT) -> dict:
    """
    Sends market data payload to Gemini and returns a parsed trading decision.
    Uses stateful API key rotation to bypass rate limits gracefully.
    """
    api_key = api_key_manager.get_key("gemini")
    if not api_key:
        logger.error("All Gemini API Keys are exhausted or missing!")
        return {
            "agent": "Gemini",
            "provider": "google",
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": "Gemini API Keys exhausted.",
            "is_valid": False,
            "latency_ms": 0,
            "raw_response": "Missing or exhausted API Keys",
        }
        
    start_time = time.time()

    try:
        # Spread out bursts (e.g. 3 parallel analyst calls in one debate round) instead of
        # firing them all in the same instant, which is what trips free-tier per-minute limits.
        await pace("gemini")

        genai.configure(api_key=api_key)

        # Log usage BEFORE making the call (optimistic tracking)
        api_key_manager.record_usage("gemini", api_key)
        
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=system_prompt,
        )

        response = model.generate_content(
            payload,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=1000,
            ),
        )

        raw_text = response.text
        latency_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"Gemini responded in {latency_ms}ms")

        parsed = parse_ai_response(raw_text)
        parsed["agent"] = "Gemini"
        parsed["provider"] = "google"
        parsed["latency_ms"] = latency_ms
        parsed["raw_response"] = raw_text

        return parsed

    except Exception as e:
        err_msg = str(e)
        masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "unknown"
        
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
            logger.warning(f"Gemini API key {masked_key} rate-limited/exhausted.")
            api_key_manager.mark_exhausted("gemini", api_key)
        else:
            logger.error(f"Gemini API key {masked_key} error: {err_msg}")


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
