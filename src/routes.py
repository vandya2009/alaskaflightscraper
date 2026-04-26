"""Builds the list of flight searches to run, based on settings.yaml.

Each plan is a (origin, destination, depart_date) combination, with the
great-circle distance pre-computed. Routes shorter than `min_distance_miles`
are filtered out so we never query Google Flights for them.
"""
from datetime import date, timedelta
from typing import Iterator

import airportsdata
from haversine import Unit, haversine

from src.config import SETTINGS

_AIRPORTS = airportsdata.load("IATA")


def _coords(code: str) -> tuple[float, float]:
    info = _AIRPORTS.get(code.upper())
    if info is None:
        raise ValueError(f"Unknown airport code in airportsdata: {code}")
    return (info["lat"], info["lon"])


def _distance_miles(origin: str, destination: str) -> float:
    return haversine(_coords(origin), _coords(destination), unit=Unit.MILES)


def planned_searches(dates_override: list[str] | None = None) -> Iterator[dict]:
    """Yield one search plan per (origin, destination, departure date).

    If `dates_override` is given, those dates are used and the date-sweep
    settings in settings.yaml are ignored.
    """
    origins = [o.upper() for o in SETTINGS["home_airports"]]
    destinations = [d.upper() for d in SETTINGS["destinations"]]
    min_dist = float(SETTINGS.get("min_distance_miles", 0))

    if dates_override:
        dates = list(dates_override)
    else:
        start = int(SETTINGS["search_start_days"])
        window = int(SETTINGS["search_window_days"])
        step = max(1, int(SETTINGS["search_step_days"]))
        today = date.today()
        dates = [
            (today + timedelta(days=d)).isoformat()
            for d in range(start, start + window, step)
        ]

    for origin in origins:
        for dest in destinations:
            if dest == origin:
                continue
            dist = _distance_miles(origin, dest)
            if dist < min_dist:
                continue
            for depart_date in dates:
                yield {
                    "origin": origin,
                    "destination": dest,
                    "depart_date": depart_date,
                    "distance_miles": round(dist, 1),
                }
