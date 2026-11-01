"""
GRaCEmo ViRa — Isolated YOLO11 Object Detector
Runs lightweight pretrained YOLO11n inference on simulated camera frames.
Supports ONNX Runtime (fast, lightweight CPU) and Ultralytics.
"""

import os
import logging
from pathlib import Path
from typing import List, Tuple, Set, Optional, Dict
import numpy as np
import cv2

from .models import BoundingBox

logger = logging.getLogger("perception.detector")

# Full canonical 80 COCO class names
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed",
    "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven",
    "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

COCO_CLASS_ALIASES: Dict[str, str] = {
    "dining table": "table",
    "couch": "sofa",
    "cell phone": "phone",
    "tv": "monitor",
}

DEFAULT_CLASSES_OF_INTEREST: Set[str] = {
    "person",
    "chair",
    "table",
    "dining table",
    "bottle",
    "cup",
    "backpack",
    "laptop",
    "door",
    "tv",
    "monitor",
    "couch",
    "sofa",
    "bowl",
    "bed",
    "refrigerator",
    "book",
}


class ObjectDetector:
    """
    Object detector using pretrained YOLO11n.
    Supports ONNX Runtime backend and Ultralytics backend.
    """

    def __init__(
        self,
        model_name: str = "yolo11n.pt",
        confidence_threshold: float = 0.35,
        classes_of_interest: Optional[Set[str]] = None,
        device: str = "cpu",
    ):
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.classes_of_interest = set(classes_of_interest or DEFAULT_CLASSES_OF_INTEREST)
        self.device = device

        self.ort_session = None
        self.yolo_model = None
        self._load_model()

    def _load_model(self):
        """Attempts to load ONNX Runtime session or Ultralytics model."""
        # 1. Check for ONNX model first (preferred lightweight engine)
        repo_root = Path(__file__).resolve().parent.parent.parent
        onnx_candidates = [
            repo_root / "yolo11n.onnx",
            Path("yolo11n.onnx"),
            repo_root / "models" / "yolo11n.onnx",
        ]

        for onnx_path in onnx_candidates:
            if onnx_path.exists():
                try:
                    import onnxruntime as ort
                    logger.info(f"Loading YOLO11 ONNX model from '{onnx_path}' with ONNX Runtime...")
                    opts = ort.SessionOptions()
                    opts.intra_op_num_threads = 2
                    self.ort_session = ort.InferenceSession(str(onnx_path), opts, providers=["CPUExecutionProvider"])
                    logger.info("✓ YOLO11 ONNX model loaded successfully.")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load ONNX session: {e}")

        # 2. Try Ultralytics YOLO
        try:
            from ultralytics import YOLO
            logger.info(f"Loading Ultralytics YOLO '{self.model_name}' on '{self.device}'...")
            self.yolo_model = YOLO(self.model_name)
            logger.info(f"✓ Ultralytics YOLO '{self.model_name}' loaded successfully.")
            return
        except Exception as e:
            logger.debug(f"Ultralytics not available: {e}")

        logger.warning("ObjectDetector: No active inference engine could be initialized.")

    def detect(self, image_bgr: np.ndarray) -> List[Tuple[str, float, BoundingBox]]:
        """
        Runs object detection on a BGR numpy image frame.
        Returns list of (class_name, confidence, BoundingBox).
        """
        if image_bgr is None:
            return []

        if self.ort_session is not None:
            return self._detect_onnx(image_bgr)
        elif self.yolo_model is not None:
            return self._detect_ultralytics(image_bgr)
        return []

    def _detect_onnx(self, image_bgr: np.ndarray) -> List[Tuple[str, float, BoundingBox]]:
        """Executes YOLO11 inference using ONNX Runtime."""
        h, w = image_bgr.shape[:2]
        # Preprocess: Letterbox to 640x640, BGR -> RGB, / 255.0, NCHW
        input_size = 640
        scale = min(input_size / h, input_size / w)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        resized = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)

        canvas = np.full((input_size, input_size, 3), 114, dtype=np.uint8)
        pad_x = (input_size - nw) // 2
        pad_y = (input_size - nh) // 2
        canvas[pad_y:pad_y + nh, pad_x:pad_x + nw] = resized

        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)

        # Run ONNX inference
        outputs = self.ort_session.run(None, {self.ort_session.get_inputs()[0].name: blob})
        output = outputs[0]  # Shape: (1, 84, 8400)

        # Transpose to (8400, 84)
        predictions = np.transpose(output[0], (1, 0))

        boxes = []
        confidences = []
        class_ids = []

        for pred in predictions:
            class_scores = pred[4:]
            cls_id = int(np.argmax(class_scores))
            conf = float(class_scores[cls_id])

            if conf >= self.confidence_threshold:
                # Bounding box in canvas coordinates: cx, cy, bw, bh
                cx_c, cy_c, bw_c, bh_c = pred[:4]
                # Shift by padding and scale back to original image
                x1 = (cx_c - bw_c / 2.0 - pad_x) / scale
                y1 = (cy_c - bh_c / 2.0 - pad_y) / scale
                x2 = (cx_c + bw_c / 2.0 - pad_x) / scale
                y2 = (cy_c + bh_c / 2.0 - pad_y) / scale

                # Clamp to image bounds
                x1 = max(0.0, min(float(w), x1))
                y1 = max(0.0, min(float(h), y1))
                x2 = max(0.0, min(float(w), x2))
                y2 = max(0.0, min(float(h), y2))

                bw = x2 - x1
                bh = y2 - y1

                if bw > 3 and bh > 3:
                    boxes.append([int(x1), int(y1), int(bw), int(bh)])
                    confidences.append(conf)
                    class_ids.append(cls_id)

        # Apply Non-Maximum Suppression
        detections: List[Tuple[str, float, BoundingBox]] = []
        if len(boxes) > 0:
            indices = cv2.dnn.NMSBoxes(boxes, confidences, self.confidence_threshold, nms_threshold=0.45)
            if len(indices) > 0:
                for idx in indices:
                    i = int(idx[0]) if isinstance(idx, (list, tuple, np.ndarray)) else int(idx)
                    cls_id = class_ids[i]
                    raw_name = COCO_CLASSES[cls_id] if cls_id < len(COCO_CLASSES) else f"class_{cls_id}"
                    canonical_name = COCO_CLASS_ALIASES.get(raw_name, raw_name)

                    if canonical_name in self.classes_of_interest or raw_name in self.classes_of_interest:
                        bx, by, bw, bh = boxes[i]
                        bbox = BoundingBox(x1=float(bx), y1=float(by), x2=float(bx + bw), y2=float(by + bh))
                        detections.append((canonical_name, confidences[i], bbox))

        return detections

    def _detect_ultralytics(self, image_bgr: np.ndarray) -> List[Tuple[str, float, BoundingBox]]:
        """Executes YOLO11 inference using Ultralytics."""
        h, w = image_bgr.shape[:2]
        detections: List[Tuple[str, float, BoundingBox]] = []

        try:
            results = self.yolo_model.predict(
                image_bgr,
                conf=self.confidence_threshold,
                device=self.device,
                verbose=False,
            )
            if not results:
                return []

            result = results[0]
            boxes = result.boxes
            if boxes is None:
                return []

            for box in boxes:
                cls_id = int(box.cls[0].item())
                raw_class = self.yolo_model.names[cls_id]
                canonical_class = COCO_CLASS_ALIASES.get(raw_class, raw_class)
                conf = float(box.conf[0].item())

                if canonical_class in self.classes_of_interest or raw_class in self.classes_of_interest:
                    xyxy = box.xyxy[0].tolist()
                    x1 = max(0.0, min(float(w), float(xyxy[0])))
                    y1 = max(0.0, min(float(h), float(xyxy[1])))
                    x2 = max(0.0, min(float(w), float(xyxy[2])))
                    y2 = max(0.0, min(float(h), float(xyxy[3])))

                    bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
                    if bbox.width > 2 and bbox.height > 2:
                        detections.append((canonical_class, conf, bbox))

        except Exception as e:
            logger.error(f"Detection error during Ultralytics inference: {e}")

        return detections
