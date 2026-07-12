# Alaska Flight Scraper

Searches Google Flights for one-way itineraries that are bookable directly on
alaskaair.com — Alaska Airlines, its Oneworld partners, and its "Earn & Redeem"
partners — and logs the ones with good value (low cents-per-mile) to a Google Sheet.

> Note: I couldn't pull the content of the original design artifact this project was
> built from (it's a JS-rendered page that fetches as an empty shell), so this README
> reflects the code as it exists in this repo today, not the original plan.

## What it does

- For every `(origin, destination, departure date)` combination, queries Google
  Flights via the [`fli`](https://pypi.org/project/flights/) library for one-way fares.
- Keeps only itineraries where **every leg** is flown by an airline in
  `allowed_airlines` — Oneworld members plus AS's Earn & Redeem partners (Aer Lingus,
  Icelandair, Korean Air) — since those are the only ones bookable through
  alaskaair.com.
- Computes cents-per-mile (price ÷ great-circle distance) for each result.
- Writes qualifying results to a Google Sheet:
  - **Results** tab — anything under `record_threshold_cpm` (default 10.0¢/mi).
  - **Best Deals** tab — the subset under `deal_threshold_cpm` (default 6.0¢/mi).
  - **Log** tab — one row per run: timestamp, status (`OK`/`PARTIAL`), a summary,
    and result/deal counts.
- Generates a one-click `alaskaair.com/planbook` booking link for each result.
- Skips routes shorter than `min_distance_miles` (default 1900 mi) before ever
  hitting the network, since this is meant for long-haul award value, not short hops.

## How far along it is

Working and runnable end-to-end for the flow above: prompt → search → filter →
write to Sheets. Commit history (`git log`) shows it's been tuned against real runs
(rate-limit pause adjusted after measuring a 1.5% failure rate at ~640 searches,
thresholds and destination list adjusted iteratively).

What exists:
- Interactive CLI (`python -m src.scrape`) that prompts for origin airport(s) and a
  departure date, or falls back to `config/settings.yaml` defaults.
- ~100 pre-configured destinations spanning the US, Alaska, Hawaii, Canada, Mexico,
  Central America, Asia, Oceania, Europe, and the Middle East/Africa — trimmed to
  those ≥1900 mi from the configured origins.
- Basic resilience: per-search failures are caught and logged individually rather
  than aborting the whole run; a known `fli` quirk (alternate-airport suggestions it
  can't map to its own enum) is swallowed as "no results" instead of crashing.

What's not there:
- **No automated scheduling.** No cron job, GitHub Action, or launchd plist — you
  run it by hand each time.
- **No tests, linter, or CI.** There is no test suite in this repo.
- **No dedup.** Every run appends new rows to the Sheet; nothing checks whether a
  route/date/price was already recorded on a previous run.
- **One-way only.** No round-trip search support.
- **Sequential, not parallel.** Searches run one at a time with a 2-second pause
  between them (to avoid Google Flights rate-limiting), so a full sweep over 2
  origins × ~100 destinations × a few dates takes on the order of 20+ minutes.
- **Fixed destination list.** Only the origin airport(s) and date are prompted at
  runtime; destinations always come from `config/settings.yaml`.
- **No alerting.** Results land in the Sheet and a Log row is appended; there's no
  email/Slack/push notification when a good deal is found.
- **Scraper-dependent.** It relies on `fli` scraping Google Flights' internal API,
  which is unofficial and could break if Google changes that surface.

## Setup

1. **Python dependencies**
   ```
   pip install -r requirements.txt
   ```

2. **Google Sheet + service account**
   - Create a Google Cloud service account with Sheets + Drive API access, download
     its JSON key, and place it in `credentials/` (gitignored).
   - Share your target Google Sheet with the service account's email address.

3. **`.env`** (gitignored) in the project root:
   ```
   SHEET_ID=your_google_sheet_id
   GOOGLE_APPLICATION_CREDENTIALS=credentials/service_account.json
   ```
   `src/config.py` fails fast with a descriptive error if either is missing, or if
   the credentials file doesn't exist at that path.

4. **`config/settings.yaml`** — tune origins, destinations, date sweep, seat type,
   stop limits, cents-per-mile thresholds, and the allowed-airline list. See the
   comments in that file for each option.

## Usage

```
python -m src.scrape
```

You'll be prompted for:
- **Departure airport(s)** — comma-separated IATA codes (e.g. `JFK,EWR`). Press
  Enter to use `home_airports` from `settings.yaml`.
- **Departure date** (`YYYY-MM-DD`) — expands to that date ± 1 day (3 dates
  searched). Press Enter to use the date sweep configured in `settings.yaml`
  instead (`search_start_days` / `search_window_days` / `search_step_days`).

Progress prints to the console as each `(origin, destination, date)` search runs.
At the end, results are written to the Sheet and a summary row is appended to the
`Log` tab.
