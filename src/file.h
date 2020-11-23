//
// Created by rancohen on 22/11/2020.
//

#ifndef GARDEN_FILE_H
#define GARDEN_FILE_H

#include <fstream>
#include <string>
#include <vector>

class ThrowCatcher
{
    std::stringstream _stst;
public:
    ~ThrowCatcher() noexcept(false)
    {
        throw std::runtime_error(_stst.str());
    }

    std::stringstream &st() { return _stst;}
};

#define Throw ThrowCatcher th; th.st()

// trim from start (in place)
static inline void ltrim(std::string &s) {
    s.erase(s.begin(), std::find_if(s.begin(), s.end(), [](unsigned char ch) {
        return !std::isspace(ch);
    }));
}

// trim from end (in place)
static inline void rtrim(std::string &s) {
    s.erase(std::find_if(s.rbegin(), s.rend(), [](unsigned char ch) {
        return !std::isspace(ch);
    }).base(), s.end());
}

// trim from both ends (in place)
static inline std::string trim(const std::string &s) {
    std::string ret = s;
    ltrim(ret);
    rtrim(ret);

    return ret;
}

static inline std::vector<std::string> explode(const std::string & s, char delim)
{
    std::vector<std::string> result;
    std::istringstream iss(s);

    for (std::string token; std::getline(iss, token, delim); )
    {
        result.push_back(std::move(token));
    }

    return result;
}


static inline int strtime_to_min(const std::string &str)
{
    auto lstr = trim(str);
    auto hour_min = explode(lstr, ':');
    if (hour_min.size()!=2)
    {
        Throw << "time is not in correct syntax, got: "<<lstr;
    }
    return atoi(hour_min[0].c_str())*60+atoi(hour_min[1].c_str());
}


class FileStream: public std::fstream
{
public:
    explicit FileStream(const std::string &filename, openmode mode=std::fstream::in);
    ~FileStream() override;
};

#endif //GARDEN_FILE_H
