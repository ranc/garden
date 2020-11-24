#include <iostream>
#include <cassert>
#include "GPIOCtrl.h"
#include "Scheduler.h"
#include "file.h"

#define HAS_2_ARGS (argc > 2)
#define HAS_3_ARGS (argc > 3)
#define HAS_4_ARGS (argc > 3)

int main(int argc, char *argv[])
{
    try {
        if (argc < 2 || 0 == strcmp(argv[1], "stat")) {
            for (int i = 0; i < 8; i++) {
                auto *pGpio = new GPIOCtrl(i + 1);
                std::cout << (i + 1) << ": " << (pGpio->stat() ? "on" : "off");
            }
            return 0;
        }
        GPIOCtrl *pGpio = nullptr;
        if (HAS_2_ARGS) {
            int gi = atoi(argv[2]);
            if (gi < 1 || gi > 8) {
                std::cerr << "please specify gpio index from 1 to 8.\n";
                return 2;
            }
            pGpio = new GPIOCtrl(gi);
        }
        if (0 == strcmp(argv[1], "on") && pGpio != nullptr) {
            pGpio->turn(true);
            return 0;
        }
        if (0 == strcmp(argv[1], "off") && pGpio != nullptr) {
            pGpio->turn(false);
            return 0;
        }
        if (0 == strcmp(argv[1], "check")) {
            // read gpioDB
            Scheduler sched;
            GPIOCtrl *gpio[8] = {nullptr};
            for (int i : sched.getGPIOList()) {
                assert((i >= 1 && i <= 8) && "GPIO must be 1 to 8");
                int gi=i-1;
                if (gpio[gi] == nullptr) gpio[gi] = new GPIOCtrl(i);
                gpio[gi]->setSched(sched.getSchedule(i));
            }
            tm ti = get_current_time();
            int now_min = ti.tm_hour*60+ti.tm_min;
            for (auto & pCtrl : gpio) {
                if (pCtrl != nullptr)
                    pCtrl->check(ti.tm_wday+1, now_min);
            }
            return 0;
        }

        if (0 == strcmp(argv[1], "override") &&
            pGpio != nullptr) { // override <gpio> <min | clear | print> <1=on/0=off>
            if (!HAS_3_ARGS) return -1;
            if (0 == strcmp(argv[3], "clear")) {
                pGpio->override().clear();
                return 0;
            }
            if (0 == strcmp(argv[3], "print")) {
                pGpio->override().print();
                return 0;
            }
            if (!HAS_4_ARGS) return -1;
            int min = atoi(argv[2]);
            int is_on = atoi(argv[3]);
            pGpio->override().set(min, is_on);
            return 0;
        }
    } catch (const std::exception &exp) {
        std::cerr << exp.what();
    }
    return -1;
}

