"""Configuration helpers for Refurboard Python edition."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple
import json
import time

from platformdirs import PlatformDirs

CONFIG_FILENAME = "refurboard.config.json"


@dataclass
class CalibrationPoint:
    name: str
    camera_px: Tuple[float, float]
    screen_px: Tuple[float, float]
    normalized_screen: Tuple[float, float]


@dataclass
class CalibrationProfile:
    screen_size: Tuple[int, int]
    screen_origin: Tuple[int, int] = (0, 0)
    monitor_name: str | None = None
    monitor_index: int | None = None
    completed_at: float | None = None
    reprojection_error: float | None = None
    points: List[CalibrationPoint] = field(default_factory=list)

    def is_complete(self) -> bool:
        return len(self.points) == 4


@dataclass
class CameraSettings:
    device_id: int
    frame_width: int = 1280
    frame_height: int = 720
    fps: int = 30
    mirror: bool = False


@dataclass
class DetectionSettings:
    sensitivity: float = 0.65
    hysteresis: float = 0.15
    smoothing: float = 0.25
    click_hold_ms: int = 120
    min_blob_area: int = 5
    max_blob_area: int = 500
    min_move_px: int = 5


@dataclass
class AppConfig:
    camera: CameraSettings = field(default_factory=lambda: CameraSettings(device_id=0))
    detection: DetectionSettings = field(default_factory=DetectionSettings)
    calibration: CalibrationProfile | None = None


def _config_dir() -> Path:
    dirs = PlatformDirs(appname="Refurboard", appauthor="Refurboard", roaming=True)
    path = Path(dirs.user_data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return _config_dir() / CONFIG_FILENAME


def default_config() -> AppConfig:
    return AppConfig()


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        cfg = default_config()
        save_config(cfg)
        return cfg

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    camera = CameraSettings(**payload.get("camera", {}))
    detection = DetectionSettings(**payload.get("detection", {}))
    calibration_payload = payload.get("calibration")
    calibration = None
    if calibration_payload:
        points = [
            CalibrationPoint(
                name=point["name"],
                camera_px=tuple(point["camera_px"]),
                screen_px=tuple(point["screen_px"]),
                normalized_screen=tuple(point["normalized_screen"]),
            )
            for point in calibration_payload.get("points", [])
        ]
        calibration = CalibrationProfile(
            screen_size=tuple(calibration_payload["screen_size"]),
            screen_origin=tuple(calibration_payload.get("screen_origin", (0, 0))),
            monitor_name=calibration_payload.get("monitor_name"),
            monitor_index=calibration_payload.get("monitor_index"),
            completed_at=calibration_payload.get("completed_at"),
            reprojection_error=calibration_payload.get("reprojection_error"),
            points=points,
        )
    return AppConfig(camera=camera, detection=detection, calibration=calibration)


def save_config(config: AppConfig) -> None:
    payload: Dict[str, object] = {
        "camera": asdict(config.camera),
        "detection": asdict(config.detection),
    }

    if config.calibration:
        payload["calibration"] = {
            "screen_size": list(config.calibration.screen_size),
            "screen_origin": list(config.calibration.screen_origin),
            "monitor_name": config.calibration.monitor_name,
            "monitor_index": config.calibration.monitor_index,
            "completed_at": config.calibration.completed_at or time.time(),
            "reprojection_error": config.calibration.reprojection_error,
            "points": [
                {
                    "name": point.name,
                    "camera_px": list(point.camera_px),
                    "screen_px": list(point.screen_px),
                    "normalized_screen": list(point.normalized_screen),
                }
                for point in config.calibration.points
            ],
        }

    path = config_path()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
