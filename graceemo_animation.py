# ============================================================
# GRACEEMO-01 - ANIMATION ADD-ON (Blender 5.x)
#
# Run AFTER the 4-wheel model script (or paste at the very end of it).
# No parts are modified, moved, resized or re-made.
#
# Adds:
#   - 4 wheels rolling (wheel + blue ring + hub spin together)
#   - Right arm waving, left arm swinging, both hands curling fingers
#
# Timeline: frames 1-240 @ 24 fps (loops cleanly: frame 240 = frame 1 pose)
#
# How hands move without changing parts:
#   Small empties named ANIM_* are placed on the joint positions
#   (shoulder / elbow / wrist / knuckles) and the existing parts are
#   parented to them at their current position. The empties are animated.
# ============================================================

import bpy
import math

TARGET = "01_GRACEEMO_REFERENCE"

# ---------------- SETTINGS ----------------
FPS = 24
END = 240
WHEEL_TURNS = 6            # full wheel revolutions over the timeline
WHEEL_FORWARD = True       # robot front = -Y
ADD_WHEEL_MARKERS = False  # True = adds a small orange tread mark on each
                           # wheel so the spin is visible (adds 4 tiny parts)
# ------------------------------------------

COL = bpy.data.collections.get(TARGET)
if COL is None:
    raise RuntimeError("Run the GRACEEMO model script first (collection not found).")

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = END
scene.render.fps = FPS
scene.frame_set(1)
bpy.context.view_layer.update()


# ============================================================
# CLEAN PREVIOUS ANIMATION RUN (safe to re-run)
# ============================================================

for o in list(COL.objects):
    if o.parent is not None and o.parent.name.startswith("ANIM_"):
        m = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = m

for o in list(COL.objects):
    if o.name.startswith("ANIM_") or o.name.startswith("WHEEL_MARK_"):
        bpy.data.objects.remove(o, do_unlink=True)

for o in COL.objects:
    if o.animation_data:
        o.animation_data_clear()

bpy.context.view_layer.update()


# ============================================================
# HELPERS
# ============================================================

def get(name):
    return bpy.data.objects.get(name)


def pivot(name, loc, parent=None):
    """Empty placed at a joint. Parent keeps world position unchanged."""
    p = bpy.data.objects.new("ANIM_" + name, None)
    COL.objects.link(p)
    p.empty_display_type = "ARROWS"
    p.empty_display_size = 0.025
    p.location = loc
    if parent is not None:
        p.parent = parent
        p.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()
    return p


def adopt(child_name, p):
    """Parent an existing part to a pivot without moving it."""
    c = get(child_name)
    if c is None:
        return
    c.parent = p
    c.matrix_parent_inverse = p.matrix_world.inverted()


def animate(o, keys):
    """keys = [(frame, (rx, ry, rz) in degrees), ...]"""
    for f, (rx, ry, rz) in keys:
        o.rotation_euler = (
            math.radians(rx),
            math.radians(ry),
            math.radians(rz),
        )
        o.keyframe_insert("rotation_euler", frame=f)
    o.rotation_euler = (0, 0, 0)


# ============================================================
# 1) WHEELS
# ============================================================
# Wheel parts are cylinders/tori rotated (0, 90deg, 0), so their local
# Z axis is the axle. Switching to ZYX order lets us spin local Z without
# changing the existing look (values stay identical: only Y is non-zero).

prefs = bpy.context.preferences.edit
old_interp = prefs.keyframe_new_interpolation_type
prefs.keyframe_new_interpolation_type = "LINEAR"

total = math.radians(360 * WHEEL_TURNS) * (1 if WHEEL_FORWARD else -1)

wheel_names = ["FRONT_LEFT", "FRONT_RIGHT", "REAR_LEFT", "REAR_RIGHT"]

for w in wheel_names:

    spin_parts = [
        get("WHEEL_" + w),
        get("WHEEL_RING_" + w),
        get("WHEEL_HUB_" + w),
    ]

    if ADD_WHEEL_MARKERS:
        wheel = get("WHEEL_" + w)
        if wheel:
            wx, wy, wz = wheel.location
            bpy.ops.mesh.primitive_cube_add(
                location=(wx, wy, wz + 0.115 - 0.003)
            )
            mk = bpy.context.object
            mk.name = "WHEEL_MARK_" + w
            mk.dimensions = (0.077, 0.020, 0.008)
            bpy.ops.object.transform_apply(
                location=False, rotation=False, scale=True
            )
            mat = bpy.data.materials.get("GRACE_ACCENT")
            if mat:
                mk.data.materials.append(mat)
            for c in list(mk.users_collection):
                c.objects.unlink(mk)
            COL.objects.link(mk)
            mk.parent = wheel
            mk.matrix_parent_inverse = wheel.matrix_world.inverted()
            spin_parts.append(None)  # marker follows parent wheel

    for o in spin_parts:
        if o is None:
            continue
        o.rotation_mode = "ZYX"
        base = o.rotation_euler.copy()

        o.rotation_euler = base
        o.keyframe_insert("rotation_euler", index=2, frame=1)

        o.rotation_euler = (base[0], base[1], total)
        o.keyframe_insert("rotation_euler", index=2, frame=END)

        o.rotation_euler = base

