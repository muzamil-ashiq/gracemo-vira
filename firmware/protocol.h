#pragma once
#include <Arduino.h>
#include <math.h>
#include <string.h>
#include <stdlib.h>

enum CommandType {
  CMD_NONE,
  CMD_HEARTBEAT,
  CMD_STATUS,
  CMD_STOP,
  CMD_CLEAR_FAULT,
  CMD_DRIVE
};

struct ParsedCommand {
  CommandType type = CMD_NONE;
  uint16_t seq = 0;
  float linear = 0.0f;
  float angular = 0.0f;
};

enum ParseResult {
  PARSE_WAITING,
  PARSE_COMPLETE,
  PARSE_ERROR,
  PARSE_OVERFLOW
};

class ProtocolParser {
public:
  ParseResult push(char c, ParsedCommand &out) {
    if (c == '\r') {
      return PARSE_WAITING;
    }

    if (c == '\n') {
      if (overflow_) {
        reset();
        return PARSE_OVERFLOW;
      }
      buffer_[length_] = '\0';
      const bool ok = parseBuffer(out);
      reset();
      return ok ? PARSE_COMPLETE : PARSE_ERROR;
    }

    if (length_ >= sizeof(buffer_) - 1) {
      overflow_ = true;
      return PARSE_WAITING;
    }

    if (!overflow_) {
      buffer_[length_++] = c;
    }
    return PARSE_WAITING;
  }

  void reset() {
    length_ = 0;
    overflow_ = false;
    buffer_[0] = '\0';
  }

private:
  char buffer_[96] = {0};
  size_t length_ = 0;
  bool overflow_ = false;

  bool parseBuffer(ParsedCommand &out) {
    if (length_ == 0) return false;

    char copy[sizeof(buffer_)];
    strncpy(copy, buffer_, sizeof(copy));
    copy[sizeof(copy) - 1] = '\0';

    // Optional Checksum validation: check for '*'
    char *chk_sep = strrchr(copy, '*');
    if (chk_sep != nullptr) {
      *chk_sep = '\0';  // isolate payload from checksum
      const char *expected_chk_str = chk_sep + 1;
      char *end_chk = nullptr;
      long expected_chk = strtol(expected_chk_str, &end_chk, 16);
      if (end_chk == expected_chk_str || *end_chk != '\0') {
        return false;
      }

      // Calculate XOR checksum over characters up to '*'
      uint8_t calc_chk = 0;
      for (const char *p = copy; *p != '\0'; ++p) {
        calc_chk ^= static_cast<uint8_t>(*p);
      }
      if (calc_chk != static_cast<uint8_t>(expected_chk)) {
        return false;
      }
    }

    char *save = nullptr;
    char *token = strtok_r(copy, ",", &save);
    if (!token || strcmp(token, "CMD") != 0) return false;

    // Sequence ID
    token = strtok_r(nullptr, ",", &save);
    if (!token || token[0] == '\0') return false;
    char *end_seq = nullptr;
    long seq_val = strtol(token, &end_seq, 10);
    if (end_seq == token || *end_seq != '\0' || seq_val < 0 || seq_val > 65535) {
      return false;
    }
    out.seq = static_cast<uint16_t>(seq_val);

    // Command verb
    token = strtok_r(nullptr, ",", &save);
    if (!token) return false;

    if (strcmp(token, "HEARTBEAT") == 0) {
      out.type = CMD_HEARTBEAT;
    } else if (strcmp(token, "STATUS") == 0) {
      out.type = CMD_STATUS;
    } else if (strcmp(token, "STOP") == 0) {
      out.type = CMD_STOP;
    } else if (strcmp(token, "CLEAR_FAULT") == 0) {
      out.type = CMD_CLEAR_FAULT;
    } else if (strcmp(token, "DRIVE") == 0) {
      char *linear_str = strtok_r(nullptr, ",", &save);
      char *angular_str = strtok_r(nullptr, ",", &save);
      if (!linear_str || !angular_str) return false;

      char *end_lin = nullptr;
      char *end_ang = nullptr;
      float lin = strtof(linear_str, &end_lin);
      float ang = strtof(angular_str, &end_ang);

      if (end_lin == linear_str || *end_lin != '\0' ||
          end_ang == angular_str || *end_ang != '\0') {
        return false;
      }
      if (!isfinite(lin) || !isfinite(ang)) {
        return false;
      }

      out.linear = lin;
      out.angular = ang;
      out.type = CMD_DRIVE;
    } else {
      return false;
    }

    // Reject trailing fields
    if (strtok_r(nullptr, ",", &save) != nullptr) {
      return false;
    }

    return true;
  }
};
