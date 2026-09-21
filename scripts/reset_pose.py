import sys
import math
import gz.transport13 as gz_t
from gz.msgs10.pose_pb2 import Pose
from gz.msgs10.boolean_pb2 import Boolean

x = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
y = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
yaw = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0

node = gz_t.Node()
req = Pose()
req.name = "gracemo_vira"
req.id = 171
req.position.x = x
req.position.y = y
req.position.z = 0.08
req.orientation.z = math.sin(yaw / 2.0)
req.orientation.w = math.cos(yaw / 2.0)

rep = Boolean()
res, rep = node.request("/world/gracemo_home/set_pose", req, Pose, Boolean, 2000)
print(f"Pose set to ({x}, {y}, yaw={yaw}): {rep.data if res else False}")
