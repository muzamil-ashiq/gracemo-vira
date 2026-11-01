"""
GRaCEmo ViRa — Perception Visualizer
Renders 2D bounding boxes, confidence scores, metric depths, and 3D world positions
onto camera frames for simulation debugging and verification.
"""

from typing import List, Optional
import cv2
import numpy as np

from .models import Detection


class PerceptionVisualizer:
    """
    Renders visual debug overlays on top of camera frames.
    """

    def __init__(self):
        # Color palette for classes (BGR)
        self.colors = [
            (0, 255, 0),    # Green
            (255, 140, 0),  # Blue/Cyan
            (0, 165, 255),  # Orange
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Yellow
            (255, 255, 0),  # Cyan
        ]

    def annotate_frame(
        self,
        frame_bgr: np.ndarray,
        detections: List[Detection],
        save_path: Optional[str] = None,
    ) -> np.ndarray:
        """
        Draws bounding boxes and telemetry tags on the image frame:
            - Class name
            - Confidence
            - Metric depth (m)
            - 3D World position (X, Y, Z)
        """
        if frame_bgr is None:
            return frame_bgr

        annotated = frame_bgr.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX

        for i, det in enumerate(detections):
            color = self.colors[i % len(self.colors)]
            box = det.bbox

            x1, y1 = int(round(box.x1)), int(round(box.y1))
            x2, y2 = int(round(box.x2)), int(round(box.y2))

            # 1. Draw bounding box rectangle
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # 2. Draw center point
            cx, cy = int(round(box.cx)), int(round(box.cy))
            cv2.circle(annotated, (cx, cy), 4, (0, 0, 255), -1)

            # 3. Text labels
            label_top = f"{det.class_name.upper()} {det.confidence:.2f}"
            label_bot = f"d:{det.depth_m:.2f}m W:({det.position_world.x:.2f},{det.position_world.y:.2f},{det.position_world.z:.2f})"

            # Background pill for top label
            (tw1, th1), _ = cv2.getTextSize(label_top, font, 0.5, 1)
            y_top_bg = max(0, y1 - th1 - 6)
            cv2.rectangle(annotated, (x1, y_top_bg), (x1 + tw1 + 6, y1), color, -1)
            cv2.putText(annotated, label_top, (x1 + 3, y1 - 4), font, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

            # Background pill for bottom label
            (tw2, th2), _ = cv2.getTextSize(label_bot, font, 0.42, 1)
            y_bot_bg = min(annotated.shape[0], y2 + th2 + 6)
            cv2.rectangle(annotated, (x1, y2), (x1 + tw2 + 6, y_bot_bg), (30, 30, 30), -1)
            cv2.putText(annotated, label_bot, (x1 + 3, y2 + th2 + 2), font, 0.42, (255, 255, 255), 1, cv2.LINE_AA)

        if save_path is not None:
            try:
                cv2.imwrite(save_path, annotated)
            except Exception:
                pass

        return annotated
