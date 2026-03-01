"""
AUDIOVISION - Thread-safe camera and detection loop.
Single camera instance, lock for frame access, clean shutdown.
"""

import cv2
import threading
import time
from collections import defaultdict
from typing import Optional, Callable, List, Dict, Any

from detector import ObjectDetector
from tts import TTS


class Camera:
    """Thread-safe webcam capture."""

    def __init__(self, device: int = 0):
        self._device = device
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()

    def open(self) -> bool:
        with self._lock:
            if self._cap is not None:
                return self._cap.isOpened()
            self._cap = cv2.VideoCapture(self._device)
            if self._cap.isOpened():
                # Lower resolution to reduce CPU load and latency
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return self._cap is not None and self._cap.isOpened()

    def read_frame(self):
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                return None
            ret, frame = self._cap.read()
            return frame if ret else None

    def release(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None

    def is_opened(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()


# Detection state (stable frames, cooldown, debounce)
STABLE_FRAMES = 6
MISSING_FRAMES_THRESHOLD = 10
SPEECH_COOLDOWN_SEC = 2.5
FRAME_SKIP = 5


def run_detection_loop(
    camera: Camera,
    detector: ObjectDetector,
    tts: TTS,
    on_frame: Callable[[bytes], None],
    on_detections: Callable[[List[Dict[str, Any]]], None],
    stop_event: threading.Event,
    sensitivity: float = 0.5,
) -> None:
    """
    Run detection in a loop; call on_frame(encoded_jpeg_bytes) and
    on_detections([{label, confidence, direction}, ...]) for each processed frame.
    Respects stop_event and uses sensitivity to set detector confidence threshold.
    """
    detector.set_confidence_threshold(1.0 - sensitivity)
    tts.start_worker()

    frame_count: Dict[str, int] = defaultdict(int)
    missing_count: Dict[str, int] = defaultdict(int)
    announced = set()
    last_spoken_time = 0.0
    frame_index = 0

    while not stop_event.is_set():
        frame = camera.read_frame()
        if frame is None:
            time.sleep(0.05)
            continue

        frame_index += 1
        if frame_index % FRAME_SKIP == 0:
            annotated, objects = detector.detect(frame)
        else:
            annotated = frame
            objects = []

        # Encode for streaming (MJPEG) - slightly lower quality for performance
        _, jpeg = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if jpeg is not None:
            on_frame(jpeg.tobytes())

        current_labels = {o["label"] for o in objects}
        direction_by_label = {o["label"]: o["direction"] for o in objects}

        # Confirm stable objects and queue speech
        for obj in objects:
            label = obj["label"]
            frame_count[label] += 1
            missing_count[label] = 0
            if frame_count[label] == STABLE_FRAMES and label not in announced:
                announced.add(label)
                direction = direction_by_label.get(label, "center")
                dir_phrase = {
                    "left": "on your left",
                    "right": "on your right",
                    "center": "in front of you",
                }.get(direction, "in front of you")
                tts.speak(f"I see {label} {dir_phrase}")

        for label in list(frame_count.keys()):
            if label not in current_labels:
                missing_count[label] += 1
                if missing_count[label] >= MISSING_FRAMES_THRESHOLD:
                    frame_count[label] = 0
                    missing_count[label] = 0
                    announced.discard(label)

        # Send current detections to frontend
        on_detections(objects)
        time.sleep(0.03)
