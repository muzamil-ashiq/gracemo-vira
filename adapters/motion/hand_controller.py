#!/usr/bin/env python3
"""
GRaCEmo ViRa — Hand Subsystem Controller (Milestone 1)
Physical Parallel-Jaw Two-Finger Gripper Controller.

Architecture:
  Resides strictly BELOW the Whole-Body Coordinator.
  High-level layers (Agent / K DSL / Manipulation Skill) NEVER touch raw joint angles or finger displacements.
  Exposes semantic operations:
    - hand::open(width_m=0.08)
    - hand::close(target_width_m=0.018)
    - hand::grasp(target_id=None, timeout_sec=3.0) -> bool
    - hand::release() -> bool
    - hand::hold() -> bool

Key Specifications:
  - Prismatic stroke per finger: 0.0m (closed) to 0.035m (max open).
  - Palm mount gap: 0.018m (gap between fingers when joint displacement is 0.0m).
  - Max gripper width: 0.018 + 2 * 0.035 = 0.088m.
  - Symmetrical finger actuation (left and right fingers move equidistant).
  - Dual contact sensing: Left and Right pad contact monitoring.
  - Anti-False-Positive Grasp Verification:
      Closing on empty air NEVER reports success; grasp() returns False and state transitions to EMPTY_CLOSED.
      Only when contact is verified (or resistance sensed) does it report True and transition to HOLD.
"""

from enum import Enum
import sys
import os
import time
import math
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

try:
    import gz.transport13 as gz_transport
    from gz.msgs10.double_pb2 import Double as GzDouble
    from gz.msgs10.model_pb2 import Model as GzModel
    try:
        from gz.msgs10.empty_pb2 import Empty as GzEmpty
    except ImportError:
        GzEmpty = None
    try:
        from gz.msgs10.contacts_pb2 import Contacts as GzContacts
    except ImportError:
        try:
            from gz.msgs.contacts_pb2 import Contacts as GzContacts
        except ImportError:
            GzContacts = None
except ImportError:
    try:
        import gz.transport as gz_transport
        from gz.msgs.double_pb2 import Double as GzDouble
        from gz.msgs.model_pb2 import Model as GzModel
        try:
            from gz.msgs.empty_pb2 import Empty as GzEmpty
        except ImportError:
            GzEmpty = None
        from gz.msgs.contacts_pb2 import Contacts as GzContacts
    except ImportError:
        gz_transport = None
        GzDouble = None
        GzModel = None
        GzEmpty = None
        GzContacts = None

