"""
app/ai/cache.py — In-process TTL response cache for AI outputs.

Key: SHA-256 hash of the full prompt string.
Value: (response_dict, expiry_timestamp)
Thread-safe via threading.Lock.
"""
import hashlib
import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_store: Dict[str, Tuple[Any, float]] = {}
_lock = threading.Lock()


def _make_key(prompt: str) -> str:
    """SHA-256 hash of prompt → cache key."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def get(prompt: str, ttl: int) -> Optional[Any]:
    """
    Return cached response if exists and not expired, else None.

    Args:
        prompt: The full composed prompt string (used as cache key)
        ttl: Time-to-live in seconds (0 = no caching)
    """
    if ttl <= 0:
        return None
    key = _make_key(prompt)
    with _lock:
        entry = _store.get(key)
        if entry is None:
            logger.debug("Cache miss for key=%s", key[:16])
            return None
        response, expiry = entry
        if time.monotonic() > expiry:
            del _store[key]
            logger.debug("Cache expired for key=%s", key[:16])
            return None
        logger.debug("Cache hit for key=%s", key[:16])
        return response


def set(prompt: str, response: Any, ttl: int) -> None:
    """Store a response in the cache with TTL."""
    if ttl <= 0:
        return
    key = _make_key(prompt)
    expiry = time.monotonic() + ttl
    with _lock:
        _store[key] = (response, expiry)
    logger.debug("Cached response for key=%s, ttl=%ds", key[:16], ttl)


def clear() -> None:
    """Clear all cached entries (used in tests)."""
    with _lock:
        _store.clear()


def stats() -> Dict[str, int]:
    """Return cache statistics."""
    with _lock:
        now = time.monotonic()
        active = sum(1 for _, (_, exp) in _store.items() if exp > now)
        return {"total_entries": len(_store), "active_entries": active}
