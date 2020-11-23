//
// Created by rancohen on 22/11/2020.
//

#ifndef GARDEN_FILE_H
#define GARDEN_FILE_H

#include <fstream>

class fstr: public std::fstream
{
public:
    fstr(const std::string &filename, openmode mode);
    ~fstr() override;
};
#endif //GARDEN_FILE_H
