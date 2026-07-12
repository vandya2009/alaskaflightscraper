"""Pins down the two different ways a bad airport code can fail, so the
distinction (crash vs. caught-and-logged) doesn't silently drift:

1. Unknown to airportsdata (routes.py) -- crashes building the plan list,
   before scrape.py's per-search try/except even exists yet. See
   test_routes.py::test_unknown_destination_raises_before_any_search_runs.
2. Known to airportsdata but not fli's Airport enum (flights.py) -- raised
   by _airport(), NOT caught inside search_one_way (see test_flights.py),
   but IS caught by scrape.py's per-search try/except: logged as a failure,
   the run continues to the next plan, and ends with status PARTIAL instead
   of crashing. That's what this file tests.
"""
from datetime import date, timedelta

from src import scrape


def _future_date():
    return (date.today() + timedelta(days=10)).isoformat()


def _plan(n, dest="ZZZ"):
    return {
        "origin": "JFK",
        "destination": dest,
        "depart_date": "2026-08-10",
        "distance_miles": 2000.0,
    }


def test_bad_airport_code_is_caught_logged_and_run_continues(monkeypatch):
    plans = [_plan(1, dest="ZZZ"), _plan(2, dest="LAX")]
    monkeypatch.setattr(scrape, "planned_searches", lambda **kwargs: iter(plans))
    monkeypatch.setattr(scrape, "existing_keys", lambda tab_name: set())
    monkeypatch.setattr(scrape, "append_results", lambda rows, tab_name: None)
    monkeypatch.setattr(scrape, "was_cached", lambda: False)
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(scrape.sys, "argv", ["scrape.py", _future_date(), "JFK"])

    call_log = []

    def fake_search_one_way(**kwargs):
        call_log.append(kwargs["destination"])
        if kwargs["destination"] == "ZZZ":
            raise ValueError("Unknown airport code 'ZZZ'. Use 3-letter IATA codes (e.g. SEA, JFK).")
        return []  # LAX: a real search that just finds nothing

    monkeypatch.setattr(scrape, "search_one_way", fake_search_one_way)

    logged = {}
    monkeypatch.setattr(
        scrape,
        "append_log",
        lambda status, message, total_results, total_deals: logged.update(
            status=status, message=message, total_results=total_results, total_deals=total_deals
        ),
    )

    scrape.main()  # must not raise -- this is the whole point

    # Both plans were attempted; the bad one didn't stop the second from running.
    assert call_log == ["ZZZ", "LAX"]
    assert logged["status"] == "PARTIAL"
    assert "Unknown airport code 'ZZZ'" in logged["message"]


def test_planned_searches_failure_is_not_caught_by_scrape_main(monkeypatch):
    """The routes.py-level failure (case 1 above) happens before the
    try/except loop exists -- scrape.main() has no opportunity to catch it,
    so it must propagate all the way out, unlike a per-search failure."""
    def boom(**kwargs):
        raise ValueError("Unknown airport code in airportsdata: ZZZ")

    monkeypatch.setattr(scrape, "planned_searches", boom)
    monkeypatch.setattr(scrape.sys, "argv", ["scrape.py", _future_date(), "JFK"])

    import pytest
    with pytest.raises(ValueError, match="Unknown airport code in airportsdata"):
        scrape.main()
