from datetime import date, timedelta

import pytest

from src import scrape


def test_valid_date_expands_to_window_of_default_size():
    tomorrow = date.today() + timedelta(days=1)
    target = tomorrow + timedelta(days=10)
    result = scrape._validate_date_window(target.isoformat())

    expected = [
        (target + timedelta(days=offset)).isoformat()
        for offset in range(-scrape.PROMPT_WINDOW_DAYS, scrape.PROMPT_WINDOW_DAYS + 1)
    ]
    assert result == expected


def test_window_clamped_to_not_go_before_tomorrow():
    tomorrow = date.today() + timedelta(days=1)
    result = scrape._validate_date_window(tomorrow.isoformat())
    assert all(date.fromisoformat(d) >= tomorrow for d in result)


def test_malformed_date_raises():
    with pytest.raises(scrape._InvalidInput):
        scrape._validate_date_window("not-a-date")


def test_past_date_raises():
    yesterday = date.today() - timedelta(days=1)
    with pytest.raises(scrape._InvalidInput):
        scrape._validate_date_window(yesterday.isoformat())


def test_window_size_configurable(monkeypatch):
    monkeypatch.setattr(scrape, "PROMPT_WINDOW_DAYS", 3)
    tomorrow = date.today() + timedelta(days=1)
    target = tomorrow + timedelta(days=10)
    result = scrape._validate_date_window(target.isoformat())
    assert len(result) == 7  # +/- 3 days


def test_valid_airports_parsed_and_uppercased():
    assert scrape._validate_airports("jfk,ewr") == ["JFK", "EWR"]


def test_single_airport():
    assert scrape._validate_airports("sea") == ["SEA"]


def test_unknown_airport_code_raises():
    with pytest.raises(scrape._InvalidInput):
        scrape._validate_airports("ZZZ")


def test_blank_entries_between_commas_ignored():
    assert scrape._validate_airports("JFK,,EWR") == ["JFK", "EWR"]
