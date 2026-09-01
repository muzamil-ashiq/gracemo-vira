# 🎓 ROS 2 Master Hands-On Tutorial & Self-Paced Lab Guide

> **Welcome to the complete, self-paced ROS 2 curriculum for the GraceEMO Autonomous Robot Project.**  
> Everything is designed for you to code, run, experiment, break, and master by yourself.

---

## 📑 Table of Contents

- [Lesson 0: Environment & Daily Workflow](#-lesson-0-environment--daily-workflow)
- [Lesson 1: Nodes & Topics (Publish / Subscribe)](#-lesson-1-nodes--topics-publish--subscribe)
- [Lesson 2: Command-Line Power Tools (Inspection & Debugging)](#-lesson-2-command-line-power-tools)
- [Lesson 3: Services (Request ⇄ Response)](#-lesson-3-services-request--response)
- [Lesson 4: Custom Message & Service Definitions (.msg & .srv)](#-lesson-4-custom-message--service-definitions)
- [Lesson 5: Actions (Long-Running Tasks with Feedback)](#-lesson-5-actions-long-running-tasks-with-feedback)
- [Lesson 6: Node Parameters & Config Files (YAML)](#-lesson-6-node-parameters--config-files-yaml)
- [Lesson 7: Workspaces, Packages & Build System (colcon)](#-lesson-7-workspaces-packages--build-system-colcon)
- [Lesson 8: Launch Files (Multi-Node Orchestration)](#-lesson-8-launch-files-multi-node-orchestration)
- [Lesson 9: TF2 Transform System (3D Spatial Awareness)](#-lesson-9-tf2-transform-system-3d-spatial-awareness)
- [Lesson 10: Building an AI Vision Node (YOLO + ROS 2 Image Streams)](#-lesson-10-building-an-ai-vision-node)
- [Master Troubleshooting Cheatsheet](#-master-troubleshooting-cheatsheet)

---

## ⚡ Lesson 0: Environment & Daily Workflow

### 1. How Your Container Setup Works
Your host machine is macOS, but ROS 2 Jazzy runs in the background Linux Docker container named `ros2_learn`. Your workspace folder (`GraceEMO-Final`) is mounted live at `/workspace/GraceEMO-Final`.

### 2. The Golden 2-Step Routine for ANY New Terminal
Whenever you open a new terminal to work with ROS 2, run:

```bash
# Step 1: Jump into container
docker exec -it ros2_learn bash

# Step 2: Source the ROS 2 setup
source /opt/ros/jazzy/setup.bash
```

*(Tip: You can add `source /opt/ros/jazzy/setup.bash` to `/root/.bashrc` inside the container so it sources automatically).*

---

## 📡 Lesson 1: Nodes & Topics (Publish / Subscribe)

### 💡 Core Theory
- **Node**: A dedicated Python/C++ process performing a specific job.
- **Topic**: A unidirectional data bus (like a radio channel).
- **Publisher**: Broadcasts data to a topic.
- **Subscriber**: Receives data from a topic.
- **QoS (Quality of Service)**: Determines message buffering, reliability (TCP-like `Reliable` vs UDP-like `Best Effort`).

---

### 🛠️ Exercise 1.1: Build an Autonomous Telemetry Publisher

Create a file `lab1_telemetry_pub.py`:

```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32
import random

class RobotTelemetryPublisher(Node):
    def __init__(self):
        super().__init__('robot_telemetry_publisher')
        
        # Create two publishers on different topics
        self.status_pub = self.create_publisher(String, '/graceemo/status', 10)
        self.battery_pub = self.create_publisher(Float32, '/graceemo/battery_voltage', 10)
        
        # Timer fires every 0.5 seconds (2.0 Hz)
        self.timer = self.create_timer(0.5, self.publish_telemetry)
        
        self.battery_level = 12.6 # Starting 3S LiPo voltage
        self.get_logger().info('✅ Telemetry Publisher Node is ACTIVE')

    def publish_telemetry(self):
        # 1. Publish Status
        status_msg = String()
        status_msg.data = "SYSTEM_NORMAL"
        self.status_pub.publish(status_msg)
        
        # 2. Simulate battery drain & publish voltage
        self.battery_level -= random.uniform(0.001, 0.005)
        battery_msg = Float32()
        battery_msg.data = round(self.battery_level, 3)
        self.battery_pub.publish(battery_msg)
        
        self.get_logger().info(f'⚡ Battery: {battery_msg.data}V | Status: {status_msg.data}')

def main(args=None):
    rclpy.init(args=args)
    node = RobotTelemetryPublisher()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
```

---

### 🛠️ Exercise 1.2: Build a Battery Safety Watchdog Subscriber

Create a file `lab1_battery_watchdog.py`:

```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32

class BatteryWatchdogNode(Node):
    def __init__(self):
        super().__init__('battery_watchdog')
        
        # Subscribe to /graceemo/battery_voltage
        self.sub = self.create_subscription(
            Float32,
            '/graceemo/battery_voltage',
            self.battery_callback,
            10
        )
        self.critical_voltage = 12.0
        self.get_logger().info('🛡️ Battery Safety Watchdog Armed & Listening...')

    def battery_callback(self, msg: Float32):
        voltage = msg.data
        if voltage < self.critical_voltage:
            self.get_logger().error(f'🚨 CRITICAL VOLTAGE ALERT: {voltage}V! Initiating Safe Shutdown!')
        else:
            self.get_logger().info(f'🔋 Safe Voltage: {voltage}V')

def main(args=None):
    rclpy.init(args=args)
    node = BatteryWatchdogNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
```

### 🏃 How to Test
1. Terminal 1: `python3 lab1_telemetry_pub.py`
2. Terminal 2: `python3 lab1_battery_watchdog.py`

---

## 🔍 Lesson 2: Command-Line Power Tools

ROS 2 includes rich inspection utilities. Try each command while your nodes are running:

```bash
# 1. List all active nodes in the computation graph
ros2 node list

# 2. Get deep info about a specific node (its publishers, subscribers, services)
ros2 node info /robot_telemetry_publisher

# 3. List all topics currently active
ros2 topic list -t    # -t shows the message type next to each topic!

# 4. Read topic data live in your terminal
ros2 topic echo /graceemo/battery_voltage

# 5. Measure the real-time frequency (Hz)
ros2 topic hz /graceemo/battery_voltage

# 6. Measure data bandwidth (KB/s)
ros2 topic bw /graceemo/battery_voltage

# 7. Manually publish a message from the terminal!
ros2 topic pub --once /graceemo/battery_voltage std_msgs/msg/Float32 "{data: 11.2}"
# (Watch your watchdog terminal trigger the red CRITICAL error!)
```

---

## 🛎️ Lesson 3: Services (Request ⇄ Response)

### 💡 Core Theory
- **Topics** = Continuous data stream (1-way).
- **Services** = Client-Server, call-and-response (2-way).
- Use a **Service** when you need confirmation or a computed result on-demand (e.g., "Add 2 numbers", "Take a snapshot", "Get robot location", "Reset Odometry").

---

### 🛠️ Exercise 3.1: Build an AI Question-Answering Service Server

We will use the standard ROS 2 service `example_interfaces/srv/SetBool` or `std_srvs/srv/Trigger`.  
Let's build a service using `example_interfaces.srv.Trigger`!

Create `lab3_service_server.py`:

```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from example_interfaces.srv import Trigger
import random

class GraceEMOExecutiveService(Node):
    def __init__(self):
        super().__init__('graceemo_executive_service')
        
        # Create a Service Server named '/graceemo/get_campus_status'
        self.srv = self.create_service(
            Trigger,
            '/graceemo/get_campus_status',
            self.handle_campus_status_request
        )
        self.get_logger().info('🏛️ GraceEMO Campus Executive Service is READY!')

    def handle_campus_status_request(self, request, response):
        self.get_logger().info('📥 Incoming Campus Status Request received!')
        
        # Compute or fetch result
        quotes = [
            "LPU Campus: 600 Acres | NAAC A++ | All Systems Operational.",
            "LPU Campus: 30,000+ Students Active | Weather Clear | AI Systems Online.",
            "LPU Campus: Innovation Labs Active | Robotic Patrols Running."
        ]
        response.success = True
        response.message = random.choice(quotes)
        
        self.get_logger().info(f'📤 Sending Response: "{response.message}"')
        return response

def main(args=None):
    rclpy.init(args=args)
    node = GraceEMOExecutiveService()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
```

---

### 🛠️ Exercise 3.2: Build the Service Client Node

Create `lab3_service_client.py`:

```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from example_interfaces.srv import Trigger
import sys

class GraceEMOClient(Node):
    def __init__(self):
        super().__init__('graceemo_client')
        self.client = self.create_client(Trigger, '/graceemo/get_campus_status')
        
        # Wait up to 5 seconds for the server to be online
        while not self.client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('Waiting for Executive Service to come online...')
            
    def send_request(self):
        req = Trigger.Request()
        self.get_logger().info('🚀 Sending request to server...')
        future = self.client.call_async(req)
        return future

def main(args=None):
    rclpy.init(args=args)
    node = GraceEMOClient()
    future = node.send_request()
    
    # Wait until response arrives
    rclpy.spin_until_future_complete(node, future)
    
    if future.result() is not None:
        res = future.result()
        node.get_logger().info(f'🎉 Success: {res.success} | Message: "{res.message}"')
    else:
        node.get_logger().error(f'Service call failed: {future.exception()}')
        
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
```

### 🏃 How to Test
1. Terminal 1: `python3 lab3_service_server.py`
2. Terminal 2: `python3 lab3_service_client.py`
3. Terminal 3 (CLI test without Python!):
   ```bash
   ros2 service call /graceemo/get_campus_status example_interfaces/srv/Trigger "{}"
   ```

---

## 📦 Lesson 4: Custom Message & Service Definitions

When standard types (`String`, `Float32`, `Twist`) are not enough, you define custom data structures in `.msg` and `.srv` files.

### 1. Message Structure (`.msg`)
Example `PersonDetection.msg`:
```text
int32 track_id
string name
float32 confidence
float32 distance_meters
float32 center_x
float32 center_y
```

### 2. Service Structure (`.srv`)
Separated by three dashes `---` (Request above, Response below):
Example `IdentifyPerson.srv`:
```text
# REQUEST
sensor_msgs/Image face_image
---
# RESPONSE
bool is_known
string person_name
string role
float32 match_confidence
```

---

## ⏳ Lesson 5: Actions (Long-Running Tasks with Feedback)

### 💡 Core Theory
- **Topic**: Fire-and-forget stream.
- **Service**: Instant request & response (blocking).
- **Action**: For tasks that take **time to complete** (e.g. "Navigate to Room 302", "Speak a 50-word paragraph", "Rotate 360 degrees").

An Action provides:
1. **Goal**: Client requests a target (e.g. `target_room: "Library"`).
2. **Feedback**: Server continuously sends progress updates (e.g. `distance_remaining: 1.2m`).
3. **Result**: Server sends final outcome (e.g. `arrived: True, time_taken: 42s`).
4. **Cancelation**: Client can cancel the goal mid-way!

---

## 🎛️ Lesson 6: Node Parameters & Config Files (YAML)

Never hardcode variables (speeds, thresholds, model paths, IP addresses). Use **ROS 2 Parameters**.

### 🛠️ Exercise 6.1: Node with Configurable Parameters

Create `lab6_param_node.py`:

```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

class ConfigurableRobotNode(Node):
    def __init__(self):
        super().__init__('configurable_robot_node')
        
        # 1. Declare parameters with default values
        self.declare_parameter('robot_name', 'GraceEMO_V1')
        self.declare_parameter('max_speed', 0.5)
        self.declare_parameter('voice_enabled', True)
        
        # 2. Read parameter values
        robot_name = self.get_parameter('robot_name').get_parameter_value().string_value
        max_speed = self.get_parameter('max_speed').get_parameter_value().double_value
        voice_enabled = self.get_parameter('voice_enabled').get_parameter_value().bool_value
        
        self.get_logger().info(f'🤖 Robot Config: Name={robot_name} | MaxSpeed={max_speed}m/s | Voice={voice_enabled}')
        
        # Timer to print live parameters
        self.create_timer(2.0, self.timer_callback)

    def timer_callback(self):
        speed = self.get_parameter('max_speed').get_parameter_value().double_value
        self.get_logger().info(f'⚙️ Current Max Speed is: {speed} m/s')

def main(args=None):
    rclpy.init(args=args)
    node = ConfigurableRobotNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
```

### 🏃 Dynamic Parameter Tuning in Real Time:
Run the node in Terminal 1:
```bash
python3 lab6_param_node.py
```

In Terminal 2, inspect and change parameters live without restarting:
```bash
# List all parameters of active nodes
ros2 param list

# Get current value
ros2 param get /configurable_robot_node max_speed

# Change parameter on the fly!
ros2 param set /configurable_robot_node max_speed 1.25
# (Watch Terminal 1 update its speed output live!)
```

---

## 🏗️ Lesson 7: Workspaces, Packages & Build System (`colcon`)

In real robotics projects, code is organized into packages and built using `colcon`.

### 1. Workspace Layout
```text
graceemo_ws/
├── src/                      # Source code (packages live here)
│   ├── graceemo_brain/
│   ├── graceemo_vision/
│   └── graceemo_msgs/
├── build/                    # Intermediate build files
├── install/                  # Packaged binaries & setup.bash
└── log/                      # Build logs
```

### 2. Creating a Python Package
```bash
cd /workspace
mkdir -p graceemo_ws/src && cd graceemo_ws/src

# Create package with dependencies
ros2 pkg create --build-type ament_python graceemo_controller --dependencies rclpy geometry_msgs std_msgs
```

### 3. Building the Workspace
```bash
cd /workspace/graceemo_ws
colcon build --symlink-install

# Always source after building:
source install/setup.bash
```

---

## 🚀 Lesson 8: Launch Files (Multi-Node Orchestration)

Instead of opening 10 terminal tabs to start 10 nodes, a **Launch File** starts and configures your entire robot in one command: `ros2 launch package_name robot.launch.py`.

### Example Python Launch File:
```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='graceemo_controller',
            executable='telemetry_node',
            name='telemetry_publisher',
            parameters=[{'max_speed': 0.8}]
        ),
        Node(
            package='graceemo_controller',
            executable='watchdog_node',
            name='safety_watchdog'
        )
    ])
```

---

## 🧭 Lesson 9: TF2 Transform System (3D Spatial Awareness)

### 💡 Core Theory
In robotics, every sensor and joint has a coordinate frame:
- `base_link`: Center of robot on the ground.
- `camera_link`: Optical center of the camera.
- `lidar_link`: Center of the LiDAR spinning mirror.
- `odom`: World position based on wheel odometry.
- `map`: Global map origin.

**TF2 calculates where anything is relative to anything else:**  
*"Where is the detected person relative to the robot's base?"*

```text
map ──► odom ──► base_link ──► camera_link ──► detected_object
```

---

## 👁️ Lesson 10: Building an AI Vision Node

Let's see how modern Deep Learning (YOLO) connects to ROS 2.

```python
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge # Converts ROS Image <-> OpenCV numpy array
import cv2

class GraceEMOVisionNode(Node):
    def __init__(self):
        super().__init__('graceemo_vision_node')
        self.bridge = CvBridge()
        
        # Subscribe to raw camera feed
        self.subscription = self.create_subscription(
            Image,
            '/camera/image_raw',
            self.image_callback,
            10
        )
        self.get_logger().info('👁️ GraceEMO Vision AI Node is Active')

    def image_callback(self, msg):
        # 1. Convert ROS Image message to OpenCV numpy format
        cv_frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        
        # 2. Run Inference (e.g. YOLOv11 / Face Detection)
        # results = model(cv_frame)
        
        # 3. Publish detections or log
        self.get_logger().info(f'Captured Frame size: {cv_frame.shape}')
```

---

## 🛠️ Master Troubleshooting Cheatsheet

| Issue | Cause | Fix |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'rclpy'` | Running in Mac host instead of container | Run `docker exec -it ros2_learn bash` first |
| `ros2: command not found` | ROS 2 setup not sourced | Run `source /opt/ros/jazzy/setup.bash` |
| Nodes can't see each other | Different `ROS_DOMAIN_ID` | Run `export ROS_DOMAIN_ID=0` in all terminals |
| `colcon: command not found` | Build tools missing | `apt update && apt install -y python3-colcon-common-extensions` |
| Service call hangs forever | Server node is not running | Verify with `ros2 service list` |

---

### 🎯 Your Hands-On Mission:
Work through **Lesson 1** through **Lesson 6** right inside your container. Type the code, run it, change the numbers, and see how the ROS 2 graph reacts in real time! 🚀
