//
// Created by rancohen on 23/11/2020.
//

#ifndef GARDEN_SCHEDULER_H
#define GARDEN_SCHEDULER_H


#include <vector>

struct SchedEntry {
    int day;
    int start_min;
    int end_min;

    [[nodiscard]] inline bool in_range(int today, int now_min) const
    {
        if (today != day) return false;
        return start_min <= now_min && now_min < end_min;
    }
};

class Scheduler {
    std::vector<SchedEntry> _schedule[8];

public:
    explicit Scheduler();

    std::vector<int> getGPIOList();

    std::vector<SchedEntry> getSchedule(int i);
};


#endif //GARDEN_SCHEDULER_H
