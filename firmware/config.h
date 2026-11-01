#pragma once
#include <Arduino.h>

/*
 * GRaCEmo ViRa — STM32 Firmware Configuration
 * Version: 0.1.0-proposed
 *
 * SAFETY INVARIANT:
 * MOTOR_OUTPUT_ENABLED is strictly 0.
 * Real motor movement must NOT be activated until physical hardware configuration,
 * pin mappings, CAN bus topologies, and emergency stops are validated.
 */

#define FW_VERSION "0.1.0-proposed"

// Serial Ports
// STM32 Nucleo boards typically assign Serial to ST-LINK USB VCP (PA2/PA3 or USB CDC)
// and Serial1 to hardware UART headers.
#define DEBUG_PORT Serial
#define ROBOT_LINK Serial

static const uint32_t DEBUG_BAUD = 115200;
static const uint32_t ROBOT_LINK_BAUD = 115200;

// Status LED
#ifndef LED_BUILTIN
#define LED_BUILTIN 13
#endif
static const uint32_t STATUS_LED_PIN = LED_BUILTIN;

// Velocity limits matching ROS 2 gracemo_hardware safety boundaries
static constexpr float HW_MAX_LINEAR_VEL_MPS = 0.35f;   // m/s
static constexpr float HW_MAX_ANGULAR_VEL_RPS = 0.75f;  // rad/s

// Periodic timing constants (milliseconds)
static const uint32_t TELEMETRY_PERIOD_MS = 50;   // 20 Hz
static const uint32_t STATUS_PERIOD_MS = 1000;    // 1 Hz
static const uint32_t COMMAND_TIMEOUT_MS = 500;   // Watchdog: heartbeat loss enters SAFE_STOP

// Hardware Safety Guard
#define MOTOR_OUTPUT_ENABLED 0
