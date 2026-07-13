"""Main entry point for the flight scraper.

Run from the project folder with either:
    python -m src.scrape
    python -m src.scrape <date> [<airports>]

With no arguments, you're prompted interactively for departure airport(s) and
a departure date; press Enter at either prompt to fall back to settings.yaml.

With a <date> argument (YYYY-MM-DD), the prompts are skipped: results are
swept for that date +/- `date_window_days` (see settings.yaml). <airports> is
optional and comma-separated (e.g. JFK,EWR); omit it, or pass "", to use
settings.yaml's home_airports.

Only itineraries flown entirely by `allowed_airlines` are returned by the
search. Of those, only results with cents_per_mile < `record_threshold_cpm`
qualify, and are then split by `is_likely_bookable` (see src/bookability.py):
likely-bookable ones go to the Results tab (and, if below `deal_threshold_cpm`,
also to Best Deals); the rest go to Wrong Carrier instead, since we've
confirmed by hand that mixed-carrier itineraries -- and even some
single-carrier ones on settings.yaml's `known_unbookable` blocklist -- come
back with zero equivalent option on Alaska's own booking engine.
"""
import sys
import time
from datetime import date, timedelta

import airportsdata
from fli.models import Airport

from src.bookability import is_likely_bookable
from src.config import SETTINGS
from src.flights import search_one_way, was_cached
from src.routes import planned_searches
from src.output import append_log, append_results, existing_keys, reset_results
from src.dedup import result_key

_AIRPORTS = airportsdata.load("IATA")


PROMPT_WINDOW_DAYS = int(SETTINGS.get("date_window_days", 1))  # see settings.yaml


class _InvalidInput(Exception):
    """Raised by the shared validators below; callers decide how to surface it."""


def _validate_airports(raw: str) -> list[str]:
    codes = [c.strip().upper() for c in raw.split(",") if c.strip()]
    invalid = [c for c in codes if c not in Airport.__members__ or c not in _AIRPORTS]
    if invalid:
        raise _InvalidInput(f"Unknown airport code(s): {invalid}.")
    return codes


def _validate_date_window(raw: str) -> list[str]:
    """Validate a date and expand it to a window: the date +/- PROMPT_WINDOW_DAYS,
    clamped to >= tomorrow."""
    tomorrow = date.today() + timedelta(days=1)
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        raise _InvalidInput(f"'{raw}' is not a valid YYYY-MM-DD date.")
    if d < tomorrow:
        raise _InvalidInput(f"Date must be on or after {tomorrow.isoformat()}.")
    window = [
        d + timedelta(days=offset)
        for offset in range(-PROMPT_WINDOW_DAYS, PROMPT_WINDOW_DAYS + 1)
    ]
    return [day.isoformat() for day in window if day >= tomorrow]


def _prompt_for_origins() -> list[str] | None:
    """Ask for one or more origin airports. Returns None to use settings.yaml."""
    default = [o.upper() for o in SETTINGS["home_airports"]]
    prompt = (
        f"Departure airport(s) — comma-separated IATA codes (e.g. JFK, JFK,EWR),\n"
        f"  or press Enter to use settings.yaml default {default}: "
    )
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            return None
        if not raw:
            return None
        try:
            return _validate_airports(raw)
        except _InvalidInput as e:
            print(f"  {e} Try again.\n")


def _prompt_for_date() -> list[str] | None:
    """Ask for a target departure date. Returns None for sweep mode."""
    tomorrow = date.today() + timedelta(days=1)
    prompt = (
        f"Departure date (YYYY-MM-DD, must be on or after {tomorrow.isoformat()}).\n"
        f"  Searches that date +/- {PROMPT_WINDOW_DAYS} days. "
        f"Press Enter to use settings.yaml instead: "
    )
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            return None
        if not raw:
            return None
        try:
            return _validate_date_window(raw)
        except _InvalidInput as e:
            print(f"  {e} Try again.\n")


