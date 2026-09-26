import datetime

from gpio_linux import gpio_map

_state = {}


def setup(gpio:int):
    now = datetime.datetime.now()
    print(f"[{now}] setting gpio #", gpio)
    _state[gpio] = False


def turn(gpio:int, is_on: bool):
    now = datetime.datetime.now()
    print(f"[{now}] setting #{gpio}:", is_on)
    _state[gpio] = is_on


def get(gpio:int):
    return _state.get(gpio)
