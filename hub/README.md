# Toolbox Hub — the workbench shell

> 中文版说明见 [README_zh.md](README_zh.md)

`hub` is the **host shell** of the workbench. It contains **no business logic at all** — it only:

1. discovers every tool by scanning `apps/*/app.json`;
2. mounts each tool's backend at `/api/<tool id>/` (see `core/registry.py`);
3. serves the shell frontend (`hub/static/`) and each tool's frontend (`apps/<id>/frontend/`);
4. starts the HTTP server, prints the URL and opens the browser.

Business capabilities live in `apps/`, shared capabilities in `core/` — so the answer to “where is feature X?”
is always `apps/<tool>/`.

## Contents

```
hub/
├── server.py     the single entry point (builds the router + static mounts, starts the server)
├── hub.json      shell config (app name / subtitle)
├── __init__.py   package marker (lets tests and tools `import hub.server`)
└── static/       shell frontend (no CDN, no build step)
    ├── index.html    SPA entry: loads local Vue / ECharts + shell.js only
    ├── shell.js      the shell: reads /api/apps, lazily imports '/apps/<id>/panel.js'
    ├── shell.css     design system & layout (theme vars, topbar, sidebar, buttons, cards, modal, toast)
    ├── sdk/          host SDK, shared by the shell and every panel
    │   ├── runtime.js  Vue / ECharts references
    │   ├── api.js      JSON request helper + sleep
    │   ├── ui.js       global store, toast, modal components
    │   └── icons.js    inline SVG icon constants
    └── vendor/       locally hosted libraries: vue.global.prod.js, echarts.min.js
```

## Running it

```bash
python hub/server.py          # http://127.0.0.1:8080
PORT=8081 python hub/server.py
TOOLBOX_NO_BROWSER=1 python hub/server.py   # do not open a browser (servers / CI)
```

## HTTP conventions

| Path | Meaning |
| --- | --- |
| `/` | the workbench single-page app (the shell) |
| `/static/**` | shell assets + host SDK + vendored libraries |
| `/apps/<id>/**` | that tool's own frontend assets (`apps/<id>/frontend/`) |
| `/api/apps` | app manifest (drives the sidebar buttons) |
| `/api/health` | health check (launcher scripts use it to detect a running instance) |
| `/api/<id>/**` | that tool's backend API |

Every response carries `Cache-Control: no-store`, so frontend assets always match the code on disk.

## Adding a tool

Drop an `apps/<id>/` folder (`app.json` + `backend/api.py` + `frontend/panel.js`) and restart:
the button, the panel and the API all appear automatically — **nothing inside `hub` needs to change**.

The full contracts (backend `register(router, ctx)`, frontend `export default` component, host SDK usage)
are documented in [../ARCHITECTURE.md](../ARCHITECTURE.md); use `apps/treasury/` and `apps/qrcode/` as examples.

## Notes

* When packaged as a Windows single-file exe, `hub/static` and `hub.json` are bundled as resources and read
  from the read-only `_MEIPASS` directory at runtime, while data is written next to the exe
  (see `core/paths.py`).
* Task mutual exclusion (only one heavy task at a time) comes from `core/tasks.py`; the status dot in the
  top bar reflects it.
