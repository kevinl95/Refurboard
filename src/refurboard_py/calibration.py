"""Calibration workflow with a multi-monitor aware overlay."""
from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from threading import Event, Lock
from typing import List, Sequence, Tuple
import time

import cv2
import numpy as np
import tkinter as tk
from screeninfo import get_monitors
from pynput.mouse import Controller as MouseController
from pynput import keyboard

from .camera import CameraStream
from .config import AppConfig, CalibrationPoint, CalibrationProfile, save_config
from .detection import AdaptiveThreshold, IrBlobDetector

TARGET_OFFSET = 0.035
TARGET_ORDER: Sequence[Tuple[str, Tuple[float, float]]] = (
    ("top_left", (TARGET_OFFSET, TARGET_OFFSET)),
    ("top_right", (1 - TARGET_OFFSET, TARGET_OFFSET)),
    ("bottom_right", (1 - TARGET_OFFSET, 1 - TARGET_OFFSET)),
    ("bottom_left", (TARGET_OFFSET, 1 - TARGET_OFFSET)),
)
_OVERLAY_REGISTRY: set["CalibrationOverlay"] = set()
_OVERLAY_LOCK = Lock()


@dataclass
class CalibrationResult:
    profile: CalibrationProfile


class CalibrationError(Exception):
    """Raised when the user cancels the calibration session."""


@dataclass
class ScreenBounds:
    width: int
    height: int
    origin: Tuple[int, int]


class CalibrationOverlay:
    def __init__(self, bounds: ScreenBounds) -> None:
        self.bounds = bounds
        self._cancelled = False
        self._keyboard_listener: keyboard.Listener | None = None
        parent_conn, child_conn = Pipe()
        self._conn = parent_conn
        self._process = Process(target=_overlay_process, args=(bounds, child_conn), daemon=True)
        self._process.start()
        with _OVERLAY_LOCK:
            _OVERLAY_REGISTRY.add(self)
        try:
            self._keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
            self._keyboard_listener.start()
        except Exception:
            self._keyboard_listener = None

    def set_target(self, local_target: Tuple[int, int], label: str, progress: int) -> None:
        self._send({
            "type": "target",
            "local_target": local_target,
            "label": label,
            "progress": progress,
        })

    def poll_cancelled(self) -> bool:
        if self._cancelled:
            return True
        try:
            while self._conn.poll():
                message = self._conn.recv()
                if message == "cancelled" or (isinstance(message, dict) and message.get("type") == "cancelled"):
                    self._cancelled = True
        except (EOFError, OSError):
            self._cancelled = True
        return self._cancelled

    def close(self) -> None:
        self._send({"type": "close"})
        if self._process.is_alive():
            self._process.join(timeout=2)
        if self._process.is_alive():
            self._process.terminate()
        try:
            self._conn.close()
        except OSError:
            pass
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        with _OVERLAY_LOCK:
            _OVERLAY_REGISTRY.discard(self)

    def _send(self, payload: dict) -> None:
        try:
            self._conn.send(payload)
        except (BrokenPipeError, EOFError, OSError):
            pass

    def _on_key_press(self, key) -> None:
        if key == keyboard.Key.esc:
            self._cancelled = True
            self._send({"type": "cancel"})
            return False


def close_all_overlays() -> None:
    with _OVERLAY_LOCK:
        overlays = list(_OVERLAY_REGISTRY)
    for overlay in overlays:
        overlay.close()


