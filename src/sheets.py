"""Reads from and writes to the Google Sheet."""
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

from src.config import SERVICE_ACCOUNT_FILE, SHEET_ID

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
    "depart_time",
    "arrive_time",
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
