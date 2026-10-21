"""GRaCEmo ViRa design definition. Pin-level data that could not be checked against a datasheet is flagged UNVERIFIED."""
from kgen import *

PI, PO, I, O, B, P = "power_in", "power_out", "input", "output", "bidirectional", "passive"

# ---------------------------------------------------------------- symbols
sd("R", "R", "Resistor", "res", [("1", P)], [("2", P)])
sd("C", "C", "Capacitor", "cap", [("1", P)], [("2", P)])
sd("CP", "C", "Polarised capacitor (pin1 +)", "cp", [("1", P)], [("2", P)])
sd("FUSE", "F", "Fuse", "fuse", [("1", P)], [("2", P)])
sd("JUMPER", "JP", "Solder/link jumper", "sw", [("1", P)], [("2", P)])
sd("SW_SPST", "SW", "SPST switch", "sw", [("1", P)], [("2", P)])
sd("DIODE", "D", "Diode (pin1 K, pin2 A)", "diode", [("K", P)], [("A", P)])
sd("TVS", "D", "TVS diode (pin1 K to rail, pin2 A to ground)", "diode", [("K", P)], [("A", P)])
sd("TESTPOINT", "TP", "Test point", "tp", [("1", P)], [])
sd("NETTIE", "NT", "Net tie (star-point ground tie)", "nt", [("1", P)], [("2", P)])
sd("PWR_FLAG", "#FLG", "Power flag", "pwrflag", [], [("pwr", PO)], power=True, in_bom=False)

sd("BATTERY_PACK_24V_PROV", "BT", "24V-class battery pack - chemistry/cell count/capacity PENDING", "box",
   [], [("PACK+", PO), ("PACK-", PO)])
sd("BMS_PROV", "U", "Battery management system - selection pending (pins provisional)", "box",
   [("B+", P), ("B-", P), ("CELL_TAPS", P)], [("P+", P), ("P-", P), ("BMS_COMM", B)])
sd("REVERSE_POLARITY_PROV", "U", "Reverse-polarity/ideal-diode block - topology pending", "box",
   [("VIN", P), ("GND", P)], [("VOUT", P)])
sd("POWER_MONITOR_PROV", "U", "I2C high-side V/I monitor (INA228-class) - LOGICAL pin order, verify vs datasheet", "box",
   [("IN+", I), ("IN-", I), ("VBUS", I), ("VS", PI), ("GND", PI), ("A0", I), ("A1", I)],
   [("SDA", B), ("SCL", I), ("ALERT", O)])
sd("DCDC_PROV", "U", "Non-isolated DC-DC module - rating pending (logical pins)", "box",
   [("VIN", PI), ("EN", I), ("GND", PI)], [("VOUT", PO), ("PGOOD", O)])
sd("CONTACTOR_PROV", "K", "Motor power contactor - rating pending", "box",
   [("A1", P), ("A2", P)], [("1", P), ("2", P), ("13", P), ("14", P)])
sd("RELAY_2NC_PROV", "K", "Software-stop relay, 2 NC contacts - rating pending", "box",
   [("A1", P), ("A2", P)], [("11", P), ("12", P), ("21", P), ("22", P)])
sd("SAFETY_RELAY_PROV", "K", "Dual-channel safety relay - NOT selected/certified; terminal names generic", "box",
   [("A1", PI), ("A2", PI), ("S11", O), ("S12", I), ("S21", O), ("S22", I), ("Y1", P), ("Y2", P)],
   [("13", P), ("14", P), ("23", P), ("24", P), ("33", P), ("34", P)])
sd("ESTOP_MUSHROOM_2CH", "S", "E-stop pushbutton, 2 NC channels (terminals provisional)", "box",
   [("CH_A_1", P), ("CH_A_2", P), ("CH_B_1", P), ("CH_B_2", P)], [])
sd("PUSHBUTTON_NO", "SW", "Momentary NO pushbutton", "sw", [("1", P)], [("2", P)])
sd("OPTO_PC817", "U", "Single optocoupler PC817 pinout (1 A,2 K,3 E,4 C)", "box",
   [("A", I), ("K", P)], [("E", P), ("C", O)])
sd("NPN_PROV", "Q", "Small NPN relay driver - part pending", "box",
   [("B", I)], [("C", P), ("E", P)])
sd("NUCLEO_F746ZG_IF", "U", "NUCLEO-F746ZG functional interface; pin numbers are LOGICAL, not Morpho/Arduino numbers", "box",
   [("E5V", PI), ("GND", PI), ("3V3_OUT", PO), ("MOTOR_PWR_ON_N", I), ("PM_ALERT", I), ("BUMP1_N", I),
    ("BUMP2_N", I), ("PROX_IRQ", I), ("ENC_FL_A", I), ("ENC_FL_B", I), ("ENC_FR_A", I), ("ENC_FR_B", I),
    ("ENC_RL_A", I), ("ENC_RL_B", I), ("ENC_RR_A", I), ("ENC_RR_B", I), ("UART_RX", I), ("CAN1_RX", I),
    ("CAN2_RX", I), ("IMU_MISO", I), ("IMU_INT", I), ("SWD_VTREF", P)],
   [("DRV_EN", O), ("SW_STOP_REQ", O), ("UART_TX", O), ("CAN1_TX", O), ("CAN2_TX", O), ("IMU_SCK", O),
    ("IMU_MOSI", O), ("IMU_CS", O), ("I2C_SCL", B), ("I2C_SDA", B), ("PWM_AUX1", O), ("PWM_AUX2", O),
    ("PWM_AUX3", O), ("PWM_AUX4", O), ("GPIO_AUX1", B), ("GPIO_AUX2", B), ("SWDIO", B), ("SWCLK", I), ("NRST", B)])