prefs.keyframe_new_interpolation_type = old_interp


# ============================================================
# 2) ARMS + HANDS
# ============================================================

z_shoulder = 0.805
z_elbow = 0.655
z_wrist = 0.505

finger_y = (-0.030, -0.010, 0.010, 0.030)

for side, s in (("LEFT", 1), ("RIGHT", -1)):

    # ---- pivot chain: shoulder -> elbow -> wrist -> knuckles ----
    sh = pivot("SHOULDER_" + side, (s * 0.215, 0, z_shoulder))
    el = pivot("ELBOW_" + side, (s * 0.250, 0, z_elbow), sh)
    wr = pivot("WRIST_" + side, (s * 0.276, 0, z_wrist), el)

    # ---- attach existing parts (positions unchanged) ----
    adopt("UPPER_ARM_" + side, sh)
    adopt("ELBOW_" + side, sh)
    adopt("ELBOW_RING_" + side, sh)

    adopt("FOREARM_" + side, el)
    adopt("WRIST_" + side, el)

    adopt("PALM_" + side, wr)

    for i, yy in enumerate(finger_y, 1):
        fp = pivot(
            "FINGER_%s_%d" % (side, i),
            (s * 0.278, yy, 0.425),
            wr,
        )
        adopt("FINGER_%s_%d" % (side, i), fp)

        # curl, slightly staggered finger to finger
        d = 3 * i
        animate(fp, [
            (1,         (0, 0, 0)),
            (150 + d,   (0, 0, 0)),
            (180 + d,   (-65, 0, 0)),
            (205 + d,   (-65, 0, 0)),
            (235,       (0, 0, 0)),
            (END,       (0, 0, 0)),
        ])

    tp = pivot("THUMB_" + side, (s * 0.315, -0.010, 0.450), wr)
    adopt("THUMB_" + side, tp)
    animate(tp, [
        (1,   (0, 0, 0)),
        (155, (0, 0, 0)),
        (185, (-40, 0, 0)),
        (205, (-40, 0, 0)),
        (235, (0, 0, 0)),
        (END, (0, 0, 0)),
    ])

    # ---- arm motion ----
    # Rotation about X: negative = swing forward (-Y)
    # Rotation about Y: m * angle = raise arm outward
    m = -s

    if side == "RIGHT":
        # Wave: raise arm, wave forearm side to side, lower, small swing
        animate(sh, [
            (1,   (0, 0, 0)),
            (24,  (0, m * 95, 0)),
            (120, (0, m * 95, 0)),
            (150, (0, 0, 0)),
            (165, (0, 0, 0)),
            (200, (-20, 0, 0)),
            (END, (0, 0, 0)),
        ])
        animate(el, [
            (1,   (0, 0, 0)),
            (24,  (0, m * 60, 0)),
            (40,  (0, m * 110, 0)),
            (56,  (0, m * 60, 0)),
            (72,  (0, m * 110, 0)),
            (88,  (0, m * 60, 0)),
            (104, (0, m * 110, 0)),
            (120, (0, m * 60, 0)),
            (150, (0, 0, 0)),
            (165, (0, 0, 0)),
            (200, (-25, 0, 0)),
            (END, (0, 0, 0)),
        ])
        animate(wr, [
            (1,   (0, 0, 0)),
            (24,  (0, 0, 0)),
            (40,  (0, -m * 20, 0)),
            (56,  (0, 0, 0)),
            (72,  (0, -m * 20, 0)),
            (88,  (0, 0, 0)),
            (104, (0, -m * 20, 0)),
            (120, (0, 0, 0)),
            (END, (0, 0, 0)),
        ])

    else:
        # Left: continuous gentle swing, opposite phase to the right
        animate(sh, [
            (1,   (0, 0, 0)),
            (60,  (-30, 0, 0)),
            (120, (0, 0, 0)),
            (180, (20, 0, 0)),
            (END, (0, 0, 0)),
        ])
        animate(el, [
            (1,   (0, 0, 0)),
            (60,  (-35, 0, 0)),
            (120, (0, 0, 0)),
            (180, (-10, 0, 0)),
            (END, (0, 0, 0)),
        ])
        animate(wr, [
            (1,   (0, 0, 0)),
            (60,  (-15, 0, 0)),
            (120, (0, 0, 0)),
            (180, (10, 0, 0)),
            (END, (0, 0, 0)),
        ])


# ============================================================
# DONE
# ============================================================

scene.frame_set(1)

print("")
print("============================================================")
print("GRACEEMO-01 ANIMATION ADDED")
print("============================================================")
print("Frames   : 1 - %d @ %d fps" % (END, FPS))
print("Wheels   : 4 wheels, %d turns (ring + hub spin with wheel)" % WHEEL_TURNS)
print("Right arm: wave (frames 24-120), small swing (165-240)")
print("Left arm : continuous swing")
print("Hands    : finger + thumb curl (frames 150-235)")
print("Parts    : none modified (ANIM_* empties only)")
print("Press SPACE in the viewport to play.")
print("============================================================")
