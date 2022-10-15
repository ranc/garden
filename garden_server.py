import os
from symbol import pass_stmt
from telnetlib import SE
import threading
import time

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

class ValveMonitor(threading.Thread):
    def __init__(self) -> None:
        super().__init__()
        with open(cfg_path, "r") as f:
            for line in f:
                # Structure of config file: <value #> <day 0: all days, 1-7 specific day> <time 24 hours hh:mm or hh:mm:ss> <on duration in seconds>
                valve, day, start_time, period = line.split()[:4]
                print(valve, day, start_time, period)

        self.work = True

    def run(self):
        while self.work:
            self.check(time.localtime(time.time()))
            time.sleep(1)


    def check(self, now: time.struct_time):        
        # tm_wday     range [0, 6], Monday is 0, Sunday is 6
        my_week_day = 1 + ((now.tm_wday + 1) % 7) # Sunday is 1, Monday is 2, Saturday is 7        
        pass


if __name__ == "__main__":
    setup(0)
    COMMANDS = {
        'on': lambda args : turn(0, True),
        'off': lambda args: turn(0, False),
        'get': lambda args: ','.join(args)
    }
    srv = Server(COMMANDS)
    srv.wait_for_clients()
    