sd("JETSON_CARRIER_IF", "U", "Jetson carrier INTERFACE block: AGX Orin 64GB (Cfg A) OR Orin NX 16GB (Cfg B); carrier model pending, NOT pin-level", "box",
   [("VIN", PI), ("GND", PI), ("UART_TX", O), ("UART_RX", I), ("GPIO_MOTOR_ON_N", I), ("GPIO_AUDIO_MUTE", O),
    ("FAN_PWM", O), ("FAN_TACH", I)],
   [("USB_OAK_VBUS", PO), ("USB_OAK_DM", B), ("USB_OAK_DP", B), ("USB_MIC_VBUS", PO), ("USB_MIC_DM", B),
    ("USB_MIC_DP", B), ("USB_DAC_VBUS", PO), ("USB_DAC_DM", B), ("USB_DAC_DP", B), ("ETH_TX_P", B),
    ("ETH_TX_N", B), ("ETH_RX_P", B), ("ETH_RX_N", B), ("CAN_TX_RESERVED", O), ("CAN_RX_RESERVED", I)])
sd("CONN_FAN4", "J", "4-pin fan connector", "box", [("V5", P), ("GND", P), ("TACH", P), ("PWM", P)], [])
sd("OAK_D_PRO_USB_IF", "J", "Luxonis OAK-D Pro (USB variant) USB interface", "box",
   [("VBUS", P), ("D-", B), ("D+", B), ("GND", P)], [])
sd("LIDAR_PWR_CONN", "J", "LiDAR power connector - model pending", "box", [("VLIDAR", P), ("GND", P)], [])
sd("LIDAR_ETH_CONN", "J", "LiDAR Ethernet 10/100 assumed - model pending", "box",
   [("TX+", B), ("TX-", B), ("RX+", B), ("RX-", B)], [])
sd("IMU_SPI_PROV", "U", "IMU on SPI - part pending (pins provisional)", "box",
   [("VDD", PI), ("GND", PI), ("SCLK", I), ("MOSI", I), ("CS", I)], [("MISO", O), ("INT", O)])
sd("PROX_SENSOR_CONN", "J", "Proximity sensor 3-pin connector - sensor pending", "box",
   [("V5", P), ("GND", P), ("OUT", P)], [])
sd("BUMPER_CONN", "J", "Bumper switch contact (NC to GND when idle)", "box", [("SIG", P), ("GND", P)], [])
sd("ENCODER_CONN", "J", "Wheel encoder A/B quadrature connector - encoder pending", "box",
   [("V5", P), ("A", P), ("B", P), ("GND", P)], [])
sd("DRIVE_CONN", "J", "Servo-drive/actuator interface (power+CAN+STO+EN) - drive pending", "box",
   [("VMOT", P), ("GND_PWR", P), ("CAN_H", B), ("CAN_L", B), ("STO_A", P), ("STO_B", P), ("EN", P)], [])
sd("USB_DEV_CONN", "J", "USB device interface (4 wires)", "box", [("VBUS", P), ("D-", B), ("D+", B), ("GND", P)], [])
sd("USB_AUDIO_DAC_PROV", "U", "USB audio DAC - part pending", "box",
   [("VBUS", PI), ("D-", B), ("D+", B), ("GND", PI)], [("LINE_OUT", O), ("AGND", P)])
sd("AUDIO_AMP_PROV", "U", "Class-D speaker amplifier - part pending", "box",
   [("IN+", I), ("IN-", I), ("MUTE", I)], [("VDD", PI), ("GND", PI), ("OUT+", O), ("OUT-", O)])
sd("SPEAKER_CONN", "J", "Speaker output connector", "box", [("SPK+", P), ("SPK-", P)], [])
sd("CAN_XCVR_SN65HVD230", "U", "SN65HVD230 CAN transceiver (1 D,2 GND,3 VCC,4 R,5 Vref,6 CANL,7 CANH,8 Rs) - verify", "box",
   [("D", I), ("GND", PI), ("VCC", PI), ("Rs", I)], [("R", O), ("Vref", "no_connect"), ("CANL", B), ("CANH", B)])
sd("ESD_CAN_PROV", "D", "CAN ESD protection array - part pending", "box", [("H", P), ("L", P), ("GND", P)], [])
sd("CONN_CAN4", "J", "CAN bus connector H/L/GND/SHIELD", "box", [("CANH", P), ("CANL", P), ("GND", P), ("SHIELD", P)], [])
sd("CONN_UART3", "J", "UART debug header", "box", [("TX", P), ("RX", P), ("GND", P)], [])
sd("CONN_SWD5", "J", "SWD 1x05 header (VTref,SWDIO,SWCLK,NRST,GND)", "box",
   [("VTREF", P), ("SWDIO", P), ("SWCLK", P), ("NRST", P), ("GND", P)], [])
sd("CONN_AUX7", "J", "Aux PWM/GPIO header", "box",
   [("PWM1", P), ("PWM2", P), ("PWM3", P), ("PWM4", P), ("GPIO1", P), ("GPIO2", P), ("GND", P)], [])
sd("CONN_ESTOP_EXT4", "J", "External E-stop loop terminal (2 channels out/return)", "box",
   [("A_OUT", P), ("A_RET", P), ("B_OUT", P), ("B_RET", P)], [])

# ---------------------------------------------------------------- helpers
SW = {}
ROOT_UUID = U("root")
FP_R, FP_C, FP_F = "Resistor_SMD:R_0603_1608Metric", "Capacitor_SMD:C_0603_1608Metric", "Fuse:Fuse_1812_4532Metric"
TYP = "Typical placeholder value - confirm"
PEND = "Provisional - selection pending"
SEL = "Selected - verify against datasheet"


def sheet(idx, name, title, comments=()):
    s = Sheet(idx, name, title, comments)
    SW[name] = s
    return s


def res(s, val, a, b, status=TYP, fn=""):
    s.part("R", val, {"1": a, "2": b}, fp=FP_R, manufacturer="generic", mpn="TBD", function=fn, status=status, sim_class="Ideal passive - ngspice")


def cap(s, val, a, b, fn="Decoupling"):
    s.part("C", val, {"1": a, "2": b}, fp=FP_C, manufacturer="generic", mpn="TBD", function=fn, status=TYP, sim_class="Ideal passive - ngspice")


def fuse(s, val, a, b, fn):
    s.part("FUSE", val, {"1": a, "2": b}, fp=FP_F, manufacturer="TBD", mpn="TBD", function=fn, status="Rating pending", sim_class="Not simulated")


