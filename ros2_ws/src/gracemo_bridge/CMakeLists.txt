cmake_minimum_required(VERSION 3.8)
project(gracemo_bridge)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)

install(
  PROGRAMS
    gracemo_bridge/kernel_bridge.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME kernel_bridge
)

install(
  PROGRAMS
    gracemo_bridge/sensor_bridge.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME sensor_bridge
)

install(
  PROGRAMS
    gracemo_bridge/interaction_bridge.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME interaction_bridge
)

ament_package()
