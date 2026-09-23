"""
TradeOS — LLM Call Pacing
Spaces out calls to the same LLM provider instead of letting a debate round burst them
all at once (3 parallel analyst calls + 2 parallel risk-review calls per symbol). Free-tier
LLM APIs commonly cap at ~15-30 requests/minute or a tight tokens/minute budget; bursting
past that trips a 429, which under utils/api_manager.py's cooldown takes that key out of
rotation for 90s. Pacing calls proactively means far fewer 429s to recover from in the
first place.
"""

import asyncio
import time
from utils.logger import setup_logger

logger = setup_logger("llm_rate_limiter")

# Minimum gap between consecutive calls to the SAME provider.
MIN_INTERVALS = {
    "gemini": 2.5,
    "groq": 2.5,
}
DEFAULT_MIN_INTERVAL = 2.0

_last_call_time: dict[str, float] = {}
_locks: dict[str, asyncio.Lock] = {}


def _get_lock(provider: str) -> asyncio.Lock:
    if provider not in _locks:
        _locks[provider] = asyncio.Lock()
    return _locks[provider]


async def pace(provider: str):
    """Await this immediately before making an LLM call. Enforces a minimum gap since the
    last call to this same provider — parallel callers queue here instead of firing
    simultaneously, so e.g. 3 parallel analyst calls become naturally spread out rather
    than all landing on the provider in the same instant."""
    min_interval = MIN_INTERVALS.get(provider, DEFAULT_MIN_INTERVAL)
    lock = _get_lock(provider)
    async with lock:
        now = time.time()
        last = _last_call_time.get(provider, 0.0)
        elapsed = now - last
        if elapsed < min_interval:
            wait = min_interval - elapsed
            logger.debug(f"[LLM pacing] {provider}: waiting {wait:.2f}s before next call")
            await asyncio.sleep(wait)
        _last_call_time[provider] = time.time()
