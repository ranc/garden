# cmake_minimum_required(VERSION <specify CMake version here>)
cmake_minimum_required(VERSION 2.8)
project(Garden)

set(CMAKE_CXX_STANDARD 17)

file(GLOB GardenSource "src/*.cpp")

add_executable(Garden ${GardenSource})
