import json
import os
from openai import AsyncOpenAI
from utils.logger import setup_logger
from config import settings

logger = setup_logger("deepseek_agent")

async def query_deepseek(payload: str, system_prompt: str = None) -> dict:
    """
    Queries the DeepSeek-R1 model using the OpenAI-compatible SDK.
    """
    api_key = settings.DEEPSEEK_API_KEY
    if not api_key:
        logger.error("DeepSeek API key is missing. Please configure DEEPSEEK_API_KEY.")
        return {
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": "DeepSeek API key is missing. Please configure DEEPSEEK_API_KEY."
        }

    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        
        default_system_prompt = """You are an expert autonomous trading agent for TradeOS.
Analyze the provided market data and output a JSON decision.
Your response MUST be valid JSON matching this schema:
{
    "decision": "BUY" | "SHORT" | "HOLD",
    "confidence": <integer 0-100>,
    "entry_price": <float>,
    "stop_loss": <float>,
    "target": <float>,
    "quantity": <integer>,
    "reasoning": "<string>",
    "invalidation_condition": "<string>",
    "signal_expiry": "14:00"
}
"""
        sys_prompt = system_prompt if system_prompt else default_system_prompt

        response = await client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": payload}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        content = response.choices[0].message.content
        return json.loads(content)
        
    except Exception as e:
        logger.error(f"DeepSeek query failed: {e}")
        return {
            "decision": "HOLD",
            "confidence": 0,
            "reasoning": f"DeepSeek API Error: {str(e)}"
        }
