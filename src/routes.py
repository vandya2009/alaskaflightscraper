"""Builds the list of flight searches to run, based on settings.yaml."""
from datetime import date, timedelta
from typing import Iterator

from src.config import SETTINGS


def planned_searches() -> Iterator[dict]:
    """Yield one search plan per (destination, departure date) combination."""
    home = SETTINGS["home_airport"].upper()
    destinations = [d.upper() for d in SETTINGS["destinations"]]
    start = int(SETTINGS["search_start_days"])
    window = int(SETTINGS["search_window_days"])
    step = max(1, int(SETTINGS["search_step_days"]))

    today = date.today()
    for day_offset in range(start, start + window, step):
        depart_date = today + timedelta(days=day_offset)
        for dest in destinations:
            yield {
                "origin": home,
                "destination": dest,
                "depart_date": depart_date.isoformat(),
            }
