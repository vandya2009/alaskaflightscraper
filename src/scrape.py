"""Main entry point for the flight scraper.

Run from the project folder with:
    python -m src.scrape
"""
import time

from src.config import SETTINGS
from src.flights import search_one_way
from src.routes import planned_searches
from src.sheets import append_log, append_results


def main() -> None:
    threshold = SETTINGS.get("deal_threshold_usd")
    top_n = int(SETTINGS.get("top_n_per_search", 1))
    adults = int(SETTINGS.get("adults", 1))
    seat_type = str(SETTINGS.get("seat_type", "ECONOMY"))
    max_stops = str(SETTINGS.get("max_stops", "ANY"))

    all_rows: list[dict] = []
    deal_rows: list[dict] = []
    errors: list[str] = []

    plans = list(planned_searches())
    print(f"Running {len(plans)} flight searches...", flush=True)

    for i, plan in enumerate(plans, start=1):
        label = f"{plan['origin']} -> {plan['destination']} on {plan['depart_date']}"
        print(f"  [{i}/{len(plans)}] {label}", flush=True)
        try:
            rows = search_one_way(
                origin=plan["origin"],
                destination=plan["destination"],
                depart_date=plan["depart_date"],
                adults=adults,
                seat_type=seat_type,
                max_stops=max_stops,
                top_n=top_n,
            )
        except Exception as e:
            print(f"      Failed: {e}", flush=True)
            errors.append(f"{label}: {e}")
            continue

        if not rows:
            print("      No flights found.", flush=True)
            continue

        cheapest = min(r["price_usd"] for r in rows)
        print(f"      Cheapest: ${cheapest:.0f}", flush=True)

        all_rows.extend(rows)
        if threshold is not None:
            deal_rows.extend(r for r in rows if r["price_usd"] <= float(threshold))

        # Be polite. Small pause between searches.
        time.sleep(1)

    print(
        f"\nWriting {len(all_rows)} results "
        f"({len(deal_rows)} below ${threshold}) to Google Sheets...",
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
