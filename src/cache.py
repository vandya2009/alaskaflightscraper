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

# Bump whenever the row dict shape returned by search_one_way changes (fields
# added/removed/renamed). Without this, a cache hit returns an old row dict
# verbatim -- e.g. missing a newly added column -- causing a KeyError deep in
# whichever output backend tries to read it. Older entries (written before
# this field existed) have no "schema_version" key at all, so they always
# mismatch and get treated as a miss automatically -- no manual cache clear needed.
_SCHEMA_VERSION = 2


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
    if payload.get("schema_version") != _SCHEMA_VERSION:
        return None
    if time.time() - payload["cached_at"] > _ttl_seconds():
        return None
    return payload["rows"]


def set(key: str, rows: list[dict]) -> None:
    if not enabled():
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with _cache_path(key).open("w") as f:
        json.dump(
            {"key": key, "cached_at": time.time(), "schema_version": _SCHEMA_VERSION, "rows": rows},
            f,
        )
