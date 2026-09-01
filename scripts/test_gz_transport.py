import time
import numpy as np
import gz.transport13 as gz_transport
from gz.msgs10.image_pb2 import Image as GzImage
from gz.msgs10.twist_pb2 import Twist as GzTwist
from gz.msgs10.odometry_pb2 import Odometry as GzOdometry
from gz.msgs10.laserscan_pb2 import LaserScan as GzLaserScan

node = gz_transport.Node()

def on_image(msg: GzImage):
    print(f"✓ Received camera frame! {msg.width}x{msg.height}, step: {msg.step}, bytes: {len(msg.data)}")

def on_odom(msg: GzOdometry):
    p = msg.pose.position
    print(f"✓ Received odom! ({p.x:.2f}, {p.y:.2f})")

node.subscribe(GzImage, "/camera/image_raw", on_image)
node.subscribe(GzOdometry, "/odom", on_odom)

pub = node.advertise("/cmd_vel", GzTwist)
twist = GzTwist()
twist.linear.x = 0.2
pub.publish(twist)
print("✓ Published cmd_vel!")

time.sleep(2.0)
