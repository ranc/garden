import json
import logging
import os
from typing import Dict, List

'''
    Valve names and watering schedule, stored as json (edited from the Setup page, or by hand):
    {
      "valves": [
        {"id": 1, "name": "Front lawn",
         "schedule": [{"days": [1, 3, 5], "start": "06:00", "duration": 600}]},
        ...
      ]
    }
    days: 1-Sunday .. 7-Saturday, [0] means every day
    start: HH:MM or HH:MM:SS, local time
    duration: seconds
'''

MAX_NAME_LEN = 40
MAX_DURATION_SEC = 12 * 3600
MAX_ENTRIES = 20

logger = logging.getLogger('config')


def parse_time(text: str) -> int:
    '''HH:MM or HH:MM:SS -> seconds since midnight, raises ValueError'''
    parts = str(text).strip().split(':')
    if len(parts) not in (2, 3):
        raise ValueError(f"start time must be HH:MM, got: {text}")
    try:
        h, m, s = (int(p) for p in parts + ['0'] * (3 - len(parts)))
    except ValueError:
        raise ValueError(f"start time must be HH:MM, got: {text}")
    if h<0 or h>23 or m<0 or m>59 or s<0 or s>59:
        raise ValueError(f"start time is out of range: {text}")
    return (h*60 + m)*60 + s


def format_time(sec: int) -> str:
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h:02d}:{m:02d}" + (f":{s:02d}" if s else "")


def normalize_entry(entry: Dict, where: str) -> Dict:
    if not isinstance(entry, dict):
        raise ValueError(f"{where}: must be an object")
    try:
        days = sorted(set(int(d) for d in entry.get("days", [])))
    except (TypeError, ValueError):
        raise ValueError(f"{where}: days must be numbers 1-7")
    if not days:
        raise ValueError(f"{where}: pick at least one day")
    if 0 in days or days == list(range(1, 8)):
        days = [0]
    elif days[0] < 1 or days[-1] > 7:
        raise ValueError(f"{where}: days must be 1 (Sunday) to 7 (Saturday)")
    try:
        start = format_time(parse_time(entry.get("start", "")))
    except ValueError as e:
        raise ValueError(f"{where}: {e}")
    try:
        duration = int(entry.get("duration", 0))
    except (TypeError, ValueError):
        raise ValueError(f"{where}: duration must be a number of seconds")
    if duration < 1 or duration > MAX_DURATION_SEC:
        raise ValueError(f"{where}: duration must be 1 sec to {MAX_DURATION_SEC // 3600} hours")
    return {"days": days, "start": start, "duration": duration}


def normalize_valve(valve_id: int, data: Dict) -> Dict:
    '''validates one valve's settings, raises ValueError with a user readable message'''
    if not isinstance(data, dict):
        raise ValueError(f"valve {valve_id}: settings must be an object")
    name = str(data.get("name") or "").strip()[:MAX_NAME_LEN]
    schedule = data.get("schedule") or []
    if not isinstance(schedule, list):
        raise ValueError("schedule must be a list")
    if len(schedule) > MAX_ENTRIES:
        raise ValueError(f"up to {MAX_ENTRIES} watering times per valve")
    entries = [normalize_entry(e, f"watering time {i}") for i, e in enumerate(schedule, 1)]
    entries.sort(key=lambda e: parse_time(e["start"]))
    return {"id": valve_id, "name": name, "schedule": entries}


def default_config(num_valves: int) -> Dict:
    return {"valves": [{"id": v, "name": "", "schedule": []} for v in range(1, num_valves+1)]}


def load(path: str, num_valves: int) -> Dict:
    '''reads and validates the config file; a bad valve section is logged and left empty'''
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    by_id = {}
    for item in raw.get("valves", []) if isinstance(raw, dict) else []:
        if isinstance(item, dict) and isinstance(item.get("id"), int):
            by_id[item["id"]] = item
    config = default_config(num_valves)
    for i, valve in enumerate(config["valves"]):
        if valve["id"] in by_id:
            try:
                config["valves"][i] = normalize_valve(valve["id"], by_id[valve["id"]])
            except ValueError as e:
                logger.error(f"{path}: valve {valve['id']} ignored: {e}")
    return config


def save(path: str, config: Dict):
    '''atomic write, so the monitor never reads a half written file'''
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def import_legacy_cfg(cfg_path: str, num_valves: int) -> Dict:
    '''
        converts the old text schedule: <valve> <days csv> <hh:mm[:ss]> <duration sec> per line
    '''
    config = default_config(num_valves)
    with open(cfg_path, "r") as f:
        for row, line in enumerate(f, 1):
            line = line.strip()
            if not line or line[0] == "#":
                continue
            try:
                valve, days, start, duration = line.split()[:4]
                entry = normalize_entry({"days": days.split(","), "start": start, "duration": duration}, f"row {row}")
                valve = int(valve)
                if valve < 1 or valve > num_valves:
                    raise ValueError(f"row {row}: valve must be 1-{num_valves}")
            except ValueError as e:
                logger.error(f"{cfg_path}: skipped: {e} ({line})")
                continue
            config["valves"][valve-1]["schedule"].append(entry)
    for valve in config["valves"]:
        valve["schedule"].sort(key=lambda e: parse_time(e["start"]))
    return config


def expand(config: Dict) -> List[Dict]:
    '''one entry per (valve, day) with start in seconds, for the monitor'''
    ret = []
    for valve in config["valves"]:
        for entry in valve["schedule"]:
            for day in entry["days"]:
                ret.append({"valve_no": valve["id"], "sched_day": day,
                            "start_time": parse_time(entry["start"]), "duration": entry["duration"]})
    return ret