def tp(s, net):
    s.part("TESTPOINT", net, {"1": net}, function="Test point " + net, status="Placeholder", sim_class="Interface only")


def flag(s, net):
    s.part("PWR_FLAG", "PWR_FLAG", {"pwr": net}, function="ERC power flag (net fed through passive protection)", status="ERC aid", sim_class="n/a")


def N(**kw):
    return kw


# ================================================================= 00 root
root = sheet(0, "GRaCEmo_ViRa_Hardware_Overview", "00_System_Overview",
             ["DRAFT 0.1 - generated, NOT yet opened in KiCad, ERC NOT run by KiCad.",
              "Battery: 24V class nominal (chemistry/cells/capacity PENDING).",
              "Edge computer: Config A AGX Orin 64GB OR Config B Orin NX 16GB (mutually exclusive).",
              "MCU: NUCLEO-F746ZG. Pin-level data flagged UNVERIFIED unless noted."])

# ================================================================= 01 battery
s1 = sheet(1, "01_Battery_Protection", "01_Battery_Protection",
           ["24V-class pack; 6S Li-ion is 25.2V full, 7S is 29.4V full - converters/drives must cover the real range.",
            "All ratings pending until motor/power calculation. No fuse/BMS values invented."])
s1.text(["BATTERY PROTECTION CHAIN",
         "PACK -> BMS -> main fuse -> main disconnect -> reverse-polarity block -> shunt -> VBATT_MAIN",
         "Return path: GND_PWR is the power star point. Net tie to GND_LOGIC is on sheet 02."], 1.27)
s1.part("BATTERY_PACK_24V_PROV", "24V-class pack (PENDING)", N(**{"PACK+": "VBATT_RAW", "PACK-": "GND_PWR"}),
        manufacturer="TBD", mpn="TBD", function="Main battery", voltage="24V nominal (21-29.4V possible)", current="TBD", status=PEND, sim_class="Custom symbol - needs external model")
s1.part("BMS_PROV", "BMS (PENDING)", N(**{"B+": "VBATT_RAW", "B-": "GND_PWR", "CELL_TAPS": "NC", "P+": "VBATT_BMS", "P-": "GND_PWR", "BMS_COMM": "NC"}),
        manufacturer="TBD", mpn="TBD", function="Cell protection/balancing", status=PEND, sim_class="Custom symbol - real-hardware validation",
        notes="Cell tap and comm pins NC until BMS chosen")
fuse(s1, "MAIN FUSE rating TBD", "VBATT_BMS", "VBATT_FUSED", "Main fuse")
s1.part("SW_SPST", "MAIN DISCONNECT (rated TBD)", N(**{"1": "VBATT_FUSED", "2": "VBATT_SW"}),
        manufacturer="TBD", mpn="TBD", function="Main manual disconnect", status=PEND, sim_class="Interface only")
s1.part("REVERSE_POLARITY_PROV", "Reverse-polarity block (PENDING)", N(VIN="VBATT_SW", GND="GND_PWR", VOUT="VBATT_PROT"),
        manufacturer="TBD", mpn="TBD", function="Reverse polarity protection", status=PEND, sim_class="Custom symbol - ngspice if model chosen")
s1.part("TVS", "TVS (standoff voltage > max pack V, TBD)", N(K="VBATT_PROT", A="GND_PWR"),
        fp="", manufacturer="TBD", mpn="TBD", function="Transient clamp", status=PEND, sim_class="Symbol only - no model")
s1.part("R", "SHUNT (mOhm from peak I, TBD)", N(**{"1": "VBATT_PROT", "2": "VBATT_MAIN"}),
        manufacturer="TBD", mpn="TBD", function="Battery current sense shunt", status=PEND, sim_class="Ideal passive - ngspice")
s1.part("POWER_MONITOR_PROV", "INA228-class monitor (verify pins)", N(**{"IN+": "VBATT_PROT", "IN-": "VBATT_MAIN", "VBUS": "VBATT_MAIN", "VS": "3V3_LOGIC", "GND": "GND_LOGIC", "A0": "GND_LOGIC", "A1": "GND_LOGIC", "SDA": "I2C_SDA", "SCL": "I2C_SCL", "ALERT": "PM_ALERT"}),
        manufacturer="Texas Instruments", mpn="INA228 (orderable code TBD)", function="Battery V/I monitor", voltage="VBUS to 85V per datasheet - verify", status=SEL, sim_class="Symbol available, no model; real-hardware validation",
        notes="UNVERIFIED pin order", ds="https://www.ti.com/lit/ds/symlink/ina228.pdf")
for n in ("VBATT_RAW", "VBATT_PROT", "VBATT_MAIN"):
    tp(s1, n)
tp(s1, "GND_PWR")
flag(s1, "VBATT_BMS")
flag(s1, "VBATT_PROT")
s1.text(["NOTES", "1. Precharge for VMOT bulk capacitance required if drive input caps are large (see sheet 05/09).",
         "2. Fuse/TVS/shunt values depend on peak current (sheet docs/Power_Budget).",
         "3. ALERT output goes to STM32 PM_ALERT input."], 1.27)

# ================================================================= 02 power
s2 = sheet(2, "02_Power_Distribution", "02_Power_Distribution",
           ["Branch fuses separate: compute, logic/sensors, motor, safety.",
            "Converters are non-isolated: GND pin sits on GND_PWR at the star; load returns use GND_LOGIC.",
            "Ratings TBD - do not select converters before measured loads."])
for nm, a, b, fn in (("F_COMP", "VBATT_MAIN", "VBATT_COMP", "Compute branch"),
                     ("F_LOGIC", "VBATT_MAIN", "VBATT_LOGIC", "Logic/sensor/audio/LiDAR branch"),
                     ("F_MOT", "VBATT_MAIN", "VBATT_MOT", "Motor branch (feeds K1 contactor, sheet 09)"),
                     ("F_SAFE", "VBATT_MAIN", "V_SAFE_FUSED", "Safety circuit branch")):
    fuse(s2, f"{nm} rating TBD", a, b, fn)
