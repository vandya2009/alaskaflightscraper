# Alaska Flight Scraper

Searches Google Flights for one-way itineraries that are bookable directly on
alaskaair.com — Alaska Airlines, its Oneworld partners, and its "Earn & Redeem"
partners — and logs the ones with good value (low cents-per-mile) to local CSV
files (default) or a Google Sheet (optional).

> Note: I couldn't pull the content of the original design artifact this project was
> built from (it's a JS-rendered page that fetches as an empty shell), so this README
> reflects the code as it exists in this repo today, not the original plan.

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

**Real example hit while using this tool**: a recorded JFK→MEL (Melbourne) row
showed $625 on American Airlines. Alaska's own search for that exact route/date
came back with 11 results — none of them American Airlines. All were Qatar
Airways (via Doha), Qantas (via LAX/SFO), or Cathay Pacific (via Hong Kong),
cheapest at $1,434. So this wasn't Alaska charging more for the same flight —
Alaska's interline coverage doesn't include that specific AA-marketed routing
for this city pair at all, so its engine falls back to pricier alternatives via
other partners.

With ~50+ rows per full sweep, hand-checking every link isn't practical. Treat
`results.csv` as a price-discovery signal ("cents-per-mile was this good, on this
route, around this time"), not a guaranteed bookable quote — always re-verify before
booking.

### Which rows are actually worth checking?

Not all rows carry the same risk of turning out like the JFK-MEL example above.
The `single_carrier` column (True/False) flags whether every leg of the
itinerary is operated by the same airline:

- **`single_carrier: True`** — one airline handles the whole itinerary (a
  nonstop, or a same-carrier connection like `AA475 > AA281`). This rules out
  *one* failure mode (Alaska needing to combine two different partners into one
  interline ticket), but **does not guarantee Alaska sells that carrier to that
  destination at all** — see the JFK-KUL example below, where a pure
  single-carrier Japan Airlines itinerary still had zero equivalent on Alaska's
  site. Lower risk than `False`, not zero risk.
- **`single_carrier: False`** — legs split across different airlines (e.g.
  `AA475 > AA2827 > QF94`: American domestic + Qantas international). This is
  the exact pattern that failed in the JFK-MEL example — Alaska's engine had
  zero equivalent options, not just a different price. Treat these as
  unverified until you actually check them, even though they often show the
  best cents-per-mile numbers (long-haul routes inflate the ratio).

**Second real example**: a JFK→KUL (Kuala Lumpur) row showed $644 on Japan
Airlines (`JL5 > JL723`, both legs JAL — `single_carrier: True`). Alaska's own
search for that route/date came back with 27 results, sorted by stops — all
Qatar Airways (via Doha, cheapest **$1,326**, almost exactly double) or Cathay
Pacific (via Hong Kong, $4,388+, one combined with Malaysia Airlines). Zero
Japan Airlines options at all. So the real driver isn't single- vs.
mixed-carrier — it's whether Alaska's engine has interline coverage loaded for
*that specific carrier to that specific destination*, which varies even for a
single, genuine Oneworld partner like JAL.

This split is now automated by `is_likely_bookable` (`src/bookability.py`):
`single_carrier: False` rows are written to a separate `Wrong Carrier`
tab/file instead of `Results`, and specific confirmed-bad single-carrier
itineraries (like the JFK-KUL JAL case above) are excluded the same way via
the `known_unbookable` blocklist in `settings.yaml`. `Results` still isn't a
bookability guarantee — it's the weaker-but-still-unverified prior — but it no
longer requires manually reading the `single_carrier` column to triage.

**If using `output_backend: sheets`**, rows written to `Results` also get
their background highlighted light green (every row in `Results` is now
`single_carrier: True` by construction, so this is mostly a visual confirmation
rather than a further triage signal). CSV output has no equivalent — plain
text files can't carry cell formatting.

If a result looks off, the `google_flights_url` column isolates *where* the gap
comes from: it's the same source Google Flights query `fli` used to find the fare
in the first place. If that link's live price roughly matches `price_usd`, the
tool's data is accurate and the whole gap is Alaska independently re-pricing the
itinerary (expected, structural, not fixable here). If even *that* doesn't match,
something's actually wrong with the price capture — worth reporting as a bug.

**Confirmed working**: an earlier version of this link defaulted to round trip
(Google Flights silently added its own return date when the query didn't say
"one way"), showing a price roughly double the recorded one-way fare. Fixed by
adding "one way" to the query text — verified against a real result where the
live price then matched `price_usd` exactly ($625).

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

### When should we revisit this?

Don't switch preemptively — `fli` has been reliable in practice (see below). Revisit
the SerpApi-or-similar decision when one of these actually happens, not before:

- **`log.csv` starts showing `PARTIAL` runs regularly**, not as a one-off. One bad run
  can be a transient network blip; a pattern across several runs means `fli` is
  hitting something it can't recover from — check the `message` column and the
  console's `Failed: ...` lines for what's actually erroring.
- **The failure rate climbs well above the historical baseline.** Commit history
  found ~1.5% of searches failing at an overly aggressive 1.5s pause, which is why
  it's 2.0s now. If failures start showing up meaningfully above that *even at the
  current pace*, something changed on Google's end, not just bad luck.
- **A crash outside the two quirks the code already handles** (the "has no
  attribute" alternate-airport exception, and stale cache entries — both now
  covered by regression tests). A new, different exception type surfacing
  repeatedly means Google changed something structurally and `fli` hasn't caught up.
- **`fli` itself goes quiet.** It's a small, community-maintained scraper reverse-
  engineering Google's internal API — check
  [its GitHub repo](https://github.com/punitarani/fli) for recent commits/releases
  if searches start failing. An unmaintained scraper against a moving target
  (Google) only gets more broken over time, not less.
- **Usage pattern actually changes** — e.g. moving to the planned scheduled
  GitHub Action running daily, or widening from a 3-date window to the 60-day
  window discussed earlier. Both multiply request volume, which raises both the
  rate-limit risk *and* the cost-effectiveness case for a paid, stable API (see
  the cost math above — it scales with frequency × destinations × dates).
- **You actually need the booking-link fix**, not just the cents-per-mile signal —
  i.e. if the current "sort by `single_carrier`, then verify manually" workflow
  stops being good enough for how you're using this. SerpApi's `booking_token`
  flow is a real (if imperfect) improvement there; the scraping-reliability
  argument alone isn't, on its own, worth the cost for occasional manual runs.

What to check first, in order: `output/log.csv` status column → console `Failed:`
messages for the actual error → `fli`'s release history for known issues — before
concluding a switch is needed.

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

## What it does

- For every `(origin, destination, departure date)` combination, queries Google
  Flights via the [`fli`](https://pypi.org/project/flights/) library for one-way fares.
- Keeps only itineraries where **every leg** is flown by an airline in
  `allowed_airlines` — Oneworld members plus AS's Earn & Redeem partners (Aer Lingus,
  Icelandair, Korean Air) — since those are the only ones bookable through
  alaskaair.com.
- Computes cents-per-mile (price ÷ great-circle distance) for each result.
- Writes qualifying results **as they're found** (not buffered to the end of the run):
  - **Results** — anything under `record_threshold_cpm` (default 10.0¢/mi) that
    also passes `is_likely_bookable` (see below).
  - **Wrong Carrier** — the itineraries that were under `record_threshold_cpm`
    but did *not* pass `is_likely_bookable` — split out here instead of mixed
    into `Results`, since we've confirmed by hand that these come back with
    zero equivalent option on Alaska's own booking engine.
  - **Best Deals** — the subset of `Results` under `deal_threshold_cpm`
    (default 6.0¢/mi).
  - **Log** — one row per run: timestamp, status (`OK`/`PARTIAL`), a summary,
    and result/deal counts.
  Controlled by `output_backend` in `settings.yaml`: `csv` (default, writes to
  `output/*.csv`, no setup needed) or `sheets` (writes to a Google Sheet, needs
  credentials — see Setup below; a `Wrong Carrier` tab must exist in the Sheet
  already, same as `Results`/`Best Deals`/`Log` — gspread can't create tabs).
- **Each run starts fresh**: `results.csv`/`best_deals.csv`/`wrong_carrier.csv`
  (or the equivalent Sheet tabs) are reset at the start of every run, so they
  reflect only that run's findings — not an accumulating history across runs.
  (`log.csv`/the Log tab is a separate run-history log and still accumulates,
  by design.)
- **`is_likely_bookable`** (`src/bookability.py`) is the algorithm behind the
  Results/Wrong Carrier split. Two layers, most-confident first:
  1. `known_unbookable` in `settings.yaml` — a small hand-curated blocklist of
     `"AIRLINE:DESTINATION"` pairs (the carrier on the *final* leg + destination)
     manually confirmed on alaskaair.com to have zero equivalent option. This
     overrides `single_carrier`, since the JFK-KUL case below proved
     `single_carrier: True` alone doesn't guarantee a match.
  2. Otherwise, falls back to `single_carrier`: mixed-carrier itineraries go to
     Wrong Carrier as unverified; single-carrier ones are the best remaining
     signal and stay in Results.
  Neither layer is proof of bookability — see the booking-link caveat below.
  With only two confirmed real-world outcomes so far (both negative), this is
  a triage heuristic, not a validated predictor; grow `known_unbookable` as you
  manually verify more rows on alaskaair.com.
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

