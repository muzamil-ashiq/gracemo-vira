#pragma once
#include <Arduino.h>
#include <string.h>
#include "config.h"

enum FaultCode {
  FAULT_NONE = 0x00,
  FAULT_HEARTBEAT_TIMEOUT = 0x01,
  FAULT_BAD_COMMAND = 0x02,
  FAULT_PHYSICAL_ESTOP = 0xFF
};

class SafetySupervisor {
public:
  void begin(uint32_t now) {
    lastHeartbeatMs_ = now;
    state_ = "BOOT_SAFE";
    fault_ = FAULT_NONE;
    heartbeatSeen_ = false;
  }

  void noteHeartbeat(uint32_t now) {
    lastHeartbeatMs_ = now;
    heartbeatSeen_ = true;
    if (fault_ == FAULT_HEARTBEAT_TIMEOUT) {
      fault_ = FAULT_NONE;
    }
    if (fault_ == FAULT_NONE && strcmp(state_, "STOP_REQUESTED") != 0) {
      state_ = "READY";
    }
  }

  void update(uint32_t now) {
    if (!heartbeatSeen_ || (now - lastHeartbeatMs_ > COMMAND_TIMEOUT_MS)) {
      if (fault_ == FAULT_NONE) {
        fault_ = FAULT_HEARTBEAT_TIMEOUT;
      }
      state_ = "SAFE_STOP";
    } else if (fault_ == FAULT_NONE && strcmp(state_, "STOP_REQUESTED") != 0) {
      state_ = "READY";
    }
  }

  void requestStop() {
    state_ = "STOP_REQUESTED";
  }

  void raiseFault(FaultCode code) {
    fault_ = code;
    state_ = "FAULT";
  }

  void clearRecoverableFault() {
    if (fault_ == FAULT_BAD_COMMAND || fault_ == FAULT_HEARTBEAT_TIMEOUT) {
      fault_ = FAULT_NONE;
      state_ = heartbeatSeen_ ? "READY" : "BOOT_SAFE";
    } else if (strcmp(state_, "STOP_REQUESTED") == 0) {
      state_ = heartbeatSeen_ ? "READY" : "BOOT_SAFE";
    }
  }

  bool motionAllowed() const {
    return heartbeatSeen_ &&
           fault_ == FAULT_NONE &&
           strcmp(state_, "STOP_REQUESTED") != 0 &&
           strcmp(state_, "SAFE_STOP") != 0 &&
           strcmp(state_, "BOOT_SAFE") != 0;
  }

  bool stopRequired() const {
    return !motionAllowed();
  }

  const char* stateName() const {
    return state_;
  }

  const char* faultName() const {
    switch (fault_) {
      case FAULT_HEARTBEAT_TIMEOUT: return "HEARTBEAT_TIMEOUT";
      case FAULT_BAD_COMMAND: return "BAD_COMMAND";
      case FAULT_PHYSICAL_ESTOP: return "PHYSICAL_ESTOP";
      default: return "NONE";
    }
  }

  FaultCode faultCode() const {
    return fault_;
  }

private:
  uint32_t lastHeartbeatMs_ = 0;
  bool heartbeatSeen_ = false;
  const char* state_ = "BOOT_SAFE";
  FaultCode fault_ = FAULT_NONE;
};
