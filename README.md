# Alaska Flight Scraper

Searches Google Flights for one-way itineraries that are bookable directly on
alaskaair.com — Alaska Airlines, its Oneworld partners, and its "Earn & Redeem"
partners — and logs the ones with good value (low cents-per-mile) to local CSV
files (default) or a Google Sheet (optional).

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
- Writes qualifying results **as they're found** (not buffered to the end of the run):
  - **Results** — anything under `record_threshold_cpm` (default 10.0¢/mi).
  - **Best Deals** — the subset under `deal_threshold_cpm` (default 6.0¢/mi).
  - **Log** — one row per run: timestamp, status (`OK`/`PARTIAL`), a summary,
    and result/deal counts.
  Controlled by `output_backend` in `settings.yaml`: `csv` (default, writes to
  `output/*.csv`, no setup needed) or `sheets` (writes to a Google Sheet, needs
  credentials — see Setup below).
- Dedups against whatever's already recorded (on disk or in the Sheet, depending on
  backend) so reruns don't re-log a fare you already know about. Delete the CSV (or
  clear the Sheet tab) to reset and re-record everything from scratch.
- Caches each `(route, date, filters)` search on disk for 60 minutes by default
  (`.cache/flights/`, gitignored) — reruns within that window skip the network call
  and the rate-limit pause entirely. Set `FLIGHT_CACHE=0` to disable, e.g. for a
  scheduled run where you always want live prices.
- Generates two links for each result:
  - `alaskaair.com/search/results` — see the booking-link caveat below, it's
    not a guaranteed match to the recorded price.
  - `google.com/travel/flights` — the same route/date on the actual source
    Google Flights uses, so you can sanity-check `price_usd` against what
    Google itself currently shows, independent of Alaska's own re-pricing.
- Skips routes shorter than `min_distance_miles` (default 1900 mi) before ever
  hitting the network, since this is meant for long-haul award value, not short hops.

## How far along it is

Working and runnable end-to-end for the flow above: prompt (or CLI args) → search →
filter → dedup → write. Commit history (`git log`) shows it's been tuned against real
runs (rate-limit pause adjusted after measuring a 1.5% failure rate at ~640 searches,
thresholds and destination list adjusted iteratively).

What exists:
- Interactive CLI (`python -m src.scrape`) that prompts for origin airport(s) and a
  departure date, or falls back to `config/settings.yaml` defaults — **or**
  non-interactive CLI args (`python -m src.scrape <date> [<airports>]`) for scripting
  or eventual scheduled runs. See Usage below.
- ~100 pre-configured destinations spanning the US, Alaska, Hawaii, Canada, Mexico,
  Central America, Asia, Oceania, Europe, and the Middle East/Africa — trimmed to
  those ≥1900 mi from the configured origins.
