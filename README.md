# Toolbox — 多功能工具台

> 中文版说明见 [README_zh.md](README_zh.md)

**Toolbox** is a collection of small, independent tools unified under **one local web app**.
Each tool keeps its original code untouched; a single `hub` layer integrates them into one
single-page dashboard — click a feature button to run it, no page navigation, mutual-exclusion
so only one task runs at a time.

## Included Tools

| Tool | Description | Standalone repo |
| --- | --- | --- |
| 📈 US Treasury Yields | 2 / 10 / 30-Year U.S. Treasury yield curves from FRED (official St. Louis Fed data), incremental updates, auto proxy detection | [Tokooy/us-treasury-yields](https://github.com/Tokooy/us-treasury-yields) |
| ▦ Bulk QR-Code Generator | Batch-generate QR codes from an Excel `二维码编号` column → HTML / Excel output | [Tokooy/QRcode_mouthly_work](https://github.com/Tokooy/QRcode_mouthly_work) |

> More tools can be added at any time — each tool lives in its own subdirectory and is
> registered in `hub/features.json` (see [hub/README.md](hub/README.md)).

## Layout

```
toolbox/
├── QRcode/                 # Tool 1: bulk QR generator (original, untouched)
├── us-treasury-yields/     # Tool 2: treasury yields dashboard (original, modified fetching)
└── hub/                    # Integration layer: unified server + frontend
    ├── server.py           # Unified web server (pure Python stdlib)
    ├── static/             # Single-page frontend
    ├── features.json       # Feature registry (add/remove tools dynamically)
    └── install.sh / 启动.sh  # Installer & launcher
```

## Repository Layout (GitHub)

The three repositories share the same codebase — this is intentional:

- **[Tokooy/toolbox](https://github.com/Tokooy/toolbox)** — the **main monorepo**: the complete
  integrated project (all tools + the `hub` layer). Start here.
- **[Tokooy/us-treasury-yields](https://github.com/Tokooy/us-treasury-yields)** — Tool 1's
  standalone repo (the yields dashboard itself, usable on its own).
- **[Tokooy/QRcode_mouthly_work](https://github.com/Tokooy/QRcode_mouthly_work)** — Tool 2's
  standalone repo (the QR generator itself, usable on its own).

The standalone repos are kept in sync with the copies inside `toolbox/` — no stale duplicates.
`toolbox/` is the integrated release; the standalone repos are the individual project entries.

## Quick Start

```bash
# 1) Install once (creates the conda env + desktop shortcuts)
cd ~/Desktop/toolbox/hub
bash install.sh

# 2) Launch (desktop icon / GNOME menu / command line)
bash ~/Desktop/toolbox/hub/启动.sh
```

The browser opens http://127.0.0.1:8080 automatically. Details in [hub/README.md](hub/README.md).

## Highlights

- **One page, many tools**: left sidebar switches features, never reloads;
- **On-demand & exclusive**: click a button to run that tool; tasks never overlap (global lock);
- **Offline-friendly**: ECharts bundled locally, no CDN; treasury data cached locally with
  incremental updates and automatic proxy detection for mainland-China networks;
- **Dynamically extensible**: add a tool by dropping a directory + registering it in
  `features.json`.
