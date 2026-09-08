#!/usr/bin/env python3
"""
Captures what the robot actually "sees" from its own eyes:
1. RGB Color Vision (/camera/image_raw)
2. 3D Depth Perception Heatmap (/camera/depth_image) revealing 3D obstacle shapes & contours.
"""
import os
import time
import cv2
import numpy as np
import gz.transport13 as gz_transport
from gz.msgs10.image_pb2 import Image

def capture_eyes():
    node = gz_transport.Node()

    rgb_saved = [False]
    depth_saved = [False]

    out_rgb = "/home/mab/.gemini/antigravity/brain/1927959e-bd62-449a-8832-a11c9c8e2e98/robot_eyes_rgb.jpg"
    out_depth = "/home/mab/.gemini/antigravity/brain/1927959e-bd62-449a-8832-a11c9c8e2e98/robot_eyes_depth_shapes.jpg"

    def on_rgb(msg: Image):
        if rgb_saved[0]:
            return
        w, h = msg.width, msg.height
        img = np.frombuffer(msg.data, dtype=np.uint8).reshape((h, w, 3))
        os.makedirs(os.path.dirname(out_rgb), exist_ok=True)
        cv2.imwrite(out_rgb, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        rgb_saved[0] = True
        print(f"✓ Saved Robot RGB Eyes view: {out_rgb} ({w}x{h})")

    def on_depth(msg: Image):
        if depth_saved[0]:
            return
        w, h = msg.width, msg.height
        # Float32 depth array in meters
        depth_data = np.frombuffer(msg.data, dtype=np.float32).reshape((h, w))
        # Replace NaNs / Infs
        depth_clean = np.nan_to_num(depth_data, nan=10.0, posinf=10.0, neginf=0.0)
        # Clip to 0.2m - 6.0m for contrast
        clipped = np.clip(depth_clean, 0.2, 6.0)
        norm = ((clipped - 0.2) / (6.0 - 0.2) * 255.0).astype(np.uint8)
        # Invert so near obstacles are bright/warm, far walls are cool/dark
        norm_inv = 255 - norm
        colored_depth = cv2.applyColorMap(norm_inv, cv2.COLORMAP_TURBO)
        os.makedirs(os.path.dirname(out_depth), exist_ok=True)
        cv2.imwrite(out_depth, colored_depth)
        depth_saved[0] = True
        print(f"✓ Saved Robot 3D Depth Shape view: {out_depth} ({w}x{h})")

    node.subscribe(Image, "/camera/image_raw", on_rgb)
    node.subscribe(Image, "/camera/depth_image", on_depth)

    t0 = time.time()
    while not (rgb_saved[0] and depth_saved[0]) and time.time() - t0 < 6.0:
        time.sleep(0.1)

    print(f"Capture results: RGB={rgb_saved[0]}, Depth={depth_saved[0]}")
    return rgb_saved[0] and depth_saved[0]

if __name__ == "__main__":
    capture_eyes()
