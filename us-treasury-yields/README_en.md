# US Treasury Yield Dashboard

> ⚠️ **Restructuring in progress**: the backend of this tool now lives in `apps/treasury/backend/`
> (network / storage / service / API layers) and is hosted by the `hub` workbench. The remaining
> static pages, data and scripts in this folder will follow in later steps. See
> [ARCHITECTURE.md](../ARCHITECTURE.md); this document will move to `apps/treasury/README_en.md`.

A local web application that plots the **US Treasury yield curves** — **2-Year / 10-Year / 30-Year** — from **2020 to today**, with a polished dark UI, mouse-wheel zoom on the time axis, and on-demand data refresh.

> 中文版说明见 [README.md](README.md) · Chinese version: [README.md](README.md)

## 1. Features

- **Three yield curves**: 2-Year (amber), 10-Year (sky blue), 30-Year (violet) on one chart — toggle each via the legend, hover for crosshair inspection.
- **X-axis in full dates**: labels are complete `YYYY-MM-DD`; the default view shows **one tick per year** (no clutter), and zooming in automatically refines the ticks to quarter / month / day granularity.
- **Hover tooltip**: shows the exact date (`YYYY-MM-DD`) on top, with that day's three yields below.
- **Latest-quote cards**: latest yield per tenor, change vs. the previous trading day, a 90-trading-day mini sparkline, plus the **10Y − 2Y term spread** (highlighted when inverted).
- **Wheel zoom on the chart**: scroll to zoom the time range in / out, drag to pan, one-click restore button.
- **On-demand refresh**: the **“Fetch Latest Data”** button in the top-right corner contacts FRED only when clicked; normal runs and page reloads never touch the network — cached data is served directly.
- **Incremental updates**: when local data already exists, only the missing days after the last observation are fetched (each series computes its own start point, so nothing is missed) — **no re-downloading of the full 2020 history**. If FRED has not published a newer trading day yet, the app reports “already up to date”.
- **Real, authoritative data**: everything comes from FRED (Federal Reserve Bank of St. Louis) — series `DGS2` / `DGS10` / `DGS30` (constant-maturity Treasury yields, daily closing values). The original downloaded files are archived in `data/raw/` for verification.

## 2. Data Source & Authority

