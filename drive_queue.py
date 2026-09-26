import collections
import itertools
import logging
import math
import threading
import time
from typing import Callable, Dict, List, Optional

'''
    All solenoid drives go through this queue, one at a time.

    The solenoids are pulsed from a 4700uF capacitor charged through 1K from 12V (tau = RC = 4.7 sec),
    so after every pulse we must wait for the capacitor to recharge before the next one:
        V(t) = 12 * (1 - e^(-t/tau))
    Galcon DC latching solenoids work from a 9V battery (reached after ~6.5 sec), we wait CHARGE_TIME
    for a comfortable margin: 10 sec -> ~10.6V.
    The wait is measured from the last pulse, so a drive only waits if the previous one was recent.

    Drive sequence for valve n (ports: power 2(n-1), direction 2(n-1)+1, see garden-gpio-wiring):
        1. charging:  wait until CHARGE_TIME passed since the last pulse (no wait if it already did)
        2. selecting: set the direction port, wait SELECT_LEAD so it settles before power arrives
        3. pulsing:   power port on for PULSE_TIME (the capacitor dumps into the coil), then off
        4. releasing: wait RELAY_SETTLE, direction port off
'''

SUPPLY_V = 12.0
CHARGE_R = 1000.0 # ohm
CHARGE_C = 4700e-6 # farad
TAU = CHARGE_R * CHARGE_C # 4.7 sec
CHARGE_TIME = 10.0 # sec from the end of one pulse to the next
REQUIRED_V = SUPPLY_V * (1 - math.exp(-CHARGE_TIME / TAU)) # ~10.6V, the charge we wait for
SELECT_LEAD = 0.15 # direction relay settles before the power relay closes
PULSE_TIME = 1.0 # the capacitor is empty long before this, it just has to be long enough
RELAY_SETTLE = 0.1 # power relay opens before the direction relay is released
HISTORY_LEN = 10


def power_port(valve: int) -> int:
    return 2 * (valve - 1)


def direction_port(valve: int) -> int:
    return 2 * (valve - 1) + 1


class DriveCommand:
    _ids = itertools.count(1)

    def __init__(self, kind: str, reason: str, valve: int = 0, is_open: bool = False, port: int = -1, sec: float = 0):
        self.id = next(self._ids)
        self.kind = kind # 'valve' or 'pulse' (raw power port test)
        self.valve = valve
        self.is_open = is_open
        self.port = port
        self.sec = sec
        self.reason = reason
        self.queued_at = time.time()
        self.phase = "queued"
        self.cancelled = False
        self.done_eta = 0.0 # monotonic time the command is expected to finish

    def describe(self) -> Dict:
        return {"id": self.id, "kind": self.kind, "valve": self.valve, "open": self.is_open,
                "port": self.port, "reason": self.reason, "phase": self.phase}


