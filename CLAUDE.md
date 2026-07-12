# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A scraper that searches Google Flights (via the `fli` library) for cheap award-equivalent
itineraries bookable through Alaska Airlines' Oneworld + partner network, and logs qualifying
results to a Google Sheet.

## Commands

Interactive (prompts for origin airport(s) and a departure date; Enter accepts the
`config/settings.yaml` defaults):
```
python -m src.scrape
```

Non-interactive (for scripting/scheduling — skips both prompts):
```
python -m src.scrape <date> [<airports>]
```

Run tests (`pip install -r requirements-dev.txt` first):
```
pytest
```
Run a single test file or test: `pytest tests/test_flights.py` or
`pytest tests/test_flights.py::test_computes_cents_per_mile`.

No linter or build step exists in this repo.

## Setup / secrets

- Default output needs no secrets at all: `output_backend: csv` in
  `config/settings.yaml` writes to `output/*.csv` (gitignored).
- `output_backend: sheets` instead requires `.env` (gitignored) defining `SHEET_ID`
  and `GOOGLE_APPLICATION_CREDENTIALS` (a path, relative to the project root, to a
  Google service-account JSON key), plus that key file in `credentials/` (gitignored).
  `src/output.py` fails fast with a descriptive error at import time if `sheets` is
  selected but either is missing — that's the first place to look when setup issues
  occur with Sheets mode.

## Architecture

Pipeline, one module per stage, wired together in `src/scrape.py`:

1. **`src/config.py`** — loads `.env` and `config/settings.yaml` into `SETTINGS` at import
   time. Every other module reads config through this, never the YAML file directly.
   `SHEET_ID`/`SERVICE_ACCOUNT_FILE` are optional here (`None` if unset) — only
   `src/output.py` enforces them, and only when `output_backend: sheets`.
2. **`src/routes.py`** (`planned_searches`) — expands settings into concrete
   `(origin, destination, depart_date)` search plans. Computes great-circle distance
   (via `airportsdata` + `haversine`) for every pair and drops any route shorter than
   `min_distance_miles` before it ever reaches a network call. Accepts `origins_override`
   and `dates_override` to replace the settings-driven origin list / date sweep with
   values entered at the interactive prompt or passed as CLI args.
3. **`src/cache.py`** — on-disk JSON cache (`.cache/flights/`, gitignored) for search
   results, keyed on every param that affects the query/filtering. 60 min default TTL
   (`FLIGHT_CACHE_TTL_MINUTES`); `FLIGHT_CACHE=0` disables it entirely (e.g. for a
   scheduled run where prices must be live). `src/flights.py` exposes `was_cached()` so
   `scrape.py` can skip the rate-limit pause on a cache hit.
4. **`src/flights.py`** (`search_one_way`) — checks the cache first; on a miss, runs
   one Google Flights query via `fli`, keeps only itineraries where **every leg** is
   operated by a carrier in `allowed_airlines` (an itinerary with even one disallowed
   connecting leg is dropped entirely), computes cents-per-mile against the route's
   precomputed distance, and builds the `alaskaair.com/search/results` link for each
   result (a generic route/date search — not a deep link to that specific itinerary;
   see the booking-link caveat in README.md). A `fli` quirk where unmappable
   alternate-airport suggestions raise `"has no attribute"` is treated as zero results
   rather than a hard failure.
5. **`src/dedup.py`** (`result_key`) — the tuple key (origin, destination, date,
   price, flight numbers) used by both output backends to recognize an
   already-recorded fare. Price is normalized to a fixed 2-decimal string since CSV
   and Sheets round-trip the same float differently (`"300.0"` vs `"300"`).
6. **`src/csv_output.py`** / **`src/sheets.py`** — the two output backends. Both expose
   the same interface: `append_results(rows, tab_name)`, `append_log(...)`,
   `existing_keys(tab_name)` (dedup keys already recorded, read from disk or the Sheet
   — used so deleting the CSV/clearing the Sheet always resets dedup regardless of
   cache state).
7. **`src/output.py`** — picks one of the two backends above based on
   `SETTINGS["output_backend"]` and re-exports its three functions; `scrape.py` always
   imports from here, never from `csv_output`/`sheets` directly.
8. **`src/scrape.py`** (`main`) — parses CLI args or runs the interactive prompts,
   builds the plan list, and for each plan calls `search_one_way`, filters by
   `record_threshold_cpm` (→ `Results`) and `deal_threshold_cpm` (also → `Best Deals`),
   dedups against `existing_keys()` before writing, writes each qualifying result
   immediately (not buffered to the end — a crash mid-sweep only loses the search in
   flight), sleeps 2.0s between *live* searches only (skipped on cache hits) to avoid
   Google Flights rate-limiting, and appends a summary row to the Log at the end.
   Per-search failures are caught and collected rather than aborting the whole run;
   the run ends with status `OK` or `PARTIAL`.

## Config (`config/settings.yaml`)

Central knobs, all consumed through `SETTINGS` in `src/config.py`:

- `output_backend` — `csv` (default) or `sheets`; see Architecture above.
- `home_airports` / `destinations` — every destination is searched from every origin.
- `search_start_days` / `search_window_days` / `search_step_days` — date sweep when no
  date is given at the prompt/CLI arg.
- `date_window_days` — when a specific date *is* given, it's expanded to that date
  +/- this many days (default 1 → 3 dates searched).
- `min_distance_miles` — route-level cutoff applied in `routes.py` (this scraper only
  cares about long-haul award value, not short hops).
- `record_threshold_cpm` / `deal_threshold_cpm` — cents-per-mile cutoffs for the
  `Results` and `Best Deals` outputs, respectively.
- `allowed_airlines` — IATA codes for carriers bookable on alaskaair.com (Oneworld
  members + Alaska "Earn & Redeem" partners). An itinerary qualifies only if **all**
  legs are on this list.
- `top_n_per_search` — cheapest N qualifying itineraries kept per (route, date).