for vin, vout, val, fn in (("VBATT_COMP", "V_COMPUTE_IN", "-> Jetson carrier input (volt per carrier TBD)", "Compute rail"),
                           ("VBATT_LOGIC", "V5_LOGIC", "-> 5V logic (Nucleo E5V, fan)", "5V logic rail"),
                           ("VBATT_LOGIC", "V5_SENS", "-> 5V sensors/encoders/prox", "5V sensor rail"),
                           ("VBATT_LOGIC", "V_LIDAR", "-> LiDAR rail (voltage TBD)", "LiDAR rail"),
                           ("VBATT_LOGIC", "V_AUDIO", "-> audio amp rail (voltage TBD)", "Audio rail")):
    s2.part("DCDC_PROV", "DC-DC " + val, N(VIN=vin, EN=vin, GND="GND_PWR", VOUT=vout, PGOOD="NC"),
            manufacturer="TBD", mpn="TBD", function=fn, voltage="input 21-29.4V class", current="TBD", status=PEND,
            sim_class="Custom symbol - ngspice only with chosen model", notes="EN tied to VIN provisional; PGOOD NC")
s2.part("NETTIE", "STAR POINT GND_PWR to GND_LOGIC", N(**{"1": "GND_PWR", "2": "GND_LOGIC"}), function="Single-point ground tie", status="Design", sim_class="n/a")
cap(s2, "100uF/bulk TBD", "VBATT_MAIN", "GND_PWR", "Bulk on main bus")
s2.part("CP", "VBATT bulk (TBD)", {"1": "VBATT_LOGIC", "2": "GND_PWR"}, manufacturer="TBD", mpn="TBD", function="Bulk input to logic converters", status=PEND, sim_class="Ideal passive - ngspice")
for n in ("V_COMPUTE_IN", "V5_LOGIC", "V5_SENS", "V_LIDAR", "V_AUDIO", "V_SAFE_FUSED", "GND_LOGIC"):
    tp(s2, n)
for n in ("VBATT_MAIN", "VBATT_COMP", "VBATT_LOGIC", "VBATT_MOT", "V_SAFE_FUSED", "GND_LOGIC"):
    flag(s2, n)
s2.text(["RAIL TABLE (assumptions in docs/Power_Budget.md)",
         "VBATT_MAIN 21-29.4V class | V_COMPUTE_IN per carrier | V5_LOGIC | V5_SENS | V_LIDAR TBD | V_AUDIO TBD",
         "VMOT: switched by K1 (sheet 09) from VBATT_MOT | 3V3_LOGIC from NUCLEO onboard regulator (low current only)",
         "Grounds: GND_PWR (motors, drives, safety 24V) | GND_LOGIC (compute, MCU, sensors) | GND_AUDIO (sheet 07)"], 1.27)

# ================================================================= 03 jetson
s3 = sheet(3, "03_Jetson_Interface", "03_Jetson_Interface",
           ["Config A: AGX Orin 64GB + dev-kit/compatible carrier. Config B: Orin NX 16GB + compatible carrier.",
            "Mutually exclusive. Carrier model PENDING: this sheet is interface-level, no Jetson pin numbers invented.",
            "Logic is 3.3V assumed - verify on chosen carrier."])
s3.part("JETSON_CARRIER_IF", "Cfg A AGX Orin 64GB | Cfg B Orin NX 16GB", N(
    VIN="V_COMPUTE_IN", GND="GND_LOGIC", UART_TX="JET_TO_STM_UART", UART_RX="STM_TO_JET_UART",
    GPIO_MOTOR_ON_N="MOTOR_PWR_ON_N", GPIO_AUDIO_MUTE="JET_AUDIO_MUTE", FAN_PWM="JET_FAN_PWM", FAN_TACH="JET_FAN_TACH",
    USB_OAK_VBUS="USB_OAK_VBUS", USB_OAK_DM="USB_OAK_DM", USB_OAK_DP="USB_OAK_DP",
    USB_MIC_VBUS="USB_MIC_VBUS", USB_MIC_DM="USB_MIC_DM", USB_MIC_DP="USB_MIC_DP",
    USB_DAC_VBUS="USB_DAC_VBUS", USB_DAC_DM="USB_DAC_DM", USB_DAC_DP="USB_DAC_DP",
    ETH_TX_P="ETH_LIDAR_TXP", ETH_TX_N="ETH_LIDAR_TXN", ETH_RX_P="ETH_LIDAR_RXP", ETH_RX_N="ETH_LIDAR_RXN",
    CAN_TX_RESERVED="NC", CAN_RX_RESERVED="NC"),
    manufacturer="NVIDIA + carrier TBD", mpn="Jetson AGX Orin 64GB module OR Orin NX 16GB module; carrier TBD",
    function="AI compute", voltage="per carrier datasheet", current="TBD", status="Selected module, carrier PENDING",
    sim_class="Hardware represented by interface only - needs real hardware",
    notes="Jetson CAN reserved NC: needs transceiver if used. Verify carrier USB VBUS budget.")
s3.part("CONN_FAN4", "Fan/thermal (design TBD)", N(V5="V5_LOGIC", GND="GND_LOGIC", TACH="JET_FAN_TACH", PWM="JET_FAN_PWM"),
        manufacturer="TBD", mpn="TBD", function="Compute cooling", current="TBD", status=PEND, sim_class="Interface only")
tp(s3, "V_COMPUTE_IN")
s3.text(["INTERFACES",
         "USB: OAK-D Pro, microphone array, USB audio DAC use carrier USB ports (data NOT on MCU GPIO).",
         "Ethernet: 10/100 LiDAR pairs to sheet 06 (1000BASE-T pairs may be needed - verify LiDAR).",
         "UART: Jetson <-> STM32, 3.3V, common GND_LOGIC. CAN: reserved; MCU owns the CAN buses.",
         "MOTOR_PWR_ON_N is active-low status from sheet 09 optocoupler (pulled to 3V3_LOGIC)."], 1.27)

# ================================================================= 04 stm32
s4 = sheet(4, "04_STM32_Controller", "04_STM32_Controller",
           ["NUCLEO-F746ZG (STM32F746ZG). Pin numbers on the symbol are LOGICAL indices.",
            "Assign real Morpho/Arduino pins from ST UM1974 + CubeMX before layout. NOT done here.",
            "On-board ST-LINK handles SWD/reset/clock/decoupling."])
