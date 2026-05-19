import httpx
import json
from config import settings
from utils.logger import setup_logger
from agents.prompts import SYSTEM_PROMPT

logger = setup_logger("openrouter_agent")

async def query_openrouter_free(payload: dict, system_prompt: str = None) -> dict:
    """
    Queries 100% free models on OpenRouter (e.g. Qwen 2.5 72B) 
    with highly generous rate limits and automatic failover API key rotation.
    """
    keys = getattr(settings, "OPENROUTER_API_KEYS", [])
    if not keys:
        keys = [getattr(settings, "OPENROUTER_API_KEY", "")]
        
    keys = [k for k in keys if k and k.strip()]
    
    if not keys:
        logger.error("OpenRouter API Keys are missing in settings!")
        return {
            "agent": "Qwen-Free",
            "provider": "openrouter",
            "decision": "HOLD",
            "reasoning": "OpenRouter API Key not provided. Please add OPENROUTER_API_KEYS in your backend/.env file."
        }
    
    sys_content = system_prompt if system_prompt else f"You are a professional NSE stock trader. You must return response in valid JSON format only. Reference rules:\n{SYSTEM_PROMPT}"
    data = {
        "model": "openrouter/free",
        "messages": [
            {
                "role": "system",
                "content": sys_content
            },
            {
                "role": "user",
                "content": f"Analyze this data and return trade decision: {json.dumps(payload)}"
            }
        ]
    }

    # Iterate through each key if the previous key fails
    for attempt, api_key in enumerate(keys):
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://tradeos.io", # Required by OpenRouter
            "X-Title": "TradeOS Platform"
        }
        
        logger.info(f"Attempting OpenRouter query with key {attempt + 1}/{len(keys)}...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    # Strip markdown blocks if returned by the auto-routed free model
                    if content.strip().startswith("```"):
                        content = content.replace("```json", "").replace("```", "").strip()
                    
                    parsed = json.loads(content)
                    
                    # Resilient normalization of decision keys and values
                    raw_decision = str(parsed.get("decision", parsed.get("action", "HOLD"))).upper()
                    if "SELL" in raw_decision or "SHORT" in raw_decision:
                        parsed["decision"] = "SHORT"
                    elif "BUY" in raw_decision:
                        parsed["decision"] = "BUY"
                    else:
                        parsed["decision"] = "HOLD"
                    
                    # Standardize quantity & confidence
                    try:
                        parsed["confidence"] = int(parsed.get("confidence", 60))
                    except Exception:
                        parsed["confidence"] = 60
                        
                    try:
                        parsed["quantity"] = int(parsed.get("quantity", parsed.get("qty", 10)))
                    except Exception:
                        parsed["quantity"] = 10
                        
                    parsed["agent"] = "Qwen-Free"
                    parsed["provider"] = "openrouter"
                    return parsed
                else:
                    logger.warning(f"OpenRouter key {attempt + 1} failed with status {response.status_code}: {response.text}. Rotating to next key...")
        except Exception as e:
            logger.warning(f"OpenRouter key {attempt + 1} exception: {e}. Rotating to next key...")
            
    # All keys exhausted
    logger.error("All OpenRouter API Keys in the failover roster are exhausted or invalid!")
    return {
        "agent": "Qwen-Free",
        "provider": "openrouter",
        "decision": "HOLD",
        "reasoning": "All OpenRouter keys exhausted (Rate limit or invalid)."
    }

