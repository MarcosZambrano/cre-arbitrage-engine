# Roadmap

Target architecture is six modules (full specification kept locally in `CLAUDE.md`).
Two are done, two are partial.

## Module status

| Module | Status | Notes |
|---|---|---|
| `ConfigManager` | ✅ Done | Reads `config.yaml` + `.env`. Exposes `max_annual_budget`, `min_square_feet`, `property_type`, `location`, `arbitrage_threshold_pct`. |
| `BrowserManager` | ✅ Done | Chrome lifecycle, Selenium attachment, anti-bot handling, profile rotation. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). |
| `LoopNetScraper` | 🟡 Partial | Loads a filtered results URL. `scrape_listing_cards()` extracts price, size, URL and property type per card, parses the rate, and projects annual rent. ZIP, address and brokerage not captured yet. |
| `Listing` | ❌ Not started | Card data is still plain dicts. |
| `ValuationEngine` | 🟡 Partial | Median baseline with a confidence tag, arbitrage delta per listing, and a threshold check. Baseline is one median for the whole search, not per ZIP; alert checks the delta only. |
| `NotificationDispatcher` | ❌ Not started | `alert_threshold()` prints a placeholder where the dispatch call will go. |

### What `ValuationEngine` does today

- **`calculate_baseline()`** — median of every listing's rate. Returns a confidence tag alongside
  it: `HIGH` with 5 or more samples, `LOW` with fewer, `NO_DATA` with none.
- **`calculate_arbitrage_listing(baseline)`** — adds `arbitrage_delta_percentage` to each card,
  `Δ = (1 - R_i / M) × 100`. Positive means cheaper than the median.
- **`alert_threshold()`** — flags cards where `Δ ≥ arbitrage_threshold_pct`.

Annual rent is projected in the scraper as `rate × sf_min`. **Decision recorded:** for a listing
advertised as a size range, the *minimum* size is used, because the result is tested against a
budget ceiling — `sf_max` would overstate the commitment and wrongly exclude listings.

### Config not yet consumed

`config.yaml` defines these, but no module reads them yet: the whole `browser` section (paths are
module constants in `browserManager.py`) and the whole `smtp` section.

## Next steps, in order

**1. Fix card scoping in `scrape_listing_cards()` — corrupts the annual rent projection.**
The size locator is `//ul[contains(@class,'data-points')]` with no leading `.`, so it searches the
whole document and every card receives the **first** card's size. Prices and URLs are correct, so
the output looks plausible, but `annual_total_rent_projection` is wrong for all but one listing.
The locator needs `.//ul[...]`.

**2. Capture ZIP and compute the median per ZIP.**
`CLAUDE.md` §3.4 specifies a submarket median per ZIP code; today there is one median for the whole
search. ZIP is free to capture — `card.get_attribute("gtm-listing-zip")`, no text parsing. Apply the
`HIGH`/`LOW` confidence tag per ZIP too: a ZIP with a single listing has a median equal to its own
rate, so `Δ = 0` by construction.

**3. Complete the alert condition.**
`alert_threshold()` checks the delta only. The spec requires all three:
`Δ ≥ arbitrage_threshold_pct` **and** `SF ≥ min_square_feet` **and**
`annual_total_rent_projection ≤ max_annual_budget`. The projection is already computed on each card
but not yet used here.

**4. Guard the no-data and unparseable-rate paths.**
- `calculate_baseline()` returns `None` for `NO_DATA`, and `calculate_arbitrage_listing()` then
  divides by it, raising `TypeError`.
- `float()` on a rate raises on "Negotiable" or a rate range (`$6.00 - $8.00 SF/YR`), both of which
  LoopNet shows in some markets. Skip and count such listings rather than crashing the run.
- The confidence tag is returned but not yet acted on; decide whether a `LOW` baseline suppresses
  alerts.

**5. `Listing` model.**
Replace the dicts with the dataclass from `CLAUDE.md` §2, exposing `total_annual_rent()`. This also
removes the rate being parsed from text in three separate places (once in the scraper, twice in
`ValuationEngine`) — parse once, store the float.

**6. `NotificationDispatcher`.**
Replace the placeholder in `alert_threshold()`. HTML table (title, ZIP, SF, rate, submarket median,
Δ, annual rent, link) over `smtplib` + TLS, credentials from `.env`.

**7. Verify `max-rent` semantics.**
It is sent as the annual budget, but LoopNet's units for that parameter are unverified (rate per SF
vs total). If they differ, the URL silently drops qualifying listings. Compare result counts with and
without it before trusting the output.

## Deferred

**Cross-platform support.** `BrowserManager` is Windows-only. `config.yaml` already carries
`browser.linux.chrome_path` and `profile_dir`; wiring those up plus a `start_new_session=True`
branch would cover Linux.

**CI on GitHub Actions.** Specified in `CLAUDE.md`, deliberately deferred. A scheduled runner starts
from a cold, cookie-less profile on an Azure datacenter IP — the combination most reliably rejected
by the bot-management layer. Headless does not help; it is more detectable, not less. Running
locally on a schedule is the workable path.