nuc = {"E5V": "V5_LOGIC", "GND": "GND_LOGIC", "3V3_OUT": "3V3_LOGIC", "MOTOR_PWR_ON_N": "MOTOR_PWR_ON_N",
       "PM_ALERT": "PM_ALERT", "BUMP1_N": "BUMP1_N", "BUMP2_N": "BUMP2_N", "PROX_IRQ": "PROX_IRQ",
       "UART_RX": "JET_TO_STM_UART", "UART_TX": "STM_TO_JET_UART", "CAN1_RX": "CAN1_RXD", "CAN1_TX": "CAN1_TXD",
       "CAN2_RX": "CAN2_RXD", "CAN2_TX": "CAN2_TXD", "IMU_MISO": "IMU_MISO", "IMU_INT": "IMU_INT",
       "IMU_SCK": "IMU_SCK", "IMU_MOSI": "IMU_MOSI", "IMU_CS": "IMU_CS", "I2C_SCL": "I2C_SCL", "I2C_SDA": "I2C_SDA",
       "DRV_EN": "DRV_EN_3V3", "SW_STOP_REQ": "SW_STOP_REQ", "SWD_VTREF": "SWD_VTREF", "SWDIO": "SWDIO",
       "SWCLK": "SWCLK", "NRST": "NRST"}
for w in ("FL", "FR", "RL", "RR"):
    nuc[f"ENC_{w}_A"] = f"ENC_{w}_A"
    nuc[f"ENC_{w}_B"] = f"ENC_{w}_B"
for i in range(1, 5):
    nuc[f"PWM_AUX{i}"] = f"PWM_AUX{i}"
for i in range(1, 3):
    nuc[f"GPIO_AUX{i}"] = f"GPIO_AUX{i}"
s4.part("NUCLEO_F746ZG_IF", "NUCLEO-F746ZG", nuc, manufacturer="STMicroelectronics", mpn="NUCLEO-F746ZG",
        function="Real-time controller", voltage="5V via E5V (JP3/power jumpers - verify UM1974)", current="TBD", status=SEL,
        sim_class="Hardware represented by interface only - firmware needs separate emulator/HIL",
        ds="https://www.st.com/resource/en/user_manual/um1974-stm32-nucleo144-boards-mb1137-stmicroelectronics.pdf",
        notes="Logical pin numbers; 3V3_OUT only for light loads")
s4.text(["NOTES",
         "1. bxCAN on F746 = classic CAN only (CAN1/CAN2 used). CAN-FD would need FDCAN MCU or SPI controller.",
         "2. Encoder timer pins: confirm 5V tolerance of the chosen pins; series resistors on sheet 05.",
         "3. Power select (E5V vs USB vs VIN) must be set by jumpers per UM1974 - UNVERIFIED here.",
         "4. SWD for target debug via ST-LINK/CN4 or external header on sheet 08."], 1.27)
flag(s4, "3V3_LOGIC")

# ================================================================= 05 drives
s5 = sheet(5, "05_Motor_Drives", "05_Motor_Drives",
           ["ASSUMPTION: four independently driven wheels (confirm mechanical design).",
            "Drive model PENDING: DRIVE_CONN is a provisional interface (VMOT, CAN, STO A/B, EN).",
            "STO pins are NOT valid until the real drive STO terminals are known."])
s5.part("CP", "VMOT bulk (TBD)", {"1": "VMOT", "2": "GND_PWR"}, manufacturer="TBD", mpn="TBD", function="Motor bus bulk cap", status=PEND, sim_class="Ideal passive - ngspice")
tp(s5, "VMOT")
for w in ("FL", "FR", "RL", "RR"):
    fuse(s5, f"F_{w} rating TBD", "VMOT", f"VMOT_{w}", f"Wheel {w} drive branch")
    s5.part("DRIVE_CONN", f"Wheel {w} drive (PENDING)",
            N(VMOT=f"VMOT_{w}", GND_PWR="GND_PWR", CAN_H="CAN_DRV_H", CAN_L="CAN_DRV_L", STO_A="STO_A", STO_B="STO_B", EN="DRV_EN_24V"),
            manufacturer="TBD", mpn="TBD", function=f"Wheel {w} BLDC/PMSM servo drive", voltage="24V class", current="TBD", status=PEND,
            sim_class="Hardware represented by connector/interface only")
    s5.part("ENCODER_CONN", f"Wheel {w} encoder (PENDING)",
            N(V5="V5_SENS", A=f"ENC_{w}_A_RAW", B=f"ENC_{w}_B_RAW", GND="GND_LOGIC"),
            manufacturer="TBD", mpn="TBD", function=f"Wheel {w} odometry encoder", voltage="5V assumed", status=PEND, sim_class="Interface only")
    res(s5, "1k (Rs, provisional)", f"ENC_{w}_A_RAW", f"ENC_{w}_A", fn=f"Series protect enc {w} A")
    res(s5, "1k (Rs, provisional)", f"ENC_{w}_B_RAW", f"ENC_{w}_B", fn=f"Series protect enc {w} B")
for a in ("ARM_L", "ARM_R", "HEAD"):
    fuse(s5, f"F_{a} rating TBD", "VMOT", f"VMOT_{a}", f"{a} branch")
    s5.part("DRIVE_CONN", f"{a} actuators (PENDING)",
            N(VMOT=f"VMOT_{a}", GND_PWR="GND_PWR", CAN_H="CAN_ARM_H", CAN_L="CAN_ARM_L", STO_A="STO_A", STO_B="STO_B", EN="DRV_EN_24V"),
            manufacturer="TBD", mpn="TBD", function=f"{a} actuator harness", current="TBD", status=PEND,
            sim_class="Hardware represented by connector/interface only")
s5.text(["NOTES",
         "1. Fit CAN termination only at physical bus ends (sheet 08 jumpers).",
         "2. Motor return current uses GND_PWR only; encoders/sensors return on GND_LOGIC.",
         "3. Wire gauge/connector sizing needs peak current: see docs/Wiring_and_Grounding.md method."], 1.27)

