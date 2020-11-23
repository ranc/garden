//
// Created by rancohen on 22/11/2020.
//

#include "GPIOCtrl.h"
#include <sstream>
#include <stdexcept>
#include "file.h"

fstr::fstr(const std::string &filename, std::ios_base::openmode mode) {
    open(filename, mode);
    if (!is_open())
        throw std::runtime_error("Error opening GPIO file " +filename);
}

fstr::~fstr() {
    close();
}
