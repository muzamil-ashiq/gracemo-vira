# GRaCEmo ViRa — Physical Hardware Verification Checklist

**Document ID:** `VIRA-VERIF-HW-001`  
**Classification:** Pre-Hardware Activation Safety Gate  
**Target Platform:** NVIDIA Jetson Orin Nano + STM32F746ZG (NUCLEO-144)  
**Status:** MANDATORY BEFORE PHYSICAL MOTOR POWER ACTIVATION  
**Date:** 2026-10-28  

---

## 1. Safety Invariant Notice

> [!CAUTION]
> **UNDER NO CIRCUMSTANCES SHALL PHYSICAL MOTOR POWER OR `MOTOR_OUTPUT_ENABLED = 1` BE ACTIVATED BEFORE EVERY ITEM IN THIS CHECKLIST HAS BEEN CONFIRMED, MEASURED, AND SIGNED OFF BY A QUALIFIED SYSTEMS ENGINEER.**
>
> Automated software tests and mock simulation passes DO NOT certify physical hardware safety.

---

## 2. Physical Chassis Measurements

| Parameter | Current Model Values | Required Measurement Tool | Measurement Method | Target Tolerance | Sign-off Value |
|---|---|---|---|---|---|
| **Wheel Track ($W$)** | `0.34 m` (URDF/Params) vs `0.32 m` (Adapter/Config) | Steel vernier caliper or calibrated tape | Distance between centerline of left tire contact patch and centerline of right tire contact patch on flat ground | $\pm 1.0\text{ mm}$ | `[ _____ m ]` |
| **Wheel Radius ($R$)** | `0.065 m` ($130\text{ mm}$ diameter) | Vernier caliper + rolling roll-out test | 1. Direct uncompressed tire diameter. <br>2. Roll robot forward 10 wheel revolutions under full robot payload weight and measure distance travelled ($D / (10 \times 2\pi)$). | $\pm 0.5\text{ mm}$ | `[ _____ m ]` |
| **Chassis Ground Clearance** | $\sim 0.04\text{ m}$ | Caliper / depth gauge | Lowest point on battery tray / motor brackets to floor surface | $\pm 2.0\text{ mm}$ | `[ _____ m ]` |
| **LiDAR Sensor Offset** | `x=0.15 m, y=0.0 m, z=0.28 m` | Laser distance meter / plumb bob | From `base_footprint` origin to LiDAR optical mirror center | $\pm 2.0\text{ mm}$ | `[ _____ m ]` |
| **Camera Optical Center** | `x=0.18 m, y=0.0 m, z=0.45 m` | Height gauge | From `base_footprint` origin to camera sensor plane | $\pm 2.0\text{ mm}$ | `[ _____ m ]` |

---

## 3. Drive Topology & Motor Actuation Architecture

| Item | Options in Documentation | Physical Inspection Criteria | Selected Architecture | Sign-off |
|---|---|---|---|---|
| **Chassis Drive Topology** | A: 2 Differential Drive Wheels + 2 Passive Casters <br>B: 4 Driven Wheels (Skid-Steer / 4WD) | Count physical motors and gearboxes mounted to chassis. Check electrical schematic Sheet 05 vs URDF. | `[ ] 2WD + Casters`<br>`[ ] 4WD Skid-Steer` | `[ _______ ]` |
| **Motor Controller Model** | Cytron / Roboteq / Sabertooth / ODrive / Custom CAN | Inspect motor controller PCB markings, part numbers, and interface headers. | `Model: [ __________ ]` | `[ _______ ]` |
| **Motor Control Interface** | A: PWM + Direction logic (LVTTL 3.3V) <br>B: CAN / CANopen bus <br>C: UART direct protocol | Trace wiring harness from STM32 headers to motor controller signal inputs. | `[ ] PWM/DIR`<br>`[ ] CANbus`<br>`[ ] UART` | `[ _______ ]` |
| **Motor Maximum Current** | 10A / 15A / 20A per channel | Motor controller datasheet and fuse ratings on power distribution board. | `[ _____ A ]` | `[ _______ ]` |

---

## 4. Microcontroller Board & Clocking Verification

| Item | Requirement | Verification Method | Pass Criteria | Sign-off |
|---|---|---|---|---|
| **MCU Board Part** | NUCLEO-F746ZG | Read silkscreen on PCB and laser marking on LQFP144 package (`STM32F746ZGT6`) | Silkscreen reads `NUCLEO-F746ZG` | `[ _______ ]` |
| **Core Supply Rail** | +3.3V $\pm 5\%$ | Multimeter on JP3 / 3V3 test point | $3.25\text{ V} \le V_{3V3} \le 3.35\text{ V}$ | `[ _____ V ]` |
| **5V Peripheral Rail** | +5.0V $\pm 5\%$ | Multimeter on 5V pin header | $4.85\text{ V} \le V_{5V} \le 5.15\text{ V}$ | `[ _____ V ]` |
| **Oscillator Frequency** | 8 MHz HSE or 216 MHz SysTick | Inspect solder bridges SB8 / SB9 on ST-LINK MCO input | SysTick calibrated to $1\text{ ms} \pm 0.1\%$ | `[ _______ ]` |
| **Firmware Build FQBN** | `STMicroelectronics:stm32:Nucleo_144:pnum=NUCLEO_F746ZG` | Arduino CLI compile output | Verified 0 errors, Flash 38 kB, RAM 2 kB | `[ VERIFIED ]` |

---

## 5. Wheel Encoder Calibration

