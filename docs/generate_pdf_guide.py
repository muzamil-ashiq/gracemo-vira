#!/usr/bin/env python3
import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "GRACEemo ViRa — Master ROS 2 Handbook & Curriculum")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)
            
        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 36, page_str)
        self.drawString(54, 36, "Lovely Professional University | School of CSE | Autonomous Robotics")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 48, letter[0] - 54, 48)
        
        self.restoreState()

def create_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette
    PRIMARY = colors.HexColor("#1E3A8A")   # Deep Navy
    SECONDARY = colors.HexColor("#0284C7") # Vibrant Sky Blue
    ACCENT = colors.HexColor("#0F766E")    # Emerald Teal
    DARK_TEXT = colors.HexColor("#0F172A") # Slate Dark
    LIGHT_BG = colors.HexColor("#F8FAFC")  # Off-white
    CODE_BG = colors.HexColor("#1E293B")   # Slate code box
    CODE_TEXT = colors.HexColor("#38BDF8") # Bright Cyan
    BORDER_COLOR = colors.HexColor("#E2E8F0")

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=30,
        textColor=PRIMARY,
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=SECONDARY,
        spaceAfter=15
    )
    
    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=SECONDARY,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=DARK_TEXT,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet',
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=4
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B")
    )
    
    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=CODE_TEXT
    )

    story = []

    def add_callout(text, bg="#EFF6FF", border="#3B82F6"):
        p = Paragraph(text, callout_style)
        t = Table([[p]], colWidths=[letter[0] - 108])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bg)),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(border)),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))

    def add_code_block(code_text):
        p = Preformatted(code_text.strip(), code_style)
        t = Table([[p]], colWidths=[letter[0] - 108])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), CODE_BG),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))

    # ==================== COVER / HEADER ====================
    story.append(Paragraph("🤖 GRACEemo ViRa", title_style))
    story.append(Paragraph("Master ROS 2 Hands-On Tutorial & Self-Paced Lab Guide", subtitle_style))
    add_callout("<b>Institutional Project:</b> School of Computer Science & Engineering | Lovely Professional University<br/><b>Mentor:</b> Dr. Mohit Arora | <b>Project Lead:</b> Sam Davi | <b>Target Distro:</b> ROS 2 Jazzy (Ubuntu 24.04)")
    story.append(Spacer(1, 10))

    # ==================== LESSON 0 ====================
    story.append(Paragraph("Lesson 0: Environment & Daily Workflow", h1_style))
    story.append(Paragraph("Your ROS 2 environment runs inside the Linux Docker container <code>ros2_learn</code> with direct live volume mapping to your workspace folder.", body_style))
    story.append(Paragraph("<b>The Golden 2-Step Routine for ANY Terminal:</b>", body_style))
    add_code_block("""# Step 1: Jump into the active ROS 2 container
docker exec -it ros2_learn bash

# Step 2: Source the ROS 2 setup environment
source /opt/ros/jazzy/setup.bash""")

    # ==================== LESSON 1 ====================
    story.append(Paragraph("Lesson 1: Nodes & Topics (Publish / Subscribe)", h1_style))
    story.append(Paragraph("In ROS 2, a <b>Node</b> is an isolated executable performing a specific function. Nodes communicate asynchronously over named channels called <b>Topics</b>.", body_style))
    
    story.append(Paragraph("<b>1.1 Building a Telemetry Publisher:</b>", h2_style))
    add_code_block("""import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, String
import random

class TelemetryPub(Node):
    def __init__(self):
        super().__init__('telemetry_publisher')
        self.batt_pub = self.create_publisher(Float32, '/graceemo/battery_voltage', 10)
        self.timer = self.create_timer(0.5, self.publish_telemetry)
        self.voltage = 12.6

    def publish_telemetry(self):
        self.voltage -= random.uniform(0.001, 0.005)
        msg = Float32()
        msg.data = round(self.voltage, 3)
        self.batt_pub.publish(msg)
        self.get_logger().info(f'⚡ Voltage: {msg.data}V')

def main():
    rclpy.init()
    node = TelemetryPub()
    try:
        rclpy.spin(node)
    except:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()

if __name__ == '__main__': main()""")

    story.append(Paragraph("<b>1.2 Building a Battery Safety Watchdog Subscriber:</b>", h2_style))
    add_code_block("""import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32

class BatteryWatchdog(Node):
    def __init__(self):
        super().__init__('battery_watchdog')
        self.sub = self.create_subscription(
            Float32, '/graceemo/battery_voltage', self.callback, 10)

    def callback(self, msg):
        if msg.data < 12.0:
            self.get_logger().error(f'🚨 CRITICAL VOLTAGE: {msg.data}V! Triggering Safe E-Stop!')
        else:
            self.get_logger().info(f'🔋 Voltage Normal: {msg.data}V')

def main():
    rclpy.init()
    node = BatteryWatchdog()
    try:
        rclpy.spin(node)
    except:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()

if __name__ == '__main__': main()""")

    # ==================== LESSON 2 ====================
    story.append(Paragraph("Lesson 2: Command-Line Power Tools (Inspection & Debugging)", h1_style))
    story.append(Paragraph("Essential CLI tools to inspect the active ROS 2 computation graph in real time:", body_style))
    
    cli_table_data = [
        [Paragraph("<b>Command</b>", body_style), Paragraph("<b>Description</b>", body_style)],
        [Paragraph("<code>ros2 node list</code>", body_style), Paragraph("List all currently running nodes", body_style)],
        [Paragraph("<code>ros2 node info &lt;node_name&gt;</code>", body_style), Paragraph("Show publishers, subscribers, services of a node", body_style)],
        [Paragraph("<code>ros2 topic list -t</code>", body_style), Paragraph("List all active topics along with their message types", body_style)],
        [Paragraph("<code>ros2 topic echo &lt;topic&gt;</code>", body_style), Paragraph("Stream live data published on a topic to terminal", body_style)],
        [Paragraph("<code>ros2 topic hz &lt;topic&gt;</code>", body_style), Paragraph("Measure live publish rate (frequency in Hz)", body_style)],
        [Paragraph("<code>ros2 topic pub --once &lt;topic&gt; &lt;type&gt; '&lt;data&gt;'</code>", body_style), Paragraph("Manually broadcast a single message from the terminal", body_style)],
    ]
    t_cli = Table(cli_table_data, colWidths=[180, letter[0] - 108 - 180])
    t_cli.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_cli)
    story.append(Spacer(1, 8))

    # ==================== LESSON 3 ====================
    story.append(Paragraph("Lesson 3: Services (Request ⇄ Response Architecture)", h1_style))
    story.append(Paragraph("While topics provide continuous streams, <b>Services</b> provide synchronous, two-way Remote Procedure Calls (client requests a task, server computes and returns a response).", body_style))
    
    add_code_block("""# Service Server Example
from example_interfaces.srv import Trigger
import rclpy
from rclpy.node import Node

class GraceEMOService(Node):
    def __init__(self):
        super().__init__('graceemo_status_service')
        self.srv = self.create_service(
            Trigger, '/graceemo/get_campus_status', self.handle_request)
        self.get_logger().info('🏛️ Campus Status Service Online')

    def handle_request(self, request, response):
        response.success = True
        response.message = "LPU Campus: 600 Acres | NAAC A++ | All Systems Operational"
        return response

def main():
    rclpy.init()
    node = GraceEMOService()
    try: rclpy.spin(node)
    finally: node.destroy_node(); rclpy.shutdown()

if __name__ == '__main__': main()""")

    # ==================== LESSON 4 ====================
    story.append(Paragraph("Lesson 4: Custom Message & Service Definitions", h1_style))
    story.append(Paragraph("Custom schemas are defined inside a dedicated messages package (e.g. <code>graceemo_msgs</code>):", body_style))
    
    add_code_block("""# PersonDetection.msg (Message definition)
int32 track_id
string name
float32 confidence
geometry_msgs/Point position_in_map

---
# IdentifyPerson.srv (Service definition with Request and Response)
sensor_msgs/Image face_crop
---
bool is_authorized
string full_name
string designation""")

    # ==================== LESSON 5 ====================
    story.append(Paragraph("Lesson 5: Actions (Long-Running Tasks with Feedback)", h1_style))
    story.append(Paragraph("<b>Actions</b> are used for preemptible tasks that take measurable time (e.g., navigating to a room, executing a speech dialogue, or executing a motion trajectory).", body_style))
    
    action_table_data = [
        [Paragraph("<b>Component</b>", body_style), Paragraph("<b>Function</b>", body_style)],
        [Paragraph("<b>Goal</b>", body_style), Paragraph("Client sends target destination or command (e.g. <code>target: 'Library'</code>)", body_style)],
        [Paragraph("<b>Feedback</b>", body_style), Paragraph("Server continuously transmits incremental progress (e.g. <code>distance_remaining: 1.2m</code>)", body_style)],
        [Paragraph("<b>Result</b>", body_style), Paragraph("Server returns final status upon completion (e.g. <code>arrived: True, duration: 32s</code>)", body_style)],
        [Paragraph("<b>Preemption</b>", body_style), Paragraph("Client can cancel the goal at any time while in progress", body_style)],
    ]
    t_action = Table(action_table_data, colWidths=[120, letter[0] - 108 - 120])
    t_action.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_action)
    story.append(Spacer(1, 8))

    # ==================== LESSON 6 ====================
    story.append(Paragraph("Lesson 6: Node Parameters & Config Files (YAML)", h1_style))
    story.append(Paragraph("Never hardcode values. Parameters allow external configuration at startup or runtime dynamic tuning.", body_style))
    add_code_block("""# Declaring and using parameters in Python
self.declare_parameter('max_speed', 0.5)
self.declare_parameter('robot_name', 'GraceEMO_V1')

# Reading parameter value
current_speed = self.get_parameter('max_speed').get_parameter_value().double_value

# Dynamic CLI inspection and live modification:
# ros2 param list
# ros2 param get /node_name max_speed
# ros2 param set /node_name max_speed 1.2  <-- Instant live update!""")

    # ==================== LESSON 7 ====================
    story.append(Paragraph("Lesson 7: Workspaces, Packages & Build System (colcon)", h1_style))
    story.append(Paragraph("ROS 2 uses <code>colcon</code> to build multiple modular packages in a clean workspace tree:", body_style))
    add_code_block("""# Workspace Directory Structure:
# graceemo_ws/
#   src/ (source packages)
#   build/ (compilation artifacts)
#   install/ (deployed binaries and setup.bash)

# 1. Create a new Python package
cd ~/graceemo_ws/src
ros2 pkg create --build-type ament_python graceemo_brain --dependencies rclpy std_msgs geometry_msgs

# 2. Build the workspace
cd ~/graceemo_ws
colcon build --symlink-install

# 3. Source the built workspace
source install/setup.bash""")

    # ==================== LESSON 8 ====================
    story.append(Paragraph("Lesson 8: Launch Files (Multi-Node Orchestration)", h1_style))
    story.append(Paragraph("Launch files allow you to start your entire robot stack (perception, navigation, voice, and drivers) with a single command: <code>ros2 launch graceemo_bringup robot.launch.py</code>.", body_style))
    add_code_block("""# Python Launch File Example (robot.launch.py)
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='graceemo_perception',
            executable='detector_node',
            name='yolo_detector',
            parameters=[{'confidence_thresh': 0.5, 'device': 'cuda:0'}]
        ),
        Node(
            package='graceemo_voice',
            executable='stt_node',
            name='speech_transcriber'
        )
    ])""")

    # ==================== LESSON 9 ====================
    story.append(Paragraph("Lesson 9: TF2 Transform System (3D Spatial Awareness)", h1_style))
    story.append(Paragraph("<b>TF2</b> maintains the coordinate tree representing the relative 3D position and orientation of every sensor and link:", body_style))
    add_callout("<b>Coordinate Tree:</b><br/><code>map (World) ──► odom (Odometry) ──► base_link (Robot Center) ──► camera_link / lidar_link</code>")

    # ==================== LESSON 10 ====================
    story.append(Paragraph("Lesson 10: Building an AI Vision Node (YOLO + ROS 2)", h1_style))
    story.append(Paragraph("Bridge OpenCV image arrays and ROS 2 standard image messages seamlessly:", body_style))
    add_code_block("""import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

class VisionNode(Node):
    def __init__(self):
        super().__init__('vision_node')
        self.bridge = CvBridge()
        self.sub = self.create_subscription(
            Image, '/camera/image_raw', self.image_callback, 10)

    def image_callback(self, msg):
        # Convert ROS Image -> OpenCV BGR Numpy Array
        cv_frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        
        # Run YOLO / AI Inference here:
        # detections = yolo_model(cv_frame)
        self.get_logger().info(f'Processed Frame: {cv_frame.shape}')

def main():
    rclpy.init(); node = VisionNode()
    try: rclpy.spin(node)
    finally: node.destroy_node(); rclpy.shutdown()""")

    # ==================== TROUBLESHOOTING CHEATSHEET ====================
    story.append(Paragraph("Master Troubleshooting Cheatsheet", h1_style))
    trouble_data = [
        [Paragraph("<b>Error / Symptom</b>", body_style), Paragraph("<b>Root Cause</b>", body_style), Paragraph("<b>Immediate Fix</b>", body_style)],
        [Paragraph("<code>ModuleNotFoundError: No module named 'rclpy'</code>", body_style), Paragraph("Executed on host macOS instead of container", body_style), Paragraph("Run <code>docker exec -it ros2_learn bash</code> first", body_style)],
        [Paragraph("<code>ros2: command not found</code>", body_style), Paragraph("ROS 2 environment not sourced", body_style), Paragraph("Run <code>source /opt/ros/jazzy/setup.bash</code>", body_style)],
        [Paragraph("Nodes cannot discover each other", body_style), Paragraph("Domain ID mismatch across shells", body_style), Paragraph("Run <code>export ROS_DOMAIN_ID=0</code> in all terminals", body_style)],
        [Paragraph("Service call hangs indefinitely", body_style), Paragraph("Target service server is not active", body_style), Paragraph("Check with <code>ros2 service list</code>", body_style)],
    ]
    t_trouble = Table(trouble_data, colWidths=[150, 150, letter[0] - 108 - 300])
    t_trouble.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_trouble)

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully created at: {output_path}")

if __name__ == '__main__':
    target_path = "/Users/samdavi/projects/GraceEMO-Final/GraceEMO_ROS2_Master_Guide.pdf"
    create_pdf(target_path)
