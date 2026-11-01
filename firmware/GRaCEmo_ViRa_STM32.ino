/*
 * GRaCEmo ViRa — STM32 Firmware Scaffold
 * Version: 0.1.0-proposed
 *
 * SAFETY INVARIANT:
 * - Motor outputs are completely disabled by default (MOTOR_OUTPUT_ENABLED = 0).
 * - Real hardware movement must NOT be activated until physical board markings,
 *   motor driver topologies, encoder calibration, and hardwired emergency stops
 *   have been physically validated.
 */

#include <Arduino.h>
#include "config.h"
#include "protocol.h"
#include "safety.h"
#include "telemetry.h"
#include "motor_interface.h"

static ProtocolParser parser;
static SafetySupervisor safety;
static MotorInterface motors;
static TelemetryData telemetry;

static uint32_t lastTelemetryMs = 0;
static uint32_t lastStatusMs = 0;
static bool linkSeen = false;

static void sendLine(const char *msg) {
  ROBOT_LINK.println(msg);
}

static void sendStatus() {
  char buf[128];
  snprintf(buf, sizeof(buf),
           "STATUS,fw=%s,safety=%s,motor_output=%s,link=%s,fault=%s",
           FW_VERSION,
           safety.stateName(),
           MOTOR_OUTPUT_ENABLED ? "enabled" : "disabled",
           linkSeen ? "seen" : "waiting",
           safety.faultName());
  sendLine(buf);
}

static void sendTelemetry() {
  telemetry.seq = (telemetry.seq + 1) % 65536;
  telemetry.mcu_fault_code = static_cast<uint8_t>(safety.faultCode());
  telemetry.physical_estop_pressed = 0; // Will be read from active-low contactor pin in production
  
  char telem_line[128];
  telemetry.formatLine(telem_line, sizeof(telem_line));
  sendLine(telem_line);
}

static void handleCommand(const ParsedCommand &cmd) {
  linkSeen = true;

  if (cmd.type == CMD_HEARTBEAT) {
    safety.noteHeartbeat(millis());
    char buf[32];
    snprintf(buf, sizeof(buf), "ACK,%u,HEARTBEAT", cmd.seq);
    sendLine(buf);
    return;
  }

  if (cmd.type == CMD_STATUS) {
    sendStatus();
    return;
  }

  if (cmd.type == CMD_STOP) {
    motors.stop();
    safety.requestStop();
    char buf[32];
    snprintf(buf, sizeof(buf), "ACK,%u,STOP", cmd.seq);
    sendLine(buf);
    return;
  }

  if (cmd.type == CMD_CLEAR_FAULT) {
    if (motors.isStopped()) {
      safety.clearRecoverableFault();
      char buf[32];
      snprintf(buf, sizeof(buf), "ACK,%u,CLEAR_FAULT", cmd.seq);
      sendLine(buf);
    } else {
      char buf[48];
      snprintf(buf, sizeof(buf), "ERR,%u,CANNOT_CLEAR_WHILE_MOVING", cmd.seq);
      sendLine(buf);
    }
    return;
  }

  if (cmd.type == CMD_DRIVE) {
    if (!safety.motionAllowed()) {
      motors.stop();
      char buf[32];
      snprintf(buf, sizeof(buf), "ERR,%u,MOTION_INHIBITED", cmd.seq);
      sendLine(buf);
      return;
    }

    if (fabs(cmd.linear) > HW_MAX_LINEAR_VEL_MPS ||
        fabs(cmd.angular) > HW_MAX_ANGULAR_VEL_RPS) {
      motors.stop();
      safety.raiseFault(FAULT_BAD_COMMAND);
      char buf[32];
      snprintf(buf, sizeof(buf), "ERR,%u,DRIVE_RANGE", cmd.seq);
      sendLine(buf);
      return;
    }

    motors.setCommand(cmd.linear, cmd.angular);
    char buf[48];
    snprintf(buf, sizeof(buf), "ACK,%u,DRIVE_ACCEPTED_OUTPUT_DISABLED", cmd.seq);
    sendLine(buf);
    return;
  }

  char buf[32];
  snprintf(buf, sizeof(buf), "ERR,%u,UNKNOWN_COMMAND", cmd.seq);
  sendLine(buf);
}

void setup() {
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);

  DEBUG_PORT.begin(DEBUG_BAUD);
  ROBOT_LINK.begin(ROBOT_LINK_BAUD);

  motors.begin();
  motors.stop();
  safety.begin(millis());

  DEBUG_PORT.println(F("GRaCEmo ViRa STM32 firmware scaffold (SAFE MODE)"));
  DEBUG_PORT.print(F("Firmware version: "));
  DEBUG_PORT.println(FW_VERSION);
  DEBUG_PORT.println(F("Motor outputs: DISABLED (scaffold only)."));

  sendLine("HELLO,GRACEMO_VIRA," FW_VERSION);
  sendLine("READY,MOTOR_OUTPUT_DISABLED");
}

void loop() {
  const uint32_t now = millis();

  // Non-blocking serial reception
  while (ROBOT_LINK.available() > 0) {
    const char c = static_cast<char>(ROBOT_LINK.read());
    ParsedCommand cmd;
    const ParseResult result = parser.push(c, cmd);

    if (result == PARSE_COMPLETE) {
      handleCommand(cmd);
    } else if (result == PARSE_ERROR) {
      sendLine("ERR,0,PARSE");
    } else if (result == PARSE_OVERFLOW) {
      sendLine("ERR,0,OVERFLOW");
    }
  }

  // Safety watchdog update
  safety.update(now);
  if (safety.stopRequired()) {
    motors.stop();
  }

  // Periodic Telemetry (20 Hz)
  if (now - lastTelemetryMs >= TELEMETRY_PERIOD_MS) {
    lastTelemetryMs = now;
    sendTelemetry();
  }

  // Periodic Status (1 Hz)
  if (now - lastStatusMs >= STATUS_PERIOD_MS) {
    lastStatusMs = now;
    sendStatus();
  }

  // Heartbeat status LED toggle (1 Hz)
  static uint32_t lastLedToggle = 0;
  if (now - lastLedToggle >= 500) {
    lastLedToggle = now;
    digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
  }
}
