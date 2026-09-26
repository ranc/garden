import logging
import os
import signal
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

from web_server import WebServer

if os.name == 'nt':
    from gpio_nt import turn, setup, get, gpio_map
    cfg_path = "test.cfg"
    http_port = 8080
else:
    from gpio_linux import turn, setup, get, gpio_map
    cfg_path = "/home/pi/garden_sched.cfg"
    http_port = 80
http_port = int(os.environ.get("GARDEN_HTTP_PORT", http_port))
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "website")


'''
    wires on hoze:
            white: ground
            red: when positive: open
            black: when positive: close

 strcuture of GPIO (logical ports 0-7, see gpio_map for the BCM pins):
    each solenoid has a pair of ports:
        port 2*(n-1)  : power of solenoid *n*, turns on only while the solenoid needs to change state
        port 2*(n-1)+1: direction of solenoid *n*, on: to open, off: to close
    so: 0,1 -> solenoid 1 | 2,3 -> solenoid 2 | 4,5 -> solenoid 3 | 6,7 -> solenoid 4

    For Example, to open solenoid 2:
        1. turn on port 3 (direction: open)
        2. wait a moment for the direction relay to settle
        3. turn on port 2 (power) for change_drive_time seconds, then turn it off
        4. turn off port 3 to save power
    only solenoids whose state changed are driven, one after the other.
'''

NUM_VALVES = 4
NUM_PORTS = 2 * NUM_VALVES
MAX_OVERRIDE_SEC = 3 * 3600
MAX_PULSE_SEC = 10
change_drive_time = 3 # time it takes to change the valve
relay_settle_time = 0.1 # time for the direction relay to settle before/after power


def power_port(valve: int) -> int:
    return 2 * (valve - 1)


def direction_port(valve: int) -> int:
    return 2 * (valve - 1) + 1


class ValveSchedData:
    valve_no: int # 1-4
    sched_day: int # 0 - all day, 1-Sunday, 7- Saturday
    start_time: int # seconds since midnight
    duration: int # seconds

    def set_start_time(self, start_time_str: str) -> bool:
        '''
            returns false if the format is illegal
        '''
        h_m_s = start_time_str.split(':')
        if len(h_m_s)<2 or len(h_m_s)>3:
            return False
        if len(h_m_s)==2:
            h_m_s.append(0) # assume 0 sec if just HH:mm
        h,m,s = tuple(int(_) for _ in h_m_s)
        if h<0 or h>23 or m<0 or m>59 or s<0 or s>59:
            return False
        m += h*60
        s += m*60
        self.start_time = s
        return True

    def check_if_on(self, wday, day_sec) -> bool:
        if self.sched_day > 0 and wday != self.sched_day:
            return False # not today :-)
        return self.start_time <= day_sec and day_sec <= self.start_time + self.duration


class ValveOverrideData:
    valve_no: int # 1-4
    start_time: int # seconds since midnight
    duration: int # seconds

    def __init__(self, valve: int, duration: int) -> None:
        self.valve_no = valve
        self.duration = duration
        now = time.localtime(time.time())
        self.start_time = (now.tm_hour*60 + now.tm_min)*60 + now.tm_sec


    def check_if_on(self, day_sec) -> bool:
        return self.start_time <= day_sec and day_sec <= self.start_time + self.duration


