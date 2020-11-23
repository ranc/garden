//
// Created by rancohen on 23/11/2020.
//

#include <cassert>
#include <sstream>
#include "Scheduler.h"
#include "file.h"

#define SCHEDULER_DATABASE "/home/pi/garder_schedule."

/* DB file:
 * each line is in the form of : <list of gpio's, CSV>: <list of day's, CSV> : hh:mm - hh:mm
 * For example, gpio no 1,3,4 should be turned on each Sunday & wednesday from 6am to 6:10:
 *         1,3,4 : 1,4 : 0600-06:10
 */

Scheduler::Scheduler() {
    FileStream dbf(SCHEDULER_DATABASE);

    std::string line;
    int lineNo=0;
    while (std::getline(dbf, line))
    {
        lineNo++;
        line = trim(line);
        if (line[0]=='#') continue;
        // parse the three main sections delimited by ':'
        auto args = explode(line, ':');
        if (args.size()!=3)
        {
           Throw << "line " << lineNo << " is not in the right syntax, expecting 3 values with ':' delimiter";
        }
        auto csvList = trim(args[0]);
        auto gpioStrList = explode(csvList, ',');
        csvList = trim(args[1]);
        auto dayStrList = explode(csvList, ',');
        csvList = trim(args[2]);
        // parse the time
        auto periodStrList = explode(csvList, '-');
        if (periodStrList.size() != 2)
        {
            Throw << "period must containt start time - stop time, got: " << csvList;
        }
        int start_min = strtime_to_min(periodStrList[0]);
        int end_min = strtime_to_min(periodStrList[1]);

        //parse the days, create an entry per day
        std::vector<SchedEntry> sched;
        for (const auto& s: dayStrList)
        {
            auto &de = sched.emplace_back();
            de.day = atoi(trim(s).c_str());
            de.start_min = start_min;
            de.end_min = end_min;
        }

        for (const auto& s : gpioStrList) {
            int gi = atoi(trim(s).c_str());
            if (gi<1 || gi>8)
            {
                Throw << "GPIO number must be from 1 to 8, got: "<<gi ;
            }
            // append to scheduler
            _schedule[gi-1].insert(_schedule[gi-1].end(), sched.begin(), sched.end());
        }
    }

}

std::vector<int> Scheduler::getGPIOList() {
    std::vector<int> ret;
    for (int i=0; i<8; i++)
        if (!_schedule[i].empty())
            ret.push_back(i+1);
    return ret;
}

std::vector<SchedEntry> Scheduler::getSchedule(int i) {
    assert((i>=1 && i<=8) && "GPIO must be 1 to 8");
    return _schedule[i-1];
}
