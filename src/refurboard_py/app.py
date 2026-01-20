"""Main entry point for the Refurboard Python application."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import threading
import time

import cv2
import numpy as np

from .camera import CameraStream, CameraDescriptor, enumerate_devices
from .calibration import CalibrationError, close_all_overlays, run_calibration
from .config import AppConfig, load_config, save_config
from .detection import AdaptiveThreshold, IrBlobDetector, Smoother
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
        self.smoother = Smoother(self.config.detection.smoothing)
        self.pointer_driver = PointerDriver(self.config.detection.click_hold_ms)

        self.camera_stream: CameraStream | None = None
        self.camera_lock = threading.Lock()
        self.homography: Optional[np.ndarray] = None
        self.telemetry = Telemetry(calibration_error=self._calibration_error())
        self.telemetry_lock = threading.Lock()

        self._tracking_thread: threading.Thread | None = None
        self._running = threading.Event()
        self._calibration_thread: threading.Thread | None = None
        self._calibration_abort = threading.Event()

        self.devices: list[CameraDescriptor] = enumerate_devices()
        self._start_camera()
        self._rebuild_homography()
        self._start_tracking_loop()

    def _calibration_error(self) -> float | None:
        if self.config.calibration:
            return self.config.calibration.reprojection_error
        return None

    def _start_camera(self) -> None:
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
            blobs = self.detector.find_blobs(frame)
            click_active = False
            normalized: Tuple[float, float] | None = None
            intensity = 0.0
            if blobs:
                best = blobs[0]
                intensity = best.intensity
                click_active = self.click_threshold.evaluate(best.intensity)
                projected = self._project(best.center)
                if projected:
                    normalized = self.smoother.update(projected)
                    if self.config.calibration:
                        self.pointer_driver.move(normalized, self.config.calibration)
            self.pointer_driver.update_click(click_active)
            self._update_telemetry(normalized, intensity, click_active)
            time.sleep(0.01)

    def _update_telemetry(self, pointer: Tuple[float, float] | None, intensity: float, click: bool) -> None:
        with self.telemetry_lock:
            self.telemetry.pointer = pointer
            self.telemetry.blob_intensity = intensity
            self.telemetry.click_active = click
            self.telemetry.calibration_error = self._calibration_error()

    def _project(self, camera_point: Tuple[float, float]) -> Tuple[float, float] | None:
        if self.homography is None or not self.config.calibration:
            return None
        vec = np.array([[camera_point[0]], [camera_point[1]], [1.0]], dtype=np.float32)
        projected = self.homography @ vec
        projected /= projected[2]
        origin_x, origin_y = getattr(self.config.calibration, "screen_origin", (0, 0))
        x = (projected[0][0] - origin_x) / self.config.calibration.screen_size[0]
        y = (projected[1][0] - origin_y) / self.config.calibration.screen_size[1]
        return (float(np.clip(x, 0.0, 1.0)), float(np.clip(y, 0.0, 1.0)))

    def _rebuild_homography(self) -> None:
        if not self.config.calibration or len(self.config.calibration.points) < 4:
            self.homography = None
            return
        source = np.array([point.camera_px for point in self.config.calibration.points], dtype=np.float32)
        dest = np.array([point.screen_px for point in self.config.calibration.points], dtype=np.float32)
        self.homography = cv2.getPerspectiveTransform(source, dest)

    # UI hooks -----------------------------------------------------------------
    def get_devices(self) -> list[CameraDescriptor]:
        self.devices = enumerate_devices()
        return self.devices

    def select_camera(self, device_id: int) -> None:
        self.config.camera.device_id = device_id
        save_config(self.config)
        self._start_camera()

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
            self._calibration_thread = None
            return
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
            self.homography = cv2.getPerspectiveTransform(
                np.array([point.camera_px for point in result.profile.points], dtype=np.float32),
                np.array([point.screen_px for point in result.profile.points], dtype=np.float32),
            )
        except CalibrationError:
            # User cancelled; nothing to do.
            pass
        finally:
            self._calibration_abort.clear()
            self._calibration_thread = None


def main() -> None:
    app = RefurboardApp()
    try:
        ui.launch(app)
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
