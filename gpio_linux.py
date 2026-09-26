import os


gpio_map=(18,27,22,23,24,25,4,2)

def turn(gpio:int, is_on: bool):
    gpiofile = f"/sys/class/gpio/gpio{gpio_map[gpio]}/value"
    if not os.path.exists(gpiofile):
        print("setting gpio", gpio_map[gpio])
        setup(gpio)
    with open(gpiofile, "w") as f:
        f.write('0' if is_on else '1')


def setup(gpio:int):    
    gpiofile = f"/sys/class/gpio/export"
    try:
      with open(gpiofile, "w") as f:
        f.write(str(gpio_map[gpio]))
    except Exception as ex:
      print(f"Warning exporting gpio {gpio} device {gpio_map[gpio]}:", ex)
    try:
      gpiofile = f"/sys/class/gpio/gpio{gpio_map[gpio]}/direction"
      with open(gpiofile, "w") as f:
        f.write("out")
    except Exception as ex:
      print(f"Warning setting gpio direction {gpio} device {gpio_map[gpio]}:", ex)
    turn(gpio, False)



def get(gpio:int):
    '''returns True if the port is on (active low), None if it is not set up'''
    gpiofile = f"/sys/class/gpio/gpio{gpio_map[gpio]}/value"
    if not os.path.exists(gpiofile):
        return None
    with open(gpiofile, "r") as f:
        return f.read().strip() == '0'
