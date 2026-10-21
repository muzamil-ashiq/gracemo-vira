EESchema Schematic File Version 4
LIBS:power
LIBS:Connector_Generic
EELAYER 29 0
EELAYER END
$Descr A4 11693 8268
encoding utf-8
Sheet 1 1
Title "GRaCEmo ViRa - Hardware System Overview"
Date "2026-10-19"
Rev "0.1 - editable planning schematic"
Comp "GRaCEmo ViRa"
Comment1 "System-level hardware inventory and interface planning"
Comment2 "Connector symbols are interface placeholders, not exact vendor pinouts"
Comment3 "Verify every pin against the selected manufacturer's datasheet before wiring"
Comment4 "Not a validated circuit; no power or SPICE simulation implied"
$EndDescr
Text Notes 700 650 0    120  ~ 24
GRACEMO VIRA - MASTER HARDWARE INTERFACE OVERVIEW
Text Notes 700 900 0    70   ~ 14
This is an editable starting schematic. J* symbols represent subsystem interfaces / placeholders.
Text Notes 700 1050 0    70   ~ 14
Do not connect real hardware using these generic pin numbers. Replace each placeholder with the exact connector / carrier-board pinout.
Text Notes 700 1300 0    90   ~ 18
EDGE COMPUTING
$Comp
L Connector_Generic:Conn_01x08 J1
U 1 1 67100001
P 2100 1900
F 0 "J1" H 2180 1892 50  0000 L CNN
F 1 "JETSON AGX ORIN 64GB OR ORIN NX 16GB - CARRIER INTERFACE" H 2180 1801 50 0000 L CNN
F 2 "" H 2100 1900 50 0001 C CNN
F 3 "Placeholder only; carrier board varies by module and vendor" H 2100 1900 50 0001 C CNN
	1    2100 1900
	1 0 0 -1
$EndComp
Text Notes 700 2500 0    90   ~ 18
REAL-TIME CONTROL / ACTUATION
$Comp
L Connector_Generic:Conn_01x08 J2
U 1 1 67100002
P 2100 3050
F 0 "J2" H 2180 3042 50 0000 L CNN
F 1 "STM32F746Z6T6 MCU BOARD - PLACEHOLDER" H 2180 2951 50 0000 L CNN
F 2 "" H 2100 3050 50 0001 C CNN
F 3 "Exact MCU package / board pinout must be added" H 2100 3050 50 0001 C CNN
	1    2100 3050
	1 0 0 -1
$EndComp
$Comp
L Connector_Generic:Conn_01x08 J3
U 1 1 67100003
P 2100 4050
F 0 "J3" H 2180 4042 50 0000 L CNN
F 1 "MOTOR CONTROLLERS - BLDC/PMSM SERVO DRIVES" H 2180 3951 50 0000 L CNN
F 2 "" H 2100 4050 50 0001 C CNN
F 3 "Roboteq / selected controller model TBD" H 2100 4050 50 0001 C CNN
	1    2100 4050
	1 0 0 -1
$EndComp
$Comp
L Connector_Generic:Conn_01x08 J4
U 1 1 67100004
P 2100 5050
F 0 "J4" H 2180 5042 50 0000 L CNN
F 1 "FOUR-WHEEL DRIVE MOTORS + ENCODERS" H 2180 4951 50 0000 L CNN
F 2 "" H 2100 5050 50 0001 C CNN
F 3 "Motor count / drive topology to be finalized" H 2100 5050 50 0001 C CNN
	1    2100 5050
	1 0 0 -1
$EndComp
Text Notes 4700 1300 0    90   ~ 18
PERCEPTION / NAVIGATION / AUDIO
$Comp
L Connector_Generic:Conn_01x08 J5
U 1 1 67100005
P 5800 1900
F 0 "J5" H 5880 1892 50 0000 L CNN
F 1 "LUXONIS OAK-D PRO CAMERA" H 5880 1801 50 0000 L CNN
F 2 "" H 5800 1900 50 0001 C CNN
F 3 "USB / power details depend on exact camera variant" H 5800 1900 50 0001 C CNN
	1    5800 1900
	1 0 0 -1