def main() -> None:
    # Each run reflects only its own findings, not an accumulating history
    # across runs -- results.csv/best_deals.csv (or the Sheet tabs) are reset here.
    reset_results()

    if len(sys.argv) > 1:
        date_arg = sys.argv[1]
        airports_arg = sys.argv[2] if len(sys.argv) > 2 else ""
        try:
            dates_override = _validate_date_window(date_arg) if date_arg else None
            origins_override = _validate_airports(airports_arg) if airports_arg else None
        except _InvalidInput as e:
            sys.exit(str(e))
    else:
        origins_override = _prompt_for_origins()
        dates_override = _prompt_for_date()

    if origins_override:
        print(f"\nOrigins: {origins_override}", flush=True)
    else:
        print(f"\nOrigins: {SETTINGS['home_airports']} (from settings.yaml)", flush=True)

    if dates_override:
        print(
            f"Dates: {len(dates_override)} dates "
            f"({dates_override[0]} -> {dates_override[-1]})\n",
            flush=True,
        )
    else:
        print("Dates: sweep from settings.yaml\n", flush=True)

    record_cpm = float(SETTINGS["record_threshold_cpm"])
    deal_cpm = float(SETTINGS["deal_threshold_cpm"])
    top_n = int(SETTINGS.get("top_n_per_search", 1))
    adults = int(SETTINGS.get("adults", 1))
    seat_type = str(SETTINGS.get("seat_type", "ECONOMY"))
    max_stops = str(SETTINGS.get("max_stops", "ANY"))
    exclude_basic_economy = bool(SETTINGS.get("exclude_basic_economy", True))
    allowed_airlines = {a.upper() for a in SETTINGS["allowed_airlines"]}
    known_unbookable = {str(k).upper() for k in SETTINGS.get("known_unbookable", [])}

    total_results = 0
    total_deals = 0
    total_wrong_carrier = 0
    errors: list[str] = []
    # reset_results() above means this is always empty at this point -- kept as
    # a within-run safety net in case the exact same (route, date, price) ever
    # turns up twice in one sweep, rather than assuming that can't happen.
    seen_results = existing_keys("Results")

    plans = list(
        planned_searches(
            dates_override=dates_override,
            origins_override=origins_override,
        )
    )
    print(f"Running {len(plans)} flight searches...", flush=True)

    for i, plan in enumerate(plans, start=1):
        label = (
            f"{plan['origin']} -> {plan['destination']} on {plan['depart_date']} "
            f"({plan['distance_miles']:.0f} mi)"
        )
        print(f"  [{i}/{len(plans)}] {label}", flush=True)
        try:
            try:
                rows = search_one_way(
                    origin=plan["origin"],
                    destination=plan["destination"],
                    depart_date=plan["depart_date"],
                    distance_miles=plan["distance_miles"],
                    allowed_airlines=allowed_airlines,
                    adults=adults,
                    seat_type=seat_type,
                    max_stops=max_stops,
                    top_n=top_n,
                    exclude_basic_economy=exclude_basic_economy,
                )
            except Exception as e:
                print(f"      Failed: {e}", flush=True)
                errors.append(f"{label}: {e}")
                continue

            if not rows:
                print("      No qualifying flights.", flush=True)
                continue

            kept = [r for r in rows if r["cents_per_mile"] < record_cpm]
            if not kept:
                cheapest_cpm = min(r["cents_per_mile"] for r in rows)
                print(f"      Above threshold (cheapest {cheapest_cpm:.1f}¢/mi).", flush=True)
                continue

            new_kept = [r for r in kept if result_key(r) not in seen_results]
            if not new_kept:
                print("      Already recorded (no new fares).", flush=True)
                continue
            seen_results.update(result_key(r) for r in new_kept)

            bookable = [r for r in new_kept if is_likely_bookable(r, known_unbookable)]
            wrong_carrier = [r for r in new_kept if not is_likely_bookable(r, known_unbookable)]

            if bookable:
                best = min(bookable, key=lambda r: r["cents_per_mile"])
                print(
                    f"      Recording {len(bookable)}: best ${best['price_usd']:.0f} "
                    f"@ {best['cents_per_mile']:.1f}¢/mi on {best['airline']}",
                    flush=True,
                )
                append_results(bookable, tab_name="Results")
                total_results += len(bookable)

                deals = [r for r in bookable if r["cents_per_mile"] < deal_cpm]
                if deals:
                    append_results(deals, tab_name="Best Deals")
                    total_deals += len(deals)

            if wrong_carrier:
                print(f"      +{len(wrong_carrier)} screened to Wrong Carrier.", flush=True)
                append_results(wrong_carrier, tab_name="Wrong Carrier")
                total_wrong_carrier += len(wrong_carrier)
        finally:
            # Pause after every LIVE search to avoid Google Flights rate-limiting
            # (HTTP 429). 1.5s was too aggressive at ~640 plans (10/642 = 1.5%
            # failure rate). Skipped for cache hits since no request was made.
            if not was_cached():
                time.sleep(2.0)

    print(
        f"\n{total_results} results ({total_deals} below {deal_cpm}¢/mi), "
        f"{total_wrong_carrier} screened to Wrong Carrier, "
        f"written incrementally to output/ as they were found.",
        flush=True,
    )

    status = "OK" if not errors else "PARTIAL"
    summary = "All searches completed" if not errors else "; ".join(errors)
    append_log(status, summary[:500], total_results, total_deals)
    print(f"Done. Status: {status}.", flush=True)


if __name__ == "__main__":
    main()
