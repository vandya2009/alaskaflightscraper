from src.dedup import result_key


def test_result_key_stable_for_identical_row(sample_row):
    assert result_key(sample_row) == result_key(dict(sample_row))


def test_result_key_normalizes_float_vs_string_price(sample_row):
    """Regression test: an in-memory float price and a CSV-round-tripped
    string price for the same fare must produce the same key, or dedup
    silently never matches anything (the bug this was built to catch)."""
    as_float = {**sample_row, "price_usd": 334.0}
    as_csv_string = {**sample_row, "price_usd": "334.0"}
    assert result_key(as_float) == result_key(as_csv_string)


def test_result_key_normalizes_trailing_zero_dropped(sample_row):
    """Regression test: Google Sheets can round-trip 334.0 as the bare
    string "334" (trailing .0 stripped) — must still match."""
    as_float = {**sample_row, "price_usd": 334.0}
    as_sheets_string = {**sample_row, "price_usd": "334"}
    assert result_key(as_float) == result_key(as_sheets_string)


def test_result_key_differs_on_price(sample_row):
    cheaper = {**sample_row, "price_usd": 300.0}
    assert result_key(sample_row) != result_key(cheaper)


def test_result_key_differs_on_route_or_date(sample_row):
    other_dest = {**sample_row, "destination": "SEA"}
    other_date = {**sample_row, "depart_date": "2026-08-11"}
    assert result_key(sample_row) != result_key(other_dest)
    assert result_key(sample_row) != result_key(other_date)
