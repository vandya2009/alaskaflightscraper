"""Main entry point for the flight scraper.

Run from the project folder with:
    python -m src.scrape

You'll be prompted for departure airport(s) and a departure date.
Press Enter at either prompt to fall back to the values in settings.yaml.

Only itineraries flown entirely by `allowed_airlines` are returned by the
search. Of those, only results with cents_per_mile < `record_threshold_cpm`
are written to the Results tab; results below `deal_threshold_cpm` are also
written to the Best Deals tab.
"""
import sys
import time
from datetime import date, timedelta

import airportsdata
from fli.models import Airport

from src.config import SETTINGS
from src.flights import search_one_way
from src.routes import planned_searches
from src.sheets import append_log, append_results

_AIRPORTS = airportsdata.load("IATA")


PROMPT_WINDOW_DAYS = 1  # +/- N days around the entered date


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
        codes = [c.strip().upper() for c in raw.split(",") if c.strip()]
        invalid = [
            c for c in codes
            if c not in Airport.__members__ or c not in _AIRPORTS
        ]
        if invalid:
            print(f"  Unknown airport code(s): {invalid}. Try again.\n")
            continue
        return codes


def _prompt_for_date() -> list[str] | None:
    """Ask for a target departure date. Returns None for sweep mode.

    A valid input expands to a 9-date window: the entered date plus
    `PROMPT_WINDOW_DAYS` days before and after, clamped to >= tomorrow.
    """
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
            d = date.fromisoformat(raw)
        except ValueError:
            print(f"  '{raw}' is not a valid YYYY-MM-DD date. Try again.\n")
            continue
        if d < tomorrow:
            print(f"  Date must be on or after {tomorrow.isoformat()}. Try again.\n")
            continue
        window = [
            d + timedelta(days=offset)
            for offset in range(-PROMPT_WINDOW_DAYS, PROMPT_WINDOW_DAYS + 1)
        ]
        return [day.isoformat() for day in window if day >= tomorrow]


def main() -> None:
    origins_override = _prompt_for_origins()
    if origins_override:
        print(f"\nOrigins: {origins_override}", flush=True)
    else:
        print(f"\nOrigins: {SETTINGS['home_airports']} (from settings.yaml)", flush=True)

    dates_override = _prompt_for_date()
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

    all_rows: list[dict] = []
    deal_rows: list[dict] = []
    errors: list[str] = []

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

        best = min(kept, key=lambda r: r["cents_per_mile"])
        print(
            f"      Recording {len(kept)}: best ${best['price_usd']:.0f} "
            f"@ {best['cents_per_mile']:.1f}¢/mi on {best['airline']}",
            flush=True,
        )
        all_rows.extend(kept)
        deal_rows.extend(r for r in kept if r["cents_per_mile"] < deal_cpm)

        # Pause between searches to avoid Google Flights rate-limiting (HTTP 429).
        # 1.5s was too aggressive at ~640 plans (10/642 = 1.5% failure rate).
        time.sleep(2.0)

    print(
        f"\nWriting {len(all_rows)} results "
        f"({len(deal_rows)} below {deal_cpm}¢/mi) to Google Sheets...",
        flush=True,
    )

    if all_rows:
        append_results(all_rows, tab_name="Results")
    if deal_rows:
        append_results(deal_rows, tab_name="Best Deals")

    status = "OK" if not errors else "PARTIAL"
    summary = "All searches completed" if not errors else "; ".join(errors)
    append_log(status, summary[:500], len(all_rows), len(deal_rows))
    print(f"Done. Status: {status}.", flush=True)


if __name__ == "__main__":
    main()
