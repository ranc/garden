#include <iostream>
#include "GPIOCtrl.h"

#define HAS_2_ARGS (argc > 2)
#define HAS_3_ARGS (argc > 3)
#define HAS_4_ARGS (argc > 3)

int main(int argc, char *argv[])
{
    if (argc < 2 || 0 == strcmp(argv[1], "stat")) {
        for (int i=0; i<8; i++)
        {
            auto *pGpio = new GPIOCtrl(i+1);
            std::cout << (i+1) << ": " << (pGpio->stat() ? "on" : "off");
        }
        return 0;
    }
    GPIOCtrl *pGpio = nullptr;
    if (HAS_2_ARGS)
    {
        int gi = atoi(argv[2]);
        if (gi<1 || gi>8)
        {
            std::cerr << "please specify gpio index from 1 to 8.\n";
            return 2;
        }
        pGpio = new GPIOCtrl(gi);
    }
    if (0 == strcmp(argv[1], "on") && pGpio!=nullptr) {
        pGpio->turn(true);
        return 0;
    }
    if (0 == strcmp(argv[1], "off") && pGpio!=nullptr) {
        pGpio->turn(false);
        return 0;
    }
    if (0 == strcmp(argv[1], "check")) {
        // read gpioDB
        check();
    }
    if (0 == strcmp(argv[1], "override") && pGpio!=nullptr) { // override <gpio> <min | clear | print> <1=on/0=off>
        if (!HAS_3_ARGS) return -1;
        if (0 == strcmp(argv[3], "clear")) {
            pGpio->override().clear();
            return 0;
        }
        if (0 == strcmp(argv[3], "print")) {
            pGpio->override().clear();
            return 0;
        }
        if (!HAS_4_ARGS) return -1;
        int min = atoi(argv[2]);
        int is_on = atoi(argv[3]);
        pGpio->override().set(min, is_on);
        return 0;
    }
    return -1;
}

