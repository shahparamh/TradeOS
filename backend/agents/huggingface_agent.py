"""
TradeOS — Hugging Face AI Agent
Uses Hugging Face's OpenAI-compatible chat completions Inference API.
"""

import time
import httpx
from config import settings
from agents.prompts import SYSTEM_PROMPT, parse_ai_response
from utils.logger import setup_logger

logger = setup_logger("agent_huggingface")

HF_API_URL = "https://router.huggingface.co/v1/chat/completions"

async def query_huggingface(payload: str, system_prompt: str = SYSTEM_PROMPT) -> dict:
    """
    Sends market data payload to Hugging Face Inference API and returns a parsed trading decision.
    """
    api_key = settings.HF_API_KEY.strip() if settings.HF_API_KEY else ""
    
    if not api_key:
        logger.error("No valid Hugging Face API Key found!")
        return {
            "agent": "HuggingFace Model",
            "provider": "huggingface",
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": "Hugging Face API Key not provided. Please add HF_API_KEY in your backend/.env file.",
            "is_valid": False,
            "latency_ms": 0,
            "raw_response": "Missing API Key",
        }
        
    start_time = time.time()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    # Model default is meta-llama/Llama-3.3-70B-Instruct or custom from Settings
    body = {
        "model": settings.HF_MODEL or "meta-llama/Llama-3.3-70B-Instruct",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload},
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(HF_API_URL, headers=headers, json=body)

        latency_ms = int((time.time() - start_time) * 1000)

        # Handle rate limits (429) or unauthorized keys (401, 403)
        if response.status_code in [429, 401, 403]:
            masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "unknown"
            logger.warning(f"Hugging Face API failed with status {response.status_code} using key {masked_key}. Deactivating agent...")
            raise httpx.HTTPStatusError(
                f"Rate limit or authorization failure: {response.status_code}",
                request=response.request,
                response=response
            )
            
        if response.status_code != 200:
            error_text = response.text
            masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "unknown"
            logger.error(f"Hugging Face API key {masked_key} failed (status {response.status_code}): {error_text}")
            
            return {
                "agent": "HuggingFace Model",
                "provider": "huggingface",
                "decision": "HOLD",
                "confidence": 0,
                "reasoning": f"Hugging Face API error {response.status_code}: {error_text[:200]}",
                "is_valid": False,
                "latency_ms": latency_ms,
                "raw_response": error_text,
            }

        # Success!
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]

        logger.info(f"HuggingFace Model ({settings.HF_MODEL}) responded in {latency_ms}ms")

        parsed = parse_ai_response(raw_text)
        parsed["agent"] = "HuggingFace Model"
        parsed["provider"] = "huggingface"
        parsed["latency_ms"] = latency_ms
        parsed["raw_response"] = raw_text

        return parsed

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Hugging Face API query failed: {str(e)}. Auto-deactivating HuggingFace agent in the database.")
        
        try:
            from database.connection import SessionLocal
            from database.models import Agent
            db = SessionLocal()
            agent_db = db.query(Agent).filter(Agent.provider == "huggingface").first()
            if agent_db and agent_db.is_active:
                agent_db.is_active = False
                db.commit()
                logger.info("Successfully auto-deactivated agent HuggingFace Model in the database.")
        except Exception as db_ex:
            logger.error(f"Error auto-deactivating Hugging Face agent in database: {db_ex}")
            
        return {
            "agent": "HuggingFace Model",
            "provider": "huggingface",
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": f"Hugging Face Model error: {str(e)}",
            "is_valid": False,
            "latency_ms": latency_ms,
            "raw_response": f"Failed with exception: {str(e)}",
        }
