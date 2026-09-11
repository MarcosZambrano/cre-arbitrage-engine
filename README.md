# CRE Arbitrage Engine

Automated system for identifying undervalued commercial real estate listings on LoopNet.
It monitors target submarkets, computes a live median rate per search, and alerts on listings
priced below a configurable discount threshold.

> **Status: early development.** The browser access layer, configuration and filtered search are
> working - the scraper reaches a filtered results page. Data extraction, valuation and alerting
> are not built yet.
>
> See [ROADMAP.md](ROADMAP.md) for module status and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
> for how the browser layer works.

## Requirements

Python 3.14, Google Chrome, Windows. Selenium Manager resolves chromedriver automatically.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` next to `config.yaml`:

```
EMAIL=your-address@gmail.com
APP_NAME=your-app-name
APP_PASSWORD=your-gmail-app-password
```

Then edit `config.yaml`:

- `search.target_location` — e.g. `"Dallas, TX"`
- `search.property_type` — Office, Retail, Industrial, Flex, Coworking, Medical, Land,
  Restaurant or Lab
- `filters.min_square_feet`, `filters.max_annual_budget`, `filters.arbitrage_threshold_pct`

## Run

```bash
python main.py
```

Chrome starts on a persistent profile, waits for the anti-bot challenge to clear, then loads the
filtered results URL built from `config.yaml`.

If a profile gets blocked, the program detects it, deletes it and rotates to a clean one
automatically — no flag needed.

## Current limitations

- **Windows only.** Process management uses Win32 creation flags and PowerShell.
- **Each navigation costs a Chrome relaunch (~25s).** Akamai rejects page loads made in a browser
  ChromeDriver has attached to, so every navigation restarts the browser on the target URL — see
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#navigation-restarts-the-browser).
- **Non-US coverage is partial.** France, Germany and Spain resolve; the UK, Canada and Italy
  return 404 from LoopNet itself.
- **No data extraction yet.** Nothing is parsed, valued or emailed.

## Note

LoopNet is operated by CoStar, whose terms prohibit automated collection. This project is
educational; consider that before running it at scale or on a schedule.