def _overlay_process(bounds: ScreenBounds, conn: Connection) -> None:
    root = tk.Tk()
    root.overrideredirect(True)
    root.configure(bg="#050505")
    root.geometry(f"{bounds.width}x{bounds.height}+{bounds.origin[0]}+{bounds.origin[1]}")
    root.attributes("-topmost", True)
    canvas = tk.Canvas(
        root,
        width=bounds.width,
        height=bounds.height,
        highlightthickness=0,
        bg="#050505",
    )
    canvas.pack(fill="both", expand=True)

    try:
        root.grab_set()
    except tk.TclError:
        pass

    cancelled = False

    def _send_cancel() -> None:
        nonlocal cancelled
        if cancelled:
            return
        cancelled = True
        try:
            conn.send("cancelled")
        except (BrokenPipeError, EOFError, OSError):
            pass

    def _on_escape(_event=None):
        _send_cancel()
        try:
            root.quit()
        except tk.TclError:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass

    root.protocol("WM_DELETE_WINDOW", _on_escape)
    root.bind("<Escape>", _on_escape)
    root.bind("<KeyPress-Escape>", _on_escape)
    root.bind_all("<Escape>", _on_escape)
    root.bind_all("<KeyPress-Escape>", _on_escape)
    canvas.bind("<Escape>", _on_escape)
    canvas.bind("<KeyPress-Escape>", _on_escape)
    root.focus_force()
    canvas.focus_set()

    def _draw_target(local_target: Tuple[int, int], label: str, progress: int) -> None:
        canvas.delete("all")
        base = min(bounds.width, bounds.height)
        radius = max(20, int(base * 0.05))
        header_size = max(18, min(48, int(bounds.height * 0.095)))
        body_size = max(14, min(32, int(bounds.height * 0.06)))
        header_y = int(bounds.height * 0.2)
        footer_y = bounds.height - int(bounds.height * 0.15)
        canvas.create_oval(
            local_target[0] - radius,
            local_target[1] - radius,
            local_target[0] + radius,
            local_target[1] + radius,
            fill="#1E90FF",
            outline="",
        )
        header = f"Aim IR pen at {label.replace('_', ' ').title()} ({progress}/4)"
        canvas.create_text(
            bounds.width / 2,
            header_y,
            text=header,
            fill="#FFFFFF",
            font=("Helvetica", header_size, "bold"),
            justify="center",
            width=int(bounds.width * 0.9),
        )
        canvas.create_text(
            bounds.width / 2,
            footer_y,
            text="Hold steady until the marker locks. Press ESC to cancel.",
            fill="#D2D2D2",
            font=("Helvetica", body_size),
            justify="center",
            width=int(bounds.width * 0.9),
        )

    def _pump_pipe() -> None:
        if cancelled:
            return
        try:
            while conn.poll():
                message = conn.recv()
                if not isinstance(message, dict):
                    continue
                kind = message.get("type")
                if kind == "target":
                    _draw_target(message["local_target"], message["label"], message["progress"])
                elif kind == "close":
                    try:
                        root.quit()
                    except tk.TclError:
                        pass
                    try:
                        root.destroy()
                    except tk.TclError:
                        pass
                    return
                elif kind == "cancel":
                    _on_escape()
                    return
        except (EOFError, OSError):
            try:
                root.quit()
            except tk.TclError:
                pass
            try:
                root.destroy()
            except tk.TclError:
                pass
            return
        root.after(16, _pump_pipe)

    root.after(0, _pump_pipe)
    try:
        root.mainloop()
    finally:
        try:
            conn.close()
        except OSError:
            pass


def _pointer_position() -> Tuple[int, int]:
    controller = MouseController()
    x, y = controller.position
    return int(x), int(y)


def _screen_bounds() -> ScreenBounds:
    pointer_x, pointer_y = _pointer_position()
    try:
        monitors = get_monitors()
    except Exception:
        monitors = []
    chosen = monitors[0] if monitors else None
    for monitor in monitors:
        if monitor.x <= pointer_x < monitor.x + monitor.width and monitor.y <= pointer_y < monitor.y + monitor.height:
            chosen = monitor
            break
    if chosen is None:
        root = tk.Tk()
        root.withdraw()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        return ScreenBounds(width=width, height=height, origin=(0, 0))
    return ScreenBounds(width=chosen.width, height=chosen.height, origin=(chosen.x, chosen.y))


