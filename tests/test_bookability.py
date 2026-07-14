from src.bookability import is_likely_bookable


def test_alaska_own_metal_is_always_bookable():
    row = {"single_carrier": True, "last_leg_airline": "AS", "destination": "ANYWHERE"}
    assert is_likely_bookable(row, known_bookable=set()) == True


def test_mixed_carrier_ending_on_as_is_not_bookable():
    """Regression: `AA1029 > AA693 > AS1062` and `AA2917 > AA2852 > AS660`
    both landed in Results during a real scrape because only last_leg_airline
    was checked -- Alaska still has to interline the earlier AA leg here, so
    this must NOT get the Alaska's-own-metal exception."""
    row = {"single_carrier": False, "last_leg_airline": "AS", "destination": "ITO"}
    assert is_likely_bookable(row, known_bookable=set()) == False


def test_unlisted_partner_carrier_is_not_bookable(sample_row):
    assert is_likely_bookable(sample_row, known_bookable=set()) == False


def test_allowlisted_partner_pair_is_bookable():
    row = {"single_carrier": True, "last_leg_airline": "QR", "destination": "DOH"}
    assert is_likely_bookable(row, known_bookable={"QR:DOH"}) == True


def test_allowlist_entry_for_different_destination_does_not_match():
    row = {"single_carrier": True, "last_leg_airline": "QR", "destination": "MCT"}
    assert is_likely_bookable(row, known_bookable={"QR:DOH"}) == False


def test_allowlist_entry_for_different_airline_does_not_match():
    row = {"single_carrier": True, "last_leg_airline": "CX", "destination": "DOH"}
    assert is_likely_bookable(row, known_bookable={"QR:DOH"}) == False
