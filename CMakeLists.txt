# cmake_minimum_required(VERSION <specify CMake version here>)
cmake_minimum_required(VERSION 2.8)
project(garden)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_FLAGS "-D_DEBUG")
#set(CMAKE_EXE_LINKER_FLAGS "-lstdc++fs")

file(GLOB GardenSource "src/*.cpp")

add_executable(garden ${GardenSource})

