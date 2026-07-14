"""Tests src/sheets.py against a fake in-memory sheet, never a real Google API."""
import re

import gspread
import pytest
from gspread.utils import rowcol_to_a1

from src import sheets


class FakeWorksheet:
    def __init__(self):
        self.rows: list[list[str]] = []
        self.formatted_ranges: list[tuple] = []  # (ranges, format_dict) pairs applied

    def row_values(self, n):
        return self.rows[0] if self.rows else []

    def update(self, range_name=None, values=None):
        if self.rows:
            self.rows[0] = list(values[0])
        else:
            self.rows = [list(values[0])]

    def append_rows(self, payload, value_input_option="USER_ENTERED"):
        start_row = len(self.rows) + 1
        for row in payload:
            self.rows.append([str(v) for v in row])
        end_row = len(self.rows)
        num_cols = max((len(r) for r in payload), default=0)
        end_col_letter = re.match(r"[A-Z]+", rowcol_to_a1(1, num_cols)).group() if num_cols else "A"
        return {"updates": {"updatedRange": f"Sheet1!A{start_row}:{end_col_letter}{end_row}"}}

    def format(self, ranges, format):
        self.formatted_ranges.append((list(ranges) if not isinstance(ranges, str) else [ranges], format))

    def get_all_values(self):
        return self.rows

    def clear(self):
        self.rows = []
        self.formatted_ranges = []


class FakeSheet:
    def __init__(self):
        self._tabs: dict[str, FakeWorksheet] = {}

    def worksheet(self, name):
        if name not in self._tabs:
            raise gspread.exceptions.WorksheetNotFound(name)
        return self._tabs[name]

    def ensure(self, name):
        return self._tabs.setdefault(name, FakeWorksheet())


@pytest.fixture
def fake_sheet(monkeypatch):
    sheet = FakeSheet()
    monkeypatch.setattr(sheets, "_open_sheet", lambda: sheet)
    return sheet


def test_existing_keys_empty_when_tab_missing(fake_sheet):
    assert sheets.existing_keys("Results") == set()


def test_reset_results_clears_both_existing_tabs(fake_sheet, sample_row):
    results_ws = fake_sheet.ensure("Results")
    deals_ws = fake_sheet.ensure("Best Deals")
    sheets.append_results([sample_row], tab_name="Results")
    sheets.append_results([sample_row], tab_name="Best Deals")
    assert results_ws.rows and deals_ws.rows

    sheets.reset_results()

    assert results_ws.rows == []
    assert deals_ws.rows == []


def test_reset_results_is_a_noop_when_tabs_dont_exist(fake_sheet):
    sheets.reset_results()  # must not raise, even though neither tab was created
    assert fake_sheet._tabs == {}


def test_append_then_existing_keys_recognizes_it(fake_sheet, sample_row):
    fake_sheet.ensure("Results")  # tabs must pre-exist in the real Sheet; gspread won't create them
    sheets.append_results([sample_row], tab_name="Results")
    assert sheets.result_key(sample_row) in sheets.existing_keys("Results")


def test_header_written_once(fake_sheet, sample_row):
    fake_sheet.ensure("Results")
    sheets.append_results([sample_row], tab_name="Results")
    sheets.append_results([{**sample_row, "price_usd": 999.0}], tab_name="Results")

    worksheet = fake_sheet.ensure("Results")
    assert worksheet.rows[0] == sheets.RESULT_HEADERS
    assert len(worksheet.rows) == 3  # header + 2 data rows


def test_existing_keys_matches_regardless_of_trailing_zero_formatting(fake_sheet, sample_row):
    """Regression: gspread's raw get_all_values() can come back with a price
    like "334" (no decimal) even though we wrote 334.0 — result_key() must
    still match it."""
    worksheet = fake_sheet.ensure("Results")
    worksheet.rows = [
        sheets.RESULT_HEADERS,
        ["2026-07-12T00:00:00+00:00", "JFK", "LAX", "2026-08-10", "2470.0", "334", "13.53",
         "1", "507", "American Airlines", "AA475 > AA2827", "06:30", "11:57", "https://example.com"],
    ]
    assert sheets.result_key(sample_row) in sheets.existing_keys("Results")


def test_append_log_writes_header_and_row(fake_sheet):
    fake_sheet.ensure("Log")
    sheets.append_log("OK", "All searches completed", 5, 2)
    worksheet = fake_sheet.ensure("Log")
    assert worksheet.rows[0] == sheets.LOG_HEADERS
    assert worksheet.rows[1][1:] == ["OK", "All searches completed", "5", "2"]


def test_single_carrier_row_gets_highlighted(fake_sheet, sample_row):
    worksheet = fake_sheet.ensure("Results")
    assert sample_row["single_carrier"] is True
    sheets.append_results([sample_row], tab_name="Results")

    assert len(worksheet.formatted_ranges) == 1
    ranges, fmt = worksheet.formatted_ranges[0]
    assert ranges == ["A2:Q2"]  # header is row 1, so the data row lands on row 2
    assert fmt == {"backgroundColor": sheets._PREFERRED_ROW_COLOR}


def test_non_single_carrier_row_is_not_highlighted(fake_sheet, sample_row):
    worksheet = fake_sheet.ensure("Results")
    mixed_carrier_row = {**sample_row, "single_carrier": False}
    sheets.append_results([mixed_carrier_row], tab_name="Results")
    assert worksheet.formatted_ranges == []


def test_only_single_carrier_rows_highlighted_within_a_mixed_batch(fake_sheet, sample_row):
    worksheet = fake_sheet.ensure("Results")
    rows = [
        {**sample_row, "single_carrier": True},
        {**sample_row, "single_carrier": False},
        {**sample_row, "single_carrier": True},
    ]
    sheets.append_results(rows, tab_name="Results")

    assert len(worksheet.formatted_ranges) == 1
    ranges, _ = worksheet.formatted_ranges[0]
    # header=row1, so the 3 data rows land on 2,3,4 -- only rows 2 and 4 (True) get highlighted
    assert ranges == ["A2:Q2", "A4:Q4"]


def test_second_append_highlights_at_the_correct_row_offset(fake_sheet, sample_row):
    """Regression: row numbers must account for rows already in the sheet
    from a prior append, not just the current batch."""
    worksheet = fake_sheet.ensure("Results")
    sheets.append_results([{**sample_row, "single_carrier": False}], tab_name="Results")
    sheets.append_results([{**sample_row, "price_usd": 999.0, "single_carrier": True}], tab_name="Results")

    assert len(worksheet.formatted_ranges) == 1
    ranges, _ = worksheet.formatted_ranges[0]
    assert ranges == ["A3:Q3"]  # header(1) + first append(2) -> second append lands on row 3
