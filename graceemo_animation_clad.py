# ============================================================
# GRACEEMO-01 - ANIMATION ADD-ON v3 (Blender 5.x)
#
# Run AFTER the 4-wheel model script. Replaces animation v2.
# Safe to re-run. No parts are modified, moved or resized.
#
# Timeline: frames 1-480 @ 24 fps. The robot ends exactly where and
# how it started, so the animation loops.
#
#   1-40     idle: breathing, blinking, head looks up and around
#   40-84    drives forward, WAVES at the viewer while rolling
#   128-200  curved drive to the left (head leads the turn)
#   204-264  360 degree spin, both arms out (celebration)
#   270-300  reverses 0.2 m
#   300-384  stops: nods yes, OFFERS A HANDSHAKE (fingers grip and
#            release), left hand to chin "thinking" pose, curious tilt
#   384-464  turns to home, drives back, turns to the start heading
#   440-480  bows and waves goodbye
#
# Real-robot behaviour:
#   - Skid-steer wheels: left/right wheels turn at different speeds
#     during turns; wheel rotation is computed from the real path.
#   - Upper body leans back when accelerating, forward when braking and
#     away from the turn in curves (spring motion with overshoot).
#   - Head looks into the turn before the body turns (anticipation).
#   - Breathing, eye blinks, smile changes, pulsing blue lights,
#     wobbling antenna, finger flutter and grip.
#
# Rig: ANIM_* empties sit on the joints and existing parts are parented
# to them at their current position.
#   ROOT -> base + wheels
#   ROOT -> ANIM_TORSO (lean + breathing) -> arms, head, upper body
# ============================================================

import bpy
import math

TARGET = "01_GRACEEMO_REFERENCE"
ROOT_NAME = "GRACEEMO_01_ROOT"

# ---------------- SETTINGS ----------------
FPS = 24
END = 480

WHEEL_RADIUS = 0.115
TRACK = 0.570            # distance between left and right wheels
TORSO_Z = 0.32           # height where the upper body can lean

MAX_PITCH = 4.0          # degrees, lean back/forward when accelerating
MAX_ROLL = 3.0           # degrees, lean in curves
HEAD_LEAD_GAIN = 8.0     # head yaw degrees per (degree/frame) of body turn
HEAD_LEAD_MAX = 25.0
HEAD_LEAD_FRAMES = 6     # head looks this many frames ahead of the body

# Driving plan: (start, end, kind, value)
#   "drive" metres (negative = reverse)
#   "spin"  degrees in place (positive = counter-clockwise from above)
#   "arc"   (metres, degrees) curve while moving
# Robot front = -Y. Keep all plan segments before frame 384, because the
# return trip home is added automatically in 384-464.
PLAN = [
    (40, 84, "drive", 0.35),
    (128, 200, "arc", (0.50, 90)),
    (204, 264, "spin", 360),
    (270, 300, "drive", -0.20),
]
RETURN_FRAMES = ((384, 408), (408, 440), (440, 464))

STATIC_NAMES = {
    "GROUND",
    "MASTER_HEIGHT",
    "HEIGHT_LABEL",
    "GRACEEMO_FRONT_CAMERA",
}
BASE_PREFIXES = ("BASE_", "FRONT_", "WHEEL_")

# ------------------------------------------

COL = bpy.data.collections.get(TARGET)
if COL is None:
    raise RuntimeError("Run the GRACEEMO model script first (collection not found).")

# ============================================================
# ROOT LOOKUP
# ============================================================

root = bpy.data.objects.get(ROOT_NAME)
if root is None:
    for o in COL.objects:
        if o.name.startswith(ROOT_NAME):
            root = o
            break
