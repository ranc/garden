---
name: garden-gpio-wiring
description: Authoritative GPIO wiring map for the garden solenoids (4 solenoids, each with a power port and an on/off direction port), BCM pin numbers, active-low relay polarity, and the correct valve drive sequence. Load before touching gpio_linux.py, gpio_nt.py, change_valves(), valve numbering, or anything that turns ports on or off.
---

# GPIO wiring map

## Source of truth (as the user stated it)

Logical ports 0-7 (the index into `gpio_map` in `gpio_linux.py`):

| Logical port | BCM pin | Header pin | Function |
|---|---|---|---|
| 0 | GPIO18 | 12 | **Power**, solenoid 1 |
| 1 | GPIO27 | 13 | **Direction** (on/off select), solenoid 1 |
| 2 | GPIO22 | 15 | **Power**, solenoid 2 |
| 3 | GPIO23 | 16 | **Direction**, solenoid 2 |
| 4 | GPIO24 | 18 | **Power**, solenoid 3 |
| 5 | GPIO25 | 22 | **Direction**, solenoid 3 |
| 6 | GPIO4  | 7  | **Power**, solenoid 4 |
| 7 | GPIO2  | 3  | **Direction**, solenoid 4 |

For solenoid `n` (1-4): `power_port = 2*(n-1)` and `direction_port = 2*(n-1) + 1`.

The BCM-to-header column comes from the standard 40-pin layout. The logical-to-BCM column comes from `gpio_map = (18,27,22,23,24,25,4,2)`.

## Electrical conventions

- **Relays are active-low.** `turn(port, True)` writes `'0'` to `/sys/class/gpio/gpioN/value`, and `False` writes `'1'`. `setup()` exports the pin, sets it as output and turns it off (high).
- **The solenoids are latching.** A pulse moves them and they hold position with no power. The valve hose has 3 wires (from the `garden_server.py` docstring): white = ground, red positive = **open**, black positive = **close**. The direction relay picks which of red/black gets the pulse.
- Direction port ON means open the valve, OFF means close it.
- **Drive power comes from a capacitor:** 4700 µF charged through 1 kΩ from 12 V, so τ = RC = 4.7 s and V(t) = 12·(1 − e^(−t/τ)). Every pulse empties it, and the next pulse must wait for it to recharge. Galcon DC latching solenoids work from 9 V (their controllers use a 9 V battery), which takes 6.5 s to reach. The user chose `CHARGE_TIME = 10` s ("no reason to rush"), which charges to about 10.6 V. `REQUIRED_V` is **derived** from it and is only used for the UI marker. While the power relay is closed the capacitor is empty (the coil loads the 1 kΩ feed down to about 0 V), so charging only starts once power opens again.
- GPIO2 (logical port 7) is the I2C SDA pin and has a fixed 1.8 kΩ pull-up on the board. It reads high (relay off) before `setup()`, which is safe. Don't enable I2C on this Pi, because that would claim the pin.
- Worth checking on real hardware (not verified from code): before `setup()` runs at boot, BCM 18/22-25/27 default to input with a pull-down. If a power relay's input sees that as low, it could pulse a solenoid during boot.

## Drive sequence (per solenoid), `drive_queue.DriveQueue.execute()`

To move solenoid `n` to `state` (True = open):

1. **charging**: wait only if needed, until `last_discharge + CHARGE_TIME`. A stop request, or a newer request for the same valve, cancels the command here without touching any port.
2. **selecting**: `turn(power, False)`, `turn(direction, state)`, then wait `SELECT_LEAD = 0.15` s so the direction relay has settled before power arrives. The user asked for 100-200 ms.
3. **pulsing**: `turn(power, True)` for `PULSE_TIME = 1.0` s, then `turn(power, False)` in a `finally`, and record `last_discharge`. The capacitor is spent long before the second is up; the time just has to be long enough.
4. **releasing**: wait `RELAY_SETTLE = 0.1` s, then `turn(direction, False)`. Now `actual[n] = state`.

Rules:
- **Every power pulse goes through the queue**, one at a time and spaced by the charge time. Nothing else may pulse a power port while the queue is busy.
- Never switch the direction relay while power is on. Power off comes first, then direction.
- Drive only the solenoids whose state changed.
- Leave every port off (high) between drives.
- Back-to-back changes are about 11.25 s apart (10 s charge + 1.25 s drive). A single change after a quiet period starts immediately. The startup sync of 4 valves takes about 35 s (the first drive is immediate).

## How the code implements it

- `drive_queue.py`: the electrical constants (`TAU`, `CHARGE_TIME` (the setting), `REQUIRED_V` (derived), `SELECT_LEAD`, `PULSE_TIME`, `RELAY_SETTLE`), `power_port(v)` / `direction_port(v)`, and the `DriveQueue` thread.
  - `request(valve, open, reason)` sets `target[valve]` and replaces any queued, not yet started command for that valve. If the requested state is already the effective state (the actual state, or the state being driven right now), nothing is queued. If the running command is still charging and the request reverses it, that command is cancelled.
  - `pulse_port(port, sec)` queues a raw power-port test pulse.
  - `note_discharge()` is called when a power port is switched outside the queue.
  - `busy()`, `status()` (capacitor volts, current command and phase, pending list with ETAs, last 10 drives in history, `actual`/`target`), and `stop()` (drops pending commands, finishes a pulse in progress).
  - `last_discharge` starts at `-inf` (never pulsed). A reboot takes longer than the charge time, so the first drive doesn't wait. A quick service restart right after a pulse isn't tracked, because the time isn't persisted.
- `garden_server.py`: `ValveMonitor.change_valves()` only calls `queue.request()` for valves whose required state differs from `queue.target`. The reason is one of `startup sync`, `schedule`, `manual`, `manual stop` or `watering done`. The monitor never blocks on a drive.
- `target` starts as `[None]*5`, so the first tick requests all 4 valves (normally closed). That syncs the latching valves after a restart.
- Valve numbers are validated as 1-4 in `configure()` and `ValveMonitor.add_override()`. The web UI gets `num_valves` and `gpio_map` from `/api/state`.
- Test endpoints: a `pulse` on a **power** port (even) is queued. `on`/`off`, and pulses on direction ports, are refused while the queue is busy. Switching a power port on/off calls `note_discharge()`. `alloff` is always allowed (safety).
- `gpio_linux.get(port)` / `gpio_nt.get(port)` read the port state: True = on (pin low), None = not exported.

Don't change `gpio_map` unless the user reports a physical rewiring.

## Testing without hardware

On Windows, `gpio_nt.turn` prints `[timestamp] setting #port: bool`. Run `garden_server.py`, POST `{"valve":2,"sec":5}` to `http://localhost:8080/api/override` (or use the Manual tab), and check that the printed sequence is: (wait for charge) port 2 → False, port 3 → True, (0.15 s) port 2 → True, (1 s) port 2 → False, (0.1 s) port 3 → False. The Activity panel shows each phase. When the override expires you should see the close sequence with port 3 staying False. For fast unit tests, patch the `drive_queue` constants (for example `CHARGE_TIME = 0.5`) and pass a recording `turn` function to `DriveQueue`.