$EndComp
$Comp
L Connector_Generic:Conn_01x08 J6
U 1 1 67100006
P 5800 2900
F 0 "J6" H 5880 2892 50 0000 L CNN
F 1 "LIDAR SENSOR" H 5880 2801 50 0000 L CNN
F 2 "" H 5800 2900 50 0001 C CNN
F 3 "Model / interface TBD: Ethernet, USB or UART" H 5800 2900 50 0001 C CNN
	1    5800 2900
	1 0 0 -1
$EndComp
$Comp
L Connector_Generic:Conn_01x08 J7
U 1 1 67100007
P 5800 3900
F 0 "J7" H 5880 3892 50 0000 L CNN
F 1 "IMU + WHEEL ENCODERS + SAFETY SENSORS" H 5880 3801 50 0000 L CNN
F 2 "" H 5800 3900 50 0001 C CNN
F 3 "Sensor models and voltage levels TBD" H 5800 3900 50 0001 C CNN
	1    5800 3900
	1 0 0 -1
$EndComp
$Comp
L Connector_Generic:Conn_01x08 J8
U 1 1 67100008
P 5800 4900
F 0 "J8" H 5880 4892 50 0000 L CNN
F 1 "MICROPHONE ARRAY + SPEAKERS / AUDIO I-O" H 5880 4801 50 0000 L CNN
F 2 "" H 5800 4900 50 0001 C CNN
F 3 "Audio codec / USB audio hardware TBD" H 5800 4900 50 0001 C CNN
	1    5800 4900
	1 0 0 -1
$EndComp
Text Notes 8200 1300 0    90   ~ 18
POWER / SAFETY / COMMUNICATIONS
$Comp
L Connector_Generic:Conn_01x08 J9
U 1 1 67100009
P 9300 1900
F 0 "J9" H 9380 1892 50 0000 L CNN
F 1 "BATTERY PACK + BMS" H 9380 1801 50 0000 L CNN
F 2 "" H 9300 1900 50 0001 C CNN
F 3 "Battery chemistry / voltage / current rating TBD" H 9300 1900 50 0001 C CNN
	1    9300 1900
	1 0 0 -1
$EndComp
$Comp
L Connector_Generic:Conn_01x08 J10
U 1 1 6710000A
P 9300 2900
F 0 "J10" H 9380 2892 50 0000 L CNN
F 1 "FUSES + MAIN DISCONNECT + EMERGENCY STOP" H 9380 2801 50 0000 L CNN
F 2 "" H 9300 2900 50 0001 C CNN
F 3 "Safety chain must be engineered and verified physically" H 9300 2900 50 0001 C CNN
	1    9300 2900
	1 0 0 -1
$EndComp
$Comp
L Connector_Generic:Conn_01x08 J11
U 1 1 6710000B
P 9300 3900
F 0 "J11" H 9380 3892 50 0000 L CNN
F 1 "DC-DC POWER RAILS + DISTRIBUTION" H 9380 3801 50 0000 L CNN
F 2 "" H 9300 3900 50 0001 C CNN
F 3 "Rails to be designed from actual component input ratings" H 9300 3900 50 0001 C CNN
	1    9300 3900
	1 0 0 -1
$EndComp
$Comp
L Connector_Generic:Conn_01x08 J12
U 1 1 6710000C
P 9300 4900
F 0 "J12" H 9380 4892 50 0000 L CNN
F 1 "ETHERNET / CAN / UART / I2C / USB HUBS" H 9380 4801 50 0000 L CNN
F 2 "" H 9300 4900 50 0001 C CNN
F 3 "Bus topology and isolation requirements TBD" H 9300 4900 50 0001 C CNN
	1    9300 4900
	1 0 0 -1
$EndComp
Text Notes 700 6250 0    80   ~ 16
PLANNED INTERFACES (NOT CONNECTED YET): Jetson <-> STM32: USB/UART/CAN/Ethernet as selected; STM32 <-> motor controllers: CAN/UART/PWM as supported;
Text Notes 700 6400 0    80   ~ 16
Camera/LiDAR <-> Jetson: USB/Ethernet; sensors <-> STM32: I2C/SPI/GPIO; battery -> fuse/disconnect -> power distribution -> protected DC/DC rails.
Text Notes 700 6600 0    80   ~ 16
NEXT STEP: replace each J* placeholder with exact manufacturer connector pinout and add validated power nets, grounds, fuses, and interface wiring.
Text Notes 700 6800 0    80   ~ 16
This file is a system inventory scaffold, not a tested circuit or manufacturer-approved design.
$EndSCHEMATC