if root is None:
    root = bpy.data.objects.new(ROOT_NAME, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.1
    COL.objects.link(root)
    print("NOTE: root empty was missing, created a new one at the origin.")
if root.name not in COL.objects:
    COL.objects.link(root)
ROOT_NAME = root.name

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = END
scene.render.fps = FPS
scene.frame_set(1)
bpy.context.view_layer.update()

# ============================================================
# CLEAN PREVIOUS RUN (safe to re-run)
# ============================================================

for o in list(COL.objects):
    if o.parent is not None and (
        o.parent.name.startswith("ANIM_") or o.parent.name == ROOT_NAME
    ):
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw

for o in list(COL.objects):
    if o.name.startswith("ANIM_") or o.name.startswith("WHEEL_MARK_"):
        bpy.data.objects.remove(o, do_unlink=True)

for o in COL.objects:
    if o.animation_data:
        o.animation_data_clear()

for m in bpy.data.materials:
    if m.node_tree and m.node_tree.animation_data:
        m.node_tree.animation_data_clear()

root.location = (0, 0, 0)
root.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()


# ============================================================
# HELPERS
# ============================================================

def get(name):
    return bpy.data.objects.get(name)


def pivot(name, loc, parent=None, size=0.025):
    """Empty placed at a joint. Parenting keeps the world position."""
    p = bpy.data.objects.new("ANIM_" + name, None)
    COL.objects.link(p)
    p.empty_display_type = "ARROWS"
    p.empty_display_size = size
    p.location = loc
    if parent is not None:
        p.parent = parent
        p.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.update()
    return p


def adopt(child, p):
    """Parent an existing part to a pivot without moving it."""
    if isinstance(child, str):
        child = get(child)
    if child is None:
        return
    child.parent = p
    child.matrix_parent_inverse = p.matrix_world.inverted()


def animate(o, keys):
    """keys = [(frame, (rx, ry, rz) degrees), ...]"""
    for f, (rx, ry, rz) in sorted(keys, key=lambda k: k[0]):
        o.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
        o.keyframe_insert("rotation_euler", frame=f)
    o.rotation_euler = (0, 0, 0)


def animate_scale(o, keys):
    for f, sc in sorted(keys, key=lambda k: k[0]):
        o.scale = sc
        o.keyframe_insert("scale", frame=f)
    o.scale = (1, 1, 1)


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def smooth(a, w):
    n = len(a)
    h = w // 2
    out = []
    for i in range(n):
        lo = max(0, i - h)
        hi = min(n, i + h + 1)
        out.append(sum(a[lo:hi]) / (hi - lo))
    return out


def spring(target, k=0.08, c=0.25):
    """Under-damped spring: follows the target with a little overshoot."""
    x = vel = 0.0
    out = []
    for tg in target:
        vel += k * (tg - x) - c * vel
        x += vel
        out.append(x)
    return out


def stag(keys, d):
    """Delay keys by d frames (not the first/last) for finger ripple."""
    return [(f if f in (1, END) else f + d, v) for f, v in keys]


# ============================================================
# 1) BUILD THE RIG
# ============================================================

torso = pivot("TORSO", (0, 0, TORSO_Z), root, 0.05)

z_shoulder, z_elbow, z_wrist = 0.805, 0.655, 0.505
finger_y = (-0.030, -0.010, 0.010, 0.030)

joints = {}   # (side, joint) -> pivot

for side, s in (("LEFT", 1), ("RIGHT", -1)):
    sh = pivot("SHOULDER_" + side, (s * 0.215, 0, z_shoulder), torso)
    el = pivot("ELBOW_" + side, (s * 0.250, 0, z_elbow), sh)
    wr = pivot("WRIST_" + side, (s * 0.276, 0, z_wrist), el)
    joints[(side, "SH")] = sh
    joints[(side, "EL")] = el
    joints[(side, "WR")] = wr

    adopt("UPPER_ARM_" + side, sh)
    adopt("ELBOW_" + side, sh)
    adopt("ELBOW_RING_" + side, sh)
    adopt("FOREARM_" + side, el)
    adopt("WRIST_" + side, el)
    adopt("PALM_" + side, wr)

    for i, yy in enumerate(finger_y, 1):
        fp = pivot("FINGER_%s_%d" % (side, i), (s * 0.278, yy, 0.425), wr)
        adopt("FINGER_%s_%d" % (side, i), fp)
        joints[(side, "F%d" % i)] = fp

    tp = pivot("THUMB_" + side, (s * 0.315, -0.010, 0.450), wr)
    adopt("THUMB_" + side, tp)
    joints[(side, "THUMB")] = tp

# head: HEADLEAD (anticipation yaw) -> HEAD (gestures)
headlead = pivot("HEADLEAD", (0, 0, 0.905), torso, 0.04)
head = pivot("HEAD", (0, 0, 0.905), headlead, 0.04)

antenna = pivot("ANTENNA", (0, 0, 1.21), head, 0.015)
adopt("HEAD_ANTENNA", antenna)

eye_pivots = []
for nm, x in (("EYE_LEFT", 0.055), ("EYE_RIGHT", -0.055)):
    ep = pivot(nm, (x, -0.112, 1.02), head, 0.015)
    adopt(nm, ep)
    eye_pivots.append(ep)

mouth_p = pivot("MOUTH", (0, -0.112, 1.015), head, 0.015)
adopt("MOUTH", mouth_p)

for o in list(COL.objects):
    if o.parent is None and o.name.startswith("HEAD_"):
        adopt(o, head)

# everything else on the upper body rides on the torso pivot,
# the base and wheels stay on the root
bpy.context.view_layer.update()

for o in list(COL.objects):
    if o == root or o == torso or o.name in STATIC_NAMES or o.parent is not None:
        continue
    if o.name.startswith("ANIM_"):
        continue
    if o.name.startswith(BASE_PREFIXES):
        o.parent = root
        o.matrix_parent_inverse = root.matrix_world.inverted()
    else:
        adopt(o, torso)

# ============================================================
# 2) MOTION PLAN (path + wheel rotation)
# ============================================================

def normalise(plan):
    segs = []
    for f0, f1, kind, val in plan:
        if kind == "drive":
            segs.append((f0, f1, val, 0.0))
        elif kind == "spin":
            segs.append((f0, f1, 0.0, math.radians(val)))
        elif kind == "arc":
            segs.append((f0, f1, val[0], math.radians(val[1])))
    return segs


def simulate(segs):
    x = y = th = 0.0
    phi = {"L": 0.0, "R": 0.0}
    s_prev = t_prev = 0.0
    out = []
    for f in range(1, END + 1):
        s = t = 0.0
        for f0, f1, d, a in segs:
            e = ease((f - f0) / float(f1 - f0))
            s += d * e
            t += a * e
        ds = s - s_prev
        dth = t - t_prev
        mid = th + dth / 2.0
        x += math.sin(mid) * ds
        y += -math.cos(mid) * ds
        th = t
        phi["L"] += (ds - dth * TRACK / 2.0) / WHEEL_RADIUS
        phi["R"] += (ds + dth * TRACK / 2.0) / WHEEL_RADIUS
        s_prev, t_prev = s, t
        out.append({
            "x": x, "y": y, "th": th, "ds": ds, "dth": dth,
            "L": phi["L"], "R": phi["R"],
        })
    return out


plan_segs = normalise(PLAN)
end_pose = simulate(plan_segs)[-1]
px, py, pth = end_pose["x"], end_pose["y"], end_pose["th"]
dist_home = math.hypot(px, py)

if dist_home > 0.01:
    target = math.atan2(-px, py)
    a1 = wrap(target - pth)
    a2 = wrap(-target)
else:
    a1 = 0.0
    dist_home = 0.0
    a2 = wrap(-pth)

(r0, r1), (d0, d1), (t0, t1) = RETURN_FRAMES
all_segs = plan_segs + [
    (r0, r1, 0.0, a1),
    (d0, d1, dist_home, 0.0),
    (t0, t1, 0.0, a2),
]

path = simulate(all_segs)

v = smooth([p["ds"] for p in path], 7)
w = smooth([p["dth"] for p in path], 7)

acc = [0.0] + [v[i] - v[i - 1] for i in range(1, len(v))]
lat = [v[i] * w[i] for i in range(len(v))]
acc_max = max(abs(a) for a in acc) or 1.0
lat_max = max(abs(a) for a in lat) or 1.0
v_max = max(abs(a) for a in v) or 1.0
w_max = max(abs(a) for a in w) or 1.0

# lean: back when speeding up, forward when braking, away from the turn
pitch = spring([-(a / acc_max) * MAX_PITCH for a in acc])
roll = spring([-(a / lat_max) * MAX_ROLL for a in lat])

activity = [min(1.0, abs(v[i]) / v_max + abs(w[i]) / w_max) for i in range(len(v))]

# head looks into the turn a few frames before the body
w_deg = smooth([math.degrees(p["dth"]) for p in path], 9)
lead = []
for i in range(len(w_deg)):
    j = min(i + HEAD_LEAD_FRAMES, len(w_deg) - 1)
    lead.append(max(-HEAD_LEAD_MAX, min(HEAD_LEAD_MAX, w_deg[j] * HEAD_LEAD_GAIN)))

# ============================================================
# 3) GESTURES (keyed, bezier = natural ease in/out)
# ============================================================

# arm keys: (frame, forward-bend rx, outward-raise, rz) in degrees.
# rx negative = forward, outward is converted to the right sign per side.

R_SH = [
    (1, 0, 0, 0), (40, 0, 0, 0),
    (58, 0, 100, 0), (150, 0, 100, 0), (172, 0, 0, 0),        # wave
    (206, 0, 0, 0), (222, 0, 70, 0), (256, 0, 70, 0), (272, 0, 0, 0),   # arms out
    (300, 0, 0, 0), (322, -55, 8, 0), (372, -55, 8, 0), (394, 0, 0, 0), # handshake
    (440, 0, 0, 0), (454, 0, 95, 0), (468, 0, 95, 0), (END, 0, 0, 0),   # goodbye
]
R_EL = [
    (1, 0, 0, 0), (40, 0, 0, 0),
    (58, 0, 60, 0), (74, 0, 110, 0), (90, 0, 60, 0), (106, 0, 110, 0),
    (122, 0, 60, 0), (138, 0, 110, 0), (150, 0, 60, 0), (172, 0, 0, 0),
    (310, 0, 0, 0), (322, -40, 0, 0), (372, -40, 0, 0), (394, 0, 0, 0),
    (440, 0, 0, 0), (454, 0, 60, 0), (461, 0, 110, 0), (468, 0, 60, 0),
    (END, 0, 0, 0),
]
R_WR = [
    (1, 0, 0, 0), (58, 0, 0, 0),
    (74, 0, -20, 0), (90, 0, 0, 0), (106, 0, -20, 0), (122, 0, 0, 0),
    (138, 0, -20, 0), (150, 0, 0, 0),
    (454, 0, 0, 0), (461, 0, -20, 0), (468, 0, 0, 0), (END, 0, 0, 0),
]

L_SH = [
    (1, 0, 0, 0), (40, 0, 0, 0),
    (70, -12, 0, 0), (110, 6, 0, 0), (140, -6, 0, 0), (172, 0, 0, 0),   # swing
    (206, 0, 0, 0), (222, 0, 70, 0), (256, 0, 70, 0), (272, 0, 0, 0),   # arms out
    (300, 0, 0, 0), (330, -25, 0, 0), (372, -25, 0, 0), (394, 0, 0, 0), # thinking
    (END, 0, 0, 0),
]
L_EL = [
    (1, 0, 0, 0), (40, 0, 0, 0),
    (70, -10, 0, 0), (110, -4, 0, 0), (140, -8, 0, 0), (172, 0, 0, 0),
    (300, 0, 0, 0), (334, -95, 0, 0), (372, -95, 0, 0), (394, 0, 0, 0),
    (END, 0, 0, 0),
]
L_WR = [
    (1, 0, 0, 0),
    (70, -8, 0, 0), (110, 4, 0, 0), (140, -4, 0, 0), (172, 0, 0, 0),
    (334, 0, 0, 0), (350, -15, 0, 0), (366, 0, 0, 0), (END, 0, 0, 0),
]

ARM_KEYS = {
    ("RIGHT", "SH"): R_SH, ("RIGHT", "EL"): R_EL, ("RIGHT", "WR"): R_WR,
    ("LEFT", "SH"): L_SH, ("LEFT", "EL"): L_EL, ("LEFT", "WR"): L_WR,
}

for (side, jn), keys in ARM_KEYS.items():
    m = 1 if side == "RIGHT" else -1      # raise-outward sign about Y
    animate(
        joints[(side, jn)],
        [(f, (rx, m * out, rz)) for f, rx, out, rz in keys],
    )

# finger curl (degrees of curl; 0 = open hand, 10 = relaxed)
R_FING = [
    (1, 10), (44, 10), (58, 0),
    (74, 14), (90, 0), (106, 14), (122, 0), (138, 14), (150, 0),   # flutter
    (172, 10), (210, 10), (224, 0), (258, 0), (272, 10),           # open for arms out
    (310, 10), (322, 0), (338, 0), (350, 55), (364, 55), (376, 0), # grip + release
    (392, 10), (452, 10), (458, 0), (472, 0), (END, 10),
]
L_FING = [
    (1, 10), (210, 10), (224, 0), (258, 0), (272, 10),
    (330, 10), (346, 45), (372, 45), (392, 10), (END, 10),
]

for side, curls in (("RIGHT", R_FING), ("LEFT", L_FING)):
    for i in range(1, 5):
        d = 2 * (i - 1)          # fingers ripple one after another
        animate(
            joints[(side, "F%d" % i)],
            [(f, (-c, 0, 0)) for f, c in stag(curls, d)],
        )
    animate(
        joints[(side, "THUMB")],
        [(f, (-c * 0.6, 0, 0)) for f, c in stag(curls, 3)],
    )

# head gestures (rx + = nod down, ry = tilt, rz + = look left)
animate(head, [
    (1, (0, 0, 0)),
    (20, (-4, 0, 0)),
    (34, (0, 0, 0)),
    (54, (0, 0, 24)),
    (68, (0, 0, -24)),
    (84, (0, 0, 0)),
    (110, (-5, 0, 0)),         # chin up while waving
    (140, (0, 0, 0)),
    (208, (0, 0, 0)),
    (268, (0, 0, 0)),
    (278, (12, 0, 0)),         # nod yes
    (286, (-6, 0, 0)),
    (294, (12, 0, 0)),
    (302, (0, 0, 0)),
    (316, (0, -10, 0)),        # curious tilt
    (340, (8, -12, 10)),       # thinking
    (372, (8, -12, 10)),
    (388, (0, 0, 0)),
    (462, (0, 0, 0)),
    (470, (15, 0, 0)),         # bow
    (474, (15, 0, 0)),
    (END, (0, 0, 0)),
])

# eye blinks
blink = [(1, (1, 1, 1))]
for f in (30, 92, 150, 226, 284, 350, 410, 455):
    blink += [
        (f - 2, (1, 1, 1)),
        (f, (1, 1, 0.08)),
        (f + 3, (1, 1, 1)),
    ]
blink.append((END, (1, 1, 1)))

for ep in eye_pivots:
    animate_scale(ep, blink)

# smile gets bigger when happy
animate_scale(mouth_p, [
    (1, (1, 1, 1)), (44, (1, 1, 1)),
    (58, (1.2, 1, 1.3)), (150, (1.2, 1, 1.3)), (172, (1, 1, 1)),
    (222, (1.25, 1, 1.35)), (256, (1.25, 1, 1.35)), (272, (1, 1, 1)),
    (322, (1.12, 1, 1.2)), (372, (1.12, 1, 1.2)), (394, (1, 1, 1)),
    (454, (1.25, 1, 1.35)), (470, (1.25, 1, 1.35)), (END, (1, 1, 1)),
])

# ============================================================
# 4) DENSE MOTION (every frame, linear keys)
# ============================================================

prefs = bpy.context.preferences.edit
old_interp = prefs.keyframe_new_interpolation_type
prefs.keyframe_new_interpolation_type = "LINEAR"

try:
    # wheels: Z is the axle (parts are rotated 90 deg about Y)
    wheel_parts = {
        "FRONT_LEFT": "L", "REAR_LEFT": "L",
        "FRONT_RIGHT": "R", "REAR_RIGHT": "R",
    }
    wheel_objs = []
    for w_name, side_key in wheel_parts.items():
        for prefix in ("WHEEL_", "WHEEL_RING_", "WHEEL_HUB_"):
            o = get(prefix + w_name)
            if o is not None:
                o.rotation_mode = "ZYX"
                wheel_objs.append((side_key, o, o.rotation_euler.copy()))

    torso_base = torso.location.copy()

    for f in range(1, END + 1):
        p = path[f - 1]

        # robot drives
        root.location = (p["x"], p["y"], 0.0)
        root.rotation_euler = (0.0, 0.0, p["th"])
        root.keyframe_insert("location", frame=f)
        root.keyframe_insert("rotation_euler", frame=f)

        # wheels roll in sync
        for side_key, o, base in wheel_objs:
            o.rotation_euler = (base[0], base[1], p[side_key])
            o.keyframe_insert("rotation_euler", index=2, frame=f)

        # upper body: lean (spring) + breathing
        torso.rotation_euler = (
            math.radians(pitch[f - 1]),
            math.radians(roll[f - 1]),
            0.0,
        )
        breath = 0.003 * math.sin(2 * math.pi * (f - 1) / 96.0)
        torso.location = (torso_base.x, torso_base.y, torso_base.z + breath)
        torso.keyframe_insert("rotation_euler", frame=f)
        torso.keyframe_insert("location", frame=f)

        # head leads the turn
        headlead.rotation_euler = (0.0, 0.0, math.radians(lead[f - 1]))
        headlead.keyframe_insert("rotation_euler", frame=f)

        # antenna wobble, bigger when the robot moves
        amp = 1.5 + 6.0 * activity[f - 1]
        antenna.rotation_euler = (
            math.radians(amp * math.sin(2 * math.pi * (f - 1) * 40 / 480.0)),
            math.radians(amp * math.sin(2 * math.pi * (f - 1) * 30 / 480.0 + 1.0)),
            0.0,
        )
        antenna.keyframe_insert("rotation_euler", frame=f)

    # blue lights pulse and glow brighter while moving
    try:
        glow = bpy.data.materials.get("GRACE_BLUE_GLOW")
        sock = glow.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        frames = sorted(set(range(1, END + 1, 3)) | {END})
        for f in frames:
            sock.default_value = (
                11.0
                + 3.0 * math.sin(2 * math.pi * (f - 1) / 60.0)
                + 5.0 * activity[f - 1]
            )
            sock.keyframe_insert("default_value", frame=f)
        sock.default_value = 12.0
    except Exception as e:
        print("Light pulse skipped:", e)

finally:
    prefs.keyframe_new_interpolation_type = old_interp

# back to rest values
for side_key, o, base in wheel_objs:
    o.rotation_euler = base

root.location = (0, 0, 0)
root.rotation_euler = (0, 0, 0)
torso.location = torso_base
torso.rotation_euler = (0, 0, 0)
headlead.rotation_euler = (0, 0, 0)
antenna.rotation_euler = (0, 0, 0)

# ============================================================
# DONE
# ============================================================

scene.frame_set(1)

print("")
print("============================================================")
print("GRACEEMO-01 ANIMATION v3 ADDED")
print("============================================================")
print("Frames : 1 - %d @ %d fps (loops)" % (END, FPS))
print("Drive  : forward, curve, 360 spin, reverse, auto return home")
print("Wheels : skid-steer, every wheel rolls with the real path")
print("Body   : breathing + lean on accel/brake/turns (spring)")
print("Head   : looks into turns first, nod, tilt, bow, blinks")
print("Arms   : wave, arms out, handshake offer, thinking, goodbye")
print("Hands  : finger flutter, grip and release")
print("Lights : blue glow pulses, brighter while moving")
print("Press SPACE in the viewport to play.")
print("============================================================")