def run_calibration(
    camera: CameraStream,
    detector: IrBlobDetector,
    threshold: AdaptiveThreshold,
    config: AppConfig,
    dwell_frames: int = 7,
    abort_event: Event | None = None,
) -> CalibrationResult:
    bounds = _screen_bounds()
    overlay = CalibrationOverlay(bounds)
    if abort_event and abort_event.is_set():
        overlay.close()
        raise CalibrationError("Calibration aborted by user")

    camera_points: List[Tuple[float, float]] = []
    screen_points: List[Tuple[float, float]] = []
    calibration_points: List[CalibrationPoint] = []

    try:
        for index, (name, normalized) in enumerate(TARGET_ORDER, start=1):
            if abort_event and abort_event.is_set():
                raise CalibrationError("Calibration aborted by user")
            threshold.reset()
            local_target = (
                int(normalized[0] * bounds.width),
                int(normalized[1] * bounds.height),
            )
            screen_target = (
                local_target[0] + bounds.origin[0],
                local_target[1] + bounds.origin[1],
            )
            overlay.set_target(local_target, name, index)
            collected = _collect_point(
                camera,
                detector,
                threshold,
                overlay,
                dwell_frames,
                abort_event,
                camera_points,
            )
            if collected is None:
                raise CalibrationError("Calibration aborted by user")
            camera_points.append(collected)
            screen_points.append(screen_target)
            calibration_points.append(
                CalibrationPoint(
                    name=name,
                    camera_px=collected,
                    screen_px=screen_target,
                    normalized_screen=normalized,
                )
            )
    finally:
        overlay.close()

    homography = cv2.getPerspectiveTransform(
        np.array(camera_points, dtype=np.float32),
        np.array(screen_points, dtype=np.float32),
    )
    errors = []
    for cam, screen in zip(camera_points, screen_points):
        vec = np.array([[cam[0]], [cam[1]], [1.0]], dtype=np.float32)
        projected = homography @ vec
        projected /= projected[2]
        px = (projected[0][0], projected[1][0])
        errors.append(float(np.linalg.norm(np.array(px) - np.array(screen), ord=2)))
    reprojection_error = float(np.mean(errors)) if errors else None

    profile = CalibrationProfile(
        screen_size=(bounds.width, bounds.height),
        screen_origin=bounds.origin,
        reprojection_error=reprojection_error,
        points=calibration_points,
    )
    config.calibration = profile
    save_config(config)
    print(f"[Calibration] Saved config with {len(profile.points)} points:")
    for i, pt in enumerate(profile.points):
        print(f"  Point {i}: camera={pt.camera_px}, screen={pt.screen_px}")
    return CalibrationResult(profile=profile)


def _collect_point(
    camera: CameraStream,
    detector: IrBlobDetector,
    threshold: AdaptiveThreshold,
    overlay: CalibrationOverlay,
    dwell_frames: int,
    abort_event: Event | None = None,
    existing_points: Sequence[Tuple[float, float]] | None = None,
) -> Tuple[float, float] | None:
    dwell = 0
    last_hit: Tuple[float, float] | None = None
    last_log_time = time.time()
    while True:
        if overlay.poll_cancelled() or (abort_event and abort_event.is_set()):
            return None
        frame = camera.latest_frame()
        if frame is None:
            continue
        blobs = detector.find_blobs(frame)
        if not blobs:
            dwell = 0
            continue
        if existing_points:
            blobs = [blob for blob in blobs if not _too_close(blob.center, existing_points)]
        if not blobs:
            dwell = 0
            continue
        best = blobs[0]
        if threshold.evaluate(best.intensity):
            dwell += 1
            last_hit = best.center
        else:
            dwell = max(0, dwell - 1)
        
        # Log progress every 2 seconds
        now = time.time()
        if now - last_log_time > 2.0:
            print(f"[Calibration] Dwell: {dwell}/{dwell_frames}, Blob count: {len(detector.find_blobs(frame))}, Filtered: {len(blobs)}, Intensity: {best.intensity:.1f}")
            last_log_time = now
        
        if dwell >= dwell_frames and last_hit is not None:
            print(f"[Calibration] Point locked at {last_hit}")
            return last_hit


def _too_close(candidate: Tuple[float, float], existing: Sequence[Tuple[float, float]], min_distance: float = 40.0) -> bool:
    cx, cy = candidate
    for px, py in existing:
        if ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5 < min_distance:
            return True
    return False
