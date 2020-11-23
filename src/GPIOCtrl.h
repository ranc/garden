//
// Created by rancohen on 22/11/2020.
//

#ifndef GARDEN_GPIOCTRL_H
#define GARDEN_GPIOCTRL_H

#include "Override.h"

class GPIOCtrl {
    std::string _gpioCtrlFilename;
    Override _override;
public:
    explicit GPIOCtrl(int gpioIndex);

    bool stat();

    void turn(bool is_on);

    void check();

    Override &override() { return _override;}
};

struct day_entry_t {
    int day;
    int start_min;
    int end_min;
};

#endif //GARDEN_GPIOCTRL_H
