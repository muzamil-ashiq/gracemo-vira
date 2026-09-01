cmake_minimum_required(VERSION 3.8)
project(gracemo_control)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(gracemo_interfaces REQUIRED)

add_executable(safety_servo_node src/safety_servo_node.cpp)
ament_target_dependencies(safety_servo_node
  rclcpp
  std_msgs
  sensor_msgs
  geometry_msgs
  gracemo_interfaces
)

install(TARGETS safety_servo_node
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME})

ament_package()