# ================================================================= 06 sensors
s6 = sheet(6, "06_Camera_LiDAR_IMU", "06_Camera_LiDAR_IMU",
           ["OAK-D Pro on USB (via carrier). LiDAR via Ethernet + own power rail. IMU on SPI.",
            "No USB/Ethernet data lines are connected to MCU GPIO."])
s6.part("OAK_D_PRO_USB_IF", "OAK-D Pro (USB)", N(VBUS="USB_OAK_VBUS", **{"D-": "USB_OAK_DM", "D+": "USB_OAK_DP"}, GND="GND_LOGIC"),
        manufacturer="Luxonis", mpn="OAK-D Pro (USB variant; SKU TBD)", function="Stereo depth/RGB camera",
        voltage="5V USB", current="verify peak incl. IR illuminators", status=SEL, sim_class="Hardware represented by interface only - real hardware validation",
        ds="https://docs.luxonis.com/hardware/products/OAK-D%20Pro", notes="Check whether carrier USB port supplies enough current")
s6.part("LIDAR_PWR_CONN", "LiDAR power (model PENDING)", N(VLIDAR="V_LIDAR", GND="GND_LOGIC"),
        manufacturer="TBD", mpn="TBD", function="LiDAR supply", status=PEND, sim_class="Interface only")
s6.part("LIDAR_ETH_CONN", "LiDAR Ethernet (model PENDING)", {"TX+": "ETH_LIDAR_RXP", "TX-": "ETH_LIDAR_RXN", "RX+": "ETH_LIDAR_TXP", "RX-": "ETH_LIDAR_TXN"},
        manufacturer="TBD", mpn="TBD", function="LiDAR data", status=PEND, sim_class="Interface only",
        notes="LiDAR TX pairs to Jetson RX pairs (crossover) - verify magnetics/PHY and PoE absent")
s6.part("IMU_SPI_PROV", "IMU (PENDING, SPI)", N(VDD="3V3_LOGIC", GND="GND_LOGIC", SCLK="IMU_SCK", MOSI="IMU_MOSI", CS="IMU_CS", MISO="IMU_MISO", INT="IMU_INT"),
        manufacturer="TBD", mpn="TBD", function="Inertial measurement", voltage="3.3V assumed", status=PEND, sim_class="Custom symbol - no model")
cap(s6, "100nF", "3V3_LOGIC", "GND_LOGIC", "IMU decoupling")
s6.part("PROX_SENSOR_CONN", "Proximity sensor (PENDING)", N(V5="V5_SENS", GND="GND_LOGIC", OUT="PROX_OUT_5V"),
        manufacturer="TBD", mpn="TBD", function="Proximity", status=PEND, sim_class="Interface only")
res(s6, "10k divider top (provisional)", "PROX_OUT_5V", "PROX_IRQ", fn="Level divider for 5V sensor output")
res(s6, "20k divider bottom (provisional)", "PROX_IRQ", "GND_LOGIC", fn="Level divider for 5V sensor output")
for i in (1, 2):
    s6.part("BUMPER_CONN", f"Bumper {i} (PENDING)", N(SIG=f"BUMP{i}_N", GND="GND_LOGIC"), manufacturer="TBD", mpn="TBD",
            function="Collision contact", status=PEND, sim_class="Interface only")
    res(s6, "10k pull-up", "3V3_LOGIC", f"BUMP{i}_N", fn="Bumper pull-up")
s6.text(["NOTES", "1. Divider assumes 5V push-pull output: remove if sensor is open-drain/3.3V.",
         "2. IMU orientation and mounting handled mechanically.", "3. Wheel encoders are on sheet 05."], 1.27)

# ================================================================= 07 audio
s7 = sheet(7, "07_Audio", "07_Audio",
           ["Mic array and DAC on USB through Jetson (not on MCU). Amplifier rail V_AUDIO, ground GND_AUDIO.",
            "All audio parts PENDING selection."])
s7.part("USB_DEV_CONN", "USB mic array (PENDING)", N(VBUS="USB_MIC_VBUS", **{"D-": "USB_MIC_DM", "D+": "USB_MIC_DP"}, GND="GND_LOGIC"),
        manufacturer="TBD", mpn="TBD", function="Microphone array", voltage="5V USB", status=PEND, sim_class="Interface only")
s7.part("USB_AUDIO_DAC_PROV", "USB audio DAC (PENDING)", N(VBUS="USB_DAC_VBUS", **{"D-": "USB_DAC_DM", "D+": "USB_DAC_DP"}, GND="GND_LOGIC", LINE_OUT="AUDIO_LINE", AGND="GND_AUDIO"),
        manufacturer="TBD", mpn="TBD", function="Audio output", status=PEND, sim_class="Interface only")
s7.part("AUDIO_AMP_PROV", "Class-D amp (PENDING)", N(**{"IN+": "AUDIO_LINE", "IN-": "GND_AUDIO", "MUTE": "AMP_MUTE", "VDD": "V_AUDIO", "GND": "GND_AUDIO", "OUT+": "SPK_P", "OUT-": "SPK_N"}),
        manufacturer="TBD", mpn="TBD", function="Speaker amplifier", voltage="V_AUDIO TBD", status=PEND, sim_class="Custom symbol - ngspice if model chosen")
s7.part("SPEAKER_CONN", "Speaker (PENDING)", N(**{"SPK+": "SPK_P", "SPK-": "SPK_N"}), manufacturer="TBD", mpn="TBD", function="Speaker", status=PEND, sim_class="Interface only")
res(s7, "100k pull-down default mute", "AMP_MUTE", "GND_AUDIO", fn="Amp mute default")
res(s7, "1k mute series (provisional)", "JET_AUDIO_MUTE", "AMP_MUTE", fn="Mute drive from Jetson 3.3V GPIO")
s7.part("CP", "Amp bulk (TBD)", {"1": "V_AUDIO", "2": "GND_AUDIO"}, manufacturer="TBD", mpn="TBD", function="Amp supply bulk", status=PEND, sim_class="Ideal passive - ngspice")
cap(s7, "100nF", "V_AUDIO", "GND_AUDIO", "Amp decoupling")
s7.part("NETTIE", "STAR GND_LOGIC to GND_AUDIO", {"1": "GND_LOGIC", "2": "GND_AUDIO"}, function="Audio ground single-point tie", status="Design", sim_class="n/a")
flag(s7, "GND_AUDIO")
s7.text(["NOTES", "1. If an I2S codec is chosen instead, replace USB DAC and route I2S from Jetson per carrier docs.",
         "2. Mute threshold level of amp unknown - verify 3.3V compatibility."], 1.27)

