# US Treasury Yield Dashboard

A local web app that plots the **US Treasury yield curves** — **2-Year / 10-Year / 30-Year** —
from **2020 to today**, with mouse-wheel zoom on the time axis and on-demand incremental refresh.

This directory is the tool's **complete implementation** (frontend and backend separated;
runnable on its own, and hosted by the `hub` workbench).

> 中文版说明见 [README.md](README.md)

## 1. Layout

```
apps/treasury/
├── app.json              app manifest (drives the hub sidebar button and API route)
├── backend/              backend, four layers bottom-up
│   ├── fred.py             network: download DGS2 / DGS10 / DGS30 from FRED
│   ├── store.py            storage: local cache (CSV / meta.json), atomic replace
│   ├── service.py          service: refresh_data() (incremental) / load_data()
│   └── api.py              HTTP API: /api/treasury/*
├── frontend/
│   ├── panel.js            chart panel (Vue + ECharts, shared by hub & standalone)
│   └── panel.css
├── standalone.py         run this tool alone (its own web page)
├── seed_data.py          optional: rebuild the cache from raw FRED CSVs (no network)
├── environment.yml       optional conda env (the backend has zero third-party deps)
└── requirements.txt      notes: zero third-party dependencies
```

## 2. Features

- **Three yield curves** — 2Y (amber), 10Y (sky blue), 30Y (violet); legend toggles, crosshair tooltip;
- **Full dates on the axis** — yearly ticks by default, refined to quarters / months / days as you zoom;
- **Latest-quote cards** — last yield per tenor, change vs. previous trading day, 90-day sparkline,
  plus the **10Y − 2Y spread** (highlighted red when the curve is inverted);
- **Wheel zoom / drag pan** — ECharts inside dataZoom; the ↺ button restores the full view;
- **On-demand only** — the app never goes online unless you click “Fetch Latest Data”;
- **Incremental** — only the days missing after the last observation are downloaded; on failure the
  cached data stays untouched;
- **Automatic proxy detection** — env vars plus common local proxy ports (7890 / 7897 / 1080 …).

## 3. Running it

```bash
# 1) inside the workbench (recommended)
python hub/server.py                       # http://127.0.0.1:8080 → 「美债收益率」

# 2) this tool alone
python apps/treasury/standalone.py         # http://127.0.0.1:5000
PORT=9000 python apps/treasury/standalone.py

# 3) rebuild the local cache from raw CSVs (offline, rarely needed)
python apps/treasury/seed_data.py
```

The backend is **pure Python standard library** — any Python 3.9+ runs it with no packages installed.

## 4. Data source

| Item | Detail |
| --- | --- |
| Source | [FRED — Federal Reserve Bank of St. Louis](https://fred.stlouisfed.org/) |
| Series | `DGS2` / `DGS10` / `DGS30` (constant-maturity yields, daily close, %) |
| Frequency | Daily, trading days only (holidays have no data — the line simply breaks) |
| Range | 2020-01-01 → today (snapshot date in `data/treasury/meta.json`) |
| Raw archive | `data/treasury/raw/DGS*.csv` — the raw FRED downloads, verifiable line by line |

Data lives in `<repo>/data/treasury/` by default (override with `TOOLBOX_DATA_ROOT`):

```
data/treasury/
├── raw/DGS{2,10,30}.csv    raw FRED CSVs (committed)
├── treasury_yields.csv     merged cache (date, DGS2, DGS10, DGS30)
└── meta.json               last date, row count, update time, refresh mode
```

Writes are atomic (temp file + `os.replace`), so a crash mid-write never corrupts the cache.

## 5. HTTP API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/treasury/data` | read the local cache and build chart data (never touches the network) |
| POST | `/api/treasury/refresh` | incremental online refresh; returns the updated payload + refresh meta |

Paths are identical in the workbench and in standalone mode, so the same `panel.js` serves both.

## 6. Chart interactions

| Action | Effect |
| --- | --- |
| Mouse wheel over the chart | zoom the time span in / out |
| Click and drag | pan the time window |
| ↺ (top right) | restore the 2020-to-today view |
| Hover | crosshair + tooltip (date on top, three tenors below) |
| Click a curve | highlight it, dim the others; click again to restore |
| Click a legend item | show / hide that curve |

## 7. Fetching strategy (tuned for mainland-China networks)

1. **Proxy auto-detection** — `HTTPS_PROXY` and friends first, then common local proxy ports;
2. **No browser User-Agent** — FRED's Akamai edge blackholes “browser UA + non-browser TLS fingerprint”
   requests (they connect but never reply); the honest default UA (curl / urllib) is reliably allowed;
3. **System curl first, urllib as fallback** — curl forces HTTP/1.1 (avoids HTTP/2 frame interference)
   and retries a couple of times;
4. **Incremental start = the last cached date itself** — FRED's `cosd` falls back to the *full* history
   when it is out of range, so using the last date (not the next day) is safer; overlapping days are
   overwritten, which also picks up FRED's revisions of the most recent trading day.

## 8. FAQ

**Refresh fails?** Check that FRED is reachable; if you run a local proxy without env vars, the server
usually detects it on startup. You can also set it explicitly and restart:
`export HTTPS_PROXY=http://127.0.0.1:7890`. Cached data is never affected by a failure.

**No new data for “today”?** FRED dates are **US trading days (ET) close values**, 12–13 hours behind
Beijing time — the UI reports “already up to date” until FRED publishes.

**Blank chart?** ECharts is served locally by the workbench (`/static/vendor/echarts.min.js`, no CDN);
hard-refresh once (Ctrl+F5).

**Start over?** Delete `data/treasury/treasury_yields.csv` and restart; the page opens instantly with a
“no local data” hint and the button re-downloads everything.

**Why is 2020-01-01 missing?** New Year's Day — FRED publishes trading days only; the first row is 2020-01-02.

## 9. Tech stack

- **Backend**: Python standard library (`http.server`, `urllib`, `csv`, `subprocess`) — zero third-party
  dependencies, thread-safe, atomic writes; the HTTP layer comes from `core/http.py`;
- **Frontend**: Vue 3 + ECharts 5, both hosted locally by the workbench (no CDN, no build step);
- **Data**: FRED's public CSV endpoint, no API key required.