| Parameter | Theoretical / Configured Value | Verification Method | Measured Value | Sign-off |
|---|---|---|---|---|
| **Encoder Type** | Quadrature Optical / Magnetic (Channels A, B) | Inspect encoder datasheet / markings on motor rear bell | `[ Optical / Hall ]` | `[ _______ ]` |
| **CPR (Cycles Per Revolution)** | Unknown / Pending physical tag | Spin motor shaft 1 rev by hand, record oscilloscope pulse count | `[ _____ CPR ]` | `[ _______ ]` |
| **Gear Reduction Ratio ($G$)** | $20:1$ / $30:1$ / $50:1$ | Rotate wheel 1 full revolution, count motor shaft turns | `[ _____ : 1 ]` | `[ _______ ]` |
| **Total Ticks per Wheel Rev** | $N_{ticks} = CPR \times 4 \times G$ | Count accumulator change over 10 full wheel revolutions | `[ _____ ticks ]` | `[ _______ ]` |
| **Encoder Direction Polarity** | Forward motion = Positive count increase | Push robot forward by hand with bridge running | Both left and right ticks increment | `[ _______ ]` |

---

## 6. Jetson ↔ STM32 Communications Link

| Item | Target Specification | Verification Method | Status | Sign-off |
|---|---|---|---|---|
| **Physical Interface** | Micro-USB to ST-LINK VCP or UART header | Connect cable to Jetson Orin Nano USB 3.0 port | `dmesg \| grep tty` identifies device | `[ _______ ]` |
| **Device Path & Symlink** | `/dev/gracemo_mcu` via udev rule | Install rule: `KERNEL=="ttyACM*", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="374b", SYMLINK+="gracemo_mcu", MODE="0666"` | Verify `ls -la /dev/gracemo_mcu` | `[ _______ ]` |
| **Baud Rate** | 115200 baud, 8 data bits, no parity, 1 stop bit | Serial loopback test using `minicom` or python script | 0 dropped characters at 20 Hz frame rate | `[ _______ ]` |
| **Signal Voltage** | 3.3V LVTTL | Verify no 5V signals directly enter STM32 non-5V-tolerant pins | Maximum voltage $\le 3.3\text{ V}$ | `[ _______ ]` |

---

## 7. Hardwired Safety Circuit & Contactor Inspection

| Safety Check Item | Requirement | Physical Test Procedure | Pass / Fail Criteria | Sign-off |
|---|---|---|---|---|
| **Emergency Stop Button** | Red latching mushroom head switch (twist to release) | Mechanically press button | Positive latching action; opens circuit with $< 2\text{ mm}$ stroke | `[ _______ ]` |
| **Normally Closed Contacts** | Dual-channel NC contacts | Measure continuity across terminals with DMM | $0.0\ \Omega$ when released, open-circuit ($\infty$) when pressed | `[ _______ ]` |
| **Main Contactor De-energization** | Contactor coil cuts 24V/12V motor power rail | Press E-stop while monitoring motor power terminal with DMM | Voltage drops to $0.0\text{ V}$ in $< 20\text{ ms}$ | `[ _______ ]` |
| **Feedback Sense Pin** | Contactor aux contact connected to STM32 pin `PE0` | Monitor serial telemetry `physical_estop_pressed` bit | Bit transitions from `0` to `1` upon E-stop press | `[ _______ ]` |
| **Contactor Lockout Circuit** | Releasing button must NOT immediately spin motors | Press E-stop, command velocity, release E-stop without software `CLEAR_FAULT` | Robot remains safely stopped in `SAFE_STOP` state | `[ _______ ]` |
| **Flywheel Protection Diode** | 1N4007 or Schottky across contactor coil | Visual inspection of coil suppression circuit | Diode cathode to +V, anode to GND switch | `[ _______ ]` |

---

## 8. Battery Voltage Measurement Subsystem

| Parameter | Nominal Specification | Measurement Method | Calibrated Value | Sign-off |
|---|---|---|---|---|
| **Battery Chemistry & Pack** | 3S LiPo ($11.1\text{ V}$ nom, $12.6\text{ V}$ max) or 4S LiFePO4 ($12.8\text{ V}$ nom) | Inspect battery pack labeling | `Chemistry: [ _____ ]` | `[ _______ ]` |
| **Voltage Divider Ratio** | $R_1 / (R_1 + R_2)$ to scale $15.0\text{ V} \to 3.0\text{ V}$ ($5:1$) | Measure resistor values with DMM | $R_1 = \_\_\_\ k\Omega, R_2 = \_\_\_\ k\Omega$ | `[ _______ ]` |
| **ADC Scaling Factor** | $V_{bus} = ADC \times \frac{3.3}{4095} \times \frac{R_1 + R_2}{R_2}$ | Compare serial telemetry `v_bat` with calibrated digital voltmeter | Difference $\le \pm 0.1\text{ V}$ | `[ _______ ]` |
| **Low-Voltage Cutoff** | Soft alert at $10.8\text{ V}$, hard motion cutoff at $10.2\text{ V}$ | Bench PSU ramp-down test | Firmware raises `FAULT_BATTERY_LOW` | `[ _______ ]` |

---

## 9. Final Sign-Off and Hardware Activation Authorization

This section must be completed and signed by the Systems Engineer, Electrical Engineer, and Safety Lead prior to changing `MOTOR_OUTPUT_ENABLED = 1` or `PROTOCOL_CONFIRMED = True`.

| Role | Engineer Name | Signature | Date |
|---|---|---|---|
| **Lead Systems Engineer** | `________________________` | `________________________` | `____ / ____ / 2026` |
| **Lead Electrical Engineer** | `________________________` | `________________________` | `____ / ____ / 2026` |
| **Firmware / ROS 2 Lead** | `________________________` | `________________________` | `____ / ____ / 2026` |

---
*Notice: Completed checklist must be archived in repository at `docs/hardware_signoff_records/` with attached photos of measurement verniers and oscilloscope traces.*
