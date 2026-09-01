"""
GRACEEMO-01 — Interactive 3D Viewport Sidebar Control Panel
Panel: 'GRACEEMO CONTROL' in 3D View -> Sidebar (N) -> GRACEEMO Tab.
"""

import math
import bpy
try:
    from phase2.animation.poses import (
        reset_robot_pose, pose_idle, pose_greeting, pose_namaste, pose_point,
        pose_guide, pose_assist, hand_left_open, hand_left_close, hand_right_open,
        hand_right_close, wheels_forward, wheels_reverse, wheels_rotate, wheels_stop
    )
    from phase2.validation.validate_phase2 import validate_phase2_motion
except ImportError:
    from animation.poses import (
        reset_robot_pose, pose_idle, pose_greeting, pose_namaste, pose_point,
        pose_guide, pose_assist, hand_left_open, hand_left_close, hand_right_open,
        hand_right_close, wheels_forward, wheels_reverse, wheels_rotate, wheels_stop
    )
    from validation.validate_phase2 import validate_phase2_motion

# -------------------------------------------------------------
# Operators
# -------------------------------------------------------------
class GRACEEMO_OT_HeadAction(bpy.types.Operator):
    bl_idname = "graceemo.head_action"
    bl_label = "Head Action"
    action: bpy.props.StringProperty()

    def execute(self, context):
        c_yaw = bpy.data.objects.get("CTRL_NECK_YAW")
        c_pitch = bpy.data.objects.get("CTRL_NECK_PITCH")
        c_roll = bpy.data.objects.get("CTRL_NECK_ROLL")

        if self.action == "LEFT" and c_yaw:
            c_yaw.rotation_euler.z = math.radians(35)
        elif self.action == "RIGHT" and c_yaw:
            c_yaw.rotation_euler.z = math.radians(-35)
        elif self.action == "CENTER" and c_yaw:
            c_yaw.rotation_euler.z = 0.0
        elif self.action == "UP" and c_pitch:
            c_pitch.rotation_euler.x = math.radians(25)
        elif self.action == "DOWN" and c_pitch:
            c_pitch.rotation_euler.x = math.radians(-20)
        elif self.action == "FORWARD" and c_pitch:
            c_pitch.rotation_euler.x = 0.0
        elif self.action == "TILT_LEFT" and c_roll:
            c_roll.rotation_euler.y = math.radians(-15)
        elif self.action == "TILT_RIGHT" and c_roll:
            c_roll.rotation_euler.y = math.radians(15)

        bpy.context.view_layer.update()
        return {'FINISHED'}

class GRACEEMO_OT_ArmAction(bpy.types.Operator):
    bl_idname = "graceemo.arm_action"
    bl_label = "Arm Action"
    arm: bpy.props.StringProperty()
    action: bpy.props.StringProperty()

    def execute(self, context):
        c_sh = bpy.data.objects.get(f"CTRL_{self.arm}_SHOULDER")
        c_el = bpy.data.objects.get(f"CTRL_{self.arm}_ELBOW")

        if self.action == "RAISE" and c_sh:
            c_sh.rotation_euler.x = -math.radians(75)
        elif self.action == "LOWER" and c_sh:
            c_sh.rotation_euler.x = 0.0
        elif self.action == "BEND" and c_el:
            c_el.rotation_euler.x = -math.radians(75)
        elif self.action == "STRAIGHT" and c_el:
            c_el.rotation_euler.x = 0.0

        bpy.context.view_layer.update()
        return {'FINISHED'}

class GRACEEMO_OT_HandAction(bpy.types.Operator):
    bl_idname = "graceemo.hand_action"
    bl_label = "Hand Action"
    side: bpy.props.StringProperty()
    action: bpy.props.StringProperty()

    def execute(self, context):
        if self.side == "LEFT":
            if self.action == "OPEN": hand_left_open()
            elif self.action == "CLOSE": hand_left_close()
        elif self.side == "RIGHT":
            if self.action == "OPEN": hand_right_open()
            elif self.action == "CLOSE": hand_right_close()
        return {'FINISHED'}

class GRACEEMO_OT_PoseAction(bpy.types.Operator):
    bl_idname = "graceemo.pose_action"
    bl_label = "Pose Action"
    pose: bpy.props.StringProperty()

    def execute(self, context):
        if self.pose == "IDLE": pose_idle()
        elif self.pose == "GREETING": pose_greeting()
        elif self.pose == "NAMASTE": pose_namaste()
        elif self.pose == "POINT": pose_point()
        elif self.pose == "GUIDE": pose_guide()
        elif self.pose == "ASSIST": pose_assist()
        return {'FINISHED'}

class GRACEEMO_OT_MobilityAction(bpy.types.Operator):
    bl_idname = "graceemo.mobility_action"
    bl_label = "Mobility Action"
    action: bpy.props.StringProperty()

    def execute(self, context):
        if self.action == "FORWARD": wheels_forward(0.4)
        elif self.action == "REVERSE": wheels_reverse(0.4)
        elif self.action == "LEFT": wheels_rotate(-30.0)
        elif self.action == "RIGHT": wheels_rotate(30.0)
        elif self.action == "STOP": wheels_stop()
        return {'FINISHED'}

class GRACEEMO_OT_SystemAction(bpy.types.Operator):
    bl_idname = "graceemo.system_action"
    bl_label = "System Action"
    action: bpy.props.StringProperty()

    def execute(self, context):
        if self.action == "RESET":
            reset_robot_pose()
        elif self.action == "VALIDATE":
            validate_phase2_motion()
        return {'FINISHED'}

