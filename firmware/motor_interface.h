#pragma once
#include <Arduino.h>
#include <math.h>
#include "config.h"

/*
 * GRaCEmo ViRa — Safe Motor Interface Hardware Abstraction
 *
 * SAFETY INVARIANT:
 * No physical pins or PWM timers are modulated in this scaffold.
 * MOTOR_OUTPUT_ENABLED is enforced at compile time.
 *
 * HARDWARE NOTE:
 * Physical motor controller configuration (e.g. CANopen nodes, PWM H-bridges,
 * or smart BLDC serial drivers) must be confirmed and bench-tested with wheels
 * off the ground before any pin-level driver is attached.
 */

class MotorInterface {
public:
  void begin() {
    stopped_ = true;
    linearCommand_ = 0.0f;
    angularCommand_ = 0.0f;
  }

  void setCommand(float linear, float angular) {
    linearCommand_ = linear;
    angularCommand_ = angular;

#if MOTOR_OUTPUT_ENABLED
    #error "MOTOR_OUTPUT_ENABLED cannot be 1 in scaffold firmware without verified driver backend."
#else
    // Intentionally safe stub: registers values without actuating hardware.
    stopped_ = (fabs(linear) < 0.0001f && fabs(angular) < 0.0001f);
#endif
  }

  void stop() {
    linearCommand_ = 0.0f;
    angularCommand_ = 0.0f;
    stopped_ = true;
  }

  bool isStopped() const {
    return stopped_;
  }

  float commandedLinear() const { return linearCommand_; }
  float commandedAngular() const { return angularCommand_; }

private:
  float linearCommand_ = 0.0f;
  float angularCommand_ = 0.0f;
  bool stopped_ = true;
};
