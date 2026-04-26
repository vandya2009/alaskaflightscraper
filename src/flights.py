"""Searches Google Flights for one (origin, destination, date) at a time.

Filters results down to itineraries flown ENTIRELY by carriers in
`allowed_airlines` (matched on the IATA two-letter code) and computes
cents-per-mile against the supplied great-circle distance.
"""
from fli.models import (
    Airport,
    FlightSearchFilters,
    FlightSegment,
    MaxStops,
    PassengerInfo,
    SeatType,
    SortBy,
    TripType,
)
from fli.search import SearchFlights

_SEARCH_CLIENT = SearchFlights()

_SEAT_TYPE_MAP = {
    "ECONOMY": SeatType.ECONOMY,
    "PREMIUM_ECONOMY": SeatType.PREMIUM_ECONOMY,
    "BUSINESS": SeatType.BUSINESS,
    "FIRST": SeatType.FIRST,
}
_MAX_STOPS_MAP = {
    "ANY": MaxStops.ANY,
    "NON_STOP": MaxStops.NON_STOP,
    "ONE_STOP_OR_FEWER": MaxStops.ONE_STOP_OR_FEWER,
    "TWO_OR_FEWER_STOPS": MaxStops.TWO_OR_FEWER_STOPS,
}


def _airport(code: str) -> Airport:
    code = code.strip().upper()
    try:
        return Airport[code]
    except KeyError as e:
        raise ValueError(
            f"Unknown airport code '{code}'. Use 3-letter IATA codes (e.g. SEA, JFK)."
        ) from e


def _all_legs_allowed(itinerary, allowed: set[str]) -> bool:
    return all(leg.airline.name in allowed for leg in itinerary.legs)


def search_one_way(
    origin: str,
    destination: str,
    depart_date: str,
    distance_miles: float,
    allowed_airlines: set[str],
    adults: int = 1,
    seat_type: str = "ECONOMY",
    max_stops: str = "ANY",
    top_n: int = 1,
) -> list[dict]:
    """Return up to `top_n` cheapest qualifying one-way itineraries.

    "Qualifying" = every leg is operated by a carrier in `allowed_airlines`.
    """
    filters = FlightSearchFilters(
        trip_type=TripType.ONE_WAY,
        passenger_info=PassengerInfo(adults=adults),
        seat_type=_SEAT_TYPE_MAP[seat_type.upper()],
        stops=_MAX_STOPS_MAP[max_stops.upper()],
        sort_by=SortBy.CHEAPEST,
        flight_segments=[
            FlightSegment(
                departure_airport=[[_airport(origin), 0]],
                arrival_airport=[[_airport(destination), 0]],
                travel_date=depart_date,
            )
        ],
    )

    try:
        results = _SEARCH_CLIENT.search(filters) or []
    except Exception as e:
        # The fli library occasionally returns alternate-airport suggestions
        # (e.g. "type object 'Airport' has no attribute 'XRL'") that it
        # cannot map back to its own enum. Treat as "no results" instead of
        # a hard failure so the run status stays OK.
        if "has no attribute" in str(e):
            return []
        raise

    qualifying = [r for r in results if _all_legs_allowed(r, allowed_airlines)]

    rows: list[dict] = []
    for r in qualifying[:top_n]:
        first_leg = r.legs[0]
        last_leg = r.legs[-1]
        price = float(r.price)
        cpm = (price * 100.0) / distance_miles if distance_miles > 0 else 0.0
        rows.append(
            {
                "origin": origin.upper(),
                "destination": destination.upper(),
                "depart_date": depart_date,
                "distance_miles": round(distance_miles, 1),
                "price_usd": price,
                "cents_per_mile": round(cpm, 2),
                "stops": int(r.stops),
                "duration_minutes": int(r.duration),
                "airline": first_leg.airline.value,
                "flight_numbers": " > ".join(
                    f"{leg.airline.name}{leg.flight_number}" for leg in r.legs
                ),
                "depart_time": first_leg.departure_datetime.strftime("%H:%M"),
                "arrive_time": last_leg.arrival_datetime.strftime("%H:%M"),
            }
        )
    return rows
