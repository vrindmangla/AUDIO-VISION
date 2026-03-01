"""
AUDIOVISION - Object detection module.
Refactored from Vision_Assist detector with clean class-based API.
Uses YOLO (ultralytics) for object detection with direction and confidence.
"""

import cv2
from typing import List, Tuple, Optional

# Optional YOLO - graceful fallback if not installed
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    YOLO = None


class ObjectDetector:
    """
    Detects objects in video frames and annotates with bounding boxes,
    labels, confidence, and directional hint (left / right / center).
    """

    def __init__(self, model_path: str = "yolov8n.pt", confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold
        self.model = None
        if YOLO_AVAILABLE and YOLO is not None:
            try:
                self.model = YOLO(model_path)
            except Exception:
                self.model = None

    def detect(self, frame) -> Tuple[object, List[dict]]:
        """
        Run detection on a single frame.
        Returns: (annotated_frame, list of {label, confidence, direction})
        """
        if self.model is None:
            return frame, []

        try:
            results = self.model(frame, imgsz=416, verbose=False)
        except Exception:
            return frame, []

        h, w = frame.shape[:2]
        detected: List[dict] = []

        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf < self.confidence_threshold:
                    continue
                cls_id = int(box.cls[0])
                label = self.model.names[cls_id]
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cx = (x1 + x2) // 2
                if cx < w * 0.33:
                    direction = "left"
                elif cx > w * 0.66:
                    direction = "right"
                else:
                    direction = "center"

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    frame,
                    f"{label} {conf:.2f}",
                    (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )
                detected.append({
                    "label": label,
                    "confidence": round(conf, 2),
                    "direction": direction,
                })

        return frame, detected

    def set_confidence_threshold(self, value: float) -> None:
        """Update confidence threshold (0.0 - 1.0)."""
        self.confidence_threshold = max(0.0, min(1.0, value))

    @property
    def is_ready(self) -> bool:
        """Whether the detector model is loaded and ready."""
        return self.model is not None
