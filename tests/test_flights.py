from datetime import datetime
from types import SimpleNamespace

import pytest

from src import flights


def _leg(airline_name, airline_value, flight_number, dep, arr):
    return SimpleNamespace(
        airline=SimpleNamespace(name=airline_name, value=airline_value),
        flight_number=flight_number,
        departure_datetime=dep,
        arrival_datetime=arr,
    )


def _itinerary(legs, price, stops, duration):
    return SimpleNamespace(legs=legs, price=price, stops=stops, duration=duration)


@pytest.fixture
def one_leg_aa():
    return _itinerary(
        legs=[_leg("AA", "American Airlines", "475", datetime(2026, 8, 10, 6, 30), datetime(2026, 8, 10, 11, 57))],
        price=334.0,
        stops=0,
        duration=507,
    )


@pytest.fixture
def two_leg_mixed_disallowed():
    """AA leg then a disallowed 'XX' leg — should be filtered out entirely."""
    return _itinerary(
        legs=[
            _leg("AA", "American Airlines", "100", datetime(2026, 8, 10, 6, 0), datetime(2026, 8, 10, 9, 0)),
            _leg("XX", "Not A Partner", "200", datetime(2026, 8, 10, 10, 0), datetime(2026, 8, 10, 13, 0)),
        ],
        price=200.0,
        stops=1,
        duration=420,
    )


@pytest.fixture
def two_leg_mixed_allowed():
    """AA domestic leg + QF international leg -- both allowed carriers, so it
    qualifies, but it's the exact pattern confirmed (via a real Alaska search)
    to sometimes have zero equivalent option on Alaska's own engine at all."""
    return _itinerary(
        legs=[
            _leg("AA", "American Airlines", "100", datetime(2026, 8, 10, 6, 0), datetime(2026, 8, 10, 9, 0)),
            _leg("QF", "Qantas", "94", datetime(2026, 8, 10, 10, 0), datetime(2026, 8, 11, 6, 45)),
        ],
        price=900.0,
        stops=1,
        duration=1245,
    )


def _search_kwargs(**overrides):
    kwargs = dict(
        origin="JFK",
        destination="LAX",
        depart_date="2026-08-10",
        distance_miles=2470.0,
        allowed_airlines={"AA", "AS", "QF"},
    )
    kwargs.update(overrides)
    return kwargs


def test_filters_out_itinerary_with_any_disallowed_leg(monkeypatch, one_leg_aa, two_leg_mixed_disallowed):
    monkeypatch.setattr(
        flights._SEARCH_CLIENT, "search", lambda filters: [two_leg_mixed_disallowed, one_leg_aa]
    )
    rows = flights.search_one_way(**_search_kwargs(top_n=5))
    assert len(rows) == 1
    assert rows[0]["airline"] == "American Airlines"


def test_single_carrier_true_when_all_legs_same_airline(monkeypatch, one_leg_aa):
    monkeypatch.setattr(flights._SEARCH_CLIENT, "search", lambda filters: [one_leg_aa])
    rows = flights.search_one_way(**_search_kwargs())
    assert rows[0]["single_carrier"] is True


def test_single_carrier_false_when_legs_span_multiple_airlines(monkeypatch, two_leg_mixed_allowed):
    """Both legs are individually allowed (so the itinerary qualifies), but
    they're different carriers -- exactly the AA+QF pattern confirmed via a
    real Alaska search to sometimes have no equivalent option at all."""
    monkeypatch.setattr(flights._SEARCH_CLIENT, "search", lambda filters: [two_leg_mixed_allowed])
    rows = flights.search_one_way(**_search_kwargs())
    assert rows[0]["single_carrier"] is False


def test_google_flights_url_is_a_real_search_link(monkeypatch, one_leg_aa):
    """Format confirmed from fli's own source (_booking_capture.py), which
    drives a real browser to this same URL for its Playwright-based booking
    flow -- not a guess, unlike the Alaska /planbook URL bug we hit earlier."""
    monkeypatch.setattr(flights._SEARCH_CLIENT, "search", lambda filters: [one_leg_aa])
    rows = flights.search_one_way(**_search_kwargs(origin="jfk", destination="lax", depart_date="2026-08-10"))
    url = rows[0]["google_flights_url"]
    assert url.startswith("https://www.google.com/travel/flights?")
    assert "q=Flights%20to%20LAX%20from%20JFK%20on%202026-08-10%20one%20way" in url


