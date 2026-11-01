import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from nav_msgs.msg import Odometry, Path
import time
import json
import math

def main():
    rclpy.init()
    node = Node("diag_node")
    qos_best_effort = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
    qos_transient = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)

    state = {
        "map_x": None, "map_y": None, "map_yaw": None,
        "odom_x": 0.0, "odom_y": 0.0,
        "cmd_vel_x": 0.0, "cmd_vel_theta": 0.0,
        "feedback": [], "speech": [], "plan_points": 0,
    }

    def amcl_cb(msg):
        p = msg.pose.pose.position
        state["map_x"] = p.x
        state["map_y"] = p.y
        q = msg.pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        state["map_yaw"] = math.atan2(siny_cosp, cosy_cosp)

    def odom_cb(msg):
        p = msg.pose.pose.position
        state["odom_x"] = p.x
        state["odom_y"] = p.y

    def cmd_cb(msg):
        state["cmd_vel_x"] = msg.linear.x
        state["cmd_vel_theta"] = msg.angular.z

    def fb_cb(msg):
        try:
            data = json.loads(msg.data)
            state["feedback"].append(data)
            sp = data.get("speech", data.get("state"))
            print(f"  [FEEDBACK] {sp}")
        except Exception:
            state["feedback"].append(msg.data)
            print(f"  [FEEDBACK] {msg.data}")

    def speech_cb(msg):
        state["speech"].append(msg.data)
        print(f"  [SPEECH] {msg.data}")

    def plan_cb(msg):
        state["plan_points"] = len(msg.poses)
        if len(msg.poses) > 0:
            first = msg.poses[0].pose.position
            last = msg.poses[-1].pose.position
            print(f"  [GLOBAL PLAN] {len(msg.poses)} poses, start=({first.x:.2f}, {first.y:.2f}) -> end=({last.x:.2f}, {last.y:.2f})")

    node.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", amcl_cb, qos_transient)
    node.create_subscription(Odometry, "/odom", odom_cb, qos_best_effort)
    node.create_subscription(Twist, "/cmd_vel", cmd_cb, 10)
    node.create_subscription(String, "/coordinator/feedback", fb_cb, 10)
    node.create_subscription(String, "/interaction/spoken_feedback", speech_cb, 10)
    node.create_subscription(Path, "/plan", plan_cb, 10)

    pub = node.create_publisher(String, "/interaction/user_input", 10)

    print("Connecting and waiting for subscriber on /interaction/user_input...")
    while pub.get_subscription_count() == 0:
        rclpy.spin_once(node, timeout_sec=0.1)

    print("Waiting for initial AMCL pose...")
    wait_pose_start = time.time()
    while state["map_x"] is None and time.time() - wait_pose_start < 5.0:
        rclpy.spin_once(node, timeout_sec=0.1)

    if state["map_x"] is None:
        state["map_x"], state["map_y"], state["map_yaw"] = 0.0, 0.0, 0.0
        print("AMCL pose timed out; assuming (0.0, 0.0)")
    else:
        print(f"Initial Pose: Map=({state['map_x']:.3f}, {state['map_y']:.3f}, yaw={math.degrees(state['map_yaw']):.1f}°)")

    # Send navigate to living_room
    print("Dispatching command: 'navigate to living room'")
    cmd = String()
    cmd.data = "navigate to living room"
    pub.publish(cmd)

    start = time.time()
    last_print = 0.0
    succeeded = False
    while time.time() - start < 85.0:
        rclpy.spin_once(node, timeout_sec=0.1)
        now = time.time() - start
        if now - last_print >= 2.0:
            last_print = now
            dist_to_goal = math.hypot(state["map_x"] - 4.0, state["map_y"] - (-2.5))
            print(f"T+{now:4.1f}s | Map=({state['map_x']:5.2f}, {state['map_y']:5.2f}) | CmdVel=(lin:{state['cmd_vel_x']:4.2f}, ang:{state['cmd_vel_theta']:4.2f}) | DistToGoal={dist_to_goal:4.2f}m | PlanPoses={state['plan_points']}")

        # Check if arrived
        for fb in state["feedback"]:
            if isinstance(fb, dict) and (fb.get("state") == "SUCCEEDED" or "arrived" in fb.get("speech", "").lower()):
                print(f"✅ SUCCESS CONFIRMED at T+{now:.1f}s!")
                succeeded = True
                break
        if succeeded:
            break

    print(f"Final Pose: Map=({state['map_x']:.3f}, {state['map_y']:.3f}), Succeeded={succeeded}")
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
