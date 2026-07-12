"""Reads from and writes to the Google Sheet."""
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

from src.config import SERVICE_ACCOUNT_FILE, SHEET_ID
from src.dedup import result_key

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

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
    "single_carrier",
    "depart_time",
    "arrive_time",
    "alaska_booking_url",
    "google_flights_url",
]
LOG_HEADERS = ["timestamp_utc", "status", "message", "total_results", "total_deals"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _open_sheet():
    creds = Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE), scopes=_SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)


def _ensure_headers(worksheet, headers: list[str]) -> None:
    first_row = worksheet.row_values(1)
    if first_row != headers:
        worksheet.update(range_name="A1", values=[headers])


def existing_keys(tab_name: str) -> set[tuple]:
    """Dedup keys already in this tab. Empty if the tab doesn't exist yet.

    Uses get_all_values() (raw strings) rather than get_all_records(), since
    the latter lets gspread infer types — which can round-trip the same price
    as "300" instead of "300.0", silently breaking key matching.
    """
    sheet = _open_sheet()
    try:
        worksheet = sheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        return set()
    values = worksheet.get_all_values()
    if not values:
        return set()
    headers, *data_rows = values
    return {result_key(dict(zip(headers, row))) for row in data_rows}


def append_results(rows: list[dict], tab_name: str) -> None:
    if not rows:
        return
    sheet = _open_sheet()
    worksheet = sheet.worksheet(tab_name)
    _ensure_headers(worksheet, RESULT_HEADERS)
    timestamp = _utc_now_iso()
    payload = [
        [timestamp] + [row[h] for h in RESULT_HEADERS[1:]]
        for row in rows
    ]
    worksheet.append_rows(payload, value_input_option="USER_ENTERED")


def append_log(status: str, message: str, total_results: int, total_deals: int) -> None:
    sheet = _open_sheet()
    worksheet = sheet.worksheet("Log")
    _ensure_headers(worksheet, LOG_HEADERS)
    worksheet.append_rows(
        [[_utc_now_iso(), status, message, total_results, total_deals]],
        value_input_option="USER_ENTERED",
    )
