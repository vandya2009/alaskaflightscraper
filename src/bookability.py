"""Splits qualifying itineraries into likely-bookable-on-Alaska vs. not.

A real spot check of 10 partner itineraries against alaskaair.com (see
README) found single_carrier: True predicts almost nothing on its own --
only 2 matched, 8 were confirmed substitutions onto a different carrier,
including two cases of American's own metal on long-haul international
routes. So the default is now the opposite of the tool's original design:
every partner itinerary is Wrong Carrier unless specifically confirmed.
"""


def is_likely_bookable(row: dict, known_bookable: set[str]) -> bool:
    """True if `row` should stay in Results; False if it belongs in Wrong Carrier.

    1. Alaska Airlines' own metal (last_leg_airline == "AS") is always
       bookable -- selling its own scheduled flight isn't an interline
       dependency, so there's no realistic substitution failure mode here,
       unlike every partner-carrier case below.
    2. Otherwise, only "AIRLINE:DESTINATION" pairs in `known_bookable` --
       partner itineraries manually confirmed on alaskaair.com to actually
       match -- stay in Results. Everything else defaults to Wrong Carrier.
    """
    if row["last_leg_airline"] == "AS":
        return True
    key = f"{row['last_leg_airline']}:{row['destination']}"
    return key in known_bookable
