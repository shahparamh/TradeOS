import time
import threading
from utils.logger import setup_logger

logger = setup_logger("rate_limiter")

# Minimum gap in seconds between any two yfinance calls
MIN_REQUEST_INTERVAL = 1.5

_last_request_time = 0.0
_lock = threading.Lock()

def rate_limited_call(func, *args, **kwargs):
    """
    Enforces a minimum interval between calls globally using a threading.Lock.
    Thread-safe and suitable for use with asyncio.to_thread.
    """
    global _last_request_time
    with _lock:
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - elapsed
            logger.debug(f"Rate limiter: sleeping {sleep_time:.2f}s before calling {func.__name__ if hasattr(func, '__name__') else str(func)}")
            time.sleep(sleep_time)
        
        # Record execution start time
        _last_request_time = time.time()
        
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in rate-limited call to {func.__name__ if hasattr(func, '__name__') else str(func)}: {e}")
            raise e
