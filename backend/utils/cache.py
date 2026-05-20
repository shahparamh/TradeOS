"""
TradeOS — Generic TTL Cache Decorator
Provides a simple in-memory time-to-live cache for expensive function calls.
"""

import time
import functools
from utils.logger import setup_logger

logger = setup_logger("cache")

# Global cache store: { "function_name:args_hash": (result, expire_time) }
_cache_store: dict = {}


def ttl_cache(seconds: int = 300):
    """
    Decorator that caches a function's return value for `seconds` seconds.
    The cache key is built from the function name and all positional + keyword args.

    Usage:
        @ttl_cache(seconds=900)
        def fetch_option_oi_metrics(symbol: str) -> dict:
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build a stable cache key from function identity + arguments
            key_parts = [func.__module__, func.__name__] + [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
            cache_key = ":".join(key_parts)

            now = time.time()
            if cache_key in _cache_store:
                result, expire_at = _cache_store[cache_key]
                if now < expire_at:
                    logger.debug(f"[TTL-CACHE HIT] {func.__name__}({', '.join(str(a) for a in args)})")
                    return result
                else:
                    # Expired — remove from store
                    del _cache_store[cache_key]

            # Cache miss — call the real function
            result = func(*args, **kwargs)
            _cache_store[cache_key] = (result, now + seconds)
            logger.debug(f"[TTL-CACHE SET] {func.__name__}({', '.join(str(a) for a in args)}) — expires in {seconds}s")
            return result

        # Expose cache management helpers on the wrapper
        def invalidate(*args, **kwargs):
            """Manually invalidate a specific cache entry."""
            key_parts = [func.__module__, func.__name__] + [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
            cache_key = ":".join(key_parts)
            if cache_key in _cache_store:
                del _cache_store[cache_key]

        def invalidate_all():
            """Clear all cached entries for this function."""
            prefix = f"{func.__module__}:{func.__name__}:"
            keys_to_delete = [k for k in _cache_store if k.startswith(prefix)]
            for k in keys_to_delete:
                del _cache_store[k]

        wrapper.invalidate = invalidate
        wrapper.invalidate_all = invalidate_all
        return wrapper
    return decorator


def get_cache_stats() -> dict:
    """Returns statistics about the current in-memory cache."""
    now = time.time()
    total = len(_cache_store)
    active = sum(1 for _, (_, exp) in _cache_store.items() if now < exp)
    expired = total - active
    return {
        "total_entries": total,
        "active_entries": active,
        "expired_entries": expired,
    }


def clear_all_caches():
    """Wipes the entire in-memory cache store. Use with caution."""
    _cache_store.clear()
    logger.info("All in-memory TTL caches cleared.")
