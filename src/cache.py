"""On-disk cache for flight search results, keyed by search parameters.

For local development: repeated runs against the same route/date/filters hit
disk instead of Google Flights, which speeds up iteration and avoids adding to
rate-limiting. Enabled by default; set FLIGHT_CACHE=0 to disable (e.g. for the
eventual GitHub Action run, where prices should always be fresh).
"""
import hashlib
import json
import os
import time
from pathlib import Path

from src.config import PROJECT_ROOT

CACHE_DIR = PROJECT_ROOT / ".cache" / "flights"
_DEFAULT_TTL_MINUTES = 60


def enabled() -> bool:
    return os.environ.get("FLIGHT_CACHE", "1") != "0"


def _ttl_seconds() -> int:
    return int(os.environ.get("FLIGHT_CACHE_TTL_MINUTES", _DEFAULT_TTL_MINUTES)) * 60


def _cache_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{digest}.json"


def get(key: str) -> list[dict] | None:
    if not enabled():
        return None
    path = _cache_path(key)
    if not path.exists():
        return None
    with path.open() as f:
        payload = json.load(f)
    if time.time() - payload["cached_at"] > _ttl_seconds():
        return None
    return payload["rows"]


def set(key: str, rows: list[dict]) -> None:
    if not enabled():
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with _cache_path(key).open("w") as f:
        json.dump({"key": key, "cached_at": time.time(), "rows": rows}, f)
