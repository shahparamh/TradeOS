import httpx
import json
from config import settings
from utils.logger import setup_logger

logger = setup_logger("openrouter_agent")

async def query_openrouter_free(payload: dict) -> dict:
    """
    Queries 100% free models on OpenRouter (e.g. Qwen 2.5 72B) 
    with highly generous rate limits.
    """
    api_key = getattr(settings, "OPENROUTER_API_KEY", "sk-or-v1-mock")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://tradeos.io", # Required by OpenRouter
        "X-Title": "TradeOS Platform"
    }
    
    # We use openrouter/free - OpenRouter's auto-router that always selects an active free model!
    data = {
        "model": "openrouter/free",




        "messages": [
            {
                "role": "system",
                "content": "You are a professional NSE stock trader. You must return response in valid JSON format only."
            },
            {
                "role": "user",
                "content": f"Analyze this data and return trade decision: {json.dumps(payload)}"
            }
        ]
    }

    
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
                logger.error(f"OpenRouter Error: {response.status_code} - {response.text}")
                return {
                    "agent": "Qwen-Free",
                    "provider": "openrouter",
                    "decision": "HOLD",
                    "reasoning": f"OpenRouter API error: {response.status_code}"
                }
                
    except Exception as e:
        logger.error(f"Failed to query OpenRouter: {e}")
        return {
            "agent": "Qwen-Free",
            "provider": "openrouter",
            "decision": "HOLD",
            "reasoning": f"Exception: {str(e)}"
        }

