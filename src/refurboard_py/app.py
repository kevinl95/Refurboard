"""Main entry point for the Refurboard Python application."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import threading
import time

import cv2
import numpy as np

from .camera import CameraStream, CameraDescriptor, enumerate_devices
from .calibration import CalibrationError, close_all_overlays, run_calibration, check_display_setup
from .config import AppConfig, load_config, save_config
from .detection import AdaptiveThreshold, BlobTracker, IrBlobDetector, OneEuroFilter, QuadFilter, Smoother
from .pointer import PointerDriver
from . import ui


@dataclass
class Telemetry:
    pointer: Tuple[float, float] | None = None
    blob_intensity: float = 0.0
    click_active: bool = False
    calibration_error: float | None = None


class RefurboardApp:
    def __init__(self) -> None:
        self.config: AppConfig = load_config()
        self.detector = IrBlobDetector(
            min_area=self.config.detection.min_blob_area,
            max_area=self.config.detection.max_blob_area,
        )
        self.click_threshold = AdaptiveThreshold(
            sensitivity=self.config.detection.sensitivity,
            hysteresis=self.config.detection.hysteresis,
        )
        # One-Euro Filter for smooth, low-latency drawing
        self.smoother = OneEuroFilter(
            min_cutoff=getattr(self.config.detection, "filter_min_cutoff", 1.0),
            beta=getattr(self.config.detection, "filter_beta", 0.007),
        )
        self.pointer_driver = PointerDriver(
            click_hold_ms=self.config.detection.click_hold_ms,
            min_move_px=self.config.detection.min_move_px,
        )
        
        # Tracking filters (initialized after calibration loaded)
        self.quad_filter: QuadFilter | None = None
        self.blob_tracker = BlobTracker(persistence_frames=3, association_radius=20.0)

        self.camera_stream: CameraStream | None = None
        self.camera_lock = threading.Lock()
        self.homography: Optional[np.ndarray] = None
        self.telemetry = Telemetry(calibration_error=self._calibration_error())
        self.telemetry_lock = threading.Lock()

        self._tracking_thread: threading.Thread | None = None
        self._running = threading.Event()
        self._calibration_thread: threading.Thread | None = None
        self._calibration_abort = threading.Event()
        self._calibrating = threading.Event()
        self._pointer_resume_time = 0.0

        self.devices: list[CameraDescriptor] = enumerate_devices()
        self.camera_failed = not self._start_camera()
        self._rebuild_homography()
        self._rebuild_filters()
        
        # Check display setup for mirrored mode
        display_ok, display_msg = check_display_setup()
        if display_ok:
            print(f"[Refurboard] {display_msg}")
        else:
            print(f"[Refurboard] WARNING: {display_msg}")
        
        # Startup validation
        if self.config.calibration is None:
            print("[Refurboard] No calibration data found. Please run calibration.")
        elif len(self.config.calibration.points) < 4:
            print(f"[Refurboard] Incomplete calibration: {len(self.config.calibration.points)}/4 points.")
        elif self.homography is None:
            print("[Refurboard] Warning: Calibration exists but homography is None.")
        else:
            print(f"[Refurboard] Loaded calibration with {len(self.config.calibration.points)} points, RMS error: {self.config.calibration.reprojection_error:.4f}px")
            if self.config.calibration.monitor_name is not None:
                print(f"[Refurboard] Calibration monitor: {self.config.calibration.monitor_name} (index {self.config.calibration.monitor_index})")
            if self.config.calibration.learned_intensity_min is not None:
                print(f"[Refurboard] Learned thresholds: intensity=[{self.config.calibration.learned_intensity_min:.1f}, {self.config.calibration.learned_intensity_max:.1f}], area=[{self.config.calibration.learned_area_min:.1f}, {self.config.calibration.learned_area_max:.1f}]")
        
        self._start_tracking_loop()

    def _calibration_error(self) -> float | None:
        if self.config.calibration:
            return self.config.calibration.reprojection_error
        return None

    def _start_camera(self) -> bool:
        camera_cfg = self.config.camera
        new_stream = CameraStream(
            camera_cfg.device_id,
            camera_cfg.frame_width,
            camera_cfg.frame_height,
            camera_cfg.fps,
            camera_cfg.mirror,
        )
        started = new_stream.start()
        with self.camera_lock:
            if self.camera_stream:
                self.camera_stream.stop()
            self.camera_stream = new_stream if started else None
        if not started:
            print(f"[Refurboard] Unable to open camera {camera_cfg.device_id}. Check connections and permissions.")
        return started

    def _start_tracking_loop(self) -> None:
        if self._tracking_thread:
            return
        self._running.set()
        self._tracking_thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self._tracking_thread.start()

    def shutdown(self) -> None:
        self._running.clear()
        self._calibration_abort.set()
        if self._tracking_thread:
            self._tracking_thread.join(timeout=2)
            self._tracking_thread = None
        if self._calibration_thread:
            self._calibration_thread.join(timeout=4)
            self._calibration_thread = None
        with self.camera_lock:
            if self.camera_stream:
                self.camera_stream.stop()
                self.camera_stream = None
        close_all_overlays()

    def _tracking_loop(self) -> None:
        last_debug_time = 0.0
        while self._running.is_set():
            with self.camera_lock:
                stream = self.camera_stream
            if stream is None:
                time.sleep(0.05)
                continue
            frame = stream.latest_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            now = time.monotonic()
            pointer_blocked = self._calibrating.is_set() or now < self._pointer_resume_time
            
            # === BLOB DETECTION PIPELINE ===
            blobs = self.detector.find_blobs(frame)
            raw_count = len(blobs)
            
            # Step 1: Filter by camera-space quad (reject blobs outside calibrated region)
            if blobs and self.quad_filter:
                blobs = self.quad_filter.filter_blobs(blobs)
            in_quad_count = len(blobs)
            
            # Step 2: Intensity threshold - use config value (3.5 by default)
            # This filters ambient IR noise (~2-3) from pen LED (~5+ at angle, ~70+ direct)
            min_int = getattr(self.config.detection, "min_intensity", 3.5)
            if blobs and min_int > 0:
                blobs = [b for b in blobs if b.intensity >= min_int]
            above_threshold_count = len(blobs)
            
            # Note: Stationary source filtering removed - intensity threshold (min_intensity=10)
            # already separates pen (intensity 50-100) from background noise (intensity ~3)
            moving_blobs = blobs
            
            # === POINTER MOVEMENT ===
            click_active = False
            normalized: Tuple[float, float] | None = None
            intensity = 0.0
            
            if moving_blobs:
                # Take brightest blob as the pen
                best = max(moving_blobs, key=lambda b: b.intensity)
                intensity = best.intensity
                cam_x, cam_y = best.center
                
                # Log tracking (reduced frequency - only when moving significantly)
                projected = self._project(best.center)
                if projected and self.config.calibration:
                    origin_x, origin_y = self.config.calibration.screen_origin
                    scr_w, scr_h = self.config.calibration.screen_size
                    expected_scr_x = int(origin_x + projected[0] * scr_w)
                    expected_scr_y = int(origin_y + projected[1] * scr_h)
                    print(f"[Track] ({expected_scr_x}, {expected_scr_y}) Int={intensity:.0f}")
                
                if projected:
                    # smoother.update() returns None during reacquisition (after reset)
                    # This prevents cursor jumping to reflections when pen reappears
                    smoothed = self.smoother.update(projected)
                    if smoothed is not None:
                        normalized = smoothed
                        # Only click when we have stable tracking (not during reacquisition)
                        click_active = True
                        if self.config.calibration and not pointer_blocked:
                            self.pointer_driver.move(normalized, self.config.calibration)
                    else:
                        # Reacquisition in progress - don't move or click yet
                        print(f"[Track] Reacquiring... Int={intensity:.0f}")
            elif blobs:
                # We have blobs but they're all stationary - don't reset, just hold position
                # This prevents jumping when the pen stops moving momentarily
                pass
            else:
                # No valid blobs at all - reset position
                self.smoother.reset()
                self.pointer_driver.reset_position()
            
            if pointer_blocked:
                self.pointer_driver.update_click(False)
            else:
                self.pointer_driver.update_click(click_active)
            self._update_telemetry(normalized, intensity, click_active)
            
            # Debug telemetry every 2 seconds - show what's happening at each stage
            if now - last_debug_time > 2.0:
                blocked_reason = "calibrating" if self._calibrating.is_set() else "cooldown" if now < self._pointer_resume_time else "none"
                
                # Get fresh blob data for detailed diagnostics
                raw_blobs = self.detector.find_blobs(frame)
                in_quad = [b for b in raw_blobs if self.quad_filter and self.quad_filter.contains(b.center)]
                
                if in_quad:
                    # Sort by intensity and show top blob
                    sorted_blobs = sorted(in_quad, key=lambda b: b.intensity, reverse=True)[:5]
                    top_blob = sorted_blobs[0]
                    cam_x, cam_y = top_blob.center
                    
                    # Show what's happening
                    tracking_count = len(moving_blobs) if moving_blobs else 0
                    status = f"TRACKING ({tracking_count})" if tracking_count > 0 else f"FILTERED (int {top_blob.intensity:.0f} < {min_int})"
                    print(f"[Tracking] InQuad: {len(in_quad)}, Above {min_int:.0f}: {above_threshold_count}, "
                          f"TopBlob: ({cam_x:.0f},{cam_y:.0f}) int={top_blob.intensity:.0f}, "
                          f"Status: {status}, Blocked: {blocked_reason}")
                else:
                    print(f"[Tracking] No blobs in calibrated region, Blocked: {blocked_reason}")
                
                last_debug_time = now
            
            time.sleep(0.01)

    def _update_telemetry(self, pointer: Tuple[float, float] | None, intensity: float, click: bool) -> None:
        with self.telemetry_lock:
            self.telemetry.pointer = pointer
            self.telemetry.blob_intensity = intensity
            self.telemetry.click_active = click
            self.telemetry.calibration_error = self._calibration_error()

    def _project(self, camera_point: Tuple[float, float]) -> Tuple[float, float] | None:
        """Project camera coordinates to normalized screen coordinates (0-1).
        
        In mirrored mode, the homography maps camera coords → local screen coords
        (relative to 0,0 on primary display), then we normalize to 0-1.
        """
        if self.homography is None or not self.config.calibration:
            return None
        vec = np.array([[camera_point[0]], [camera_point[1]], [1.0]], dtype=np.float32)
        projected = self.homography @ vec
        projected /= projected[2]
        # Homography outputs local coords (relative to 0,0), normalize to 0-1
        x = projected[0][0] / self.config.calibration.screen_size[0]
        y = projected[1][0] / self.config.calibration.screen_size[1]
        adjusted = self._apply_field_correction(float(x), float(y))
        return adjusted

    def _apply_field_correction(self, x: float, y: float) -> Tuple[float, float]:
        # FoV/corner gain disabled: return unclamped normalized coords.
        return (float(np.clip(x, 0.0, 1.0)), float(np.clip(y, 0.0, 1.0)))

    def _rebuild_homography(self) -> None:
        if not self.config.calibration or len(self.config.calibration.points) < 4:
            self.homography = None
            return
        source = np.array([point.camera_px for point in self.config.calibration.points], dtype=np.float32)
        dest = np.array([point.screen_px for point in self.config.calibration.points], dtype=np.float32)
        self.homography = cv2.getPerspectiveTransform(source, dest)

    def _rebuild_filters(self) -> None:
        """Rebuild QuadFilter from calibration data."""
        if not self.config.calibration:
            self.quad_filter = None
            return
        quad = self.config.calibration.camera_quad()
        if quad:
            self.quad_filter = QuadFilter(quad)
            print(f"[Refurboard] QuadFilter initialized with camera quad: {quad}")
        else:
            self.quad_filter = None
        # Reset trackers when calibration changes
        self.blob_tracker.reset()

    # UI hooks -----------------------------------------------------------------
    def get_devices(self) -> list[CameraDescriptor]:
        self.devices = enumerate_devices()
        return self.devices

    def select_camera(self, device_id: int) -> bool:
        self.config.camera.device_id = device_id
        save_config(self.config)
        success = self._start_camera()
        self.camera_failed = not success
        return success

    def update_sensitivity(self, value: float) -> None:
        self.config.detection.sensitivity = value
        save_config(self.config)
        self.click_threshold = AdaptiveThreshold(
            sensitivity=self.config.detection.sensitivity,
            hysteresis=self.config.detection.hysteresis,
        )

    def update_hysteresis(self, value: float) -> None:
        self.config.detection.hysteresis = value
        save_config(self.config)
        self.click_threshold = AdaptiveThreshold(
            sensitivity=self.config.detection.sensitivity,
            hysteresis=self.config.detection.hysteresis,
        )

    def update_fov_scale(self, value: float) -> None:
        self.config.detection.fov_scale = value
        save_config(self.config)

    def update_corner_gain(self, corner: str, value: float) -> None:
        if corner not in ("top_left", "top_right", "bottom_right", "bottom_left"):
            return
        self.config.detection.corner_gain[corner] = value
        save_config(self.config)

    def get_status(self) -> Dict[str, object]:
        with self.telemetry_lock:
            pointer = self.telemetry.pointer
            intensity = self.telemetry.blob_intensity
            click = self.telemetry.click_active
            error = self.telemetry.calibration_error
        return {
            "pointer": pointer,
            "blob_intensity": intensity,
            "click_active": click,
            "calibration_error": error,
            "calibrated": self.homography is not None,
        }

    def run_calibration(self) -> None:
        if self._calibration_thread and self._calibration_thread.is_alive():
            return
        self._calibration_thread = threading.Thread(target=self._calibrate, daemon=True)
        self._calibration_thread.start()

    def _calibrate(self) -> None:
        with self.camera_lock:
            stream = self.camera_stream
        if stream is None:
            print("[Refurboard] Cannot start calibration: no camera stream. Select a camera first.")
            self._calibration_thread = None
            return
        self._calibrating.set()
        self._calibration_abort.clear()
        try:
            result = run_calibration(
                stream,
                self.detector,
                AdaptiveThreshold(
                    sensitivity=self.config.detection.sensitivity,
                    hysteresis=self.config.detection.hysteresis,
                ),
                self.config,
                abort_event=self._calibration_abort,
            )
            self._after_calibration(result.profile)
        except CalibrationError:
            # User cancelled; nothing to do.
            pass
        finally:
            self.pointer_driver.update_click(False)
            self._pointer_resume_time = time.monotonic() + 1.5
            self._calibrating.clear()
            self._calibration_abort.clear()
            self._calibration_thread = None
            print(f"[Refurboard] Calibration complete. Pointer control resumes in 1.5s.")

    def _after_calibration(self, profile) -> None:
        # Config already updated/saved inside run_calibration; rebuild homography + telemetry.
        print(f"[Refurboard] Updating calibration: {len(profile.points)} points, RMS: {profile.reprojection_error:.4f}px")
        # Reload config from disk to ensure we have the freshest data
        from .config import load_config
        self.config = load_config()
        print(f"[Refurboard] Reloaded config from disk. Calibration points: {len(self.config.calibration.points) if self.config.calibration else 0}")
        print(f"[Refurboard] Config reprojection_error after reload: {self.config.calibration.reprojection_error if self.config.calibration else 'None'}")
        self._rebuild_homography()
        self._rebuild_filters()
        with self.telemetry_lock:
            self.telemetry.calibration_error = profile.reprojection_error
            print(f"[Refurboard] Telemetry calibration_error set to: {self.telemetry.calibration_error}")
        print(f"[Refurboard] Homography rebuilt. Matrix shape: {self.homography.shape if self.homography is not None else 'None'}")


def main() -> None:
    app = RefurboardApp()
    try:
        ui.launch(app)
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
