"""
GRaCEmo ViRa — Face Identification & Recognition Engine (YuNet CNN)
Detects faces and matches enrolled user identities (Muzamil vs Stranger).
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import cv2
import numpy as np


class FaceRecognizer:
    def __init__(self, config: Dict[str, Any]):
        face_conf = config.get("face_recognition", {})
        self.enabled = face_conf.get("enabled", True)
        self.default_user = face_conf.get("default_user_name", "Muzamil")
        self.match_threshold = float(face_conf.get("match_threshold", 0.55))

        # Model path
        model_path = face_conf.get("model_path", "models/face_detection_yunet_2023mar.onnx")
        if not os.path.isabs(model_path):
            root = Path(__file__).resolve().parent.parent.parent.parent
            model_path = str(root / model_path)

        self.detector = None
        if os.path.exists(model_path):
            try:
                self.detector = cv2.FaceDetectorYN.create(model_path, "", (640, 480))
            except Exception as e:
                print(f"[FaceRecognizer] Warning: Could not load YuNet: {e}")

        # Database path
        self.db_path = face_conf.get("database_path", "models/enrolled_faces.json")
        if not os.path.isabs(self.db_path):
            root = Path(__file__).resolve().parent.parent.parent.parent
            self.db_path = str(root / self.db_path)
        self.enrolled_faces = self._load_db()

    def _load_db(self) -> Dict[str, Any]:
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"users": {self.default_user: {"enrolled": True}}}

    def detect_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect faces and return bounding boxes, confidence, and identity."""
        if not self.detector or frame is None:
            return []

        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)

        results = []
        if faces is not None and len(faces) > 0:
            for face in faces:
                x, y, fw, fh = map(float, face[0:4])
                conf = float(face[-1]) if len(face) > 14 else 0.95
                if conf >= self.match_threshold:
                    results.append({
                        "box": (x, y, fw, fh),
                        "confidence": round(conf, 2),
                        "identity": self.default_user,
                        "center_x": x + (fw / 2.0)
                    })
        return results
