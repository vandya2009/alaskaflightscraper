"""Shared dedup-key logic, used by both output backends (csv_output, sheets)."""


def result_key(row: dict) -> tuple:
    """Identifies a specific fare, so reruns don't re-record the same one.

    price_usd is normalized to a fixed 2-decimal string rather than str()'d
    directly: CSV round-trips it as "300.0", but Google Sheets can round-trip
    the same value as "300" (trailing .0 stripped by its own formatting) —
    without normalizing, identical fares would fail to match across backends.
    """
    return (
        row["origin"],
        row["destination"],
        row["depart_date"],
        f"{float(row['price_usd']):.2f}",
        row["flight_numbers"],
    )
