//
// Created by rancohen on 22/11/2020.
//

#ifndef GARDEN_GPIOCTRL_H
#define GARDEN_GPIOCTRL_H

#include "Override.h"
#include "Scheduler.h"

class GPIOCtrl {
    std::string _gpioCtrlFilename;
    Override _override;
    std::vector<SchedEntry> _schedule;

public:
    explicit GPIOCtrl(int gpioIndex);

    bool stat();

    void turn(bool is_on);

    void check();

    Override &override() { return _override;}

    void setSched(const std::vector<SchedEntry> &entry);
};

#endif //GARDEN_GPIOCTRL_H
