"""Calibration workflow for mirrored display mode.

Refurboard operates in mirrored mode, where your projector displays the same content
as your primary display. This simplifies cursor control on Wayland/GNOME since all
coordinates stay within the primary display's bounds.

To use: Mirror your projector with your primary display in GNOME Settings → Displays.
"""
from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from threading import Event, Lock
from typing import List, Optional, Sequence, Tuple, TYPE_CHECKING
import os
import time

import cv2
import numpy as np
# NOTE: tkinter is imported lazily inside _overlay_process() to avoid issues
# with macOS multiprocessing (Cocoa framework conflicts when forking/spawning
# after GUI toolkit initialization in the main process).
from screeninfo import get_monitors
from pynput.mouse import Controller as MouseController
from pynput import keyboard

from .camera import CameraStream
from .config import AppConfig, CalibrationPoint, CalibrationProfile, save_config
from .detection import AdaptiveThreshold, IrBlobDetector


def _get_gnome_display_resolution() -> Optional[Tuple[int, int]]:
    """Get actual display resolution from GNOME Mutter via DBus.
    
    In mirrored mode, screeninfo lies and reports scaled/virtual resolutions.
    GNOME's DBus API tells us the real current mode.
    
    Strategy: Find the current mode for an external (non-builtin) display,
    since in mirrored mode that's the resolution both screens share.
    If no external display, use the primary/builtin display's current mode.
    """
    try:
        import subprocess
        result = subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Mutter.DisplayConfig",
                "--object-path", "/org/gnome/Mutter/DisplayConfig",
                "--method", "org.gnome.Mutter.DisplayConfig.GetCurrentState"
            ],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode != 0:
            print(f"[Calibration] GNOME DBus failed with code {result.returncode}: {result.stderr[:100]}")
            return None
        
        output = result.stdout
        import re
        
        # Split by monitor blocks - each starts with (('ConnectorName', 
        # Look for blocks with 'is-builtin': <false> that have a current mode
        # External displays (projectors) aren't builtin
        
        # Find external display's current mode
        # Pattern: is-current followed eventually by is-builtin: false
        # Actually, let's look for the DP-* connector's current mode
        
        # Find all connectors and their current modes
        # Format: (('DP-3', ...), [('1920x1080@60.000', 1920, 1080, ..., {'is-current': <true>})...], {'is-builtin': <false>...})
        
        # Simpler: find resolutions marked current, prefer the one that appears
        # with an external connector (DP-*, HDMI-*)
        
        # Pattern to find connector block with its modes and builtin status
        # Look for mode with is-current in a block where is-builtin is false
        external_pattern = r"\('(DP-\d+|HDMI-\d+)',.*?\('(\d+)x(\d+)@[\d.]+',.*?'is-current': <true>"
        ext_match = re.search(external_pattern, output, re.DOTALL)
        if ext_match:
            width, height = int(ext_match.group(2)), int(ext_match.group(3))
            print(f"[Calibration] GNOME DBus found external display: {width}x{height}")
            return (width, height)
        
        # Fallback: find any current mode
        pattern = r"\('(\d+)x(\d+)@[\d.]+',.*?\{'is-current': <true>\}"
        matches = re.findall(pattern, output)
        if matches:
            # If multiple, prefer smaller (more likely to be actual mirrored mode)
            resolutions = [(int(w), int(h)) for w, h in matches]
            resolutions.sort(key=lambda r: r[0] * r[1])
            print(f"[Calibration] GNOME DBus found displays: {resolutions}")
            return resolutions[0]
        print(f"[Calibration] GNOME DBus: no current mode found in output")
    except Exception as e:
        print(f"[Calibration] GNOME DBus exception: {e}")
    return None


@dataclass
class CollectedPointData:
    """Data collected for a single calibration point."""
    camera_px: Tuple[float, float]
    intensity: float
    area: float


