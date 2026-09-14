# Toolbox — Multi-Tool Workbench

> 中文版说明见 [README_zh.md](README_zh.md) · Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

**Toolbox** puts several small tools into **one local web app**: click a button in the sidebar to switch
tools — no page reloads, no command lines to remember. All tools share one shell and one backend kernel,
and **each tool can also run completely on its own**.

| Tool | Description | Code |
| --- | --- | --- |
| 📈 US Treasury Yields | 2 / 10 / 30-year U.S. Treasury yield curves (authoritative FRED data), on-demand incremental refresh | [`apps/treasury/`](apps/treasury/README_en.md) |
| ▦ Bulk QR-Code Generator | Reads the `二维码编号` column from Excel and batch-generates QR codes → HTML / Excel | [`apps/qrcode/`](apps/qrcode/README.md) |

## 1. Quick start

### Windows: single-file exe (no Python needed)

1. Build (double-click in the repo root, or run from a terminal):
   ```bat
   packaging\windows\build_windows.bat
   ```
2. Copy `dist\Toolbox.exe` to any Windows 10/11 machine and **double-click it** (the Python runtime is bundled);
3. Your browser opens <http://127.0.0.1:8080>; press `Ctrl+C` to stop.

> ⚠️ After changing code you **must rebuild** for the exe to pick it up — the frontend, backend and
> dependencies are baked into it at build time. Running from source and Docker always read the latest code.

### From source (any platform, best for development)

```bash
# Only the QR generator needs third-party packages; the workbench and the treasury tool are stdlib-only
python -m pip install "qrcode[pil]" pillow openpyxl

python hub/server.py             # opens http://127.0.0.1:8080
PORT=8081 python hub/server.py   # another port
```

### Docker (server / NAS / headless)

```bash
docker build -f packaging/docker/Dockerfile -t toolbox .
docker run -d --name toolbox -p 8080:8080 -v toolbox_data:/app/data toolbox
# visit http://<host-ip>:8080
```

### Linux / macOS desktop shortcut

```bash
bash packaging/linux/install.sh   # conda env + desktop icon + app menu entry
bash packaging/linux/启动.sh       # launch (same as double-clicking the icon)
```

> Full details for all three paths (migration, backup, data volumes) live in [packaging/README.md](packaging/README.md).

## 2. Running a single tool

You do not need the workbench to use one tool — its API and frontend panel are **identical** either way:

```bash
python apps/treasury/standalone.py   # treasury dashboard only → http://127.0.0.1:5000
python apps/qrcode/standalone.py     # QR generator only      → http://127.0.0.1:5001
python apps/qrcode/cli.py            # no web page, batch-generate from the terminal
```

## 3. Where the data lives

Code is read-only, data is writable, and they are kept apart (essential for the packaged exe and for volumes):

```
data/
├── treasury/   cached yields + raw FRED CSV archive (committed, works offline out of the box)
└── qrcode/     input (uploaded Excel) / output (generated files) / qrcodes (PNG cache)
```

The data root is resolved as: `TOOLBOX_DATA_ROOT` env var ▸ the folder holding the exe (packaged runs)
▸ the repository root. So wherever you put the exe, its `data/` folder goes with it — copy both to move.

## 4. Repository layout

```
toolbox/
├── core/          shared kernel: path resolution / HTTP framework / tasks & locking / app registry
├── apps/          business code: one tool = one folder = backend + frontend (+ optional entry points)
│   ├── treasury/    US Treasury yield dashboard
│   └── qrcode/      bulk QR-code generator
├── hub/           workbench shell: discovers apps/, mounts their APIs and serves the SPA
├── data/          runtime data (see above)
├── packaging/     delivery: Windows exe / Docker / Linux desktop install
├── tests/         smoke test
└── ARCHITECTURE.md  responsibilities, dependency direction, contracts, how to add a tool
```

## 5. Verifying a checkout

```bash
python tests/smoke_test.py
```

Zero third-party dependencies (except `openpyxl` for QR generation). It boots a real server against a
temporary data directory and exercises the shell, both tools and their standalone modes; exit code 0
means everything passed — safe to wire into CI.

## 6. FAQ

**Port already in use?** Start on another port: `PORT=8081 python hub/server.py`
(PowerShell: `$env:PORT=8081; python hub/server.py`). A conflict is reported with a hint at startup.

**FRED fetch failing?** Proxy auto-detection is built in (env vars plus common local proxy ports
7890 / 7897 / 1080 …). If it still fails, set one explicitly and restart:
`export HTTPS_PROXY=http://127.0.0.1:7890`. A failed fetch never affects already-cached data.

**The exe still shows the old UI after a code change?** Rebuild it
(`packaging\windows\build_windows.bat`) — and quit the running exe first so the file can be replaced.

**The page looks stale?** Every response carries `Cache-Control: no-store`, so nothing should be cached;
if in doubt, force-refresh once with `Ctrl+F5`.

**Antivirus flags the exe?** PyInstaller single-file builds are sometimes false-flagged; check it on
[VirusTotal](https://www.virustotal.com/), or use the source / Docker route instead.

## 7. Tech stack and design choices

- **Backend**: pure Python standard library (`http.server`, `urllib`, `csv`) — zero third-party deps.
  Shared capabilities live in `core/`, business logic in `apps/<tool>/backend/`, and the workbench shell
  only wires things together;
- **Frontend**: Vue 3 + ECharts 5, **hosted locally, no CDN, no build step**. The shell (`hub/static`)
  owns navigation and notifications; each tool's panel (`apps/<tool>/frontend/panel.js`) is loaded on demand;
- **Task mutual exclusion**: every heavy task shares one global lock — only one runs at a time, so
  network, disk and CPU are never fought over;
- **Extensible**: adding a tool means adding an `apps/<id>/` folder (manifest + backend + frontend);
  nothing inside `hub` needs to change — see [ARCHITECTURE.md](ARCHITECTURE.md).
