# Toolbox — Multi-Tool Workbench

> 中文版说明见 [README_zh.md](README_zh.md)

**Toolbox** is a collection of small, independent tools unified under **one local web app**.
Each tool keeps its original code intact; a single `hub` layer integrates them into one
single-page dashboard — click a feature button to run it, no page navigation, and tasks are
mutually exclusive (only one runs at a time).

The project is **cross-platform**: run from source on Linux/macOS, or build a **single-file
`Toolbox.exe`** on Windows — double-click to run, no Python installation required (runtime bundled).

## Included Tools

| Tool | Description | Standalone repo |
| --- | --- | --- |
| 📈 US Treasury Yields | 2 / 10 / 30-Year U.S. Treasury yield curves from FRED (official St. Louis Fed data), incremental updates, auto proxy detection | [Tokooy/us-treasury-yields](https://github.com/Tokooy/us-treasury-yields) |
| ▦ Bulk QR-Code Generator | Batch-generate QR codes from an Excel `二维码编号` column → HTML / Excel output | [Tokooy/QRcode_mouthly_work](https://github.com/Tokooy/QRcode_mouthly_work) |

> More tools can be added at any time — each tool lives in its own subdirectory and is
> registered in `hub/features.json` (see [hub/README.md](hub/README.md)).

## 🪟 Windows Quick Start

### Option A: Use the packaged `Toolbox.exe` (recommended, no Python needed)

1. Put **`Toolbox.exe`** (from a Release, or built with the steps below) anywhere;
2. **Double-click to run** — a console window opens, and your browser opens
   <http://127.0.0.1:8080> automatically;
3. To stop: press **Ctrl+C** in the console window.

The exe **manages its own data folders** next to itself:

```
folder of Toolbox.exe/
├── QRcode/
│   ├── input/    ← drop the Excel file here (or upload it in the web UI)
│   ├── output/   ← generated HTML / Excel
│   └── qrcodes/  ← QR image cache
└── us-treasury-yields/
    └── data/     ← treasury data cache (fetched once online, usable offline afterwards)
```

> 💡 If you place `Toolbox.exe` **next to this repo root** (where `QRcode/` and
> `us-treasury-yields/` already exist), it reuses those folders and shares data with the source.

### Option B: Run from source (development)

```bat
:: 1) Install dependencies (once)
python -m pip install "qrcode[pil]" pillow openpyxl

:: 2) Start (keep the window open)
cd hub
python server.py
```

The browser opens <http://127.0.0.1:8080>. Notes: the treasury dashboard is pure Python
standard library (no third-party packages); the QR generator needs `qrcode[pil] / pillow / openpyxl`.

## 🛠 Building the Windows exe

Packaging config (PyInstaller single-file) is included:

```bat
:: double-click, or run from a terminal
build_windows.bat
```

Equivalent manual steps:

```bat
python -m pip install pyinstaller "qrcode[pil]" pillow openpyxl
pyinstaller --clean --noconfirm toolbox.spec
:: output: dist\Toolbox.exe
```

- Requires **Python 3.8+** (conda/miniconda recommended) and network access on first run;
- Output is a single **`dist\Toolbox.exe`** — copy it to any Windows 10/11 machine and run;
- See [`toolbox.spec`](toolbox.spec) for details: QR dependencies are bundled, frontend assets
  and helper scripts are embedded, while writable data is redirected next to the exe at runtime
  (never into the read-only `_MEIPASS` temp folder, so nothing is lost on exit).
### 🔄 Updating Toolbox.exe (important: you MUST rebuild after changing code)

**Why does the exe still show the old behavior after I changed the code?**
`Toolbox.exe` is a PyInstaller single file: the frontend, backend logic and both tool
scripts are **baked into the exe at build time** (extracted to a read-only temp folder at
runtime). Any code you change or pull afterwards never reaches an already-built exe —
running from source (`python hub/server.py`) and Docker always read the latest files, so
**only the exe gets stuck on an old version**. If the exe behaves differently from the
source, compare the exe's modified time with your code change time first — you most likely
forgot to rebuild.

**Update steps (every time you changed code and want to try it via the exe):**

1. **Quit the running old Toolbox.exe first** (otherwise the exe file is locked and cannot
   be overwritten): press `Ctrl+C` in its console window, or end the `Toolbox.exe` process
   in Task Manager;
2. Pull the latest code: `git pull` (or simply build from your local, modified source);
3. Rebuild (either way; needs Python 3.8+ locally, first run installs dependencies):
   ```bat
   :: Option A: double-click build_windows.bat in the repo root
   :: Option B: run manually in a terminal
   python -m pip install pyinstaller "qrcode[pil]" pillow openpyxl
   pyinstaller --clean --noconfirm toolbox.spec
   ```
4. The new artifact is `dist\Toolbox.exe`: use it to **overwrite the old exe** (it is a
   good idea to rename the old exe first as a backup);
5. Double-click the new exe to verify. **Your data is not affected**: QR input/output and
   the treasury cache live in persistent folders next to the exe
   (`QRcode/input`, `QRcode/output`, `us-treasury-yields/data`, …), so overwriting the exe
   never clears or loses any data.

**FAQ**

- Exe unchanged after code changes → you forgot to rebuild; just re-run step 3;
- “File in use / cannot write” when overwriting the exe → quit the running old
  Toolbox.exe first, then overwrite;
- Page still shows the old UI → assets carry a `?v=` version and the server sends
  `Cache-Control: no-store`, so the new files load automatically; if it still looks stale,
  force-refresh once with `Ctrl+F5`;
- The new exe is quarantined/deleted by security software → single-file exes built with
  PyInstaller are sometimes false-flagged; see the FAQ below and check on VirusTotal
  before adding an exception.

## 🐧 Linux / macOS (original flow, still supported)

```bash
# 1) Install once (creates a conda env + desktop shortcut)
cd hub
bash install.sh

# 2) Launch (desktop icon / app menu / command line)
bash 启动.sh
```

> Windows and Linux share the same source: on Windows the QR generator runs in-process
> (no conda env needed); the Linux/macOS `install.sh` + `启动.sh` flow is unchanged.

## 🐳 Docker (recommended for migration / headless deployment)

Containerizing Toolbox lets you run the whole workbench on **any machine with Docker**
(Linux server, NAS, VPS, cloud host) with one command — no Python install, no desktop
environment needed. This is the easiest path for future migration.

### 1. Build the image

```bash
docker build -t toolbox .
```

> The image bundles the hub server, Vue 3 frontend, QR dependencies
> (qrcode / pillow / openpyxl) and the **treasury historical seed data**
> (charts work offline right away). Image size ≈ 240MB.

### 2. Run

```bash
# Foreground, one-off (Ctrl+C to exit):
docker run --rm -p 8080:8080 toolbox

# Recommended: detached daemon with two data volumes (data survives container removal):
docker run -d --name toolbox -p 8080:8080 \
  -v toolbox_qr:/app/QRcode \
  -v toolbox_treasury:/app/us-treasury-yields/data \
  toolbox
```

Open **http://localhost:8080** (on a remote host: `http://<host-ip>:8080`).

**Data volumes** (key to migration/backup):

| Volume | Container path | Contents |
| --- | --- | --- |
| `toolbox_qr` | `/app/QRcode` | QR Excel inputs / HTML·Excel outputs / PNG cache |
| `toolbox_treasury` | `/app/us-treasury-yields/data` | Treasury cache (updated online once, offline afterwards) |

Volumes are auto-created on first run and seeded from the image; `docker rm` never deletes
them, so re-running the same `docker run` resumes with your old data.

### 3. Daily management

```bash
docker logs -f toolbox          # tail service logs
docker stop toolbox && docker start toolbox   # stop / start
docker restart toolbox          # restart in place
docker rm -f toolbox            # remove container (volumes kept)
docker volume ls                # list volumes (toolbox_qr / toolbox_treasury)
docker exec -it toolbox sh      # shell into the container
docker cp 表格.xlsx toolbox:/app/QRcode/input/   # or copy a file into the container
```

### 4. Migrating to a new machine

1. Install Docker on the new machine;
2. Move your data (either way):
   - Back up the volumes on the old host
     (`docker run --rm -v toolbox_qr:/from -v "$(pwd)":/to alpine cp -a /from/. /to/qr/`), or
     simply copy the directories you generated yourself;
   - Simple case: copy/clone the repo to the new machine and run `docker build` again —
     volumes keep your data regardless of the container;
3. Run the `docker run` command above on the new machine (same volume names resume data).

### 5. Notes

- The service listens on `0.0.0.0:8080` (`HOST=0.0.0.0` inside the image); on a port conflict
  use `-p 8081:8080`;
- To change the port: `docker run -e PORT=8080 -p 8081:8080 …`;
- There is no browser inside the container; the “auto-open browser” step is safely ignored —
  just visit the page with your browser;
- Expose it only to trusted networks (localhost / LAN). For public access, put a reverse
  proxy in front;
- Coexists with the exe / source workflows — all three share the same code and features.

## Layout

```
toolbox/
├── QRcode/                 # Tool 1: bulk QR generator (data root configurable)
├── us-treasury-yields/     # Tool 2: treasury yields dashboard (improved fetching only)
├── hub/                    # Integration layer: unified server + frontend
│   ├── server.py           # Unified web server (pure stdlib, exe-aware)
│   ├── static/             # Single-page frontend (Vue3 + ECharts, local & offline)
│   ├── features.json       # Feature registry (add/remove tools dynamically)
│   ├── install.sh / 启动.sh  # Linux/macOS installer & launcher
├── toolbox.spec            # PyInstaller config (Windows single-file exe)
├── build_windows.bat       # Windows one-click build script
├── Dockerfile              # Docker image (migration / headless deployment)
├── .dockerignore           # Docker build-context excludes
└── README.md / README_zh.md
```

## Repository Layout (GitHub)

The three repositories share the same codebase — this is intentional:

- **[Tokooy/toolbox](https://github.com/Tokooy/toolbox)** — the **main monorepo**: the complete
  integrated project (all tools + the `hub` layer + Windows packaging config). Start here.
- **[Tokooy/us-treasury-yields](https://github.com/Tokooy/us-treasury-yields)** — Tool 1's
  standalone repo (the yields dashboard itself, usable on its own).
- **[Tokooy/QRcode_mouthly_work](https://github.com/Tokooy/QRcode_mouthly_work)** — Tool 2's
  standalone repo (the QR generator itself, usable on its own).

The standalone repos are kept in sync with the copies inside `toolbox/` — no stale duplicates.
`toolbox/` is the integrated release; the standalone repos are the individual project entries.

## FAQ

**Port already in use?**
Close the old instance, or restart on another port:

```powershell
# PowerShell
$env:PORT=8088; python server.py
```
```bat
:: CMD
set PORT=8088 && python server.py
```

**Treasury data fetch failing / timing out?**
Auto proxy detection for common local proxy ports (Clash/v2ray) is built in. If it still fails,
make sure FRED is reachable, or set a proxy and restart:

```bash
export HTTPS_PROXY=http://127.0.0.1:7890
```

**Antivirus false positive?**
Single-file exes built with PyInstaller are sometimes flagged. Run from source (Option B)
instead if you prefer, or verify the file on [VirusTotal](https://www.virustotal.com/) and add
an exclusion.

## Highlights

- **One page, many tools**: left sidebar switches features, never reloads;
- **On-demand & exclusive**: click a button to run that tool; tasks never overlap (global lock);
- **Vue 3 frontend**: component-based SPA, Vue 3.5 hosted locally (no CDN, no build step),
  dark glassmorphism theme with restrained transitions;
- **Grouped QR preview**: results shown **3 per page**, flip with left/right **previous / next
  group** buttons, plus a live **task progress bar** during generation;
- **Offline-friendly**: ECharts bundled locally, no CDN; treasury data cached locally with
  incremental updates and automatic proxy detection for mainland-China networks;
- **Dynamically extensible**: add a tool by dropping a directory + registering it in
  `features.json`.
