# Roadmap

**The pipeline is complete and runs end to end:** config → browser → filtered search → card
extraction → valuation → email alert.

## Module status

| Module | Status | Notes |
|---|---|---|
| `ConfigManager` | ✅ Done | Reads `config.yaml` + `.env`. Exposes `max_annual_budget`, `min_square_feet`, `property_type`, `location`, `arbitrage_threshold_pct`. |
| `BrowserManager` | ✅ Done | Chrome lifecycle, Selenium attachment, anti-bot handling, profile rotation. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). |
| `LoopNetScraper` | ✅ Done | Builds a filtered results URL; `scrape_listing_cards()` returns price, size range, URL, property type and a projected annual rent per card. |
| `ValuationEngine` | ✅ Done | Median rate baseline with a confidence tag, arbitrage delta per listing, threshold check that hands qualifying listings to the dispatcher. |
| `NotificationDispatcher` | ✅ Done | Gmail SMTP over STARTTLS, one formatted alert email per qualifying listing. |
| `Listing` | ⚪ Not built | Deliberately skipped — cards stay plain dicts. See scope decisions. |

## How the valuation works

- **`calculate_baseline()`** — the median rate across every listing returned by the search, plus a
  confidence tag: `HIGH` at 5 or more samples, `LOW` below that, `NO_DATA` when none parsed.
- **`calculate_arbitrage_listing()`** — `Δ = (1 - rate / median) × 100` on each listing. Positive
  means priced below the baseline.
- **`alert_threshold()`** — collects listings where `Δ ≥ arbitrage_threshold_pct` and dispatches
  them. The email carries the rate, baseline, confidence tag, delta, projected annual rent, size
  range and listing link.

## Scope decisions

These are settled choices, not outstanding work.

**One baseline per search, not per ZIP.** The original spec grouped rates by ZIP code to build a
submarket median. That was dropped: a single search returns too few listings per ZIP for a median to
mean anything, and a ZIP holding one listing yields a median equal to its own rate, making `Δ = 0`
by construction. The search-wide median with a `HIGH`/`LOW` sample-size tag conveys the same caution
more honestly. Nothing location-related is collected or grouped on.

**No pagination.** Only the first page of results is scraped. Each page turn costs a full Chrome
relaunch (~25s), and one page is a large enough sample for the baseline.

**No `Listing` dataclass.** Cards are dicts. A model would be the right call if the pipeline grew,
but it would not change behaviour today. One consequence: the rate is parsed from text in three
separate places rather than once.

## Known issues

**Card scoping — affects the annual rent figure.** In `scrape_listing_cards()` the size locator is
`//ul[contains(@class,'data-points')]` with no leading dot, so it searches the whole document and
every card receives the **first** card's size. Prices and URLs are correct, so output looks
plausible, but `annual_total_rent_projection` and the "Space Available" line in the email are wrong
for every listing after the first. The fix is one character: `.//ul[...]`.

**Unguarded rate parsing.** `float()` on the rate text raises on "Negotiable" or a rate range
(`$6.00 - $8.00 SF/YR`), both of which LoopNet shows in some markets. One such listing aborts the run.

**`NO_DATA` path.** `calculate_baseline()` can return `None`, and `calculate_arbitrage_listing()`
then divides by it, raising `TypeError`.

**Alert condition is delta-only.** `min_square_feet` and `max_annual_budget` are applied as URL
filters at search time but are not re-checked against the projected annual rent before alerting.

**Hardcoded recipient.** `src/notificationDispatcher.py` sends to a literal address; `config.yaml`'s
`smtp` section (server, port, sender, recipient) is unused. `search.max_pages` is likewise leftover
from the dropped pagination.

## Possible future work

**Cross-platform support.** `BrowserManager` is Windows-only. `config.yaml` already carries
`browser.linux.chrome_path` and `profile_dir`; wiring those up plus a `start_new_session=True`
branch would cover Linux.

**CI on GitHub Actions.** Deliberately deferred. A scheduled runner starts from a cold, cookie-less
profile on an Azure datacenter IP — the combination most reliably rejected by the bot-management
layer. Headless does not help; it is more detectable, not less. Running locally on a schedule is the
workable path.
