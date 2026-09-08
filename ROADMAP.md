# Roadmap

Target architecture is six modules (full specification kept locally in `CLAUDE.md`).
Two are done.

## Module status

| Module | Status | Notes |
|---|---|---|
| `ConfigManager` | ✅ Done | Reads `config.yaml` + `.env`. Exposes `max_annual_budget`, `min_square_feet`, `property_type`, `location`. |
| `BrowserManager` | ✅ Done | Chrome lifecycle, Selenium attachment, anti-bot handling, profile rotation. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). |
| `LoopNetScraper` | 🟡 Partial | Loads a filtered results URL, and `scrape_listing_cards()` extracts price, size, URL and property type per card. ZIP, address and brokerage not captured yet. |
| `Listing` | ❌ Not started | Card data is currently plain dicts. Needs the model + `total_annual_rent()`. |
| `ValuationEngine` | 🟡 Stub | Class exists and is wired into `main.py`; `calculate_valuation()` is empty. |
| `NotificationDispatcher` | ❌ Not started | HTML payload over TLS SMTP. |

### Config not yet consumed

`config.yaml` defines these, but no module reads them yet:
`filters.arbitrage_threshold_pct`, the whole `browser` section
(paths are module constants in `browserManager.py`), and the whole `smtp` section.

## Next steps, in order

**1. Capture ZIP in `scrape_listing_cards()` — blocks everything below.**
`ValuationEngine` groups by ZIP code, and the cards currently carry price, size, URL and property
type but no ZIP. It is free to add: the card element exposes it as an attribute,
`card.get_attribute("gtm-listing-zip")`, alongside `data-id`, `gtm-listing-city` and
`gtm-listing-state`. No text parsing needed.

**2. Parse price to a number.**
`price` is stored as raw text (`"$7.00 SF/YR"`). The median and delta arithmetic need a float.
Guard the parse — LoopNet also shows "Negotiable" in some markets — and count skipped listings
rather than raising.

**3. `Listing` model.**
Replace the dicts with the dataclass from `CLAUDE.md` §2, exposing `total_annual_rent()`.
Decide explicitly which end of a size range feeds that calculation: `sf_min` understates the
commitment, `sf_max` overstates it and would wrongly exclude listings against `max_annual_budget`.

**4. `ValuationEngine.calculate_valuation()`.**
Group rates by ZIP, take the median `M_z`, compute `Δ = (1 - R_i / M_z) × 100`.
Alert when `Δ ≥ arbitrage_threshold_pct` **and** `SF ≥ min_square_feet` **and**
`SF × rate ≤ max_annual_budget`. Note a single-listing ZIP has a median equal to its own rate, so
`Δ = 0` — decide whether such submarkets are reported or dropped.

**5. `NotificationDispatcher`.**
HTML table (title, ZIP, SF, rate, submarket median, Δ, annual rent, link) over `smtplib` + TLS,
credentials from `.env`.

**6. Verify `max-rent` semantics.**
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
