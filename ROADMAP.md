# Roadmap

Target architecture is six modules (full specification kept locally in `CLAUDE.md`).
Two are done.

## Module status

| Module | Status | Notes |
|---|---|---|
| `ConfigManager` | ✅ Done | Reads `config.yaml` + `.env`. Exposes `max_annual_budget`, `min_square_feet`, `property_type`, `location`. |
| `BrowserManager` | ✅ Done | Chrome lifecycle, Selenium attachment, anti-bot handling, profile rotation. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). |
| `LoopNetScraper` | 🟡 Partial | Property-type selection works. Location search submits but the navigation is blocked. Extraction not started. |
| `Listing` | ❌ Not started | Data model + `total_annual_rent()`. |
| `ValuationEngine` | ❌ Not started | Per-ZIP medians, arbitrage delta, filter evaluation. |
| `NotificationDispatcher` | ❌ Not started | HTML payload over TLS SMTP. |

### Config not yet consumed

`config.yaml` defines these, but no module reads them yet:
`search.max_pages`, `filters.arbitrage_threshold_pct`, the whole `browser` section
(paths are module constants in `browserManager.py`), and the whole `smtp` section.

## Next steps, in order

**1. Unblock results-page navigation** — the one thing gating everything else.
Extend the detach → navigate → wait → re-attach pattern to every navigation, not just the first
page load. Detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#the-open-blocker).

**2. Replace the filter-panel locators.**
They are browser-copied absolute XPaths with positional indices
(`.../div[4]/section[3]/div/section[1]/div[5]/...`), which break on any markup change and say
nothing about what they select. Needs the same treatment as `select_property_type`: scope to a
container, match on stable text or attributes.

**3. `Listing` model + card extraction.**
Per card: title/address, ZIP, available SF, rate per SF per year, listing URL, brokerage.

**4. Pagination** up to `search.max_pages`, appending into a master `Listing` list.
Each page turn is a navigation, so this depends on step 1.

**5. `ValuationEngine`.**
Group rates by ZIP, take the median `M_z`, compute `Δ = (1 - R_i / M_z) × 100`.
Alert when `Δ ≥ arbitrage_threshold_pct` **and** `SF ≥ min_square_feet` **and**
`SF × rate ≤ max_annual_budget`.

**6. `NotificationDispatcher`.**
HTML table (title, ZIP, SF, rate, submarket median, Δ, annual rent, link) over `smtplib` + TLS,
credentials from `.env`.

## Deferred

**Cross-platform support.** `BrowserManager` is Windows-only. `config.yaml` already carries
`browser.linux.chrome_path` and `profile_dir`; wiring those up plus a `start_new_session=True`
branch would cover Linux.

**CI on GitHub Actions.** Specified in `CLAUDE.md`, deliberately deferred. A scheduled runner starts
from a cold, cookie-less profile on an Azure datacenter IP — the combination most reliably rejected
by the bot-management layer. Headless does not help; it is more detectable, not less. Running
locally on a schedule is the workable path.
