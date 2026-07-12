import pytest

from src import cache, csv_output


@pytest.fixture(autouse=True)
def isolate_filesystem(tmp_path, monkeypatch):
    """Every test gets its own throwaway cache/output dirs, never the real
    project ones — nothing here should read or write .cache/ or output/."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(csv_output, "OUTPUT_DIR", tmp_path / "output")


@pytest.fixture
def sample_row():
    return {
        "origin": "JFK",
        "destination": "LAX",
        "depart_date": "2026-08-10",
        "distance_miles": 2470.0,
        "price_usd": 334.0,
        "cents_per_mile": 13.53,
        "stops": 1,
        "duration_minutes": 507,
        "airline": "American Airlines",
        "flight_numbers": "AA475 > AA2827",
        "depart_time": "06:30",
        "arrive_time": "11:57",
        "alaska_booking_url": "https://www.alaskaair.com/search/results?A=1&O=JFK&D=LAX&OD=2026-08-10&RT=false&locale=en-us",
        "google_flights_url": "https://www.google.com/travel/flights?hl=en&curr=USD&gl=US&q=Flights%20to%20LAX%20from%20JFK%20on%202026-08-10%20one%20way",
    }
