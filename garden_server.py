import os
import errno

path = "/home/pi/pipe"
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

try:
  os.mkfifo(path)
except OSError as ex:
  if ex.errno != errno.EEXIST:
     raise

count=0
flag=True
while True:
 print("reading from pipe...")
 with open(path) as f:
   line=f.readline()
 print("got:", line)
 turn(0, flag)
 with open(path, "w") as f:
    f.write(f"response {count}\n")
 count += 1
 flag = not flag