def check_display_setup() -> Tuple[bool, str]:
    """Check if display setup is suitable for Refurboard (mirrored mode).
    
    Returns:
        (is_ok, message): True if setup looks good, message explaining status.
    """
    try:
        monitors = get_monitors()
    except Exception:
        return True, "Could not detect monitors"
    
    if len(monitors) <= 1:
        return True, "Single display detected - ready to use"
    
    # Check for mirrored displays (multiple monitors at same position)
    positions = set()
    mirrored_groups = []
    for m in monitors:
        pos = (m.x, m.y)
        if pos in positions:
            mirrored_groups.append(pos)
        positions.add(pos)
    
    if mirrored_groups:
        return True, f"Mirrored display detected at {mirrored_groups[0]} - ready to use"
    
    # Extended displays - warn user
    primary = None
    externals = []
    for m in monitors:
        name = str(getattr(m, "name", "")).lower()
        if m.x == 0 and m.y == 0:
            primary = m
        if not any(tag in name for tag in ("edp", "lvds", "dsi")):
            externals.append(m)
    
    if externals and primary:
        ext_names = [getattr(m, "name", "unknown") for m in externals]
        primary_name = getattr(primary, "name", "unknown")
        return False, (
            f"Extended display mode detected. "
            f"For best results, mirror your projector with {primary_name}.\n"
            f"External displays: {', '.join(ext_names)}"
        )
    
    return True, "Display setup OK"

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
    monitor_name: str | None = None
    monitor_index: int | None = None


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
    # Import tkinter here (not at module level) to avoid macOS Cocoa/fork issues.
    # On macOS, importing GUI toolkits before spawning subprocesses can cause crashes.
    import platform
    
    # On macOS, hide this subprocess from the Dock before importing tkinter.
    # This prevents the "phantom second app" in the Dock.
    if platform.system() == "Darwin":
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except ImportError:
            # AppKit not available - Dock icon will appear but app still works
            pass
    
    import tkinter as tk
    
    root = tk.Tk()
    root.overrideredirect(True)
    root.configure(bg="#050505")
    # Force position to (0,0) for mirrored mode - Wayland may ignore this
    geom = f"{bounds.width}x{bounds.height}+0+0"
    root.geometry(geom)
    root.attributes("-topmost", True)
    
    # On macOS, lift the window and focus it to ensure it appears
    if platform.system() == "Darwin":
        root.lift()
        root.focus_force()
    
    # Try to force the position again after the window is mapped
    def _force_position():
        root.geometry(geom)
        root.update_idletasks()
        if platform.system() == "Darwin":
            root.lift()
    root.after(50, _force_position)
    root.after(100, _force_position)
    
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
        # Small target - just needs to be visible
        radius = max(12, int(base * 0.02))
        # Modest font sizes that fit on screen
        header_size = max(14, min(28, int(bounds.height * 0.028)))
        body_size = max(10, min(18, int(bounds.height * 0.018)))
        header_y = int(bounds.height * 0.08)
        footer_y = bounds.height - int(bounds.height * 0.06)
        
        # Simple crosshair
        line_len = radius + 8
        canvas.create_line(
            local_target[0] - line_len, local_target[1],
            local_target[0] + line_len, local_target[1],
            fill="#1E90FF", width=2
        )
        canvas.create_line(
            local_target[0], local_target[1] - line_len,
            local_target[0], local_target[1] + line_len,
            fill="#1E90FF", width=2
        )
        # Small filled circle
        canvas.create_oval(
            local_target[0] - radius,
            local_target[1] - radius,
            local_target[0] + radius,
            local_target[1] + radius,
            fill="#1E90FF",
            outline="",
        )
        
        header = f"Point {progress}/4: {label.replace('_', ' ').title()}"
        canvas.create_text(
            bounds.width / 2,
            header_y,
            text=header,
            fill="#FFFFFF",
            font=("Helvetica", header_size, "bold"),
        )
        canvas.create_text(
            bounds.width / 2,
            footer_y,
            text="Aim at target, hold steady. ESC to cancel.",
            fill="#AAAAAA",
            font=("Helvetica", body_size),
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


def get_primary_display() -> ScreenBounds:
    """Get the display to use for mirrored mode calibration.
    
    In mirrored mode, screeninfo reports incorrect (scaled) resolutions.
    We query GNOME's DBus API for the actual current mode.
    """
    # First, try to get the real resolution from GNOME
    real_res = _get_gnome_display_resolution()
    if real_res:
        width, height = real_res
        print(f"[Calibration] GNOME reports actual resolution: {width}x{height}")
        return ScreenBounds(
            width=width,
            height=height,
            origin=(0, 0),
            monitor_name="primary",
            monitor_index=0,
        )
    
    # Fallback to screeninfo
    try:
        monitors = get_monitors()
    except Exception:
        monitors = []
    
    if not monitors:
        # Fallback to Tk - import here to avoid macOS multiprocessing issues
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        print("[Calibration] No monitors detected; using Tk fallback")
        return ScreenBounds(width=width, height=height, origin=(0, 0), monitor_name="primary", monitor_index=0)
    
    # Find all monitors at origin (0,0) - these are mirrored
    mirrored = [(idx, m) for idx, m in enumerate(monitors) if m.x == 0 and m.y == 0]

    if not mirrored:
        # No monitor at origin, force fallback to (0,0) 1920x1080 and warn
        print("[Calibration] WARNING: No mirrored display at (0,0) detected. Forcing 1920x1080 at (0,0) named 'mirrored'.")
        return ScreenBounds(width=1920, height=1080, origin=(0, 0), monitor_name="mirrored", monitor_index=0)

    # Use the smallest mirrored display (visible on all mirrored screens)
    smallest_idx, smallest = min(mirrored, key=lambda x: x[1].width * x[1].height)
    print(f"[Calibration] Using mirrored display at (0,0): '{getattr(smallest, 'name', 'mirrored')}' {smallest.width}x{smallest.height}")
    return ScreenBounds(
        width=smallest.width,
        height=smallest.height,
        origin=(0, 0),
        monitor_name="mirrored",
        monitor_index=0,
    )


def _screen_bounds() -> ScreenBounds:
    """Get screen bounds for calibration - always uses primary display for mirrored mode."""
    return get_primary_display()


def run_calibration(
    camera: CameraStream,
    detector: IrBlobDetector,
    threshold: AdaptiveThreshold,
    config: AppConfig,
    dwell_frames: int = 7,
    abort_event: Event | None = None,
) -> CalibrationResult:
    bounds = _screen_bounds()
    print(f"[Calibration] Using monitor '{bounds.monitor_name}' at origin {bounds.origin}, size {bounds.width}x{bounds.height}")
    overlay = CalibrationOverlay(bounds)
    if abort_event and abort_event.is_set():
        overlay.close()
        raise CalibrationError("Calibration aborted by user")

    camera_points: List[Tuple[float, float]] = []
    screen_points: List[Tuple[float, float]] = []
    calibration_points: List[CalibrationPoint] = []
    collected_data: List[CollectedPointData] = []
    # Require bright pen LED (intensity ~70-100), not ambient IR reflections (~3)
    min_intensity = getattr(config.detection, "min_intensity", 4.0)

    try:
        for index, (name, normalized) in enumerate(TARGET_ORDER, start=1):
            if abort_event and abort_event.is_set():
                raise CalibrationError("Calibration aborted by user")
            threshold.reset()
            # In mirrored mode, screen targets are relative to (0,0) on primary display
            local_target = (
                int(normalized[0] * bounds.width),
                int(normalized[1] * bounds.height),
            )
            # Store screen_target as local coords (same as local_target for mirrored mode)
            screen_target = local_target
            overlay.set_target(local_target, name, index)
            collected = _collect_point(
                camera,
                detector,
                threshold,
                overlay,
                dwell_frames,
                abort_event,
                camera_points,
                min_intensity,
                index,  # point_number for progressive distance relaxation
            )
            if collected is None:
                raise CalibrationError("Calibration aborted by user")
            camera_points.append(collected.camera_px)
            screen_points.append(screen_target)
            collected_data.append(collected)
            calibration_points.append(
                CalibrationPoint(
                    name=name,
                    camera_px=collected.camera_px,
                    screen_px=screen_target,
                    normalized_screen=normalized,
                    intensity=collected.intensity,
                    area=collected.area,
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

    # Compute learned thresholds from calibration blob statistics (mean ± 2*stddev)
    intensities = [d.intensity for d in collected_data]
    areas = [d.area for d in collected_data]
    
    int_mean = float(np.mean(intensities))
    int_std = float(np.std(intensities)) if len(intensities) > 1 else int_mean * 0.3
    area_mean = float(np.mean(areas))
    area_std = float(np.std(areas)) if len(areas) > 1 else area_mean * 0.5
    
    # Use mean ± 2*stddev with generous floor/ceiling
    learned_intensity_min = max(1.0, int_mean - 2.5 * int_std)
    learned_intensity_max = int_mean + 3.0 * int_std
    learned_area_min = max(3.0, area_mean - 2.5 * area_std)
    learned_area_max = area_mean + 3.0 * area_std

    # Detect camera orientation from first calibration point position
    # First point is top-left of screen - check where it appears in camera frame
    camera_orientation = _detect_orientation(camera_points, camera.width, camera.height)
    print(f"[Calibration] Detected camera orientation: {camera_orientation}° (0=normal, 90=CW, 180=upside-down, 270=CCW)")

    # In mirrored mode, always use origin (0,0) - cursor coords are relative to primary display
    profile = CalibrationProfile(
        screen_size=(bounds.width, bounds.height),
        screen_origin=(0, 0),  # Mirrored mode: always (0,0)
        monitor_name=bounds.monitor_name,
        monitor_index=bounds.monitor_index,
        reprojection_error=reprojection_error,
        points=calibration_points,
        learned_intensity_min=learned_intensity_min,
        learned_intensity_max=learned_intensity_max,
        learned_area_min=learned_area_min,
        learned_area_max=learned_area_max,
        camera_orientation=camera_orientation,
    )
    config.calibration = profile
    save_config(config)
    print(f"[Calibration] Mirrored mode: primary display {bounds.width}x{bounds.height}, cursor coords relative to (0,0)")
    print(f"[Calibration] Saved config with {len(profile.points)} points:")
    for i, pt in enumerate(profile.points):
        print(f"  Point {i}: camera={pt.camera_px}, screen={pt.screen_px}, intensity={pt.intensity:.1f}, area={pt.area:.1f}")
    print(f"[Calibration] Learned thresholds: intensity=[{learned_intensity_min:.1f}, {learned_intensity_max:.1f}], area=[{learned_area_min:.1f}, {learned_area_max:.1f}]")
    return CalibrationResult(profile=profile)


def _collect_point(
    camera: CameraStream,
    detector: IrBlobDetector,
    threshold: AdaptiveThreshold,
    overlay: CalibrationOverlay,
    dwell_frames: int,
    abort_event: Event | None = None,
    existing_points: Sequence[Tuple[float, float]] | None = None,
    min_intensity: float = 0.0,
    point_number: int = 1,
) -> CollectedPointData | None:
    dwell = 0
    last_hit: Tuple[float, float] | None = None
    last_log_time = time.time()
    settle_radius_sq = 6.0 * 6.0
    # Track intensity/area samples during dwell for averaging
    intensity_samples: List[float] = []
    area_samples: List[float] = []
    
    # Consistent parameters for all points - no special treatment needed
    min_distance = 40.0
    effective_min_intensity = min_intensity
    
    while True:
        if overlay.poll_cancelled() or (abort_event and abort_event.is_set()):
            return None
        frame = camera.latest_frame()
        if frame is None:
            continue
        blobs = detector.find_blobs(frame)
        if not blobs:
            dwell = 0
            intensity_samples.clear()
            area_samples.clear()
            continue
        if effective_min_intensity > 0:
            blobs = [blob for blob in blobs if blob.intensity >= effective_min_intensity]
        if not blobs:
            dwell = 0
            intensity_samples.clear()
            area_samples.clear()
            continue
        if existing_points:
            blobs = [blob for blob in blobs if not _too_close(blob.center, existing_points, min_distance)]
        if not blobs:
            dwell = 0
            intensity_samples.clear()
            area_samples.clear()
            continue
        best = blobs[0]
        if last_hit is None:
            dwell = 1
            last_hit = best.center
            intensity_samples = [best.intensity]
            area_samples = [best.area]
        else:
            dx = best.center[0] - last_hit[0]
            dy = best.center[1] - last_hit[1]
            if (dx * dx + dy * dy) <= settle_radius_sq:
                dwell += 1
                intensity_samples.append(best.intensity)
                area_samples.append(best.area)
                # Nudge toward the new point so we don't drift away from the user's aim.
                last_hit = (last_hit[0] + dx * 0.5, last_hit[1] + dy * 0.5)
            else:
                dwell = 1
                last_hit = best.center
                intensity_samples = [best.intensity]
                area_samples = [best.area]
        
        # Log progress every 2 seconds
        now = time.time()
        if now - last_log_time > 2.0:
            print(f"[Calibration] Point {point_number}: Dwell: {dwell}/{dwell_frames}, Blob count: {len(detector.find_blobs(frame))}, Filtered: {len(blobs)}, Intensity: {best.intensity:.1f}, Area: {best.area:.1f}")
            last_log_time = now
        
        if dwell >= dwell_frames and last_hit is not None:
            avg_intensity = float(np.mean(intensity_samples)) if intensity_samples else best.intensity
            avg_area = float(np.mean(area_samples)) if area_samples else best.area
            print(f"[Calibration] Point {point_number} locked at {last_hit}, intensity={avg_intensity:.1f}, area={avg_area:.1f}")
            return CollectedPointData(
                camera_px=last_hit,
                intensity=avg_intensity,
                area=avg_area,
            )


def _too_close(candidate: Tuple[float, float], existing: Sequence[Tuple[float, float]], min_distance: float = 40.0) -> bool:
    cx, cy = candidate
    for px, py in existing:
        if ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5 < min_distance:
            return True
    return False


def _detect_orientation(camera_points: List[Tuple[float, float]], frame_width: int, frame_height: int) -> int:
    """
    Detect camera rotation from calibration points.
    
    The first calibration point is always the screen's top-left corner.
    By checking where this point appears in the camera frame, we can
    determine if the camera is rotated.
    
    Returns: 0, 90, 180, or 270 degrees clockwise rotation
    """
    if not camera_points:
        return 0
    
    # Get first point (top-left of screen) and compute its quadrant in camera frame
    tl_x, tl_y = camera_points[0]
    cx, cy = frame_width / 2, frame_height / 2
    
    # Normalize to -1 to 1 relative to center
    nx = (tl_x - cx) / cx if cx > 0 else 0
    ny = (tl_y - cy) / cy if cy > 0 else 0
    
    # Determine which quadrant the "top-left" point is in
    # Normal orientation: top-left should be in upper-left quadrant (nx<0, ny<0)
    # 90° CW rotation: top-left appears in upper-right (nx>0, ny<0)  
    # 180° rotation: top-left appears in lower-right (nx>0, ny>0)
    # 270° CW rotation: top-left appears in lower-left (nx<0, ny>0)
    
    if nx < 0 and ny < 0:
        return 0    # Normal - top-left is in camera's upper-left
    elif nx > 0 and ny < 0:
        return 90   # Camera rotated 90° CW - top-left is in camera's upper-right
    elif nx > 0 and ny > 0:
        return 180  # Camera upside down - top-left is in camera's lower-right
    else:  # nx < 0 and ny > 0
        return 270  # Camera rotated 270° CW (90° CCW) - top-left is in camera's lower-left
