"""
AUDIOVISION - Text-to-Speech module.
Uses pyttsx3 for offline TTS; runs in a background thread to avoid blocking.
"""

import threading
from queue import Queue
from typing import Optional

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    pyttsx3 = None


class TTS:
    """
    Thread-safe TTS: queue phrases and speak them one by one in a worker thread.
    """

    def __init__(self, rate: int = 160):
        self.rate = rate
        self._queue: Queue = Queue()
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._enabled = True

    def speak(self, text: str) -> None:
        """Queue text for speech (non-blocking)."""
        if not self._enabled or not text.strip():
            return
        if not PYTTSX3_AVAILABLE:
            return
        self._queue.put(text.strip())

    def _run_worker(self) -> None:
        while not self._stop.is_set():
            try:
                text = self._queue.get(timeout=0.5)
                if text is None:
                    break
                self._do_speak(text)
            except Exception:
                continue

    def _do_speak(self, text: str) -> None:
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception:
            pass

    def start_worker(self) -> None:
        """Start the background TTS worker thread."""
        if self._worker is not None and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._run_worker, daemon=True)
        self._worker.start()

    def stop_worker(self) -> None:
        """Stop the worker and clear queue."""
        self._stop.set()
        self._queue.put(None)
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                break

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def available(self) -> bool:
        return PYTTSX3_AVAILABLE
