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
- Drive pulse length: `change_drive_time = 3` seconds.
- GPIO2 (logical port 7) is the I2C SDA pin and has a fixed 1.8 kΩ pull-up on the board. It reads high (relay off) before `setup()`, which is safe. Don't enable I2C on this Pi, because that would claim the pin.
- Worth checking on real hardware (not verified from code): before `setup()` runs at boot, BCM 18/22-25/27 default to input with a pull-down. If a power relay's input sees that as low, it could pulse a solenoid during boot.

## Correct drive sequence (per solenoid)

To move solenoid `n` to `state` (True = open):

1. `turn(direction_port, state)` selects the polarity.
2. Short settle delay (for example 0.1 s) so the direction relay contacts close before power arrives.
3. `turn(power_port, True)`, wait `change_drive_time`, then `turn(power_port, False)`.
4. `turn(direction_port, False)` releases the direction relay to save power.

Rules:
- Never switch the direction relay while power is on (it arcs the contacts and gives a partial pulse). Power off comes first, then direction.
- Drive only the solenoids whose state changed. Re-pulsing an unchanged latching valve is harmless, but it wastes time and relay life.
- Drive them one after another, not all at once, to limit current draw on the supply.
- Leave every port off (high) between drives.

## How the code implements it

- `garden_server.py`: `NUM_VALVES = 4`, `NUM_PORTS = 8`, `power_port(v)`, `direction_port(v)`, and `ValveMonitor.drive_valve()` follows the sequence above. It uses `relay_settle_time = 0.1` and a `try/finally` so power is always turned off.
- `change_valves(req_state)` drives only the valves whose state differs from `valves_state`.
- `valves_state` starts as `[None]*5`, so the first tick after startup drives all 4 valves to their required state (normally closed, about 13 s). That syncs the latching valves after a restart.
- Valve numbers are validated as 1-4 in `configure()` and `ValveMonitor.add_override()`. The web UI gets `num_valves` and `gpio_map` from `/api/state`, so there's nothing to keep in sync.
- The raw test endpoints `POST /api/port` (on/off/pulse) and `POST /api/alloff` work on logical ports 0-7 and bypass the monitor (see `garden-web-api`).
- `gpio_linux.get(port)` / `gpio_nt.get(port)` read the port state: True = on (pin low), None = not exported.

Don't change `gpio_map` unless the user reports a physical rewiring.

## Testing without hardware

On Windows, `gpio_nt.turn` prints `[timestamp] setting #port: bool`. Run `garden_server.py`, POST `{"valve":2,"sec":5}` to `http://localhost:8080/api/override` (or use the Manual tab), and check that the printed sequence is: port 3 → True, port 2 → True, (3 s), port 2 → False, port 3 → False. When the override expires you should see the matching close sequence with port 3 staying False.
