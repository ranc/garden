gpio_map=(18,27,22,23,24,25,4,2)

def setup(gpio:int):    
    gpiofile = f"/sys/class/gpio/export"
    with open(gpiofile, "w") as f:
        f.write(str(gpio_map[gpio]))
    gpiofile = f"/sys/class/gpio/gpio{gpio_map[gpio]}/direction"
    with open(gpiofile, "w") as f:
        f.write("out")


def turn(gpio:int, is_on: bool):
    gpiofile = f"/sys/class/gpio/gpio{gpio_map[gpio]}/value"
    if not os.path.exists(gpiofile):
        print("setting gpio", gpio_map[gpio])
        setup(gpio)
    with open(gpiofile, "w") as f:
        f.write('0' if is_on else '1')