# ================================================================= 08 comms
s8 = sheet(8, "08_Communications", "08_Communications",
           ["CAN1 -> wheel drive bus, CAN2 -> upper-body bus. 3.3V logic at MCU, bus-level at CANH/CANL.",
            "CAN-FD not available on F746 bxCAN."])
for i, (bus, tx, rx) in enumerate((("DRV", "CAN1_TXD", "CAN1_RXD"), ("ARM", "CAN2_TXD", "CAN2_RXD")), 1):
    s8.part("CAN_XCVR_SN65HVD230", f"SN65HVD230 CAN{i}",
            N(D=tx, GND="GND_LOGIC", VCC="3V3_LOGIC", Rs="GND_LOGIC", R=rx, Vref="NC", CANL=f"CAN_{bus}_L", CANH=f"CAN_{bus}_H"),
            manufacturer="Texas Instruments", mpn="SN65HVD230DR", function=f"CAN{i} transceiver ({bus} bus)", voltage="3.3V", status=SEL,
            sim_class="Symbol custom, no model; real-hardware validation", ds="https://www.ti.com/lit/ds/symlink/sn65hvd230.pdf",
            notes="Rs to GND = high-speed mode (verify)")
    cap(s8, "100nF", "3V3_LOGIC", "GND_LOGIC", f"CAN{i} xcvr decoupling")
    res(s8, "120R termination", f"CAN_{bus}_H", f"TERM_{bus}", status="Required at bus ends", fn=f"CAN {bus} termination")
    s8.part("JUMPER", f"Termination link JP{bus}", {"1": f"TERM_{bus}", "2": f"CAN_{bus}_L"}, function="Termination enable", status="Design", sim_class="n/a")
    s8.part("ESD_CAN_PROV", f"CAN {bus} ESD (PENDING)", N(H=f"CAN_{bus}_H", L=f"CAN_{bus}_L", GND="GND_LOGIC"), manufacturer="TBD", mpn="TBD", function="ESD", status=PEND, sim_class="Symbol only")
    s8.part("CONN_CAN4", f"CAN {bus} bus connector", N(CANH=f"CAN_{bus}_H", CANL=f"CAN_{bus}_L", GND="GND_LOGIC", SHIELD="NC"), manufacturer="TBD", mpn="TBD", function=f"{bus} CAN bus", status=PEND, sim_class="Interface only")
res(s8, "4.7k I2C SDA pull-up", "3V3_LOGIC", "I2C_SDA", fn="I2C pull-up")
res(s8, "4.7k I2C SCL pull-up", "3V3_LOGIC", "I2C_SCL", fn="I2C pull-up")
s8.part("CONN_UART3", "UART debug (Jetson link)", N(TX="STM_TO_JET_UART", RX="JET_TO_STM_UART", GND="GND_LOGIC"), manufacturer="TBD", mpn="TBD", function="UART debug tap", status=TYP, sim_class="Interface only")
s8.part("CONN_SWD5", "SWD header", N(VTREF="SWD_VTREF", SWDIO="SWDIO", SWCLK="SWCLK", NRST="NRST", GND="GND_LOGIC"), manufacturer="TBD", mpn="TBD", function="External SWD", status=TYP, sim_class="Interface only",
        notes="Custom 1x05 - not a standard Cortex header")
s8.part("CONN_AUX7", "Aux PWM/GPIO", N(PWM1="PWM_AUX1", PWM2="PWM_AUX2", PWM3="PWM_AUX3", PWM4="PWM_AUX4", GPIO1="GPIO_AUX1", GPIO2="GPIO_AUX2", GND="GND_LOGIC"), manufacturer="TBD", mpn="TBD", function="Aux", status=TYP, sim_class="Interface only")
s8.text(["BUS SUMMARY",
         "CAN: SN65HVD230 x2 | I2C: PM monitor | SPI: IMU | UART: Jetson | USB/Ethernet: sheet 03/06/07 only",
         "I2C pull-ups here only; do not add elsewhere. SPI/I2C level 3.3V."], 1.27)

# ================================================================= 09 safety
s9 = sheet(9, "09_Safety_EStop", "09_Safety_EStop",
           ["Hardware E-stop path: dual channel -> safety relay -> K1 contactor + drive STO.",
            "Software can only ADD a stop (K2 NC contacts in series). It cannot clear or bypass hardware.",
            "NOT a certified safety design: PL/SIL assessment and certified parts still required."])
s9.part("ESTOP_MUSHROOM_2CH", "E-stop mushroom 2-ch (PENDING)", N(CH_A_1="SR_S11", CH_A_2="ESTOP_A1", CH_B_1="SR_S21", CH_B_2="ESTOP_B1"),
        manufacturer="TBD", mpn="TBD", function="Operator E-stop", status=PEND, sim_class="Interface only")
s9.part("RELAY_2NC_PROV", "K2 SW-stop relay (PENDING)", N(A1="V_SAFE_FUSED", A2="K2_COIL_N", **{"11": "ESTOP_A1", "12": "ESTOP_A2", "21": "ESTOP_B1", "22": "ESTOP_B2"}),
        manufacturer="TBD", mpn="TBD", function="Software stop request (adds stop only)", voltage="coil 24V class", status=PEND, sim_class="Custom symbol - needs model")
