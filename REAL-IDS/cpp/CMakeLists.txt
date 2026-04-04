cmake_minimum_required(VERSION 3.16)

# Helps CMake detect MSVC when not launched from a VS Developer shell, and avoids
# a failed link-only probe if Windows SDK bin (rc.exe) is not on PATH yet.
if(WIN32)
  set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
endif()

project(real_ids LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(MSVC)
  add_compile_options(/utf-8)
endif()

add_library(real_ids STATIC
  src/eth_buffer.cpp
  src/can_ids.cpp
  src/central_processor.cpp
  src/engine.cpp
)
target_include_directories(real_ids PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}/include"
)

add_executable(real_ids_daemon
  daemon/main.cpp
)
target_include_directories(real_ids_daemon PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/third_party"
)
target_link_libraries(real_ids_daemon PRIVATE real_ids)

find_package(Threads REQUIRED)
target_link_libraries(real_ids_daemon PRIVATE Threads::Threads)

if(WIN32)
  target_link_libraries(real_ids_daemon PRIVATE ws2_32)
endif()
