"""
AUDIOVISION - FastAPI backend.
Serves frontend, WebSocket for detections/control, and MJPEG video feed.
"""

import asyncio
import json
import os
import threading
from pathlib import Path
from typing import Optional
from queue import Queue

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse

from camera_loop import Camera, run_detection_loop
from detector import ObjectDetector
from tts import TTS

# ---------------------------------------------------------------------------
# Config (env)
# ---------------------------------------------------------------------------
CAMERA_DEVICE = int(os.environ.get("AUDIOVISION_CAMERA", "0"))
MODEL_PATH = os.environ.get("AUDIOVISION_MODEL", "yolov8n.pt")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# ---------------------------------------------------------------------------
# App and shared state
# ---------------------------------------------------------------------------
app = FastAPI(title="AUDIOVISION", version="1.0.0")

latest_jpeg: Optional[bytes] = None
latest_jpeg_lock = threading.Lock()
detection_thread: Optional[threading.Thread] = None
stop_event = threading.Event()
ws_clients: list = []
ws_queue: Queue = Queue()
camera: Optional[Camera] = None
detector: Optional[ObjectDetector] = None
tts: Optional[TTS] = None
_broadcaster_task: Optional[asyncio.Task] = None


async def _broadcaster():
    """Single task that drains ws_queue and sends to all connected clients."""
    while True:
        try:
            data = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ws_queue.get(timeout=0.5)
            )
            msg = json.dumps(data)
            for ws in ws_clients[:]:
                try:
                    await ws.send_text(msg)
                except Exception:
                    pass
        except Exception:
            pass


def on_frame(jpeg_bytes: bytes) -> None:
    global latest_jpeg
    with latest_jpeg_lock:
        latest_jpeg = jpeg_bytes


def on_detections(objects: list) -> None:
    if not ws_clients:
        return
    data = {"type": "detections", "objects": objects}
    ws_queue.put_nowait(data)


def run_detection_thread(sensitivity: float = 0.5) -> None:
    global camera, detector, tts, stop_event, detection_thread
    stop_event.clear()
    camera = Camera(device=CAMERA_DEVICE)
    if not camera.open():
        return
    detector = ObjectDetector(model_path=MODEL_PATH)
    tts = TTS()
    detection_thread = threading.Thread(
        target=run_detection_loop,
        kwargs={
            "camera": camera,
            "detector": detector,
            "tts": tts,
            "on_frame": on_frame,
            "on_detections": on_detections,
            "stop_event": stop_event,
            "sensitivity": sensitivity,
        },
        daemon=True,
    )
    detection_thread.start()


def stop_detection() -> None:
    global stop_event, camera, tts, detection_thread, latest_jpeg
    stop_event.set()
    if detection_thread is not None and detection_thread.is_alive():
        detection_thread.join(timeout=3.0)
    if tts is not None:
        tts.stop_worker()
    if camera is not None:
        camera.release()
    detection_thread = None
    with latest_jpeg_lock:
        latest_jpeg = None


# ---------------------------------------------------------------------------
# Static files (frontend)
# ---------------------------------------------------------------------------
def _frontend_path(name: str) -> Path:
    return FRONTEND_DIR / name


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve frontend."""
    index_file = _frontend_path("index.html")
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>AUDIOVISION</h1><p>Place index.html in frontend/.</p>")


@app.get("/style.css")
async def style_css():
    p = _frontend_path("style.css")
    if p.exists():
        return FileResponse(p, media_type="text/css")
    from fastapi.responses import Response
    return Response(status_code=404)


@app.get("/script.js")
async def script_js():
    p = _frontend_path("script.js")
    if p.exists():
        return FileResponse(p, media_type="application/javascript")
    from fastapi.responses import Response
    return Response(status_code=404)


@app.get("/video-feed")
async def video_feed(request: Request):
    """Stream MJPEG video (annotated frames when detection is running)."""
    boundary = "frame"
    async def generate():
        while True:
            with latest_jpeg_lock:
                jpeg = latest_jpeg
            if jpeg:
                yield (
                    b"--" + boundary.encode() + b"\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                    + jpeg + b"\r\n"
                )
            await asyncio.sleep(0.033)
    return StreamingResponse(
        generate(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}",
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global _broadcaster_task
    await websocket.accept()
    ws_clients.append(websocket)
    if _broadcaster_task is None or _broadcaster_task.done():
        _broadcaster_task = asyncio.create_task(_broadcaster())
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            action = data.get("action")
            if action == "start":
                sensitivity = float(data.get("sensitivity", 0.5))
                voice = data.get("voice", True)
                run_detection_thread(sensitivity=sensitivity)
                if tts:
                    tts.set_enabled(voice)
                await websocket.send_text(json.dumps({"type": "status", "status": "started"}))
            elif action == "stop":
                stop_detection()
                await websocket.send_text(json.dumps({"type": "status", "status": "stopped"}))
            elif action == "voice":
                if tts:
                    tts.set_enabled(bool(data.get("enabled", True)))
            elif action == "sensitivity":
                sens = float(data.get("value", 0.5))
                if detector:
                    detector.set_confidence_threshold(1.0 - sens)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in ws_clients:
            ws_clients.remove(websocket)


@app.on_event("shutdown")
def shutdown():
    stop_detection()


# ---------------------------------------------------------------------------
# Run with: uvicorn app:app --reload --host 0.0.0.0 --port 8000
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
