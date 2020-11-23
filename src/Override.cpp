//
// Created by rancohen on 22/11/2020.
//
#include <sstream>
#include <filesystem>
#include <iostream>

#include "Override.h"
#include "file.h"

#ifndef WIN32
#define _stat stat
#endif


namespace fs = std::filesystem;

Override::Override(int gpioIndex) {
    std::ostringstream stst;
    stst << OVERIDE_BASE_FILENAME << gpioIndex;
    _overrideFileName = stst.str();
}

bool Override::is_exist() {
    std::fstream fs;
    fs.open(_overrideFileName);
    return fs.good();

}

void Override::clear() {
    if (is_exist())
        remove(_overrideFileName.c_str());
}

void Override::set(int min, bool is_on) {
    fstr fs(_overrideFileName,  std::fstream::out);
    fs << min << " " << is_on << std::endl;
}

void Override::get_period(time_t &start, time_t &end, bool &is_on) {

    fs::file_time_type ftime = fs::last_write_time(_overrideFileName);
    fstr fs(_overrideFileName, std::fstream::in);

    start = ftime.time_since_epoch().count();
    int min=0;
    is_on=0;
    fs >> min;
    fs >> is_on;
    end = start+min*60;
}

void Override::print() {
    if (!is_exist())
    {
        std::cout << "0" << std::endl;
        return;
    }
    time_t start,end;
    bool is_on;
    get_period(start, end, is_on);
    std::cout << "1 " << start << " " << end << " " << is_on << std::endl;
}

bool Override::check_override(bool &is_on) {
    if (!is_exist()) return false;
    time_t start,end;
    time_t now;

    get_period(start, end, is_on);
    time (&now);
    if (start<=now && now < end)
    {
        LOG(("override is %d for %d sec\n", is_on, end-start));
        return true;
    }
    LOG(("out of override period, clearing entry.\n"));
    clear(); // override period is over
    return false;
}
