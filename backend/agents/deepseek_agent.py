import httpx
import json
from config import settings
from utils.logger import setup_logger

logger = setup_logger("deepseek_agent")

async def query_deepseek(payload: dict) -> dict:
    """
    Queries the official DeepSeek R1 (deepseek-reasoning) API.
    Handles R1 reasoning output and extracts structural trade instructions.
    """
    api_key = getattr(settings, "DEEPSEEK_API_KEY", "")
    if not api_key:
        logger.error("DeepSeek API Key is missing in settings!")
        return {
            "agent": "DeepSeek-R1",
            "provider": "deepseek",
            "decision": "HOLD",
            "reasoning": "DeepSeek API Key not provided"
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # We use deepseek-reasoning to get full R1 deep-thinking capabilities!
    data = {
        "model": "deepseek-reasoning",
        "messages": [
            {
                "role": "system",
                "content": "You are a professional NSE stock trading model. You MUST respond in valid JSON format only."
            },
            {
                "role": "user",
                "content": f"Analyze the market context and technical indicators to provide a trade decision. You must return a JSON object with: 'decision' (BUY, SHORT, or HOLD), 'quantity' (integer), 'stop_loss' (float), 'target' (float), 'confidence' (integer 0-100), and 'reasoning' (string). Data: {json.dumps(payload)}"
            }
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers=headers,
                json=data,
                timeout=45.0 # R1 reasoning models take slightly longer to complete thoughts
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Strip markdown blocks if returned
                if content.strip().startswith("```"):
                    content = content.replace("```json", "").replace("```", "").strip()
                
                parsed_res = json.loads(content)
                
                # Check if deepseek returned a thinking trace
                reasoning_trace = result["choices"][0]["message"].get("reasoning_content", "")
                if reasoning_trace:
                    parsed_res["reasoning_steps"] = reasoning_trace
                    
                parsed_res["agent"] = "DeepSeek-R1"
                parsed_res["provider"] = "deepseek"
                return parsed_res
            else:
                logger.error(f"DeepSeek API Error: {response.status_code} - {response.text}")
                return {
                    "agent": "DeepSeek-R1",
                    "provider": "deepseek",
                    "decision": "HOLD",
                    "reasoning": f"DeepSeek API Error {response.status_code}"
                }
                
    except Exception as e:
        logger.error(f"Failed to query DeepSeek: {e}")
        return {
            "agent": "DeepSeek-R1",
            "provider": "deepseek",
            "decision": "HOLD",
            "reasoning": f"Exception during query: {str(e)}"
        }

