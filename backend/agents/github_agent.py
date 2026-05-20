"""
TradeOS — GitHub Model AI Agent (GPT-4o/Llama via GitHub Models)
Uses GitHub's OpenAI-compatible API for ultra-fast inference.
"""

import time
import httpx
from config import settings
from agents.prompts import SYSTEM_PROMPT, parse_ai_response
from utils.logger import setup_logger

logger = setup_logger("agent_github")

GITHUB_API_URL = "https://models.inference.ai.azure.com/chat/completions"

async def query_github(payload: str, system_prompt: str = SYSTEM_PROMPT) -> dict:
    """
    Sends market data payload to GitHub Models (GPT-4o) and returns a parsed trading decision.
    """
    api_key = settings.GITHUB_API_KEY.strip() if settings.GITHUB_API_KEY else ""
    
    if not api_key:
        logger.error("No valid GitHub API Key found!")
        return {
            "agent": "GitHub Model",
            "provider": "github",
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": "GitHub API Key not provided. Please add GITHUB_API_KEY in your backend/.env file.",
            "is_valid": False,
            "latency_ms": 0,
            "raw_response": "Missing API Key",
        }
        
    start_time = time.time()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    body = {
        "model": settings.GITHUB_MODEL or "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload},
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(GITHUB_API_URL, headers=headers, json=body)

        latency_ms = int((time.time() - start_time) * 1000)

        # Handle rate-limiting (429) or unauthorized (401/403) or token errors
        if response.status_code in [429, 401, 403]:
            masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "unknown"
            logger.warning(f"GitHub Models API failed with status {response.status_code} using key {masked_key}. Deactivating agent...")
            raise httpx.HTTPStatusError(
                f"Rate limit or authorization failure: {response.status_code}",
                request=response.request,
                response=response
            )
            
        if response.status_code != 200:
            error_text = response.text
            masked_key = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "unknown"
            logger.error(f"GitHub Models API key {masked_key} failed (status {response.status_code}): {error_text}")
            
            return {
                "agent": "GitHub Model",
                "provider": "github",
                "decision": "HOLD",
                "confidence": 0,
                "reasoning": f"GitHub Models API error {response.status_code}: {error_text[:200]}",
                "is_valid": False,
                "latency_ms": latency_ms,
                "raw_response": error_text,
            }

        # Success!
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]

        logger.info(f"GitHub Model ({settings.GITHUB_MODEL}) responded in {latency_ms}ms")

        parsed = parse_ai_response(raw_text)
        parsed["agent"] = "GitHub Model"
        parsed["provider"] = "github"
        parsed["latency_ms"] = latency_ms
        parsed["raw_response"] = raw_text

        return parsed

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"GitHub Models API query failed: {str(e)}. Auto-deactivating GitHub agent in the database.")
        
        try:
            from database.connection import SessionLocal
            from database.models import Agent
            db = SessionLocal()
            agent_db = db.query(Agent).filter(Agent.provider == "github").first()
            if agent_db and agent_db.is_active:
                agent_db.is_active = False
                db.commit()
                logger.info("Successfully auto-deactivated agent GitHub Model in the database.")
        except Exception as db_ex:
            logger.error(f"Error auto-deactivating GitHub agent in database: {db_ex}")
            
        return {
            "agent": "GitHub Model",
            "provider": "github",
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": f"GitHub Model error: {str(e)}",
            "is_valid": False,
            "latency_ms": latency_ms,
            "raw_response": f"Failed with exception: {str(e)}",
        }
