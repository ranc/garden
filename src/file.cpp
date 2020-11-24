//
// Created by rancohen on 22/11/2020.
//

#include <sstream>
#include <stdexcept>
#include "file.h"

FileStream::FileStream(const std::string &filename, std::ios_base::openmode mode) {
    open(filename, mode);
    if (!is_open()) {
        DbgThrow << "Error opening GPIO file " << filename << std::endl;
    }
}

FileStream::~FileStream() {
    close();
}
