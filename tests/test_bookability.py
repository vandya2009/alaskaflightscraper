from src.bookability import is_likely_bookable


def test_single_carrier_row_is_bookable(sample_row):
    assert is_likely_bookable(sample_row, known_unbookable=set()) == True


def test_mixed_carrier_row_is_not_bookable(sample_row):
    row = {**sample_row, "single_carrier": False}
    assert is_likely_bookable(row, known_unbookable=set()) == False


def test_blocklist_overrides_single_carrier_true():
    row = {
        "single_carrier": True,
        "last_leg_airline": "JL",
        "destination": "KUL",
    }
    assert is_likely_bookable(row, known_unbookable={"JL:KUL"}) == False


def test_blocklist_entry_for_different_destination_does_not_match():
    row = {
        "single_carrier": True,
        "last_leg_airline": "JL",
        "destination": "NRT",
    }
    assert is_likely_bookable(row, known_unbookable={"JL:KUL"}) == True
