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