s9.part("NPN_PROV", "K2 driver (PENDING)", N(B="K2_BASE", C="K2_COIL_N", E="GND_LOGIC"), manufacturer="TBD", mpn="TBD", function="K2 coil driver", status=PEND, sim_class="Custom symbol - ngspice if model chosen")
res(s9, "1k base (provisional)", "SW_STOP_REQ", "K2_BASE", fn="K2 base drive")
res(s9, "10k base pull-down", "K2_BASE", "GND_LOGIC", fn="Default off")
s9.part("DIODE", "Flyback K2", {"K": "V_SAFE_FUSED", "A": "K2_COIL_N"}, manufacturer="TBD", mpn="TBD", function="K2 coil flyback", status=PEND, sim_class="Symbol only")
s9.part("CONN_ESTOP_EXT4", "External E-stop loop", N(A_OUT="ESTOP_A2", A_RET="ESTOP_A3", B_OUT="ESTOP_B2", B_RET="ESTOP_B3"), manufacturer="TBD", mpn="TBD", function="External stop chain", status=PEND, sim_class="Interface only")
s9.part("JUMPER", "Link JP_EXT_A (fit if unused)", {"1": "ESTOP_A2", "2": "ESTOP_A3"}, function="Bypass unused external loop A", status="Design", sim_class="n/a")
s9.part("JUMPER", "Link JP_EXT_B (fit if unused)", {"1": "ESTOP_B2", "2": "ESTOP_B3"}, function="Bypass unused external loop B", status="Design", sim_class="n/a")
s9.part("PUSHBUTTON_NO", "Reset button", {"1": "SR_Y1", "2": "SR_Y2"}, manufacturer="TBD", mpn="TBD", function="Safety relay manual reset", status=PEND, sim_class="Interface only")
s9.part("SAFETY_RELAY_PROV", "Safety relay (NOT SELECTED)",
        N(A1="V_SAFE_FUSED", A2="GND_PWR", S11="SR_S11", S12="ESTOP_A3", S21="SR_S21", S22="ESTOP_B3", Y1="SR_Y1", Y2="SR_Y2",
          **{"13": "V_SAFE_FUSED", "14": "K1_COIL_P", "23": "V_SAFE_FUSED", "24": "STO_A", "33": "V_SAFE_FUSED", "34": "STO_B"}),
        manufacturer="TBD", mpn="TBD", function="Dual-channel safety logic", status=PEND, sim_class="Hardware represented by interface only",
        notes="Terminal naming generic; replace with certified part")
s9.part("CONTACTOR_PROV", "K1 motor contactor (PENDING)", N(A1="K1_COIL_P", A2="GND_PWR", **{"1": "VBATT_MOT", "2": "VMOT", "13": "V_SAFE_FUSED", "14": "K1_AUX_OUT"}),
        manufacturer="TBD", mpn="TBD", function="Motor power disconnect", voltage="24V class", current="TBD (peak)", status=PEND, sim_class="Custom symbol - needs model")
s9.part("DIODE", "Flyback K1", {"K": "K1_COIL_P", "A": "GND_PWR"}, manufacturer="TBD", mpn="TBD", function="K1 coil flyback", status=PEND, sim_class="Symbol only")
res(s9, "4.7k opto LED (6mA @29.4V)", "K1_AUX_OUT", "OPTO3_A", fn="Contactor feedback LED resistor")
s9.part("OPTO_PC817", "Feedback opto PC817", N(A="OPTO3_A", K="GND_PWR", E="GND_LOGIC", C="MOTOR_PWR_ON_N"),
        manufacturer="Sharp (or equivalent)", mpn="PC817", function="Isolated K1 status to MCU/Jetson", status=SEL, sim_class="Symbol custom; ngspice with generic opto model",
        notes="Pinout 1A 2K 3E 4C - verify")
res(s9, "10k pull-up", "3V3_LOGIC", "MOTOR_PWR_ON_N", fn="Status pull-up (active low)")
res(s9, "1k opto LED (provisional)", "DRV_EN_3V3", "OPTO2_A", fn="Enable opto LED resistor")
s9.part("OPTO_PC817", "Enable opto PC817", N(A="OPTO2_A", K="GND_LOGIC", E="DRV_EN_RAW", C="V_SAFE_FUSED"),
        manufacturer="Sharp (or equivalent)", mpn="PC817", function="Isolated drive-enable", status=SEL, sim_class="Symbol custom; ngspice with generic opto model",
        notes="Output drives drive EN input: current capability must be checked")
res(s9, "TBD series", "DRV_EN_RAW", "DRV_EN_24V", status=PEND, fn="Enable output series")
tp(s9, "STO_A")
tp(s9, "STO_B")
tp(s9, "K1_COIL_P")
flag(s9, "VMOT")
flag(s9, "K1_COIL_P")
flag(s9, "STO_A")
flag(s9, "STO_B")
s9.text(["BEHAVIOUR",
         "E-stop open or K2 energised -> safety relay drops -> K1 de-energised (VMOT off) + STO_A/STO_B low.",
         "Reset needed after release (Y1/Y2). K1 aux contact feeds MOTOR_PWR_ON_N for software status only.",
         "Missing: EDM feedback wiring, contact ratings, certified relay selection."], 1.27)

# ================================================================= 10 wiring
s10 = sheet(10, "10_Connectors_Wiring", "10_Connectors_Wiring",
            ["Documentation sheet: connector index and wiring rules. Real connectors live on their functional sheets.",
             "See docs/Interface_and_Connector_Pinouts.csv and docs/Wiring_and_Grounding.md."])
s10.text(["CONNECTOR INDEX (reference = auto-numbered; see BOM)",
          "Power: sheet 01-02 | Jetson IF: 03 | MCU: 04 | Drives/encoders: 05 | Sensors: 06 | Audio: 07 | Buses/debug: 08 | Safety: 09"], 1.27)
s10.text(["GROUNDING",
          "GND_PWR: battery, drives, safety 24V, motors. GND_LOGIC: compute, MCU, sensors. GND_AUDIO: amp.",
          "Joined at single points by net ties (02: PWR/LOGIC, 07: LOGIC/AUDIO). Chassis bond: TBD."], 1.27)
s10.text(["WIRING RULES",
          "Motor leads: twisted pairs, short, fused per branch. Signals: twisted/shielded away from VMOT.",
          "Wire gauge = f(peak current, length, temperature) - computed after peak current known (docs)."], 1.27)

ALL = [root, s1, s2, s3, s4, s5, s6, s7, s8, s9, s10]
