---
name: garden-web-api
description: Reference for the garden HTTP server (web_server.py) — the JSON API (/api/state, /api/override, /api/cancel, /api/port, /api/alloff), the static single-page UI in website/index.html (Schedule / Manual / Test tabs), and the checklist for adding an endpoint end to end. Load when editing web_server.py, the routes in garden_server.py main(), website/index.html, or when calling the running daemon with curl.
---

# Web server, JSON API and UI

`garden_server.py` runs the valve monitor thread **and** the HTTP server in one process. There's no PHP, Apache or separate command port.

## Server (`web_server.py`)

- `WebServer(port, static_dir, get_routes, post_routes)` is a `ThreadingHTTPServer` on `0.0.0.0`. It uses only the standard library.
- Port: 80 on the Pi and 8080 on Windows. Override it with the `GARDEN_HTTP_PORT` env var.
- Static files are **whitelisted** in `STATIC_FILES` (`/`, `/index.html`, `/favicon.ico` → `website/`). Add new static files there; there's no directory serving.
- `GET /api/<name>` → `get_routes[name]()` → JSON.
- `POST /api/<name>` needs `Content-Type: application/json` (otherwise 415). This blocks cross-site form posts. The body must be a JSON object and is passed to `post_routes[name](body)`. The reply is `{"message": <str>}`.
- If a handler raises `ValueError`, the response is **400** `{"error": msg}`. Any other exception is 500 and is logged with its traceback. Unknown routes give 404.
- Every POST is logged at INFO (`[web]`). Access logs go to DEBUG.
- There's no authentication. Anyone on the LAN can control the valves, so don't port-forward it to the internet as it is.

## Endpoints (routes are defined in `main()` in `garden_server.py`)

| Method & path | Body | Result |
|---|---|---|
| `GET /api/state` | none | `{now, num_valves, gpio_map, cfg_path, monitor:{tick_age, ticks, alive}, schedule:[{valve_no, sched_day, start_time, duration}], overrides:[{valve_no, start_time, duration, left}], valves:[4 × bool/null], ports:[8 × bool/null]}` |
| `POST /api/override` | `{"valve": 1-4, "sec": 1-10800}` | Starts a manual run (`ValveMonitor.add_override`). |
| `POST /api/cancel` | `{"valve": n}` | Removes that valve's manual runs. |
| `POST /api/port` | `{"port": 0-7, "action": "on"\|"off"\|"pulse", "sec": ≤10}` | Raw port test that bypasses the monitor. `pulse` turns the port off again with a `threading.Timer` (default 1 s). |
| `POST /api/alloff` | `{}` | Turns all 8 ports off. |

- `valves` is the software state (`null` = not driven since startup). `ports` is read back from GPIO (True = relay on / pin low, `null` = not exported).
- `monitor.tick_age` is normally under 1 s, and up to about 13 s during the startup sync. `alive` is false if the monitor thread died.

curl examples:
```
curl http://pi/api/state
curl -X POST -H 'Content-Type: application/json' -d '{"valve":2,"sec":300}' http://pi/api/override
```

## UI (`website/index.html`)

A single static page. There's no build step and no external libraries.
- Tabs switch by URL hash: `#schedule`, `#manual`, `#test`.
- It polls `/api/state` every 2 s (every 30 s when the tab is hidden) and re-renders from JSON. Actions call `post(api, body, button)`, which shows a toast with `message`/`error` and refreshes.
  - **Schedule**: groups per-day entries into one row per (valve, start, duration). Day 0 shows as "Every day".
  - **Manual**: one card per valve with its Open/Closed badge, remaining time and Stop for an active run, 1/5/10/30 min presets, and a custom minutes field. The tab isn't re-rendered while that field has focus.
  - **Test**: per solenoid, power and direction rows showing port, GPIO, live state and On/Off/Pulse 1s, plus "All ports off".
- Buttons are wired by event delegation on `data-api`. Their `data-valve`/`data-sec`/`data-port`/`data-action` attributes become the JSON body.
- Mobile-first: viewport meta, 44 px tap targets, and dark mode through `prefers-color-scheme` (the colours are CSS variables on `:root`).
- Offline and "scheduler stopped" banners come from fetch failures and `monitor.alive`.

## Adding an endpoint: checklist

1. Put the logic in a function or `ValveMonitor` method that returns a message `str` (for POST) or JSON-able data (for GET). Raise `ValueError` for bad input. Use `as_int(body, key)` and `check_port()` from `garden_server.py`.
2. If it touches `override_list`, take `monitor.lock`. Never hold the lock during a valve drive.
3. Register it in `get_routes` / `post_routes` in `main()`.
4. In the UI, add a button with `data-api="<name>"` and data attributes for the body, or call `post()` directly. If it changes state, include the new state in `/api/state`.
5. Test on Windows with `python garden_server.py` (it uses `gpio_nt` + `test.cfg` on port 8080), then open http://localhost:8080 or use curl.
