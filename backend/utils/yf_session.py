"""
TradeOS — Shared yfinance Session
Yahoo's bot detection fingerprints plain HTTP sessions — datacenter/cloud IPs (Render, AWS,
etc.) trip it far more easily than home IPs, and the symptom is NOT a clean error: `.info`
comes back as a real, non-empty dict but with every financial field missing, while cheaper
endpoints like fast_info/history keep working. curl_cffi impersonates a real browser's TLS
fingerprint, which yfinance's own docs recommend specifically for this failure mode.

One shared session (not a new one per call) so the TLS/cookie state — and any crumb yfinance
negotiates — gets reused across requests instead of starting cold every time.
"""

from curl_cffi import requests as curl_requests
from utils.logger import setup_logger

logger = setup_logger("yf_session")

_session = None


def get_yf_session():
    global _session
    if _session is None:
        _session = curl_requests.Session(impersonate="chrome")
        logger.info("Created shared curl_cffi (Chrome-impersonating) session for yfinance.")
    return _session
