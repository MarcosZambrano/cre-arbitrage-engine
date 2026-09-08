# CRE Arbitrage Engine

Automated system for identifying undervalued commercial real estate listings on LoopNet.
It monitors target submarkets, computes a live median rate per ZIP code, and alerts on listings
priced below a configurable discount threshold.

> **Status: early development.** The browser access layer and configuration are working. Data
> extraction, valuation and alerting are not built yet, and results-page navigation is currently
> blocked by LoopNet's anti-bot protection.
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

Chrome starts on a persistent profile, waits for the anti-bot challenge to clear, attaches Selenium
and selects the configured property type. Running again reuses the browser that is already open.

If a profile gets blocked, the program detects it, deletes it and rotates to a clean one
automatically — no flag needed.

## Current limitations

- **Windows only.** Process management uses Win32 creation flags and PowerShell.
- **Results-page navigation is blocked.** Submitting the location search returns Access Denied.
  Diagnosed but unfixed — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#the-open-blocker).
- **No data extraction yet.** Nothing is parsed, valued or emailed.

## Note

LoopNet is operated by CoStar, whose terms prohibit automated collection. This project is
educational; consider that before running it at scale or on a schedule.
