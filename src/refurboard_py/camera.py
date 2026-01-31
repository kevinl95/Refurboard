"""Camera helpers built on OpenCV."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Tuple
import os
import threading
import time

os.environ.setdefault("OPENCV_LOG_LEVEL", "OFF")

import cv2

try:
    log_level = getattr(cv2.utils.logging, "LOG_LEVEL_SILENT", cv2.utils.logging.LOG_LEVEL_FATAL)
    cv2.utils.logging.setLogLevel(log_level)
except AttributeError:
    pass


@dataclass
class CameraDescriptor:
    device_id: int
    label: str
    resolution: Tuple[int, int] | None = None


def enumerate_devices(max_devices: int = 8) -> List[CameraDescriptor]:
    devices: List[CameraDescriptor] = []
    
    # Determine the appropriate backend for the platform
    backend = cv2.CAP_ANY  # Let OpenCV choose
    if _is_macos():
        # Use AVFoundation explicitly on macOS for better compatibility
        # with built-in cameras and virtual cameras (Camo, EpocCam, etc.)
        backend = cv2.CAP_AVFOUNDATION
    
    for device_id in range(max_devices):
        # On Linux, check /dev/video* exists before trying to open
        # On macOS/Windows, just try to open the device directly
        if os.name == "posix" and not _is_macos():
            dev_path = Path(f"/dev/video{device_id}")
            if not dev_path.exists() or not os.access(dev_path, os.R_OK):
                continue
        cap = cv2.VideoCapture(device_id, backend)
        if not cap.isOpened():
            cap.release()
            continue
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        devices.append(CameraDescriptor(device_id=device_id, label=f"Camera {device_id}", resolution=(width, height)))
        cap.release()
    if not devices:
        devices.append(CameraDescriptor(device_id=0, label="Camera 0"))
    return devices


def no_real_cameras_found(devices: List[CameraDescriptor]) -> bool:
    """Check if only the fallback camera was returned (no actual cameras detected).
    
    This is useful for detecting when macOS Camera permission may be missing.
    """
    if len(devices) == 1 and devices[0].device_id == 0 and devices[0].resolution is None:
        return True
    return False


def _is_macos() -> bool:
    """Check if running on macOS."""
    import platform
    return platform.system() == "Darwin"


def _get_camera_backend() -> int:
    """Get the appropriate OpenCV video capture backend for the current platform."""
    if _is_macos():
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_ANY


class CameraStream:
    """Background thread that keeps grabbing frames from OpenCV."""

    def __init__(self, device_id: int, width: int, height: int, fps: int, mirror: bool = False) -> None:
        self.device_id = device_id
        self.width = width
        self.height = height
        self.fps = fps
        self.mirror = mirror

        self._capture: Optional[cv2.VideoCapture] = None
        self._frame_lock = threading.Lock()
        self._frame = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()

    def start(self) -> bool:
        if self._running.is_set():
            return True
        # On Linux, check /dev/video* exists; on macOS/Windows, just try to open
        if os.name == "posix" and not _is_macos():
            dev_path = Path(f"/dev/video{self.device_id}")
            if not dev_path.exists() or not os.access(dev_path, os.R_OK):
                return False
        capture = cv2.VideoCapture(self.device_id, _get_camera_backend())
        if not capture.isOpened():
            capture.release()
            return False
        self._capture = capture
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._capture.set(cv2.CAP_PROP_FPS, self.fps)
        self._running.set()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self._capture:
            self._capture.release()
            self._capture = None

    def _loop(self) -> None:
        assert self._capture is not None
        delay = 1.0 / max(self.fps, 1)
        while self._running.is_set():
            ok, frame = self._capture.read()
            if not ok:
                time.sleep(0.1)
                continue
            if self.mirror:
                frame = cv2.flip(frame, 1)
            with self._frame_lock:
                self._frame = frame
            time.sleep(delay)

    def latest_frame(self):
        with self._frame_lock:
            return None if self._frame is None else self._frame.copy()

    def frames(self) -> Iterator:
        while self._running.is_set():
            frame = self.latest_frame()
            if frame is not None:
                yield frame
            time.sleep(0.01)
