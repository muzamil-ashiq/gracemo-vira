#pragma once
#include <Arduino.h>
#include <stdio.h>

struct TelemetryData {
  uint16_t seq = 0;
  float left_wheel_vel_mps = 0.0f;
  float right_wheel_vel_mps = 0.0f;
  int32_t left_encoder_ticks = 0;
  int32_t right_encoder_ticks = 0;
  float odom_x = 0.0f;
  float odom_y = 0.0f;
  float odom_yaw = 0.0f;
  float battery_voltage_v = 12.4f;
  uint8_t physical_estop_pressed = 0;
  uint8_t mcu_fault_code = 0;

  void formatLine(char *out, size_t max_len) const {
    snprintf(out, max_len,
             "TELEM,%u,%.3f,%.3f,%ld,%ld,%.3f,%.3f,%.3f,%.2f,%u,%u",
             seq,
             left_wheel_vel_mps,
             right_wheel_vel_mps,
             static_cast<long>(left_encoder_ticks),
             static_cast<long>(right_encoder_ticks),
             odom_x,
             odom_y,
             odom_yaw,
             battery_voltage_v,
             physical_estop_pressed,
             mcu_fault_code);
  }
};