# -------------------------------------------------------------
# Sidebar Panel
# -------------------------------------------------------------
class GRACEEMO_PT_ControlPanel(bpy.types.Panel):
    bl_label = "GRACEEMO CONTROL"
    bl_idname = "GRACEEMO_PT_control_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "GRACEEMO"

    def draw(self, context):
        layout = self.layout

        # HEAD Section
        box = layout.box()
        box.label(text="HEAD", icon='OUTLINER_OB_CAMERA')
        row = box.row(align=True)
        row.operator("graceemo.head_action", text="LOOK LEFT").action = "LEFT"
        row.operator("graceemo.head_action", text="CENTER").action = "CENTER"
        row.operator("graceemo.head_action", text="LOOK RIGHT").action = "RIGHT"
        row = box.row(align=True)
        row.operator("graceemo.head_action", text="LOOK UP").action = "UP"
        row.operator("graceemo.head_action", text="LOOK FORWARD").action = "FORWARD"
        row.operator("graceemo.head_action", text="LOOK DOWN").action = "DOWN"
        row = box.row(align=True)
        row.operator("graceemo.head_action", text="HEAD TILT LEFT").action = "TILT_LEFT"
        row.operator("graceemo.head_action", text="HEAD TILT RIGHT").action = "TILT_RIGHT"

        # LEFT ARM Section
        box = layout.box()
        box.label(text="LEFT ARM", icon='OUTLINER_OB_ARMATURE')
        row = box.row(align=True)
        op = row.operator("graceemo.arm_action", text="RAISE"); op.arm = "LEFT"; op.action = "RAISE"
        op = row.operator("graceemo.arm_action", text="LOWER"); op.arm = "LEFT"; op.action = "LOWER"
        row = box.row(align=True)
        op = row.operator("graceemo.arm_action", text="ELBOW BEND"); op.arm = "LEFT"; op.action = "BEND"
        op = row.operator("graceemo.arm_action", text="ELBOW STRAIGHT"); op.arm = "LEFT"; op.action = "STRAIGHT"

        # RIGHT ARM Section
        box = layout.box()
        box.label(text="RIGHT ARM", icon='OUTLINER_OB_ARMATURE')
        row = box.row(align=True)
        op = row.operator("graceemo.arm_action", text="RAISE"); op.arm = "RIGHT"; op.action = "RAISE"
        op = row.operator("graceemo.arm_action", text="LOWER"); op.arm = "RIGHT"; op.action = "LOWER"
        row = box.row(align=True)
        op = row.operator("graceemo.arm_action", text="ELBOW BEND"); op.arm = "RIGHT"; op.action = "BEND"
        op = row.operator("graceemo.arm_action", text="ELBOW STRAIGHT"); op.arm = "RIGHT"; op.action = "STRAIGHT"

        # HANDS Section
        box = layout.box()
        box.label(text="HANDS", icon='HAND')
        row = box.row(align=True)
        op = row.operator("graceemo.hand_action", text="LEFT OPEN"); op.side = "LEFT"; op.action = "OPEN"
        op = row.operator("graceemo.hand_action", text="LEFT CLOSE"); op.side = "LEFT"; op.action = "CLOSE"
        row = box.row(align=True)
        op = row.operator("graceemo.hand_action", text="RIGHT OPEN"); op.side = "RIGHT"; op.action = "OPEN"
        op = row.operator("graceemo.hand_action", text="RIGHT CLOSE"); op.side = "RIGHT"; op.action = "CLOSE"

        # POSES Section
        box = layout.box()
        box.label(text="POSES", icon='POSE_HLT')
        grid = box.grid_flow(columns=3, align=True)
        grid.operator("graceemo.pose_action", text="IDLE").pose = "IDLE"
        grid.operator("graceemo.pose_action", text="GREETING").pose = "GREETING"
        grid.operator("graceemo.pose_action", text="NAMASTE").pose = "NAMASTE"
        grid.operator("graceemo.pose_action", text="POINT").pose = "POINT"
        grid.operator("graceemo.pose_action", text="GUIDE").pose = "GUIDE"
        grid.operator("graceemo.pose_action", text="ASSIST").pose = "ASSIST"

        # MOBILITY Section
        box = layout.box()
        box.label(text="MOBILITY", icon='ORIENTATION_GIMBAL')
        row = box.row(align=True)
        row.operator("graceemo.mobility_action", text="FORWARD").action = "FORWARD"
        row.operator("graceemo.mobility_action", text="REVERSE").action = "REVERSE"
        row = box.row(align=True)
        row.operator("graceemo.mobility_action", text="ROTATE LEFT").action = "LEFT"
        row.operator("graceemo.mobility_action", text="ROTATE RIGHT").action = "RIGHT"
        box.operator("graceemo.mobility_action", text="STOP", icon='CANCEL').action = "STOP"

        # SYSTEM Section
        box = layout.box()
        box.label(text="SYSTEM", icon='PREFERENCES')
        row = box.row(align=True)
        row.operator("graceemo.system_action", text="RESET POSE").action = "RESET"
        row.operator("graceemo.system_action", text="RESET ROBOT").action = "RESET"
        box.operator("graceemo.system_action", text="VALIDATE", icon='CHECKMARK').action = "VALIDATE"

classes = (
    GRACEEMO_OT_HeadAction,
    GRACEEMO_OT_ArmAction,
    GRACEEMO_OT_HandAction,
    GRACEEMO_OT_PoseAction,
    GRACEEMO_OT_MobilityAction,
    GRACEEMO_OT_SystemAction,
    GRACEEMO_PT_ControlPanel,
)

def register_ui():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass

def unregister_ui():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            pass
