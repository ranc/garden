import datetime


def setup(gpio:int):
    now = datetime.datetime.now()
    print(f"[{now}] setting gpio #", gpio)


def turn(gpio:int, is_on: bool):
    now = datetime.datetime.now()
    print(f"[{now}] setting #{gpio}:", is_on)

