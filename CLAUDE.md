# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A scraper that searches Google Flights (via the `fli` library) for cheap award-equivalent
itineraries bookable through Alaska Airlines' Oneworld + partner network, and logs qualifying
results to a Google Sheet.

## Commands

Run the scraper (prompts for origin airport(s) and a departure date; Enter accepts the
`config/settings.yaml` defaults):

```
python -m src.scrape
```

No test suite, linter, or build step exists in this repo.

## Setup / secrets

- `.env` (gitignored) must define `SHEET_ID` and `GOOGLE_APPLICATION_CREDENTIALS`
  (a path, relative to the project root, to a Google service-account JSON key).
- `credentials/` (gitignored) holds the service account JSON file itself.
- `src/config.py` loads both and fails fast with a descriptive `RuntimeError` if either
  is missing — that's the first place to look when setup issues occur.

## Architecture

Pipeline, one module per stage, wired together in `src/scrape.py`:

1. **`src/config.py`** — loads `.env` and `config/settings.yaml` into `SETTINGS` at import
   time. Every other module reads config through this, never the YAML file directly.
2. **`src/routes.py`** (`planned_searches`) — expands settings into concrete
   `(origin, destination, depart_date)` search plans. Computes great-circle distance
   (via `airportsdata` + `haversine`) for every pair and drops any route shorter than
   `min_distance_miles` before it ever reaches a network call. Accepts `origins_override`
   and `dates_override` to replace the settings-driven origin list / date sweep with
   values entered at the interactive prompt.
3. **`src/flights.py`** (`search_one_way`) — runs one Google Flights query via `fli`,
   keeps only itineraries where **every leg** is operated by a carrier in
   `allowed_airlines` (an itinerary with even one disallowed connecting leg is dropped
   entirely), computes cents-per-mile against the route's precomputed distance, and
   builds the `alaskaair.com` one-way booking deep link for each result. A `fli` quirk
   where unmappable alternate-airport suggestions raise `"has no attribute"` is treated
   as zero results rather than a hard failure.
4. **`src/sheets.py`** — thin gspread wrapper. Opens the sheet by `SHEET_ID`, writes to
   named tabs (`Results`, `Best Deals`, `Log`), and (re)writes the header row if it
   doesn't match the expected schema.
5. **`src/scrape.py`** (`main`) — orchestrates the above: prompts for overrides, builds
   the plan list, and for each plan calls `search_one_way`, filters by
   `record_threshold_cpm` (goes to `Results`) and `deal_threshold_cpm` (also goes to
   `Best Deals`), sleeps 2.0s between searches to avoid Google Flights rate-limiting,
   and appends a summary row to the `Log` tab at the end. Per-search failures are caught
   and collected rather than aborting the whole run; the run ends with status `OK` or
   `PARTIAL`.

## Config (`config/settings.yaml`)

Central knobs, all consumed through `SETTINGS` in `src/config.py`:

- `home_airports` / `destinations` — every destination is searched from every origin.
- `search_start_days` / `search_window_days` / `search_step_days` — date sweep when no
  date is given at the prompt.
- `min_distance_miles` — route-level cutoff applied in `routes.py` (this scraper only
  cares about long-haul award value, not short hops).
- `record_threshold_cpm` / `deal_threshold_cpm` — cents-per-mile cutoffs for the
  `Results` and `Best Deals` tabs, respectively.
- `allowed_airlines` — IATA codes for carriers bookable on alaskaair.com (Oneworld
  members + Alaska "Earn & Redeem" partners). An itinerary qualifies only if **all**
  legs are on this list.
- `top_n_per_search` — cheapest N qualifying itineraries kept per (route, date).
