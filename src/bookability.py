"""Splits qualifying itineraries into likely-bookable-on-Alaska vs. not.

Neither layer below is proof of bookability either way -- see README's
booking-link caveat. This just triages by the best signal available today.
"""


def is_likely_bookable(row: dict, known_unbookable: set[str]) -> bool:
    """True if `row` should stay in Results; False if it belongs in Wrong Carrier.

    Two layers, most-confident first:
    1. `known_unbookable` ("AIRLINE:DESTINATION" pairs, last operating leg +
       destination) is a small hand-curated blocklist of itineraries manually
       confirmed on alaskaair.com to have zero equivalent -- this overrides
       single_carrier, since the JFK-KUL case proved single_carrier: True
       alone doesn't guarantee a match.
    2. Otherwise, fall back to single_carrier: itineraries split across
       different airlines are unverified and go to Wrong Carrier; single-
       carrier itineraries are the best remaining signal and stay in Results.
    """
    key = f"{row['last_leg_airline']}:{row['destination']}"
    if key in known_unbookable:
        return False
    return bool(row["single_carrier"])
