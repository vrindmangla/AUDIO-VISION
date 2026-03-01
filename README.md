# AUDIOVISION

**AI-powered assistive vision — see with sound.**

AUDIOVISION is a production-ready web application that performs real-time object detection from your webcam, shows a live annotated overlay, and converts detection results into speech. Built for accessibility with a modern, minimalistic dark UI and optional high-contrast mode.

---

## Features

- **Real-time object detection** (YOLO) with bounding boxes and labels
- **Text-to-speech** announcements (e.g. “I see a person on your left”)
- **Live video feed** with MJPEG streaming and detection overlay
- **Web UI**: start/stop, voice toggle, sensitivity slider, detection list, log, screenshot, download log (JSON)
- **Keyboard shortcuts**: `S` Start, `E` Stop, `V` Voice, `?` Help
- **Accessibility**: high-contrast mode, ARIA labels, reduced-motion support
- **Modular backend**: FastAPI, WebSockets, thread-safe camera and TTS

---

## Project structure

```
audiovision/
├── backend/
│   ├── app.py          # FastAPI app, WebSocket, video feed, static routes
│   ├── detector.py     # ObjectDetector (YOLO), confidence + direction
│   ├── tts.py           # Text-to-speech (pyttsx3) in background thread
│   ├── camera_loop.py   # Thread-safe camera + detection loop
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── README.md
```

---

## Requirements

- **Python 3.9+**
- **Webcam**
- **YOLO model**: first run will download `yolov8n.pt` via ultralytics (or place your own in the backend directory and set `AUDIOVISION_MODEL`)

---

## Setup

### 1. Create a virtual environment (recommended)

```bash
cd audiovision/backend
python -m venv .venv
```

- **Windows (PowerShell):**  
  `.\.venv\Scripts\Activate.ps1`
- **Windows (cmd):**  
  `.venv\Scripts\activate.bat`
- **macOS/Linux:**  
  `source .venv/bin/activate`

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. (Optional) Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AUDIOVISION_CAMERA` | Camera device index | `0` |
| `AUDIOVISION_MODEL` | YOLO model path or name | `yolov8n.pt` |

Example:

```bash
set AUDIOVISION_CAMERA=0
set AUDIOVISION_MODEL=yolov8n.pt
```

---

## Run locally

From the **backend** directory (with the virtual environment activated):

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

Or:

```bash
python app.py
```

Then open in your browser:

**http://localhost:8000**

- Click **Start detection** to turn on the webcam and object detection.
- Use **Stop detection** to stop the camera and processing.
- Use **Voice** toggle and **Sensitivity** slider as needed.
- **Clear history** and **Download log (JSON)** for the detection list and log.
- **Screenshot** captures the current video frame (when detection is running).

---

## API overview

| Endpoint | Description |
|----------|-------------|
| `GET /` | Serves the frontend (index.html) |
| `GET /style.css` | Frontend styles |
| `GET /script.js` | Frontend script |
| `GET /video-feed` | MJPEG stream of annotated camera frames |
| `WebSocket /ws` | Control and detection events |

### WebSocket messages (client → server)

- `{"action": "start", "sensitivity": 0.5, "voice": true}` — start detection
- `{"action": "stop"}` — stop detection
- `{"action": "voice", "enabled": true}` — toggle TTS
- `{"action": "sensitivity", "value": 0.5}` — set sensitivity (0–1)

### WebSocket messages (server → client)

- `{"type": "status", "status": "started"|"stopped"}`
- `{"type": "detections", "objects": [{"label": "...", "confidence": 0.9, "direction": "left"|"right"|"center"}]}`

---

## Code quality

- **Backend**: Modular classes (`ObjectDetector`, `TTS`, `Camera`), thread-safe camera and TTS queue, clean shutdown on stop and app shutdown.
- **Frontend**: Vanilla JS, clear state and DOM helpers, ARIA and keyboard support.
- **Errors**: Graceful handling for missing camera, missing model, and TTS failures; optional YOLO with fallback if the model is unavailable.

---

## License

Use and modify as needed for your project.