| Item | Description |
| --- | --- |
| Source | [FRED — Federal Reserve Bank of St. Louis](https://fred.stlouisfed.org/) (official Fed data channel; the de-facto standard for macroeconomic data) |
| Series IDs | `DGS2` / `DGS10` / `DGS30` (Market Yield on U.S. Treasury Securities at 2/10/30-Year Constant Maturity) |
| Frequency | Daily, closing values on trading days (no data on holidays — the chart bridges the gaps) |
| Range | 2020-01-01 to today (bundled snapshot: 1,725 trading days through 2026-08-12) |
| Raw archive | `data/raw/DGS2.csv`, `data/raw/DGS10.csv`, `data/raw/DGS30.csv` — pristine FRED CSVs, line-by-line verifiable |

> FRED's constant-maturity yields are computed by the U.S. Treasury and the Fed from actual secondary-market Treasury prices — the standard reference for interest-rate and monetary-policy analysis worldwide.

## 3. Directory Structure

```
us-treasury-yields/
├── README.md               # Chinese documentation
├── README_en.md            # This file
├── environment.yml         # conda environment definition (python=3.11)
├── requirements.txt        # Note: zero third-party dependencies
├── server.py               # Backend: pure-Python-stdlib HTTP server (entry point)
├── scripts/
│   └── seed_data.py        # Optional: rebuild cache from data/raw originals
├── data/
│   ├── raw/                # Original FRED CSV archives (provenance)
│   │   ├── DGS2.csv
│   │   ├── DGS10.csv
│   │   └── DGS30.csv
│   ├── treasury_yields.csv # Merged local cache (date, DGS2, DGS10, DGS30)
│   └── meta.json           # Metadata (last date, row count, update time)
└── static/                 # Frontend (HTML / CSS / JS, ECharts 5 via CDN)
    ├── index.html
    ├── style.css
    └── app.js
```

## 4. How to Run

### 4.1 Install conda

Install [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or Anaconda if you don't have one yet (skip if already installed).

### 4.2 Create the conda environment

Open a terminal in the **project root** (`us-treasury-yields/`) and run:

```bash
# Create the "treasury" environment (python 3.11) from environment.yml
conda env create -f environment.yml

# Activate it
conda activate treasury
```

> The backend is a **pure Python standard-library implementation with zero third-party dependencies** (no `pip install` needed). The conda environment isolates the Python runtime and avoids dependency conflicts by construction.

### 4.3 Start the server

```bash
python server.py
```

A successful first run looks like this (the browser opens automatically):

```
美国国债收益率看板已启动：http://127.0.0.1:8080
按 Ctrl+C 停止服务
（若无本地缓存，服务会在后台自动尝试从 FRED 获取一次，失败不影响使用）
```

> This repository ships with the data snapshot pre-bundled, so it works out of the box with no network access.
> If the local cache is missing: the server tries once in the background on startup (without blocking), the page shows “暂无本地数据 / No local data”, and clicking “Fetch Latest Data” fetches on demand.

### 4.4 Open the page

Visit **http://127.0.0.1:8080** to see the three yield curves from 2020 to today.

> To change the port: `PORT=9000 python server.py` → http://127.0.0.1:9000

### 4.5 Stop the server

Press `Ctrl+C` in the terminal.

## 5. The “Fetch Latest Data” Button

- **Location**: top-right corner (emerald-green gradient button).
- **Behavior**: it contacts FRED **only when clicked**; the rest of the time it never touches the network.
- **Incremental**: when local data exists, only the days after the last observation are requested (each series computes its own start point), **not the full 2020 history**; the first run (no cache) fetches everything.
- When finished, a dialog shows the result — “N new days” or “already up to date” — and the chart plus the “data as of” timestamp refresh automatically.
- On network failure the dialog stays open with the error details; the locally cached data is untouched.
- **Time zone note**: FRED dates are **U.S. trading days (ET) closing values**, about 12–13 hours behind Beijing time, so whether “today” has new data depends on what FRED has actually published.

## 6. Chart Interactions

| Action | Effect |
| --- | --- |
| Mouse wheel (over the chart) | Zoom the time range in / out |
| Drag with the mouse | Pan the time window |
| ↺ button (top-right) | Restore the full 2020–now view |
| Hover the curves | Crosshair + tooltip (date `YYYY-MM-DD` on top, the three yields below) |
| X-axis labels | One `YYYY-MM-DD` tick per year by default; refines automatically when zoomed |
| Click the legend (2Y / 10Y / 30Y) | Show / hide the corresponding curve |

## 7. FAQ

**Q1: The chart area is blank.**
A: ECharts is loaded from a CDN — make sure the browser can reach `cdn.jsdelivr.net`, then reload.

**Q2: The button reports “failed to fetch from FRED”.**
A: The server applies several network-compatibility measures; check them in order:
1. **Automatic proxy**: on startup it detects proxy environment variables and common local proxy ports (7890 / 7897 / 1080, e.g. Clash / v2ray) and routes through the proxy automatically;
2. **No browser UA**: FRED's edge (Akamai) blackholes “browser UA + non-browser fingerprint” combinations; this app uses an honest default UA (verified to pass reliably);
3. **HTTP/1.1 + retries**: forces HTTP/1.1 to avoid HTTP/2 frame interference on some networks, with automatic retries;
4. If it still fails, make sure this machine can reach FRED (or set the `HTTPS_PROXY` env var and restart). A failure never affects the already-cached data.

**Q3: Port 8080 is already in use.**
A: The server prints a clear hint on startup. Check for a stale instance (`ss -tlnp | grep 8080`) or change the port: `PORT=9000 python server.py` → http://127.0.0.1:9000.

**Q4: I want to delete the data and re-fetch.**
A: Delete `data/treasury_yields.csv` and restart; the page shows “no local data”, and clicking “Fetch Latest Data” re-fetches everything. The page still opens instantly (it never blocks waiting for the network).

**Q5: Why is there no data for 2020-01-01?**
A: It's a New Year's holiday. FRED publishes trading days only; the first 2020 observation is 2020-01-02.

**Q6: Can the data go stale or be wrong?**
A: The bundled snapshot is the real data as published at download time; click the button to refresh. The raw originals stay in `data/raw/` and can be cross-checked against any source.

## 8. Tech Stack

- **Backend**: Python 3.11 — stdlib `http.server` / `csv`. Zero third-party dependencies, thread-safe, atomic cache writes.
- **Frontend**: vanilla HTML/CSS/JS + ECharts 5 (CDN).
- **Data**: FRED (St. Louis Fed) official CSV download endpoint — no API key required.
- **Fetch strategy**: system `curl` first (forced HTTP/1.1, browser-grade headers, auto retry), `urllib` fallback; **no browser UA** (Akamai blackholes disguised requests); **automatic proxy detection** (env vars + common local proxy ports); **incremental updates** (fetch only the missing days, atomic write-back, keep old data on failure).
