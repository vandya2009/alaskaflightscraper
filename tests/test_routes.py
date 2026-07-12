import pytest

from src.config import SETTINGS
from src.routes import planned_searches


def test_same_origin_and_destination_excluded(monkeypatch):
    monkeypatch.setitem(SETTINGS, "destinations", ["JFK", "LAX"])
    monkeypatch.setitem(SETTINGS, "min_distance_miles", 0)

    plans = list(planned_searches(dates_override=["2026-08-10"], origins_override=["JFK"]))

    assert all(p["destination"] != p["origin"] for p in plans)
    destinations = {p["destination"] for p in plans}
    assert destinations == {"LAX"}


def test_routes_shorter_than_min_distance_are_skipped(monkeypatch):
    # JFK-BOS is ~190mi (well under a 1900mi cutoff); JFK-LAX is ~2470mi.
    monkeypatch.setitem(SETTINGS, "destinations", ["BOS", "LAX"])
    monkeypatch.setitem(SETTINGS, "min_distance_miles", 1900)

    plans = list(planned_searches(dates_override=["2026-08-10"], origins_override=["JFK"]))

    destinations = {p["destination"] for p in plans}
    assert destinations == {"LAX"}


def test_dates_override_used_verbatim(monkeypatch):
    monkeypatch.setitem(SETTINGS, "destinations", ["LAX"])
    monkeypatch.setitem(SETTINGS, "min_distance_miles", 0)

    dates = ["2026-07-31", "2026-08-01", "2026-08-02"]
    plans = list(planned_searches(dates_override=dates, origins_override=["JFK"]))

    assert sorted(p["depart_date"] for p in plans) == sorted(dates)


def test_origins_override_replaces_home_airports(monkeypatch):
    monkeypatch.setitem(SETTINGS, "destinations", ["LAX"])
    monkeypatch.setitem(SETTINGS, "min_distance_miles", 0)
    monkeypatch.setitem(SETTINGS, "home_airports", ["SEA"])

    plans = list(planned_searches(dates_override=["2026-08-10"], origins_override=["JFK", "EWR"]))

    origins = {p["origin"] for p in plans}
    assert origins == {"JFK", "EWR"}


def test_falls_back_to_home_airports_when_no_override(monkeypatch):
    monkeypatch.setitem(SETTINGS, "destinations", ["LAX"])
    monkeypatch.setitem(SETTINGS, "min_distance_miles", 0)
    monkeypatch.setitem(SETTINGS, "home_airports", ["SEA"])

    plans = list(planned_searches(dates_override=["2026-08-10"]))

    origins = {p["origin"] for p in plans}
    assert origins == {"SEA"}


def test_unknown_destination_raises_before_any_search_runs(monkeypatch):
    """A destination airportsdata doesn't recognize blows up the whole plan
    list immediately (not caught anywhere) -- this happens before scrape.py
    has even printed "Running N flight searches...", let alone started one.
    Contrast with test_flights.py's version of this: a code airportsdata
    knows but fli's smaller Airport enum doesn't, which *is* caught -- but
    only once per-search, inside scrape.py's loop, not here."""
    monkeypatch.setitem(SETTINGS, "destinations", ["ZZZ"])
    monkeypatch.setitem(SETTINGS, "min_distance_miles", 0)

    with pytest.raises(ValueError, match="Unknown airport code in airportsdata"):
        list(planned_searches(dates_override=["2026-08-10"], origins_override=["JFK"]))


def test_unknown_origin_raises_before_any_search_runs(monkeypatch):
    monkeypatch.setitem(SETTINGS, "destinations", ["LAX"])
    monkeypatch.setitem(SETTINGS, "min_distance_miles", 0)

    with pytest.raises(ValueError, match="Unknown airport code in airportsdata"):
        list(planned_searches(dates_override=["2026-08-10"], origins_override=["ZZZ"]))


def test_distance_miles_matches_known_great_circle_value(monkeypatch):
    monkeypatch.setitem(SETTINGS, "destinations", ["LAX"])
    monkeypatch.setitem(SETTINGS, "min_distance_miles", 0)

    plans = list(planned_searches(dates_override=["2026-08-10"], origins_override=["JFK"]))

    # JFK-LAX great-circle distance is well-established at ~2470 miles.
    assert 2450 <= plans[0]["distance_miles"] <= 2490
