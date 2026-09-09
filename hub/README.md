# Toolbox Hub

Unifies the two standalone tools under `toolbox/` into **a single web page**:

| Feature | Source | Description |
| --- | --- | --- |
| 📈 US Treasury Yields | `us-treasury-yields/` | 2 / 10 / 30-Year U.S. Treasury yield curves (authoritative FRED data); core features & UI preserved |
| ▦ Bulk QR-Code Generator | `QRcode/` | Reads the `二维码编号` column from an Excel file and batch-generates QR codes → HTML / Excel output; UI fully redesigned |

- **Single-page app**: switch features via the left sidebar — never navigates away.
- **On-demand**: only the clicked feature runs; zero overhead otherwise.
- **Task mutual exclusion**: QR generation and yield refresh share one global lock — **only one task runs at a time**.
- **Dynamically extensible**: feature buttons are generated from `features.json` — add a feature by editing the config plus providing a panel.

> Chinese docs: [README_zh.md](README_zh.md)

## Directory Layout

```
toolbox/
├── QRcode/                 # Original QR project (configurable data root, embeddable)
├── us-treasury-yields/     # Original yields project (data dir overridable via env)
└── hub/                    # Integration layer (this app)
    ├── server.py           # Unified web server (pure Python stdlib)
    ├── static/             # Frontend (index.html / style.css / app.js)
    ├── features.json       # Feature-button config (add/remove features)
    ├── environment.yml     # conda environment definition (Linux/macOS)
    ├── install.sh          # Linux/macOS one-shot installer (env + desktop icon)
    ├── 启动.sh             # Linux/macOS one-shot launcher
    └── Toolbox工具台.desktop
```

> The two original projects only received **minimal adaptation** (configurable data root /
> env override). `hub` reuses them by dynamically loading the yields module and **invoking the
> QR script in-process** (`run(data_root=...)`) — no core feature changed. On Windows the whole
> `hub` can be packaged into a single-file `Toolbox.exe` via PyInstaller (see repo-root README).

## 🪟 Windows Quick Start

On Windows no conda / bash is needed — use the packaged single-file **`Toolbox.exe`**:

1. Double-click `Toolbox.exe` (or run from source: `python hub/server.py`, after
   `pip install "qrcode[pil]" pillow openpyxl`);