class ValveMonitor(threading.Thread):
    valves_state: List[Optional[bool]]
    schedule: List[ValveSchedData]
    override_list: List[ValveOverrideData]

    def __init__(self) -> None:
        super().__init__(name="monitor")
        self.logger = logging.getLogger('monitor')
        self.lock = threading.Lock() # guards override_list, taken by the web threads too
        self.schedule = []
        self.override_list = []
        self.cfg_path = cfg_path
        self.lastmtime = os.path.getmtime(cfg_path)
        # 0 is dummy, None means unknown: the first check drives every valve to its required state
        self.valves_state = [None]*(NUM_VALVES+1)
        self.keepalive_count = 0
        self.last_live_time = time.perf_counter()
        self.configure()
        self.work = True

    def configure(self):
        schedule = []
        with open(self.cfg_path, "r") as f:
            row = 0
            for line in f:
                row += 1
                line = line.strip()
                if len(line)==0:
                    continue
                if line[0]=="#":
                    continue
                # Structure of config file: <value #> <list(day 0: all days, 1-7 specific day)> <time 24 hours hh:mm or hh:mm:ss> <on duration in seconds>
                try:
                    valve, day_list, start_time, duration = line.split()[:4]
                    ivalve, iduration = int(valve), int(duration)
                    idays = [int(day) for day in day_list.split(",")]
                except ValueError:
                    self.logger.error(f"row {row} is not '<valve> <days> <hh:mm> <sec>': {line}")
                    continue
                if ivalve<1 or ivalve>NUM_VALVES:
                    self.logger.error(f"Got value {valve} but valve must be 1 to {NUM_VALVES} in row {row}")
                    continue
                if iduration<1:
                    self.logger.error(f"duration {duration} is less than 1 sec in row {row}")
                    continue
                for iday in idays:
                    if iday<0 or iday>7:
                        self.logger.error(f"day {iday} is illegal in row {row}")
                        continue
                    sched = ValveSchedData()
                    sched.valve_no = ivalve
                    sched.sched_day = iday
                    sched.duration = iduration
                    if not sched.set_start_time(start_time):
                        self.logger.error(f"Start Time {start_time} is illegal in row {row}")
                        break
                    schedule.append(sched)
        self.schedule = schedule
        self.logger.info(f"Loaded {len(schedule)} schedule entries from {self.cfg_path}")

    def run(self):
        while self.work:
            self.keepalive_count += 1
            self.last_live_time = time.perf_counter()
            try:
                lastmtime = os.path.getmtime(self.cfg_path)
                if lastmtime != self.lastmtime:
                    self.lastmtime = lastmtime
                    self.configure()
                self.check()
            except Exception as e:
                self.logger.exception(f"Error {e}, retrying...")
            time.sleep(1)

    def status(self) -> Tuple[float, int]:
        return time.perf_counter()-self.last_live_time, self.keepalive_count

    def stop(self):
        self.work = False
        self.join()

    def add_override(self, valve: int, duration: int) -> str:
        if valve<1 or valve>NUM_VALVES:
            raise ValueError(f"valve must be 1-{NUM_VALVES}, got: {valve}")
        if duration<1 or duration>MAX_OVERRIDE_SEC:
            raise ValueError(f"duration must be 1-{MAX_OVERRIDE_SEC} sec, got: {duration}")
        with self.lock:
            self.override_list.append(ValveOverrideData(valve, duration))
        return f"Valve {valve} on for {duration} sec"

    def cancel_override(self, valve: int) -> str:
        with self.lock:
            self.override_list = [ov for ov in self.override_list if ov.valve_no!=valve]
        return f"Manual run of valve {valve} stopped"

    @staticmethod
    def get_week_time() -> Tuple[int, int]:
        now = time.localtime(time.time())
        # tm_wday     range [0, 6], Monday is 0, Sunday is 6
        my_week_day = 1 + ((now.tm_wday + 1) % 7) # Sunday is 1, Monday is 2, Saturday is 7
        sec_since_midnight = (now.tm_hour*60 + now.tm_min)*60 + now.tm_sec
        return my_week_day, sec_since_midnight

    def get_ovl(self) -> List[Dict]:
        _, sec_since_midnight = self.get_week_time()
        with self.lock:
            return [dict(ov.__dict__, left=ov.start_time+ov.duration-sec_since_midnight)
                    for ov in self.override_list]

    def check(self):
        my_week_day, sec_since_midnight = self.get_week_time()
        # a valve is open if any of its schedule entries or overrides is active
        req_state = [False]*(NUM_VALVES+1)
        for sched in self.schedule:
            if sched.check_if_on(my_week_day, sec_since_midnight):
                req_state[sched.valve_no] = True

        with self.lock:
            next_list = []
            for override in self.override_list:
                if override.check_if_on(sec_since_midnight):
                    req_state[override.valve_no] = True
                    next_list.append(override)
            self.override_list = next_list # we do not want to keep overrides once they are done.

        self.change_valves(req_state)

    def change_valves(self, req_state: List[bool]):
        '''
         drive only the valves whose state changed, one after the other
        '''
        for v in range(1, NUM_VALVES+1):
            if req_state[v] == self.valves_state[v]:
                continue
            self.drive_valve(v, req_state[v])
            self.valves_state[v] = req_state[v]

    def drive_valve(self, valve: int, is_open: bool):
        pwr, drc = power_port(valve), direction_port(valve)
        self.logger.info(f"Driving valve {valve} to {'open' if is_open else 'close'}")
        turn(pwr, False) # never switch direction while powered
        turn(drc, is_open)
        time.sleep(relay_settle_time)
        try:
            turn(pwr, True)
            time.sleep(change_drive_time)
        finally:
            turn(pwr, False)
            time.sleep(relay_settle_time)
            turn(drc, False)


