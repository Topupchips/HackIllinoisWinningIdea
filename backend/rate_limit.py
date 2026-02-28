"""
Simple in-memory rate limiting.
Configurable via RATE_LIMIT_REQUESTS and RATE_LIMIT_WINDOW_SEC.
"""
import time
from collections import defaultdict

from fastapi import Request, HTTPException

from config import RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SEC

# client_key -> [(timestamp, ...), ...]
_request_log: dict[str, list[float]] = defaultdict(list)


def _get_client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request) -> None:
    """Raise 429 if client exceeds rate limit."""
    key = _get_client_key(request)
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SEC
    requests = _request_log[key]
    requests[:] = [t for t in requests if t > window_start]
    if len(requests) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW_SEC}s.",
        )
    requests.append(now)