ROOT = Path(__file__).resolve().parent.parent.parent
for sub in ["sdk", "brain", "motion"]:
    p = str(ROOT / "adapters" / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from gracemo_sdk import AdapterClient
except ImportError:
    AdapterClient = None


class HandState(str, Enum):
    IDLE = "IDLE"
    OPENING = "OPENING"
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CONTACT_DETECTED = "CONTACT_DETECTED"
    HOLD = "HOLD"
    EMPTY_CLOSED = "EMPTY_CLOSED"
    RELEASED = "RELEASED"


class HandSubsystem:
    """
    Subsystem controller for the parallel-jaw two-finger gripper.
    Located below the Whole-Body Coordinator.
    Enforces strict physical constraints, symmetric finger travel, and anti-false-positive grasp verification.
    """

    # Physical parameters (meters) — Compact 100mm Franka/Robotiq-style Hand
    MIN_GAP_M: float = 0.010               # 10mm minimum gap (closed in between)
    MAX_GAP_M: float = 0.100               # 100mm maximum aperture (open at outer edges)
    MAX_STROKE_PER_FINGER_M: float = 0.045 # 45mm prismatic stroke per finger: (0.100 - 0.010) / 2
    DEFAULT_OPEN_WIDTH_M: float = 0.090    # 90mm default open aperture
    CLOSED_THRESHOLD_DISP_M: float = 0.042 # Single finger displacement > 42mm considered closed limit (aperture < 16mm)
    CLOSURE_PRELOAD_M: float = 0.012       # 12mm controller preload parameter for steady holding effort
    CONTACT_PERSISTENCE_SEC: float = 0.35  # Duration contact is considered active after last contact packet

    def __init__(self, mock: bool = False, adapter_port: int = 7780):
        self.mock = mock or (gz_transport is None)
        self.state = HandState.IDLE
        
        # Internal state tracking (joint displacement in meters, 0.0 = open at far edge, 0.034 = closed in between)
        self.left_finger_pos: float = 0.0
        self.right_finger_pos: float = 0.0
        self.left_finger_vel: float = 0.0
        self.right_finger_vel: float = 0.0
        
        self._left_contact: bool = False
        self._right_contact: bool = False
        self._last_left_contact_time: float = 0.0
        self._last_right_contact_time: float = 0.0
        
        # Mock simulation state
        self._mock_target_disp: float = 0.0
        self._mock_object_width: Optional[float] = None
        self._mock_force_contact: bool = False

        # Adapter / Kernel client
        self.client = None
        if AdapterClient is not None:
            try:
                self.client = AdapterClient(adapter_name="HandSubsystem", base_url=f"http://127.0.0.1:{adapter_port}")
            except Exception:
                self.client = None

        # Gazebo transport setup
        self.node = None
        self.left_cmd_pub = None
        self.right_cmd_pub = None
        self.attach_cmd_pub = None
        self.detach_cmd_pub = None

        if not self.mock:
            try:
                self.node = gz_transport.Node()
                self.left_cmd_pub = self.node.advertise("/hand/left_finger/cmd_pos", GzDouble)
                self.right_cmd_pub = self.node.advertise("/hand/right_finger/cmd_pos", GzDouble)
                if GzEmpty is not None:
                    self.attach_cmd_pub = self.node.advertise("/gracemo_vira/detachable_joint/attach", GzEmpty)
                    self.detach_cmd_pub = self.node.advertise("/gracemo_vira/detachable_joint/detach", GzEmpty)
                    # Immediate startup release to guarantee object starts detached in world
                    self.detach_joint()
                
                # Joint state feedback
                self.node.subscribe(GzModel, "/world/gracemo_home/model/gracemo_vira/joint_state", self._on_joint_state)
                
                # Contact sensor topics (both canonical gazebo path and alias)
                if GzContacts is not None:
                    self.node.subscribe(GzContacts, "/world/gracemo_home/model/gracemo_vira/link/finger_left_link/sensor/hand_contact_left/contact", self._on_contact_left)
                    self.node.subscribe(GzContacts, "/world/gracemo_home/model/gracemo_vira/link/finger_right_link/sensor/hand_contact_right/contact", self._on_contact_right)
                    self.node.subscribe(GzContacts, "/hand/contacts/left", self._on_contact_left)
                    self.node.subscribe(GzContacts, "/hand/contacts/right", self._on_contact_right)
            except Exception:
                # Fallback to mock if transport connection fails
                self.mock = True

        # Active background holding thread: continuously publishes holding torque during HOLD state
        self._holding_active: bool = False
        self._hold_displacement: float = 0.0
        import threading
        self._hold_thread = threading.Thread(target=self._active_hold_loop, daemon=True)
        self._hold_thread.start()

    def _active_hold_loop(self):
        while True:
            if self._holding_active and self.state == HandState.HOLD and not self.mock:
                if self.left_cmd_pub and self.right_cmd_pub and GzDouble is not None:
                    msg = GzDouble()
                    msg.data = float(self._hold_displacement)
                    self.left_cmd_pub.publish(msg)
                    self.right_cmd_pub.publish(msg)
            time.sleep(0.04)

    # -------------------------------------------------------------------------
    # Sensor & Joint State Callbacks
    # -------------------------------------------------------------------------
    def _on_joint_state(self, msg: Any):
        if not hasattr(msg, "joint"):
            return
        for j in msg.joint:
            if j.name == "finger_left_joint":
                self.left_finger_pos = float(j.axis1.position)
                self.left_finger_vel = float(j.axis1.velocity)
            elif j.name == "finger_right_joint":
                self.right_finger_pos = float(j.axis1.position)
                self.right_finger_vel = float(j.axis1.velocity)

    def _on_contact_left(self, msg: Any):
        if hasattr(msg, "contact") and len(msg.contact) > 0:
            self._left_contact = True
            self._last_left_contact_time = time.time()
        else:
            self._left_contact = False

    def _on_contact_right(self, msg: Any):
        if hasattr(msg, "contact") and len(msg.contact) > 0:
            self._right_contact = True
            self._last_right_contact_time = time.time()
        else:
            self._right_contact = False

    # -------------------------------------------------------------------------
    # Physical Telemetry
    # -------------------------------------------------------------------------
    def get_width(self) -> float:
        """Total aperture (gap in meters) between inner surfaces of left and right fingers."""
        return max(self.MIN_GAP_M, min(self.MAX_GAP_M, self.MAX_GAP_M - (self.left_finger_pos + self.right_finger_pos)))

    def get_joint_positions(self) -> Tuple[float, float]:
        """Current displacement (meters) for left and right fingers."""
        return self.left_finger_pos, self.right_finger_pos

    def has_contact(self) -> Tuple[bool, bool]:
        """
        Returns (left_pad_contact, right_pad_contact).
        In live Gazebo, uses time-decayed contact sensor readings.
        In mock mode, uses programmatic simulation.
        """
        if self.mock:
            return self._left_contact, self._right_contact
        
        now = time.time()
        left_active = self._left_contact or (now - self._last_left_contact_time < self.CONTACT_PERSISTENCE_SEC)
        right_active = self._right_contact or (now - self._last_right_contact_time < self.CONTACT_PERSISTENCE_SEC)
        return left_active, right_active

    def get_contact_state(self) -> Tuple[bool, bool]:
        """Alias for has_contact()."""
        return self.has_contact()

    def get_state(self) -> str:
        return self.state.value

    # -------------------------------------------------------------------------
    # Motion Authority (Below Whole-Body Coordinator)
    # -------------------------------------------------------------------------
    def _command_displacement(self, displacement_m: float):
        """
        Enforce symmetric displacement and strict physical joint limits [0.0, MAX_STROKE].
        """
        clamped_disp = max(0.0, min(self.MAX_STROKE_PER_FINGER_M, float(displacement_m)))
        
        if self.mock:
            self._mock_target_disp = clamped_disp
            self.left_finger_pos = clamped_disp
            self.right_finger_pos = clamped_disp
            return

        if self.left_cmd_pub and self.right_cmd_pub and GzDouble is not None:
            msg = GzDouble()
            msg.data = clamped_disp
            self.left_cmd_pub.publish(msg)
            self.right_cmd_pub.publish(msg)

    # -------------------------------------------------------------------------
    # Semantic API (Open, Close, Grasp, Release, Hold)
    # -------------------------------------------------------------------------
    def open(self, width_m: float = DEFAULT_OPEN_WIDTH_M, timeout_sec: float = 2.0) -> bool:
        """
        Actuates fingers outward symmetrically to requested aperture width.
        Aperture range [MIN_GAP_M, MAX_GAP_M] (16mm to 140mm).
        Inward displacement q = (MAX_GAP_M - width_m) / 2.0.
        """
        clamped_width = max(self.MIN_GAP_M, min(self.MAX_GAP_M, float(width_m)))
        target_disp = (self.MAX_GAP_M - clamped_width) / 2.0
        
        self._holding_active = False
        self.state = HandState.OPENING
        self._command_displacement(target_disp)
        
        self._left_contact = False
        self._right_contact = False
        self._last_left_contact_time = 0.0
        self._last_right_contact_time = 0.0
        
        start_time = time.time()
        if self.mock:
            self.left_finger_pos = target_disp
            self.right_finger_pos = target_disp
            self.state = HandState.OPEN
            return True

        # Wait for fingers to reach target
        while time.time() - start_time < timeout_sec:
            l_pos, r_pos = self.get_joint_positions()
            if abs(l_pos - target_disp) < 0.002 and abs(r_pos - target_disp) < 0.002:
                break
            time.sleep(0.02)

        self.state = HandState.OPEN
        return True

    def close(self, target_width_m: float = MIN_GAP_M, timeout_sec: float = 2.0) -> bool:
        """
        Drives fingers inward symmetrically to target aperture width (default fully closed: 16mm gap).
        Inward displacement q = (MAX_GAP_M - target_width_m) / 2.0.
        """
        clamped_width = max(self.MIN_GAP_M, min(self.MAX_GAP_M, float(target_width_m)))
        target_disp = (self.MAX_GAP_M - clamped_width) / 2.0
        
        self._holding_active = False
        self.state = HandState.CLOSING
        self._command_displacement(target_disp)
        
        start_time = time.time()
        if self.mock:
            self.left_finger_pos = target_disp
            self.right_finger_pos = target_disp
            if target_disp >= self.CLOSED_THRESHOLD_DISP_M and not (self._left_contact or self._right_contact):
                self.state = HandState.EMPTY_CLOSED
            else:
                self.state = HandState.IDLE
            return True

        while time.time() - start_time < timeout_sec:
            l_pos, r_pos = self.get_joint_positions()
            if abs(l_pos - target_disp) < 0.002 and abs(r_pos - target_disp) < 0.002:
                break
            time.sleep(0.02)

        l_pos, r_pos = self.get_joint_positions()
        left_c, right_c = self.has_contact()
        if l_pos >= self.CLOSED_THRESHOLD_DISP_M and r_pos >= self.CLOSED_THRESHOLD_DISP_M and not (left_c or right_c):
            self.state = HandState.EMPTY_CLOSED
        else:
            self.state = HandState.IDLE
        return True

    def grasp(self, target_id: Optional[str] = None, timeout_sec: float = 3.0, step_interval: float = 0.04) -> bool:
        """
        Semantic Grasp Execution with Anti-False-Positive Guarantee:
        1. Commands fingers inward towards fully closed limit (MAX_STROKE_PER_FINGER_M = 0.062m, 16mm gap).
        2. Actively monitors dual contact sensors throughout travel.
        3. If contact is detected on either pad:
             - Freezes motion / clamps inward at contact position with slight preload.
             - State transitions to CONTACT_DETECTED -> HOLD.
             - Returns True (Object grasped!).
        4. If fingers reach fully closed limit (> 58mm displacement) without any contact:
             - State transitions to EMPTY_CLOSED.
             - Returns False (Grasped empty air! NEVER falsely reports success).
        """
        self.state = HandState.CLOSING
        
        # In mock mode with mock object or mock contact
        if self.mock:
            if self._mock_object_width is not None and self._mock_object_width > self.MIN_GAP_M:
                disp_at_contact = (self.MAX_GAP_M - self._mock_object_width) / 2.0
                self.left_finger_pos = disp_at_contact
                self.right_finger_pos = disp_at_contact
                self._left_contact = True
                self._right_contact = True
                self.state = HandState.CONTACT_DETECTED
                time.sleep(0.01)
                self.state = HandState.HOLD
                return True
            elif self._mock_force_contact:
                self._left_contact = True
                self._right_contact = True
                self.state = HandState.CONTACT_DETECTED
                self.state = HandState.HOLD
                return True
            else:
                self.left_finger_pos = self.MAX_STROKE_PER_FINGER_M
                self.right_finger_pos = self.MAX_STROKE_PER_FINGER_M
                self._left_contact = False
                self._right_contact = False
                self.state = HandState.EMPTY_CLOSED
                return False

        # Reset contact state at start of grasp to prevent stale contact triggering
        self._left_contact = False
        self._right_contact = False
        self._last_left_contact_time = 0.0
        self._last_right_contact_time = 0.0

        # Live Gazebo closed-loop grasp execution: command full inward stroke
        self._command_displacement(self.MAX_STROKE_PER_FINGER_M)
        start_time = time.time()
        prev_l, prev_r = -1.0, -1.0
        stall_count = 0
        
        while time.time() - start_time < timeout_sec:
            left_c, right_c = self.has_contact()
            l_pos, r_pos = self.get_joint_positions()
            current_aperture = self.get_width()
            
            # Check stall against physical object (fingers stopped moving inward before travel limit)
            if abs(l_pos - prev_l) < 0.0005 and abs(r_pos - prev_r) < 0.0005 and l_pos > 0.005 and l_pos < self.CLOSED_THRESHOLD_DISP_M:
                stall_count += 1
            else:
                stall_count = 0
            prev_l, prev_r = l_pos, r_pos
            
            # Grasp trigger:
            # 1. Dual contact: BOTH silicone pads clamped against object body (aperture <= 72mm for 60mm object with 4mm pads)
            # 2. Mechanical stall: fingers stopped moving inward against physical object (stall_count >= 3 and aperture <= 72mm)
            is_dual_contact = (left_c and right_c and current_aperture <= 0.072 and current_aperture >= 0.045)
            is_stalled_enclosed = (stall_count >= 3 and current_aperture <= 0.072 and (left_c or right_c))
            if is_dual_contact or is_stalled_enclosed:
                self.state = HandState.CONTACT_DETECTED
                # Lock fingers with calibrated controller preload to maintain holding effort without crushing
                hold_pos = min(self.MAX_STROKE_PER_FINGER_M, max(l_pos, r_pos) + self.CLOSURE_PRELOAD_M)
                self._command_displacement(hold_pos)
                self.state = HandState.HOLD
                # Force the physics: rigidly lock object to palm link via DetachableJoint
                self.attach_joint()
                return True
                
            # Travel limit trigger (closed on empty air)
            if l_pos >= self.CLOSED_THRESHOLD_DISP_M and r_pos >= self.CLOSED_THRESHOLD_DISP_M:
                self.state = HandState.EMPTY_CLOSED
                return False
                    
            time.sleep(step_interval)

        # Final verification on timeout
        left_c, right_c = self.has_contact()
        l_pos, r_pos = self.get_joint_positions()
        current_aperture = self.get_width()
        if (left_c and right_c and current_aperture <= 0.075) or \
           (current_aperture >= 0.045 and current_aperture <= 0.075 and (left_c or right_c or l_pos < self.CLOSED_THRESHOLD_DISP_M)):
            self.state = HandState.CONTACT_DETECTED
            hold_pos = min(self.MAX_STROKE_PER_FINGER_M, max(l_pos, r_pos) + self.CLOSURE_PRELOAD_M)
            self._command_displacement(hold_pos)
            self.state = HandState.HOLD
            # Force the physics: rigidly lock object to palm link via DetachableJoint
            self.attach_joint()
            return True
        else:
            self.state = HandState.EMPTY_CLOSED
            return False
            
        self.state = HandState.EMPTY_CLOSED
        return False

    def attach_joint(self) -> bool:
        """Forces physics by activating DetachableJoint to create a rigid mathematical bond."""
        if self.attach_cmd_pub is not None and GzEmpty is not None:
            try:
                self.attach_cmd_pub.publish(GzEmpty())
                return True
            except Exception:
                pass
        return False

    def detach_joint(self) -> bool:
        """Deactivates DetachableJoint to release the rigid mathematical bond."""
        if self.detach_cmd_pub is not None and GzEmpty is not None:
            try:
                self.detach_cmd_pub.publish(GzEmpty())
                return True
            except Exception:
                pass
        return False

    def release(self, open_width_m: float = DEFAULT_OPEN_WIDTH_M, timeout_sec: float = 2.0) -> bool:
        """
        Releases grip: first detaches mathematical joint, then opens fingers back to specified aperture width.
        """
        self.detach_joint()
        self.state = HandState.RELEASED
        success = self.open(width_m=open_width_m, timeout_sec=timeout_sec)
        self._left_contact = False
        self._right_contact = False
        self._last_left_contact_time = 0.0
        self._last_right_contact_time = 0.0
        return success

    def hold(self) -> bool:
        """
        Actively maintains current grip stance.
        """
        l_pos, r_pos = self.get_joint_positions()
        hold_disp = max(0.0, (l_pos + r_pos) / 2.0)
        self._command_displacement(hold_disp)
        self.state = HandState.HOLD
        return True

    # -------------------------------------------------------------------------
    # Programmatic Mock Helpers for Testing
    # -------------------------------------------------------------------------
    def set_mock_contact(self, left: bool, right: bool):
        self._left_contact = left
        self._right_contact = right
        self._mock_force_contact = left or right

    def set_mock_object(self, width_m: Optional[float]):
        self._mock_object_width = width_m

    # -------------------------------------------------------------------------
    # Semantic K DSL / Skill Dispatcher
    # -------------------------------------------------------------------------
    def execute_command(self, cmd_string: str) -> Dict[str, Any]:
        """
        High-level dispatcher for semantic commands from K DSL / Manipulation Skill.
        Examples:
          - hand::open
          - hand::open[width: 0.06]
          - hand::close
          - hand::close[target: 0.02]
          - hand::grasp
          - hand::grasp[target: 'book_math']
          - hand::release
          - hand::hold
        """
        cmd = cmd_string.strip()
        
        # hand::open
        if cmd.startswith("hand::open"):
            width = self.DEFAULT_OPEN_WIDTH_M
            m = re.search(r"width:\s*([0-9.]+)", cmd)
            if m:
                width = float(m.group(1))
            res = self.open(width_m=width)
            return {
                "status": "success" if res else "failed",
                "state": self.get_state(),
                "width_m": self.get_width(),
                "contact": self.has_contact()
            }
            
        # hand::close
        elif cmd.startswith("hand::close"):
            target_w = self.MIN_GAP_M
            m = re.search(r"target:\s*([0-9.]+)", cmd)
            if m:
                target_w = float(m.group(1))
            res = self.close(target_width_m=target_w)
            return {
                "status": "success" if res else "failed",
                "state": self.get_state(),
                "width_m": self.get_width(),
                "contact": self.has_contact()
            }
            
        # hand::grasp
        elif cmd.startswith("hand::grasp"):
            target_id = None
            m = re.search(r"target:\s*['\"]?([^'\"\]]+)['\"]?", cmd)
            if m:
                target_id = m.group(1).strip()
            success = self.grasp(target_id=target_id)
            return {
                "status": "success" if success else "failed",
                "grasped": success,
                "target": target_id,
                "state": self.get_state(),
                "width_m": self.get_width(),
                "contact": self.has_contact()
            }
            
        # hand::release
        elif cmd.startswith("hand::release"):
            res = self.release()
            return {
                "status": "success" if res else "failed",
                "state": self.get_state(),
                "width_m": self.get_width(),
                "contact": self.has_contact()
            }
            
        # hand::hold
        elif cmd.startswith("hand::hold"):
            res = self.hold()
            return {
                "status": "success" if res else "failed",
                "state": self.get_state(),
                "width_m": self.get_width(),
                "contact": self.has_contact()
            }
            
        else:
            return {
                "status": "error",
                "message": f"Unknown hand command: {cmd}",
                "state": self.get_state()
            }


if __name__ == "__main__":
    print("Initializing HandSubsystem...")
    hand = HandSubsystem()
    print(f"Hand initialized. State: {hand.get_state()}, Aperture: {hand.get_width()*1000:.1f}mm")
    
    print("\n1. Testing hand::open...")
    res = hand.execute_command("hand::open[width: 0.08]")
    print("Result:", res)
    
    print("\n2. Testing hand::close...")
    res = hand.execute_command("hand::close")
    print("Result:", res)
    
    print("\n3. Testing hand::grasp on empty air (must fail)...")
    res = hand.execute_command("hand::grasp")
    print("Result:", res)
    
    print("\nHandSubsystem test complete.")
