---
name: garden-architecture
description: Architecture map of the Raspberry Pi garden irrigation system — a single Python process (valve scheduler thread + stdlib HTTP server with JSON API and static web UI) driving latching solenoids through sysfs GPIO. Load before reading, changing, debugging, deploying or explaining any code in this repo, so you know which component owns what and where files live on the Pi.
---

# Garden irrigation system: architecture map

A Raspberry Pi opens and closes 4 latching irrigation solenoids on a schedule. Everything runs in **one Python process**, managed by systemd.

```
 Browser (phone) ──HTTP :80──▶ garden_server.py (systemd unit "garden", user pi)
                                 ├─ WebServer (web_server.py, ThreadingHTTPServer)
                                 │    ├─ GET /            → website/index.html (static SPA)
                                 │    └─ /api/*           → JSON routes defined in garden_server.main()
                                 └─ ValveMonitor thread: 1 s tick
                                      ├─ garden_config.json: names + schedule (hot reload on mtime change, written by /api/valve)
                                      ├─ in-memory override list (guarded by monitor.lock)
                                      └─ drive_valve() ──▶ gpio_linux.turn() ──▶ /sys/class/gpio/gpioN/value
                                                                                   │
                                                                     relay board ──▶ solenoids 1-4
```

## Components

| File | Role | Details in |
|---|---|---|
| `garden_server.py` | Entry point. Holds the wiring constants (`NUM_VALVES`, `power_port`, `direction_port`), the schedule and override classes, `ValveMonitor`, the API functions (`get_state`, `port_cmd`, `all_off`), and `main()`, which wires up the routes and handles shutdown. | `garden-schedule`, `garden-gpio-wiring` |
| `garden_config.py` | Load, validate, save and legacy-import of the JSON valve config (names + schedule). | `garden-schedule` |
| `web_server.py` | Generic HTTP server: static whitelist, JSON GET/POST dispatch, error mapping. It knows nothing about valves. | `garden-web-api` |
| `website/index.html` | The whole UI: 4 tabs (Schedule / Manual / Setup / Test) that poll `/api/state`. | `garden-web-api` |
| `website/favicon.ico` | Icon. | |
| `gpio_linux.py` | Real GPIO through sysfs. `gpio_map` turns logical port 0-7 into a BCM pin. **Active-low** relays. `setup`/`turn`/`get`. | `garden-gpio-wiring` |
| `gpio_nt.py` | Windows stub with the same API. It prints and keeps port state in memory, and imports `gpio_map` from `gpio_linux`. Picked automatically when `os.name == 'nt'`. | |
| `test.cfg` | Old-format sample schedule. On Windows it's imported into `test_config.json` (gitignored) on the first run. | `garden-schedule` |
| `deploy/garden.service` | systemd unit, with the install steps in its header comment. | below |

The old TCP command server (`server.py`, port 5555), `test.py`, the PHP pages, the camera viewer and the C++ CLI (`src/`) were all removed. Don't bring them back.

## Deployment and runtime (on the Pi)

- Code lives at `/home/pi/garden`. `ExecStart=/usr/bin/python3 -u /home/pi/garden/garden_server.py`, with `WorkingDirectory` set to the same folder.
- It runs as `User=pi`, `Group=gpio`. `AmbientCapabilities=CAP_NET_BIND_SERVICE` lets it use port 80 without root. `Restart=always`.
- Apache must be disabled (`systemctl disable --now apache2`) because it would hold port 80.
- Config (names + schedule): `/home/pi/garden_config.json`, hot reloaded and written atomically by the Setup page. On first start it was imported from the old `/home/pi/garden_sched.cfg`, which is no longer read.
- Logs: stdout goes to journald (`journalctl -u garden -f`), and `garden.log` sits in the working directory (rotating, 20 KB × 3).
- Shutdown: SIGTERM → `sys.exit` → `serve_forever` exits → `monitor.stop()` (waits for any valve drive in progress) → `all_off()`. `TimeoutStopSec=30`.
- The PyCharm remote mapping in `.idea/deployment.xml` still points to `/tmp/Garden`. That's only a dev upload target, and it's wiped on reboot.

## Key invariants

- **One process, shared state.** HTTP handler threads and the monitor share `ValveMonitor`. `override_list` changes must hold `monitor.lock`, and the lock must never be held during a valve drive (each drive takes about 3.2 s).
- **Edge-triggered drives.** `check()` ORs the active schedule entries and overrides into `req_state`. `change_valves()` pulses only the valves that changed. `valves_state` starts as `None`, so all valves are synced on startup (about 13 s).
- **Overrides are in memory only** and are lost on restart. Names and the schedule persist in the JSON config.
- **Time model:** 1=Sunday … 7=Saturday (0 = every day). Seconds since local midnight. Nothing wraps past midnight.
- The raw port test endpoints bypass the monitor. The monitor turns the ports off again the next time it drives that valve.

## Known limitations

1. Overrides can only force a valve ON (no forced OFF), and they end early if they cross midnight.
2. There's no authentication on the web UI or API (LAN only).
3. sysfs GPIO is deprecated. Newer Raspberry Pi OS kernels offset the sysfs numbers (for example 512+BCM), so a move to `gpiod`/`gpiozero` may be needed.
4. Must stay compatible with Python 3.7 (the version on the Pi): no walrus operator, no `force=` in `logging.basicConfig`, no 3.8+ APIs.

## Running locally

`python garden_server.py` on Windows uses `gpio_nt` + `test_config.json` (created from `test.cfg`) and serves http://localhost:8080. Delete `test_config.json` to re-import. Ctrl-C shuts it down cleanly.

## Related skills

- `garden-gpio-wiring`: pin map, relay polarity, drive sequence
- `garden-web-api`: HTTP endpoints, UI structure, adding an endpoint
- `garden-schedule`: cfg format, validation, schedule/override evaluation
