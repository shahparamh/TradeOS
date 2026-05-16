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

# Configure the SDK
genai.configure(api_key=settings.GEMINI_API_KEY)


async def query_gemini(payload: str) -> dict:
    """
    Sends market data payload to Gemini and returns a parsed trading decision.
    """
    start_time = time.time()

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
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

        logger.info(f"Gemini responded in {latency_ms}ms")

        parsed = parse_ai_response(raw_text)
        parsed["agent"] = "Gemini"
        parsed["provider"] = "google"
        parsed["latency_ms"] = latency_ms
        parsed["raw_response"] = raw_text

        return parsed

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Gemini error: {str(e)}")
        return {
            "agent": "Gemini",
            "provider": "google",
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": f"API error: {str(e)}",
            "is_valid": False,
            "latency_ms": latency_ms,
            "raw_response": str(e),
        }
