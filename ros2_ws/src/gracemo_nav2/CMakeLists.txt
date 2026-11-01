cmake_minimum_required(VERSION 3.8)
project(gracemo_nav2)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS
    gracemo_nav2/frontier_explorer.py
    gracemo_nav2/coordinator_node.py
    gracemo_nav2/terrain_monitor_node.py
    gracemo_nav2/cmd_vel_mux_node.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