def as_int(body: dict, key: str) -> int:
    try:
        return int(body[key])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"'{key}' must be an integer")


def check_port(port: int) -> int:
    if port<0 or port>=NUM_PORTS:
        raise ValueError(f"port must be 0-{NUM_PORTS-1}, got: {port}")
    return port


def port_cmd(body: dict) -> str:
    # {"port": n, "action": "on" | "off" | "pulse", "sec": pulse length (default 1)}
    port = check_port(as_int(body, "port"))
    action = body.get("action")
    if action in ("on", "off"):
        turn(port, action == "on")
        return f"Port {port} {action}"
    if action == "pulse":
        sec = float(body.get("sec", 1))
        if sec<=0 or sec>MAX_PULSE_SEC:
            raise ValueError(f"pulse must be up to {MAX_PULSE_SEC} sec, got: {sec}")
        turn(port, True)
        threading.Timer(sec, turn, (port, False)).start()
        return f"Port {port} pulsed for {sec:g} sec"
    raise ValueError(f"action must be on, off or pulse, got: {action}")


def all_off() -> str:
    for p in range(NUM_PORTS):
        turn(p, False)
    return "All ports are off"


def get_state(monitor: ValveMonitor) -> dict:
    tick_age, ticks = monitor.status()
    return {
        "now": time.strftime("%a %d %b %H:%M:%S"),
        "num_valves": NUM_VALVES,
        "gpio_map": list(gpio_map),
        "cfg_path": monitor.cfg_path,
        "monitor": {"tick_age": round(tick_age, 1), "ticks": ticks, "alive": monitor.is_alive()},
        "schedule": [sched.__dict__ for sched in monitor.schedule],
        "overrides": monitor.get_ovl(),
        "valves": monitor.valves_state[1:],
        "ports": [get(p) for p in range(NUM_PORTS)],
    }


def set_logging():
    from logging import handlers
    handler = handlers.RotatingFileHandler('garden.log', maxBytes=20000, backupCount=3)
    formatter = logging.Formatter('%(asctime)s %(levelname)-10.10s [%(name)-15.15s]: %(message)s')
    handler.setFormatter(formatter)
    logging.basicConfig(handlers=[handler, logging.StreamHandler()], force=True)
    logging.getLogger().setLevel(logging.INFO)


def main():
    set_logging()
    for g in range(NUM_PORTS):
        setup(g)
    monitor = ValveMonitor()
    monitor.start()

    get_routes = {
        'state': lambda: get_state(monitor),
    }
    post_routes = {
        'override': lambda b: monitor.add_override(as_int(b, "valve"), as_int(b, "sec")),
        'cancel': lambda b: monitor.cancel_override(as_int(b, "valve")),
        'port': port_cmd,
        'alloff': lambda b: all_off(),
    }
    srv = WebServer(http_port, static_dir, get_routes, post_routes)
    # systemd stops us with SIGTERM: turn it into a clean exit so no relay is left powered
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    logging.getLogger('web').info(f"Serving on port {http_port}")
    try:
        srv.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        srv.server_close()
        monitor.stop() # waits for a valve drive in progress to finish
        all_off()
        logging.getLogger('web').info("Stopped")


if __name__ == "__main__":
    main()
