"""
GRACEEMO-01 — Base, Power Distribution & Compute Bay Packaging
Creates realistic engineering component envelopes based on the hardware manifest.
"""

import bpy
from mathutils import Vector, Euler
try:
    from phase3.manifest.hardware_manifest import get_component
except ImportError:
    from manifest.hardware_manifest import get_component

def get_or_create_material(name, color=(0.5, 0.5, 0.5, 1.0), metallic=0.0, roughness=0.5):
    """Fetch or create a PBR engineering material."""
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = color
            bsdf.inputs["Metallic"].default_value = metallic
            bsdf.inputs["Roughness"].default_value = roughness
    return mat

def create_box_envelope(name, loc, size, collection, mat=None, parent_obj=None, comp_data=None):
    """Create a dimensionally accurate box envelope."""
    obj = bpy.data.objects.get(name)
    if not obj:
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        # Create standard box vertices: size=(dx, dy, dz)
        dx, dy, dz = size[0]/2.0, size[1]/2.0, size[2]/2.0
        verts = [
            (-dx, -dy, -dz), (dx, -dy, -dz), (dx, dy, -dz), (-dx, dy, -dz),
            (-dx, -dy, dz), (dx, -dy, dz), (dx, dy, dz), (-dx, dy, dz)
        ]
        faces = [
            (0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
            (2, 3, 7, 6), (0, 3, 7, 4), (1, 2, 6, 5)
        ]
        mesh.from_pydata(verts, [], faces)
        mesh.update()
    else:
        if collection not in obj.users_collection:
            for c in list(obj.users_collection): c.objects.unlink(obj)
            collection.objects.link(obj)

    obj.location = loc
    if mat:
        if not obj.data.materials:
            obj.data.materials.append(mat)
        else:
            obj.data.materials[0] = mat

    if parent_obj and obj.parent != parent_obj:
        m = obj.matrix_world.copy()
        obj.parent = parent_obj
        obj.matrix_parent_inverse = parent_obj.matrix_world.inverted()
        obj.matrix_world = m

    # Tag custom properties from hardware manifest
    if comp_data:
        obj["component_id"] = comp_data.get("component_id", "UNKNOWN")
        obj["component_name"] = comp_data.get("component_name", "UNKNOWN")
        obj["category"] = comp_data.get("category", "UNKNOWN")
        obj["mass_estimate_kg"] = float(comp_data.get("mass", 0.0))
        obj["status"] = comp_data.get("status", "UNKNOWN")
        obj["mounting_pattern"] = comp_data.get("mounting_pattern", "UNKNOWN")

    return obj

def setup_base_power_and_compute(manifest):
    """Package power distribution and compute bay envelopes."""
    col_power = bpy.data.collections.get("02_POWER") or bpy.context.scene.collection
    col_compute = bpy.data.collections.get("03_COMPUTE") or bpy.data.collections.get("05_COMPUTE") or bpy.context.scene.collection
    base_link = bpy.data.objects.get("base_link")
    torso_link = bpy.data.objects.get("torso_link")

    # Engineering Materials
    mat_battery = get_or_create_material("MAT_ENG_BatteryCell", (0.15, 0.20, 0.45, 1.0), 0.2, 0.3)
    mat_mount = get_or_create_material("MAT_ENG_AluminumAnodized", (0.7, 0.72, 0.75, 1.0), 0.85, 0.25)
    mat_pcb = get_or_create_material("MAT_ENG_PCB_Green", (0.05, 0.25, 0.12, 1.0), 0.1, 0.4)
    mat_heatsink = get_or_create_material("MAT_ENG_BlackAnodizedHeatsink", (0.08, 0.08, 0.09, 1.0), 0.9, 0.2)
    mat_safety_red = get_or_create_material("MAT_ENG_SafetyRed", (0.85, 0.08, 0.08, 1.0), 0.1, 0.3)
    mat_copper = get_or_create_material("MAT_ENG_CopperBus", (0.85, 0.45, 0.20, 1.0), 0.95, 0.15)

    created_objects = []

    # --------------------------------------------------------------------------
    # 1. Battery Packaging (02_POWER in base_link)
    # --------------------------------------------------------------------------
    c_batt = get_component("PWR-01", manifest)
    dim_batt = (c_batt["length"], c_batt["width"], c_batt["height"]) if c_batt else (0.28, 0.18, 0.13)
    # Battery sits low in chassis for lowest center of mass (Z: 0.085 relative to world, ~ -0.035 rel to base_link)
    o_batt = create_box_envelope(
        "COMP_BATTERY_ENVELOPE", (0.0, 0.0, -0.025), dim_batt,
        col_power, mat_battery, base_link, c_batt
    )
    created_objects.append(o_batt)

    # Battery Mounting Rails (Left / Right)
    c_mount = get_component("MEC-03", manifest)
    dim_mount = (c_mount["length"], c_mount["width"], c_mount["height"]) if c_mount else (0.14, 0.19, 0.035)
    o_mt_l = create_box_envelope("BATTERY_MOUNT_LEFT", (-0.11, 0.0, -0.085), dim_mount, col_power, mat_mount, base_link, c_mount)
    o_mt_r = create_box_envelope("BATTERY_MOUNT_RIGHT", (0.11, 0.0, -0.085), dim_mount, col_power, mat_mount, base_link, c_mount)
    created_objects.extend([o_mt_l, o_mt_r])

    # Battery Service Access Cover Concept
    c_access = get_component("MEC-04", manifest)
    dim_acc = (c_access["length"], c_access["width"], c_access["height"]) if c_access else (0.32, 0.22, 0.004)
    o_acc = create_box_envelope("BATTERY_SERVICE_ACCESS", (0.0, 0.16, 0.08), dim_acc, col_power, mat_mount, base_link, c_access)
    created_objects.append(o_acc)

    # Power Distribution Components
    c_fuse = get_component("PWR-02", manifest)
    o_fuse = create_box_envelope("MAIN_FUSE", (-0.15, -0.10, 0.04), (0.06, 0.035, 0.03), col_power, mat_safety_red, base_link, c_fuse)

    c_relay = get_component("PWR-03", manifest)
    o_dist = create_box_envelope("POWER_DISTRIBUTION", (-0.15, 0.05, 0.04), (0.065, 0.050, 0.055), col_power, mat_copper, base_link, c_relay)

    c_dcdc = get_component("PWR-04", manifest)
    o_dcdc = create_box_envelope("DC_DC_CONVERTER", (0.15, -0.05, 0.04), (0.120, 0.080, 0.040), col_power, mat_heatsink, base_link, c_dcdc)

    c_chg = get_component("PWR-05", manifest)
    o_chg = create_box_envelope("CHARGING_PORT", (0.0, 0.24, -0.03), (0.075, 0.045, 0.035), col_power, mat_copper, base_link, c_chg)

    c_sw = get_component("SAF-02", manifest)
    o_sw = create_box_envelope("MAIN_SWITCH", (0.16, 0.20, -0.02), (0.045, 0.030, 0.040), col_power, mat_heatsink, base_link, c_sw)

    # Emergency Stop switch on upper torso deck / spine
    c_estop = get_component("SAF-01", manifest)
    o_estop = create_box_envelope("EMERGENCY_STOP", (0.0, 0.12, 0.24), (0.055, 0.055, 0.065), col_power, mat_safety_red, torso_link, c_estop)

    created_objects.extend([o_fuse, o_dist, o_dcdc, o_chg, o_sw, o_estop])

    # --------------------------------------------------------------------------
    # 2. Compute Bay Packaging (05_COMPUTE inside torso_link)
    # --------------------------------------------------------------------------
    # AI Computer Envelope (Jetson Orin Nano / AGX compatible envelope)
    c_ai = get_component("CMP-01", manifest)
    dim_ai = (c_ai["length"], c_ai["width"], c_ai["height"]) if c_ai else (0.140, 0.105, 0.055)
    o_ai = create_box_envelope("COMP_AI_COMPUTER_ENVELOPE", (0.0, 0.02, 0.08), dim_ai, col_compute, mat_heatsink, torso_link, c_ai)

    # MCU Carrier Board
    c_mcu = get_component("CMP-02", manifest)
    dim_mcu = (c_mcu["length"], c_mcu["width"], c_mcu["height"]) if c_mcu else (0.110, 0.085, 0.025)
    o_mcu = create_box_envelope("COMP_MCU_ENVELOPE", (0.0, 0.02, -0.06), dim_mcu, col_compute, mat_pcb, torso_link, c_mcu)

    # Motor Controllers (Dual BLDC)
    c_mc = get_component("CTL-01", manifest)
    dim_mc = (c_mc["length"], c_mc["width"], c_mc["height"]) if c_mc else (0.105, 0.075, 0.035)
    o_mc1 = create_box_envelope("COMP_MOTOR_CONTROLLER_ENVELOPE_L", (-0.11, 0.01, -0.04), dim_mc, col_compute, mat_heatsink, torso_link, c_mc)
    o_mc2 = create_box_envelope("COMP_MOTOR_CONTROLLER_ENVELOPE_R", (0.11, 0.01, -0.04), dim_mc, col_compute, mat_heatsink, torso_link, c_mc)

    # Ethernet Switch
    c_eth = get_component("COM-02", manifest)
    dim_eth = (c_eth["length"], c_eth["width"], c_eth["height"]) if c_eth else (0.100, 0.065, 0.028)
    o_eth = create_box_envelope("COMP_ETH_SWITCH_ENVELOPE", (0.0, -0.05, -0.06), dim_eth, col_compute, mat_mount, torso_link, c_eth)

    # Serial Bus Actuator Hub
    c_hub = get_component("CTL-02", manifest)
    dim_hub = (c_hub["length"], c_hub["width"], c_hub["height"]) if c_hub else (0.080, 0.055, 0.020)
    o_hub = create_box_envelope("COMP_SERIAL_BUS_HUB_ENVELOPE", (0.0, -0.04, 0.16), dim_hub, col_compute, mat_pcb, torso_link, c_hub)

    # IMU Envelope (at imu_link)
    c_imu = get_component("SEN-03", manifest)
    dim_imu = (c_imu["length"], c_imu["width"], c_imu["height"]) if c_imu else (0.035, 0.025, 0.012)
    imu_link = bpy.data.objects.get("imu_link") or torso_link
    o_imu = create_box_envelope("COMP_IMU_ENVELOPE", (0.0, 0.0, 0.0), dim_imu, col_compute, mat_pcb, imu_link, c_imu)

    # Compute Bay Maintenance Door
    c_tdoor = get_component("MEC-05", manifest)
    dim_tdoor = (c_tdoor["length"], c_tdoor["width"], c_tdoor["height"]) if c_tdoor else (0.240, 0.220, 0.003)
    o_tdoor = create_box_envelope("COMPUTE_SERVICE_ACCESS", (0.0, 0.13, 0.04), dim_tdoor, col_compute, mat_mount, torso_link, c_tdoor)

    created_objects.extend([o_ai, o_mcu, o_mc1, o_mc2, o_eth, o_hub, o_imu, o_tdoor])

    return created_objects
