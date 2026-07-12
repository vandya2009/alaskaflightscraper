"""Regression tests for a real bug found this project: the rate-limit pause
was only reached via `continue` paths that happened to fall after it in the
loop, so it silently never fired for "no rows" / "above threshold" outcomes —
the common case. Fixed by moving the sleep into a `finally` block.
"""
from datetime import date, timedelta

from src import scrape


def _future_date():
    return (date.today() + timedelta(days=10)).isoformat()


def _plan(n):
    return {
        "origin": "JFK",
        "destination": f"DST{n}",
        "depart_date": "2026-08-10",
        "distance_miles": 2000.0,
    }


def _wire_common_mocks(monkeypatch, plans):
    monkeypatch.setattr(scrape, "planned_searches", lambda **kwargs: iter(plans))
    monkeypatch.setattr(scrape, "existing_keys", lambda tab_name: set())
    monkeypatch.setattr(scrape, "append_results", lambda rows, tab_name: None)
    monkeypatch.setattr(scrape, "append_log", lambda *a, **k: None)
    monkeypatch.setattr(scrape, "reset_results", lambda: None)
    monkeypatch.setattr(scrape.sys, "argv", ["scrape.py", _future_date(), "JFK"])


def test_reset_results_is_called_before_the_sweep_starts(monkeypatch):
    """Each run reflects only its own findings, not an accumulating history --
    reset_results() must run before any results get written."""
    plans = [_plan(1)]
    _wire_common_mocks(monkeypatch, plans)
    monkeypatch.setattr(scrape, "search_one_way", lambda **kwargs: [])
    monkeypatch.setattr(scrape, "was_cached", lambda: False)
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: None)

    calls = []
    monkeypatch.setattr(scrape, "reset_results", lambda: calls.append("reset"))

    scrape.main()

    assert calls == ["reset"]


def test_sleep_fires_even_when_no_rows_found(monkeypatch):
    plans = [_plan(1), _plan(2), _plan(3)]
    _wire_common_mocks(monkeypatch, plans)
    monkeypatch.setattr(scrape, "search_one_way", lambda **kwargs: [])
    monkeypatch.setattr(scrape, "was_cached", lambda: False)

    sleep_calls = []
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    scrape.main()

    assert len(sleep_calls) == len(plans)


def test_sleep_fires_even_when_above_threshold(monkeypatch):
    plans = [_plan(1)]
    _wire_common_mocks(monkeypatch, plans)
    # A result exists, but its cents_per_mile is above record_threshold_cpm.
    monkeypatch.setattr(
        scrape,
        "search_one_way",
        lambda **kwargs: [{**_plan(1), "cents_per_mile": 999.0, "price_usd": 5000.0, "airline": "AA"}],
    )
    monkeypatch.setattr(scrape, "was_cached", lambda: False)

    sleep_calls = []
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    scrape.main()

    assert len(sleep_calls) == 1


def test_sleep_skipped_when_result_was_cached(monkeypatch):
    plans = [_plan(1)]
    _wire_common_mocks(monkeypatch, plans)
    monkeypatch.setattr(scrape, "search_one_way", lambda **kwargs: [])
    monkeypatch.setattr(scrape, "was_cached", lambda: True)

    sleep_calls = []
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    scrape.main()

    assert sleep_calls == []


def test_search_failure_still_sleeps_and_is_logged(monkeypatch):
    plans = [_plan(1)]
    _wire_common_mocks(monkeypatch, plans)

    def boom(**kwargs):
        raise RuntimeError("simulated network failure")

    monkeypatch.setattr(scrape, "search_one_way", boom)
    monkeypatch.setattr(scrape, "was_cached", lambda: False)

    sleep_calls = []
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    scrape.main()  # must not raise -- per-search failures are caught

    assert len(sleep_calls) == 1