- Basic resilience: per-search failures are caught and logged individually rather
  than aborting the whole run; a known `fli` quirk (alternate-airport suggestions it
  can't map to its own enum) is swallowed as "no results" instead of crashing; a crash
  mid-sweep only loses the search in flight, not everything found so far, since writes
  are incremental.

What's not there:
- **No automated scheduling.** No cron job, GitHub Action, or launchd plist yet — you
  run it by hand each time (the CLI args above exist to make that easier to automate
  later).
- **No linter or CI.** There's a `pytest` suite (`tests/`) but nothing runs it
  automatically — no GitHub Action, no pre-commit hook.
- **One-way only.** No round-trip search support.
- **Sequential, not parallel.** Live searches run one at a time with a 2-second pause
  between them (to avoid Google Flights rate-limiting), so a full sweep over 2
  origins × ~100 destinations × 3 dates (~640 searches) takes ~25-30 minutes *when
  nothing is cached*. Cached reruns skip both the network call and the pause, so
  a same-day rerun can finish in well under a minute.
- **Fixed destination list.** Only the origin airport(s) and date are configurable at
  runtime; destinations always come from `config/settings.yaml`.
- **No alerting.** Results land in `output/` (or the Sheet) and a Log row is appended;
  there's no email/Slack/push notification when a good deal is found.
- **Scraper-dependent.** It relies on `fli` scraping Google Flights' internal API,
  which is unofficial and could break if Google changes that surface.

## Booking link caveat

Each row includes an `alaskaair.com/search/results` link, but it's built from just
origin/destination/date/passenger count — no flight number, carrier, or fare class.
Clicking it runs a **brand-new, independent search** on Alaska's own booking engine;
it is not a deep link to the specific itinerary the row records. Two things follow:

1. The price you see live can differ from `price_usd` simply because fares move
   over time between when the row was recorded and when you click it.
2. For itineraries operated by a partner airline (most of what gets recorded, since
   Alaska's own metal is rarely the cheapest option) there's no guarantee Alaska's
   engine can even reconstruct that same routing/fare — interline ticketing coverage
   varies by partner and route. The link can show a completely different flight.

With ~50+ rows per full sweep, hand-checking every link isn't practical. Treat
`results.csv` as a price-discovery signal ("cents-per-mile was this good, on this
route, around this time"), not a guaranteed bookable quote — always re-verify before
booking.

If a result looks off, the `google_flights_url` column isolates *where* the gap
comes from: it's the same source Google Flights query `fli` used to find the fare
in the first place. If that link's live price roughly matches `price_usd`, the
tool's data is accurate and the whole gap is Alaska independently re-pricing the
itinerary (expected, structural, not fixable here). If even *that* doesn't match,
something's actually wrong with the price capture — worth reporting as a bug.

### Could a commercial API do better?

Researched [SerpApi's Google Flights API](https://serpapi.com/google-flights-api) as
an alternative to `fli`:

- **It would fix the scraping-reliability problem** (an unofficial scraper that could
  break any time), since it's a maintained, paid wrapper around the same Google
  Flights data.
- **It might partially fix the booking-link problem.** SerpApi supports a two-step
  flow: search results include a `booking_token`, which you exchange in a second call
  for [`booking_options`](https://serpapi.com/google-flights-booking-options) — real
  vendor-specific booking URLs (or POST data) tied to *that exact itinerary*, sometimes
  pointing straight at the airline's own site. That's a structurally better model than
  hand-building a generic search URL.
- **But it's not a guaranteed fix.** An [open SerpApi GitHub
  issue](https://github.com/serpapi/public-roadmap/issues/3001) (filed Sep 2025,
  unresolved, low-priority "freezer" status) reports the `booking_options` endpoint
  returning *fewer* options than the live Google Flights site shows for the same
  query — so even paying for this wouldn't guarantee Alaska's link reliably appears.
- **Cost is real and scales with usage.** [Pricing](https://serpapi.com/pricing): free
  tier is 250 searches/month — less than half of one full 642-search sweep. Paid tiers:
  $25/mo (1,000 searches), $75/mo (5,000), $150/mo (15,000), $275/mo (30,000). A daily
  full sweep at the current destination count (~642 base searches, plus one extra
  `booking_options` call per qualifying result — currently ~54/run) is roughly
  19,000-21,000 searches/month, i.e. the $275/mo tier. Weekly runs would fit the
  $75/mo tier instead. (Not independently confirmed: whether the Google Flights
  engine consumes credits 1:1 with SerpApi's other engines, or a different rate —
  SerpApi's docs didn't specify this.)

**Bottom line:** worth it only if you're running this often enough to justify a
recurring cost, and only meaningfully improves — not fully solves — the booking-link
problem. For occasional/manual runs, the current free scraping approach is more
cost-effective despite its fragility.

## Setup

1. **Python dependencies**
   ```
   python3 -m venv .venv
   source .venv/bin/activate   # re-run this in every new terminal session
   pip install -r requirements.txt
   ```

2. **Nothing else, if using the default CSV output.** `output_backend: csv` in
   `config/settings.yaml` needs no credentials — results land in `output/*.csv`.

3. **Google Sheet + service account — only if you set `output_backend: sheets`:**
   - Create a Google Cloud service account with Sheets + Drive API access, download
     its JSON key, and place it in `credentials/` (gitignored).
   - Share your target Google Sheet with the service account's email address.
   - Add a `.env` file (gitignored) in the project root:
     ```
     SHEET_ID=your_google_sheet_id
     GOOGLE_APPLICATION_CREDENTIALS=credentials/service_account.json
     ```
   - If `output_backend: sheets` is set but these aren't configured, `src/output.py`
     fails fast at startup with a message telling you what to fix.

4. **`config/settings.yaml`** — tune origins, destinations, date sweep/window, seat
   type, stop limits, cents-per-mile thresholds, and the allowed-airline list. See
   the comments in that file for each option.

## Testing

```
pip install -r requirements-dev.txt
pytest
```

Runs against mocked `fli`/Google Sheets responses and an isolated temp
cache/output dir per test — no network calls, no real credentials needed, and
nothing touches your real `output/`, `.cache/`, or Google Sheet. Run a single
file or test with `pytest tests/test_flights.py` or
`pytest tests/test_flights.py::test_computes_cents_per_mile`.

## Usage

Interactive (prompts for origin airport(s) and a departure date; press Enter at
either to fall back to `settings.yaml`):
```
python -m src.scrape
```

Non-interactive, for scripting or a specific date/route:
```
python -m src.scrape <date> [<airports>]
```
- `<date>` (`YYYY-MM-DD`, required in this mode) — expands to that date ±
  `date_window_days` (default 1, so 3 dates total; configurable in `settings.yaml`).
- `<airports>` (optional, comma-separated, e.g. `JFK,EWR`) — omit it, or pass `""`,
  to use `home_airports` from `settings.yaml`.

Example: `python -m src.scrape 2026-08-01 JFK` searches Jul 31 – Aug 2 from JFK only.

Progress prints to the console as each `(origin, destination, date)` search runs.
Each qualifying result is written immediately (to `output/*.csv` or the Sheet,
per `output_backend`) rather than buffered to the end; a summary row is appended
to the Log at the very end.
