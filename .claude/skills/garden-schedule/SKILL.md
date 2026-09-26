---
name: garden-schedule
description: Garden valve names and watering schedule — the JSON config (/home/pi/garden_config.json) managed by garden_config.py, its validation rules, legacy garden_sched.cfg import, day/time conventions, and how ValveMonitor combines schedule entries and overrides into valve state every second. Load when changing the schedule/config format, garden_config.py, configure()/check()/update_valve(), or debugging "why didn't valve N open".
---

# Valve config, schedule and evaluation

## Config file (`garden_config.py`)

The path is `/home/pi/garden_config.json` on the Pi, and `test_config.json` in the repo dir on Windows (gitignored). It's written by the Setup page (`POST /api/valve`) and can also be edited by hand. The monitor polls the file's mtime every tick and reloads it when it changes.

```json
{
  "valves": [
    {"id": 1, "name": "Front lawn",
     "schedule": [{"days": [1, 3, 5], "start": "06:00", "duration": 600},
                  {"days": [0], "start": "19:30", "duration": 300}]},
    {"id": 2, "name": "", "schedule": []}
  ]
}
```

- `days`: 1 = Sunday … 7 = Saturday. `[0]` means every day. Selecting all 7 days is normalized to `[0]`.
- `start`: `HH:MM` or `HH:MM:SS`, local time.
- `duration`: seconds, 1 s to 12 h (`MAX_DURATION_SEC`).
- `name`: up to 40 characters, and may be empty. The UI then shows "Valve N".
- There are at most 20 entries per valve. Entries are sorted by start time when saved.

Functions:
- `normalize_valve(id, data)`: validates one valve and raises `ValueError` with a message the user can read ("watering time 2: pick at least one day"). The API and the loader both use it.
- `load(path, n)`: always returns all `n` valves. A valve section that fails validation is logged and left empty; the rest still load. Invalid JSON raises, and then `configure()` keeps the previous schedule.
- `save(path, config)`: atomic (writes `.tmp`, then `os.replace`).
- `expand(config)`: gives one `{valve_no, sched_day, start_time(sec), duration}` per day, which becomes `ValveSchedData(**e)` for the monitor.
- `import_legacy_cfg(path, n)`: used **once**. When the JSON file doesn't exist, `ValveMonitor.init_config()` imports `/home/pi/garden_sched.cfg` (old format: `<valve> <days csv> <hh:mm[:ss]> <sec>` per line) if it exists, otherwise it creates an empty config. The old file is never changed or read again.

## Saving from the API (`ValveMonitor.update_valve`)

It validates with `normalize_valve`, replaces that valve's section, `save()`s, sets `lastmtime` to the new mtime (so its own write isn't reloaded), then calls `apply_config()`. All of this happens under `monitor.lock`. `/api/state` returns the whole normalized config as `config`.

## Evaluation (`ValveMonitor.check`, every 1 s)

```
wday, sec = get_week_time()          # wday 1=Sun..7=Sat, sec since local midnight
req_state = [False]*(NUM_VALVES+1)   # index 0 unused
for sched in schedule: if sched.check_if_on(wday, sec): req_state[v] = True
for ov in overrides:   if ov.check_if_on(sec): req_state[v] = True; keep it   # expired ones are dropped
change_valves(req_state)             # drives only valves that differ from valves_state
```

- A valve is open if **any** of its schedule entries or overrides is active (OR).
- `ValveSchedData.check_if_on`: the day matches (or `sched_day == 0`) and `start <= sec <= start + duration`, inclusive at both ends.
- `ValveOverrideData`: `start_time` is fixed when the override is created, and it's active while `start <= sec <= start + duration`.
- `valves_state` starts as `None`, so the first tick drives every valve to its required state (startup sync).

### Remaining limitations

1. **Overrides can't force a valve OFF** during a scheduled window. Stopping a manual run only removes the override.
2. An override created shortly before midnight ends at midnight.
3. Schedule windows don't wrap past midnight (a 23:30 + 1 h entry stops at 23:59:59).

Keep the edge-triggered design (`change_valves()` only drives changed valves). Each drive blocks the monitor thread for about 3.2 s.
