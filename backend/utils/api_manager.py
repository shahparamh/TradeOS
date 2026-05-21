"""
TradeOS — Centralized API Key Manager
Manages multi-key rotation, per-key rate limiting, usage tracking, and exhaustion detection
for all external API providers (Gemini, Groq, NewsAPI, etc.).
"""

import time
import hashlib
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger("api_manager")


class _ProviderState:
    """Tracks the state of all keys for a single API provider."""

    def __init__(self, keys: list[str]):
        self.keys = [k.strip() for k in keys if k and k.strip()]
        # {key_hash: {"requests": int, "last_reset": float, "exhausted": bool}}
        self.usage: dict[str, dict] = {
            self._hash(k): {"requests": 0, "last_reset": time.time(), "exhausted": False}
            for k in self.keys
        }
        self._current_idx = 0

    @staticmethod
    def _hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _reset_if_needed(self, key_hash: str, window_seconds: int = 86400):
        """Reset daily counts if the window has passed."""
        state = self.usage[key_hash]
        if time.time() - state["last_reset"] >= window_seconds:
            state["requests"] = 0
            state["last_reset"] = time.time()
            state["exhausted"] = False
            logger.info(f"[APIManager] Key {key_hash} daily usage reset.")

    def get_key(self, daily_limit: int = 1500) -> Optional[str]:
        """
        Returns the next available, non-exhausted key using round-robin rotation.
        Returns None if all keys are exhausted.
        """
        if not self.keys:
            return None

        num_keys = len(self.keys)
        for attempt in range(num_keys):
            idx = (self._current_idx + attempt) % num_keys
            key = self.keys[idx]
            key_hash = self._hash(key)
            self._reset_if_needed(key_hash)

            state = self.usage[key_hash]
            if not state["exhausted"] and state["requests"] < daily_limit:
                self._current_idx = idx  # Sticky: stay on the working key
                return key

        logger.error("[APIManager] All keys for this provider are exhausted.")
        return None

    def record_usage(self, key: str, count: int = 1):
        """Increment request count for the given key."""
        key_hash = self._hash(key)
        if key_hash in self.usage:
            self.usage[key_hash]["requests"] += count

    def mark_exhausted(self, key: str):
        """Permanently mark a key as exhausted (e.g. 429 with no retry-after)."""
        key_hash = self._hash(key)
        if key_hash in self.usage:
            self.usage[key_hash]["exhausted"] = True
            # Rotate to next key
            self._current_idx = (self._current_idx + 1) % max(len(self.keys), 1)
            logger.warning(f"[APIManager] Key {key_hash} marked exhausted — rotating to next key.")

    def are_all_exhausted(self) -> bool:
        """Returns True when every key is exhausted or over daily limit."""
        for key in self.keys:
            key_hash = self._hash(key)
            self._reset_if_needed(key_hash)
            state = self.usage[key_hash]
            if not state["exhausted"]:
                return False
        return True

    def get_usage_stats(self) -> list[dict]:
        """Returns per-key usage stats for the dashboard."""
        stats = []
        for key in self.keys:
            key_hash = self._hash(key)
            self._reset_if_needed(key_hash)
            state = self.usage[key_hash]
            stats.append({
                "key_hash": key_hash,
                "requests_today": state["requests"],
                "exhausted": state["exhausted"],
                "last_reset": state["last_reset"],
            })
        return stats


class APIKeyManager:
    """
    Singleton-style manager that holds provider states.
    Usage:
        from utils.api_manager import api_key_manager
        key = api_key_manager.get_key("gemini")
        api_key_manager.record_usage("gemini", key)
        api_key_manager.mark_exhausted("gemini", key)
    """

    def __init__(self):
        self._providers: dict[str, _ProviderState] = {}

    def register(self, provider: str, keys: list[str]):
        """Register a provider with its list of API keys."""
        self._providers[provider] = _ProviderState(keys)
        logger.info(f"[APIManager] Registered '{provider}' with {len(keys)} key(s).")

    def get_key(self, provider: str, daily_limit: int = 1500) -> Optional[str]:
        """Get the next available key for the provider."""
        state = self._providers.get(provider)
        if not state:
            return None
        return state.get_key(daily_limit=daily_limit)

    def record_usage(self, provider: str, key: str, count: int = 1):
        """Record API usage for a specific key."""
        state = self._providers.get(provider)
        if state:
            state.record_usage(key, count)

    def mark_exhausted(self, provider: str, key: str):
        """Mark a key as exhausted and rotate to the next one."""
        state = self._providers.get(provider)
        if state:
            state.mark_exhausted(key)

    def are_all_exhausted(self, provider: str) -> bool:
        """Check if all keys for a provider are exhausted."""
        state = self._providers.get(provider)
        return state.are_all_exhausted() if state else True

    def get_usage_stats(self, provider: str) -> list[dict]:
        """Get usage stats for all keys of a provider."""
        state = self._providers.get(provider)
        return state.get_usage_stats() if state else []

    def get_all_stats(self) -> dict:
        """Get usage stats across all registered providers."""
        return {p: self._providers[p].get_usage_stats() for p in self._providers}


# Module-level singleton — imported and used by all agents
api_key_manager = APIKeyManager()


def initialize_api_manager():
    """
    Called at startup (in main.py) to populate the manager with all configured keys.
    """
    from config import settings

    def _to_list(val) -> list[str]:
        if isinstance(val, list):
            return [k for k in val if k and k.strip()]
        if isinstance(val, str) and val.strip():
            return [val.strip()]
        return []

    gemini_keys = _to_list(settings.GEMINI_API_KEYS) or _to_list(settings.GEMINI_API_KEY)
    groq_keys = _to_list(settings.GROQ_API_KEYS) or _to_list(settings.GROQ_API_KEY)
    newsapi_keys = _to_list(getattr(settings, "NEWS_API_KEYS", []))
    github_keys = _to_list(getattr(settings, "GITHUB_API_KEYS", [])) or _to_list(getattr(settings, "GITHUB_API_KEY", ""))
    hf_key = _to_list(getattr(settings, "HF_API_KEY", ""))
    deepseek_key = _to_list(getattr(settings, "DEEPSEEK_API_KEY", ""))

    api_key_manager.register("gemini", gemini_keys)
    api_key_manager.register("groq", groq_keys)
    api_key_manager.register("newsapi", newsapi_keys)
    api_key_manager.register("github", github_keys)
    api_key_manager.register("huggingface", hf_key)
    api_key_manager.register("deepseek", deepseek_key)

    logger.info("[APIManager] Initialized with all configured API keys.")
