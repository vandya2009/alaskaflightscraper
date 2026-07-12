"""Writes results to local CSV files instead of Google Sheets."""
import csv
from datetime import datetime, timezone
from pathlib import Path

from src.config import PROJECT_ROOT
from src.dedup import result_key

OUTPUT_DIR = PROJECT_ROOT / "output"

RESULT_HEADERS = [
    "search_timestamp_utc",
    "origin",
    "destination",
    "depart_date",
    "distance_miles",
    "price_usd",
    "cents_per_mile",
    "stops",
    "duration_minutes",
    "airline",
    "flight_numbers",
    "depart_time",
    "arrive_time",
    "alaska_booking_url",
    "google_flights_url",
]
LOG_HEADERS = ["timestamp_utc", "status", "message", "total_results", "total_deals"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append_rows(path: Path, headers: list[str], rows: list[list]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    is_new = not path.exists()
    with path.open("a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(headers)
        writer.writerows(rows)


def existing_keys(tab_name: str) -> set[tuple]:
    """Dedup keys already on disk for this tab. Empty if the file doesn't exist —
    e.g. because you deleted it — regardless of what's still in the search cache."""
    path = OUTPUT_DIR / (tab_name.lower().replace(" ", "_") + ".csv")
    if not path.exists():
        return set()
    with path.open(newline="") as f:
        return {result_key(row) for row in csv.DictReader(f)}


def append_results(rows: list[dict], tab_name: str) -> None:
    if not rows:
        return
    filename = tab_name.lower().replace(" ", "_") + ".csv"
    timestamp = _utc_now_iso()
    payload = [[timestamp] + [row[h] for h in RESULT_HEADERS[1:]] for row in rows]
    _append_rows(OUTPUT_DIR / filename, RESULT_HEADERS, payload)


def append_log(status: str, message: str, total_results: int, total_deals: int) -> None:
    _append_rows(
        OUTPUT_DIR / "log.csv",
        LOG_HEADERS,
        [[_utc_now_iso(), status, message, total_results, total_deals]],
    )