class DriveQueue(threading.Thread):
    def __init__(self, num_valves: int, turn: Callable[[int, bool], None]) -> None:
        super().__init__(name="drive-queue")
        self.logger = logging.getLogger('queue')
        self.turn = turn
        self.cond = threading.Condition()
        self.pending: List[DriveCommand] = []
        self.current: Optional[DriveCommand] = None
        self.history = collections.deque(maxlen=HISTORY_LEN)
        # index 0 unused. actual: last state driven, target: last state requested; None = unknown
        self.actual: List[Optional[bool]] = [None] * (num_valves + 1)
        self.target: List[Optional[bool]] = [None] * (num_valves + 1)
        # a (re)boot takes longer than CHARGE_TIME, so at start the capacitor is charged: no pulse yet
        self.last_discharge = float("-inf")
        self.work = True

    # ---------- producers (monitor / web threads) ----------
    def request(self, valve: int, is_open: bool, reason: str):
        '''ask for a valve state; replaces a queued, not yet started, command for the same valve'''
        with self.cond:
            self.target[valve] = is_open
            self.pending = [c for c in self.pending if not (c.kind == 'valve' and c.valve == valve)]
            running = self.current if self.current and self.current.kind == 'valve' and self.current.valve == valve else None
            if running and running.phase == "charging" and running.is_open != is_open:
                # still waiting for the capacitor, nothing was driven yet: just drop it
                running.cancelled = True
                self.logger.info(f"Cancelled {'open' if running.is_open else 'close'} valve {valve} before it started")
                running = None
            effective = running.is_open if running else self.actual[valve]
            if effective != is_open:
                self.pending.append(DriveCommand('valve', reason, valve=valve, is_open=is_open))
                self.logger.info(f"Queued {'open' if is_open else 'close'} valve {valve} ({reason}), {len(self.pending)} in queue")
            self.cond.notify_all()

    def pulse_port(self, port: int, sec: float, reason: str = "test"):
        with self.cond:
            self.pending.append(DriveCommand('pulse', reason, port=port, sec=sec))
            self.cond.notify_all()

    def note_discharge(self):
        '''a power port was switched outside the queue (test page), the capacitor may be empty'''
        with self.cond:
            self.last_discharge = time.monotonic()

    def busy(self) -> bool:
        with self.cond:
            return self.current is not None or bool(self.pending)

    def stop(self):
        '''finishes the command in progress (unless it's still charging), drops the rest'''
        with self.cond:
            self.work = False
            self.pending = []
            self.cond.notify_all()
        self.join()

    # ---------- consumer ----------
    def run(self):
        while True:
            with self.cond:
                while self.work and not self.pending:
                    self.cond.wait()
                if not self.work:
                    return
                cmd = self.current = self.pending.pop(0)
                self.cond.notify_all()
            ok = False
            try:
                ok = self.execute(cmd)
            except Exception:
                self.logger.exception(f"drive {cmd.describe()} failed")
            finally:
                with self.cond:
                    self.current = None
                    if ok:
                        self.history.appendleft(dict(cmd.describe(), finished=time.strftime("%H:%M:%S")))

    def charge_ready_at(self) -> float:
        return self.last_discharge + CHARGE_TIME

    def execute(self, cmd: DriveCommand) -> bool:
        power = cmd.port if cmd.kind == 'pulse' else power_port(cmd.valve)
        direction = None if cmd.kind == 'pulse' else direction_port(cmd.valve)
        pulse = cmd.sec if cmd.kind == 'pulse' else PULSE_TIME

        cmd.phase = "charging"
        with self.cond:
            cmd.done_eta = max(time.monotonic(), self.charge_ready_at()) + SELECT_LEAD + pulse + RELAY_SETTLE
            # interruptible: a stop request or a newer request for the valve drops the command
            while self.work and not cmd.cancelled and time.monotonic() < self.charge_ready_at():
                self.cond.wait(timeout=self.charge_ready_at() - time.monotonic())
            if not self.work or cmd.cancelled:
                return False
            cmd.phase = "selecting" # under the lock, so request() never cancels a started drive

        self.turn(power, False) # never switch direction while powered
        if direction is not None:
            self.logger.info(f"Driving valve {cmd.valve} to {'open' if cmd.is_open else 'close'} ({cmd.reason})")
            self.turn(direction, cmd.is_open)
        time.sleep(SELECT_LEAD)

        cmd.phase = "pulsing"
        try:
            self.turn(power, True)
            time.sleep(pulse)
        finally:
            self.turn(power, False)
            with self.cond:
                self.last_discharge = time.monotonic()

        cmd.phase = "releasing"
        time.sleep(RELAY_SETTLE)
        if direction is not None:
            self.turn(direction, False)
            with self.cond:
                self.actual[cmd.valve] = cmd.is_open
        return True

    # ---------- status for the UI ----------
    def status(self) -> Dict:
        with self.cond:
            now = time.monotonic()
            elapsed = now - self.last_discharge
            pulsing = self.current is not None and self.current.phase == "pulsing"
            volts = 0.0 if pulsing else SUPPLY_V * (1 - math.exp(-elapsed / TAU))
            ready_in = max(0.0, self.charge_ready_at() - now)

            current = None
            next_ready = self.charge_ready_at()
            if self.current:
                current = self.current.describe()
                current["eta"] = round(max(0.0, self.current.done_eta - now), 1)
                if self.current.phase == "charging":
                    current["ready_in"] = round(ready_in, 1)
                next_ready = max(self.current.done_eta, now) + CHARGE_TIME
            pending = []
            for cmd in self.pending:
                pulse = cmd.sec if cmd.kind == 'pulse' else PULSE_TIME
                done = max(now, next_ready) + SELECT_LEAD + pulse + RELAY_SETTLE
                pending.append(dict(cmd.describe(), eta=round(done - now, 1)))
                next_ready = done + CHARGE_TIME

            return {
                "capacitor": {"volts": round(volts, 1), "required": round(REQUIRED_V, 1), "supply": SUPPLY_V,
                              "ready": ready_in == 0 and not pulsing, "ready_in": round(ready_in, 1)},
                "charge_time": round(CHARGE_TIME, 1),
                "current": current,
                "pending": pending,
                "history": list(self.history),
                "actual": self.actual[1:],
                "target": self.target[1:],
            }
