"""
GRaCEmo ViRa — Unified Autonomous Robotics Control Center (UARCC)
"""

import sys

__version__ = "1.0.0"

# Support dual import paths: gracemo_control_center and unified_control_center
if __name__ == "unified_control_center" and "gracemo_control_center" not in sys.modules:
    sys.modules["gracemo_control_center"] = sys.modules[__name__]
elif __name__ == "gracemo_control_center" and "unified_control_center" not in sys.modules:
    sys.modules["unified_control_center"] = sys.modules[__name__]
