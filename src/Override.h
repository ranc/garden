//
// Created by rancohen on 22/11/2020.
//

#ifndef GARDEN_OVERRIDE_H
#define GARDEN_OVERRIDE_H

#include <string>

#ifdef DEBUG
#define LOG(x) printf x
#else
#define LOG(x)
#endif


#define OVERIDE_BASE_FILENAME "/tmp/override."

class Override {
    std::string _overrideFileName;
public:
    explicit Override(int gpioIndex);

    bool is_exist();

    void clear();

    void set(int min, bool is_on);

    void get_period(time_t &start, time_t &end, bool &is_on);

    void print();

    bool check_override(bool &is_on);

};


#endif //GARDEN_OVERRIDE_H