2. The browser opens http://127.0.0.1:8080 automatically;
3. The exe creates `QRcode/{input,output,qrcodes}` and `us-treasury-yields/data` next to itself
   (if placed next to the repo root, it reuses the repo's existing data folders);
4. To stop: press Ctrl+C in the console window.

Build it yourself: run `build_windows.bat` at the repo root (equivalent to
`pyinstaller --clean --noconfirm toolbox.spec`); output is `dist\Toolbox.exe`.

## 1. Install (once, Linux/macOS)

```bash
cd ~/Desktop/toolbox/hub
bash install.sh
```

The installer:
1. Creates a dedicated conda env **`self_ag`** (python 3.11 + qrcode / Pillow / openpyxl) —
   no longer depending on the `base` env;
2. Installs desktop shortcuts (desktop icon + GNOME app menu).

## 2. Run (any of three ways)

### Way 1: Double-click the desktop icon (easiest)
Double-click **「Toolbox 工具台」** on the desktop (a terminal window opens showing logs; `Ctrl+C` to stop).

### Way 2: App menu
Press `Super` in GNOME and search for **「Toolbox」** → click to launch.

### Way 3: Command line
```bash
bash ~/Desktop/toolbox/hub/启动.sh
# or
cd ~/Desktop/toolbox/hub && conda activate self_ag && python server.py
```

The browser opens **http://127.0.0.1:8080** automatically.

> If the port is busy: `PORT=8081 bash 启动.sh`, then visit http://127.0.0.1:8081.

## 3. Usage

### US Treasury Yields
- Three yield curves from 2020 to today (wheel zoom / drag pan / hover values / click to focus);
- **Smooth curves**: non-trading days (weekends/holidays) have no FRED data; null points are
  removed so the lines are continuous;
- **Click to focus**: click a curve to highlight it (others dim but stay visible); click again to restore;
- **“Fetch Latest Data”** contacts FRED only when clicked; otherwise fully offline from the local cache;
- **Incremental updates**: only the missing days after the last observation are fetched —
  no full-history re-download; on failure the local data stays untouched;
- **No cache**: the page opens instantly with a “no local data” hint; fetching is on-demand, never blocking;
- **Automatic proxy**: on startup the server detects proxy env vars and common local proxy ports
  (7890 / 7897 / 1080 etc., Clash / v2ray compatible) and routes through the proxy automatically;
- **Network compatibility**: the browser UA was removed (FRED's edge — Akamai — blackholes
  “browser UA + non-browser fingerprint” combos; an honest default UA passes reliably);
- **Time zone note**: FRED dates are **U.S. trading days (ET) closing values**, roughly 12–13 hours
  behind Beijing time, so whether “today” has new data depends on what FRED has published
  (the UI reports “already up to date” when there is nothing new).

### Bulk QR-Code Generator
1. **Upload an Excel** (click or drag-and-drop; `.xlsx` / `.xls`); the first column must be named
   `二维码编号`; Excel auto-filters are honored (only visible rows are generated);
   old input files are moved to `QRcode/input/_旧文件备份_时间戳/`, never deleted.
2. Click **「开始生成二维码」** — the run log streams live.
3. Preview the QR grid in-page and download the **HTML** and **Excel** outputs.

Outputs live in `QRcode/output/` (date-prefixed filenames); individual PNGs in `QRcode/qrcodes/`.

## 4. Adding a New Feature (dynamic)

1. Add an entry to `hub/features.json`:

```json
{
  "id": "myfeature",
  "name": "My Feature",
  "desc": "One-line description",
  "icon": "plus",
  "status": "ready"
}
```

2. Add `<section class="panel" id="panel-myfeature">…</section>` to `hub/static/index.html`;
3. Handle `myfeature` in `switchFeature()` in `hub/static/app.js`.

> Entries whose `"status"` is not `"ready"` never appear in the UI.
> The sidebar itself can collapse/expand via the single toggle button (top-right of the sidebar);
> collapsed, it becomes a 48px icon rail (feature icons remain clickable for quick switching),
> and the main area widens (the QR preview then fits more columns per row).
> For long-running tasks, use `TaskManager.acquire()` / `release()` on the client and
> `_global_task_lock` on the server.

## 5. FAQ

**Q: Double-clicking the desktop icon does nothing?**
A: GNOME may need you to trust the file first: right-click → “Allow Launching”. Or run
`gio set ~/Desktop/Toolbox工具台.desktop metadata::trusted true`.

**Q: “conda environment self_ag not found”?**
A: Run `bash ~/Desktop/toolbox/hub/install.sh` to create it.

**Q: The chart area is blank?**
A: ECharts is bundled locally (`hub/static/vendor/echarts.min.js`) — no CDN, works offline.
If still blank, hard-refresh (Ctrl+Shift+R) to clear old cached assets.

**Q: “Failed to fetch from FRED”?**
A: FRED is often unstable for direct connections in mainland China. Verify your network, or configure
a proxy and restart: `export HTTPS_PROXY=http://127.0.0.1:7890 && bash 启动.sh`.
A failure never affects cached data.

**Q: Why can't QR generation and yield refresh run at the same time?**
A: By design — both tasks share a mutual-exclusion lock so only one runs at a time, keeping
performance intact.

## Tech Stack

- Backend: Python stdlib `http.server` (zero third-party deps); yields module loaded dynamically
  (data dir overridable via `TOOLBOX_TREASURY_HOME`); QR script executed **in-process**
  (`generate_qrcodes.run(data_root=...)`; the `self_ag` conda env remains an option on Linux).
- Frontend: Vue 3 (hosted locally in `static/vendor/vue.global.prod.js` — no CDN, no build step)
  + ECharts 5 (local). Component-based SPA; QR results support **3-per-page browsing with
  left/right paging buttons** and a live task progress bar.
- Data: FRED (St. Louis Fed); QR: `qrcode[pil]` + openpyxl.
- Windows exe: PyInstaller single-file packaging (`toolbox.spec`) — runtime and deps embedded.
