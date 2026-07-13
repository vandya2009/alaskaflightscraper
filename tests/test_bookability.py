from src.bookability import is_likely_bookable


def test_alaska_own_metal_is_always_bookable():
    row = {"last_leg_airline": "AS", "destination": "ANYWHERE"}
    assert is_likely_bookable(row, known_bookable=set()) == True


def test_unlisted_partner_carrier_is_not_bookable(sample_row):
    assert is_likely_bookable(sample_row, known_bookable=set()) == False


def test_allowlisted_partner_pair_is_bookable():
    row = {"last_leg_airline": "QR", "destination": "DOH"}
    assert is_likely_bookable(row, known_bookable={"QR:DOH"}) == True


def test_allowlist_entry_for_different_destination_does_not_match():
    row = {"last_leg_airline": "QR", "destination": "MCT"}
    assert is_likely_bookable(row, known_bookable={"QR:DOH"}) == False


def test_allowlist_entry_for_different_airline_does_not_match():
    row = {"last_leg_airline": "CX", "destination": "DOH"}
    assert is_likely_bookable(row, known_bookable={"QR:DOH"}) == False
