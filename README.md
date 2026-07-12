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
- Generates an `alaskaair.com/search/results` link for each result (see the
  booking-link caveat below — it's not a guaranteed match).
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
