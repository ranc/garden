import json
import logging
import os
import threading
import time
from typing import List, Tuple

from server import Server

if os.name == 'nt':
    from gpio_nt import turn, setup
    cfg_path = "test.cfg"
else:
    from gpio_linux import turn, setup
    cfg_path = "/home/pi/garden_sched.cfg"

''' strcuture of GPIO:
    GPIO 0: main power driver for changing valves, turns on when a valve need to change state
    GPIO n: the command for valve *n*, on: to turn on, off: to turn off.
        For Example:
            if at time *t* we need to turn on valve 2, while other valve 1 should still be on and valve 3 needs to be off, then:
                1. we setup:
                    gpio 1: on
                    gpio 2: on
                    gpio 3: off
                2. we turn on gpio 0 to drive change (only gpio 2 will change)
                3. wait for 1 sec for change to take effect
                4. we turn off gpio 0, and then all other gpio to save power.

'''

class ValveSchedData:
    valve_no: int # 1-7
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
    valve_no: int # 1-7
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
    valves_state: List[bool]
    schedule: List[ValveSchedData]
    override_list: List[ValveOverrideData]
    
    def __init__(self) -> None:
        super().__init__()
        self.schedule = []
        self.override_list = []
        self.valves_state = []
        self.cfg_path = cfg_path
        self.lastmtime = os.path.getmtime(cfg_path)
        self.valves_state = [False]*8 # 0 is dummy     
        self.keepalive_count = 0
        self.last_live_time = time.perf_counter()
        self.configure()
        self.work = True

    def configure(self):
        self.schedule = []
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
                valve, day_list, start_time, duration = line.split()[:4]
                for day in day_list.split(","):
                    iday = int(day)
                    if iday<0 or iday>7:
                        print(f"day {day} is illegal in row {row}")
                        break
                    iduration = int(duration)
                    if iduration<1:
                        print(f"duration {duration} is less than 1 sec in row {row}")
                        break
                    ivalve = int(valve)
                    if ivalve<1 or ivalve>7:
                        print(f"Got value {valve} but valve must be 1 to 7 in row {row}")
                        break
                    sched = ValveSchedData()
                    sched.valve_no = ivalve
                    sched.sched_day = iday
                    sched.duration = iduration
                    if not sched.set_start_time(start_time):
                        print(f"Start Time {start_time} is illegal in row {row}")
                        del sched
                        break
                    self.schedule.append(sched)                   

    def run(self):
        while self.work:
            self.keepalive_count += 1
            self.last_live_time = time.perf_counter()
            lastmtime = os.path.getmtime(self.cfg_path)
            if lastmtime != self.lastmtime:
                self.lastmtime = lastmtime                
                self.configure()
            try:
                self.check(time.localtime(time.time()))
            except Exception as e:
                print(f"Error {e}, retrying...")
            time.sleep(1)

    def status(self):
        return time.perf_counter()-self.last_live_time, self.keepalive_count
    
    def stop(self):
        self.work = False
        self.join()

    def override(self, valve: int, duration: int):
        self.override_list.append(ValveOverrideData(valve, duration))

    def override_cmd(self, args: List[str]) -> str:
        if len(args) != 2:
            return "please provide valve no (1-7) and duration (in sec)"
        ivalve = int(args[0])
        iduration = int(args[1])
        if ivalve<1 or ivalve>7:
            return f"please provide valve no (1-7), got: {args[0]}"
        if iduration<1:
            return f"please provide a positive duration, got: {args[1]}"
        if iduration>3*3600:
            return f"override duration is limited to 3 hours, got: {args[1]}"
        self.override(ivalve, iduration)
        return f"Override of {ivalve} set for {iduration} sec"

    def check(self, now: time.struct_time):        
        # tm_wday     range [0, 6], Monday is 0, Sunday is 6
        my_week_day = 1 + ((now.tm_wday + 1) % 7) # Sunday is 1, Monday is 2, Saturday is 7
        sec_since_midnight = (now.tm_hour*60 + now.tm_min)*60 + now.tm_sec
        #print("check:", my_week_day, sec_since_midnight)
        req_state = [False]*8
        for sched in self.schedule:
            is_on = sched.check_if_on(my_week_day, sec_since_midnight)
            req_state[sched.valve_no] = is_on
        
        next_list = []
        for override in self.override_list:
            is_on = override.check_if_on(sec_since_midnight)
            req_state[override.valve_no] = is_on            
            if is_on:
                next_list.append(override)

        self.override_list = next_list # we do not want to keep overrides once they are done.

        if req_state != self.valves_state:
            self.valves_state = req_state
            self.change_valves()

        
    def change_valves(self):
        '''
         if at time *t* we need to turn on valve 2, while other valve 1 should still be on and valve 3 needs to be off, then:
                1. we setup:
                    gpio 1: on
                    gpio 2: on
                    gpio 3: off
                2. we turn on gpio 0 to drive change (only gpio 2 will change)
                3. wait for 1 sec for change to take effect
                4. we turn off gpio 0, and then all other gpio to save power.
        '''
        print("Driving change to:", self.valves_state)
        for v,s in enumerate(self.valves_state):
            if v==0:
                continue
            turn(v,s)
        turn(0, True)  # drive the change (an all valves, but just the new state will change)
        time.sleep(1)
        # turn off everything, starting with 0
        for v in range(len(self.valves_state)):
            turn(v, False)


def set_logging():
    from logging import handlers
    handler = handlers.RotatingFileHandler('garden.log', maxBytes=20000, backupCount=3)
    formatter = logging.Formatter('%(asctime)s %(levelname)-10.10s [%(name)-15.15s]: %(message)s')
    handler.setFormatter(formatter)
    logging.basicConfig(handlers=[handler], force=True)
    logging.getLogger().setLevel(logging.INFO)


if __name__ == "__main__":
    set_logging()
    for g in range(8):
        setup(g)
    monitor = ValveMonitor()
    monitor.start()
    COMMANDS = {
        'stop': monitor.stop,
        'on': lambda args : turn(0 if len(args)==0 else int(args[0]), True),
        'off': lambda args: turn(0 if len(args)==0 else int(args[0]), False),
        'get': lambda args: json.dumps([sched.__dict__ for sched in monitor.schedule], indent=4),
        'override': lambda args: monitor.override_cmd(args),
        'status': lambda args: monitor.status()
    }

    srv = Server(COMMANDS)
    srv.wait_for_clients()
    monitor.stop()
    

