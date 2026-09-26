---
name: garden-schedule
description: Garden watering schedule file format (/home/pi/garden_sched.cfg), validation rules, day/time conventions, and how ValveMonitor combines schedule entries and overrides into valve state every second. Load when writing or reviewing a schedule, editing configure()/check()/ValveSchedData/ValveOverrideData, or debugging "why didn't valve N open".
---

# Schedule and override evaluation

## Schedule file

Path: `/home/pi/garden_sched.cfg` on the Pi and `test.cfg` on Windows. The daemon polls its mtime every tick and re-parses when it changes, so there's no need to restart.

One entry per line: `<valve> <days> <start> <duration_sec> [ignored trailing text]`

- `valve`: integer, validated as 1-7 (the hardware has 4 solenoids, see `garden-gpio-wiring`).
- `days`: comma list with no spaces. `0` = every day, `1` = Sunday … `7` = Saturday.
- `start`: `HH:MM` or `HH:MM:SS`, 24-hour, local time.
- `duration_sec`: **seconds**, at least 1. (The comment in `test.cfg` says "20 min" but the value 20 means 20 s.)
- Blank lines and lines starting with `#` are skipped. Anything after the 4th token is ignored, so trailing `# comments` work.

Example: valve 2 every Sun/Tue/Thu at 06:00 for 10 min, and valve 1 every day at 19:30 for 5 min:
```
2 1,3,5 06:00 600
1 0 19:30 300
```

### Parsing quirks

- Validation errors are logged at ERROR (`[monitor]`, visible in `garden.log` and journald). An unparseable line, bad valve or bad duration **skips the whole line**. A bad day skips only that day. A bad start time skips the rest of the line.
- A reload never crashes the monitor: `configure()` builds a new list and swaps it in, and `run()` catches exceptions. The log line `Loaded N schedule entries` confirms each reload.
- The start time and window aren't checked for overflow. A window that goes past midnight just ends at 23:59:59, and the part after midnight is lost.

## Evaluation (`ValveMonitor.check`, every 1 s)

```
wday, sec = get_week_time()          # wday 1=Sun..7=Sat, sec since local midnight
req_state = [False]*(NUM_VALVES+1)   # index 0 unused
for sched in schedule: if sched.check_if_on(wday, sec): req_state[v] = True
for ov in overrides:   if ov.check_if_on(sec): req_state[v] = True; keep it   # expired ones are dropped
change_valves(req_state)             # drives only valves that differ from valves_state
```

- A valve is open if **any** of its schedule entries or overrides is active (OR).
- `ValveSchedData.check_if_on`: the day matches (or `sched_day == 0`) and `start <= sec <= start + duration`. The window is inclusive at both ends.
- `ValveOverrideData`: `start_time` is fixed when the override is created (seconds since midnight) and is active while `start <= sec <= start + duration`.
- `valves_state` starts as `None`, so the first tick drives every valve to its required state (startup sync).

### Remaining limitations

1. **Overrides can't force a valve OFF** during a scheduled window. Stopping a manual run only removes the override.
2. An override created shortly before midnight ends at midnight: after midnight `sec` is small, so `check_if_on` returns False and the override is dropped.
3. Schedule windows don't wrap past midnight.

Keep the edge-triggered design (`change_valves()` only drives changed valves). Each drive blocks the monitor thread for about 3.2 s.
