from src import cache


def test_miss_returns_none():
    assert cache.get("some-key") is None


def test_set_then_get_round_trips(sample_row):
    cache.set("route-a", [sample_row])
    assert cache.get("route-a") == [sample_row]


def test_different_keys_are_independent(sample_row):
    cache.set("route-a", [sample_row])
    assert cache.get("route-b") is None


def test_disabled_via_env_skips_both_get_and_set(sample_row, monkeypatch):
    monkeypatch.setenv("FLIGHT_CACHE", "0")
    cache.set("route-a", [sample_row])
    assert cache.get("route-a") is None  # never written, since set() no-oped


def test_expired_entry_is_treated_as_a_miss(sample_row, monkeypatch):
    monkeypatch.setenv("FLIGHT_CACHE_TTL_MINUTES", "60")
    cache.set("route-a", [sample_row])

    # Simulate time passing by rewriting the cached_at timestamp into the past,
    # rather than sleeping — same effect, instant.
    import json
    path = cache._cache_path("route-a")
    payload = json.loads(path.read_text())
    payload["cached_at"] -= 61 * 60  # 61 minutes ago, past the 60 min TTL
    path.write_text(json.dumps(payload))

    assert cache.get("route-a") is None


def test_ttl_is_configurable(sample_row, monkeypatch):
    monkeypatch.setenv("FLIGHT_CACHE_TTL_MINUTES", "5")
    cache.set("route-a", [sample_row])

    import json
    path = cache._cache_path("route-a")
    payload = json.loads(path.read_text())
    payload["cached_at"] -= 6 * 60  # 6 minutes ago, past a 5 min TTL
    path.write_text(json.dumps(payload))

    assert cache.get("route-a") is None


def test_entry_from_before_schema_versioning_existed_is_a_miss(sample_row):
    """Regression: a real crash happened when a stale cache entry (written
    before a new column was added to the row dict) was returned verbatim,
    causing a KeyError in csv_output. Entries with no schema_version at all
    (i.e. written by old code) must always be treated as a miss."""
    import json
    cache.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache._cache_path("route-a")
    path.write_text(json.dumps({"key": "route-a", "cached_at": __import__("time").time(), "rows": [sample_row]}))

    assert cache.get("route-a") is None


def test_entry_with_mismatched_schema_version_is_a_miss(sample_row):
    import json
    cache.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache._cache_path("route-a")
    path.write_text(json.dumps({
        "key": "route-a",
        "cached_at": __import__("time").time(),
        "schema_version": cache._SCHEMA_VERSION - 1,
        "rows": [sample_row],
    }))

    assert cache.get("route-a") is None
