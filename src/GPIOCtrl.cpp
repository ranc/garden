//
// Created by rancohen on 22/11/2020.
//
#include <stdexcept>
#include <sstream>
#include <fstream>

#include "GPIOCtrl.h"
#include "file.h"

static int GPIO_MAP[] = {18, 27, 22, 23, 24, 25, 4, 2};
#define GPIO "/sys/class/gpio/gpio"

GPIOCtrl::GPIOCtrl(int gpioIndex):_override(gpioIndex) {
    if (gpioIndex < 1 || gpioIndex > 8) throw std::runtime_error("GPIO index must be 1 to 8");
    int gpio_port = GPIO_MAP[gpioIndex - 1];
    std::ostringstream stst;
    stst << GPIO << gpio_port <<"/value";
    _gpioCtrlFilename = stst.str();
}

void GPIOCtrl::turn(bool is_on) {
    FileStream fs(_gpioCtrlFilename, std::fstream::out);
    fs << (is_on ? "0": "1");
    fs.close();
}

void GPIOCtrl::check() {
    bool is_on=false;
    if (_override.check_override(is_on))
    {
        turn(is_on);
        return;
    }

}

bool GPIOCtrl::stat() {
    FileStream fs(_gpioCtrlFilename, std::fstream::in);
    char c;
    fs >> c;
    return c=='0';
}

void GPIOCtrl::setSched(const std::vector<SchedEntry> &entry) {
    _schedule = entry;
}
