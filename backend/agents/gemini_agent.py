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
            "error_type": "provider_error",
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

        generation_config = genai.types.GenerationConfig(
            temperature=0.3,
            max_output_tokens=1000,
            # Guaranteed-JSON mode -- reduces (does not eliminate; the model can still emit
            # a schema-invalid or truncated body) the parse failures downstream logic must
            # distinguish from genuine reasoned decisions.
            response_mime_type="application/json",
        )

        raw_text = None
        parsed = None
        # Up to 2 attempts: retry once, only on a parse failure, with an explicit nudge.
        # This is a model-interface reliability measure, not a trading-policy change --
        # it never alters what counts as BUY/HOLD, only gives malformed output one more
        # chance to come back well-formed before we tag it as a parse error.
        for attempt in range(2):
            response = model.generate_content(payload, generation_config=generation_config)
            raw_text = response.text
            parsed = parse_ai_response(raw_text)
            if parsed.get("error_type") != "parse_error":
                break
            payload = f"{payload}\n\n(Your previous response was not valid JSON. Respond with ONLY the JSON object, no other text.)"

        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(f"Gemini responded in {latency_ms}ms")

        parsed["agent"] = "Gemini"
        parsed["provider"] = "google"
        parsed["latency_ms"] = latency_ms
        parsed["raw_response"] = raw_text

        return parsed

    except Exception as e:
        err_msg = str(e)
        masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "unknown"

        # get_key() is STICKY — it keeps returning the same key until it's marked
        # exhausted, so any error that doesn't trigger a rotation here gets retried on
        # this same key forever, permanently blocking healthier keys later in the list
        # from ever being tried. A 403 ("project denied access") is just as key-fatal as
        # a 429/quota error for this purpose, even though it isn't a rate limit — rotate
        # away from it too rather than only recognizing quota-shaped errors.
        is_key_fatal = (
            "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower()
            or "403" in err_msg or "PERMISSION_DENIED" in err_msg
            or "401" in err_msg or "UNAUTHENTICATED" in err_msg or "API_KEY_INVALID" in err_msg
        )
        if is_key_fatal:
            logger.warning(f"Gemini API key {masked_key} rejected ({err_msg[:120]}) — rotating to next key.")
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
        "error_type": "provider_error",
        "latency_ms": latency_ms,
        "raw_response": "All keys failed.",
    }