def test_google_flights_url_specifies_one_way(monkeypatch, one_leg_aa):
    """Regression test: without 'one way' in the query, Google Flights defaults
    to round trip and silently picks its own return date -- confirmed live by
    decoding a real generated URL's tfs= parameter, which came back with an
    auto-added return leg roughly doubling the displayed price."""
    monkeypatch.setattr(flights._SEARCH_CLIENT, "search", lambda filters: [one_leg_aa])
    rows = flights.search_one_way(**_search_kwargs())
    assert "one%20way" in rows[0]["google_flights_url"]


def test_computes_cents_per_mile(monkeypatch, one_leg_aa):
    monkeypatch.setattr(flights._SEARCH_CLIENT, "search", lambda filters: [one_leg_aa])
    rows = flights.search_one_way(**_search_kwargs(distance_miles=2470.0))
    # 334.0 * 100 / 2470.0 = 13.52...
    assert rows[0]["cents_per_mile"] == pytest.approx(13.52, abs=0.01)


def test_top_n_limits_results(monkeypatch, one_leg_aa):
    monkeypatch.setattr(flights._SEARCH_CLIENT, "search", lambda filters: [one_leg_aa, one_leg_aa, one_leg_aa])
    rows = flights.search_one_way(**_search_kwargs(top_n=2))
    assert len(rows) == 2


def test_no_qualifying_results_returns_empty_list(monkeypatch, two_leg_mixed_disallowed):
    monkeypatch.setattr(flights._SEARCH_CLIENT, "search", lambda filters: [two_leg_mixed_disallowed])
    rows = flights.search_one_way(**_search_kwargs())
    assert rows == []


def test_has_no_attribute_quirk_swallowed_as_empty(monkeypatch):
    def raise_quirk(filters):
        raise Exception("type object 'Airport' has no attribute 'XRL'")

    monkeypatch.setattr(flights._SEARCH_CLIENT, "search", raise_quirk)
    assert flights.search_one_way(**_search_kwargs()) == []


def test_other_exceptions_are_not_swallowed(monkeypatch):
    def raise_real_error(filters):
        raise RuntimeError("actual network failure")

    monkeypatch.setattr(flights._SEARCH_CLIENT, "search", raise_real_error)
    with pytest.raises(RuntimeError):
        flights.search_one_way(**_search_kwargs())


def test_second_identical_call_is_served_from_cache(monkeypatch, one_leg_aa):
    calls = []

    def counting_search(filters):
        calls.append(1)
        return [one_leg_aa]

    monkeypatch.setattr(flights._SEARCH_CLIENT, "search", counting_search)

    first = flights.search_one_way(**_search_kwargs())
    assert flights.was_cached() is False
    assert len(calls) == 1

    second = flights.search_one_way(**_search_kwargs())
    assert flights.was_cached() is True
    assert len(calls) == 1  # not called again
    assert first == second


def test_different_params_are_not_cached_together(monkeypatch, one_leg_aa):
    monkeypatch.setattr(flights._SEARCH_CLIENT, "search", lambda filters: [one_leg_aa])

    flights.search_one_way(**_search_kwargs(destination="LAX"))
    flights.search_one_way(**_search_kwargs(destination="SEA"))
    assert flights.was_cached() is False  # second call, different route, still a miss


def test_unknown_airport_code_raises_valueerror():
    with pytest.raises(ValueError, match="Unknown airport code 'ZZZ'"):
        flights._airport("ZZZ")


def test_unknown_airport_code_propagates_uncaught_from_search_one_way(monkeypatch):
    """Contrast with the 'has no attribute' fli quirk (swallowed as []
    inside search_one_way's own try/except): an unknown airport code raises
    before the network call even happens, from _airport() building the
    filters -- outside that try/except entirely. It is NOT caught here; it's
    only caught one level up, by scrape.py's per-search try/except."""
    search_was_called = []
    monkeypatch.setattr(
        flights._SEARCH_CLIENT, "search", lambda filters: search_was_called.append(1)
    )

    with pytest.raises(ValueError, match="Unknown airport code 'ZZZ'"):
        flights.search_one_way(**_search_kwargs(origin="ZZZ"))

    assert not search_was_called  # never got as far as the network call
