"""IR blob detection and adaptive click heuristics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np


@dataclass
class IrBlob:
    center: tuple[float, float]
    area: float
    intensity: float
    confidence: float


class AdaptiveThreshold:
    """Learns background intensity and produces a dynamic trigger level."""

    def __init__(self, sensitivity: float, hysteresis: float) -> None:
        self.sensitivity = sensitivity
        self.hysteresis = hysteresis
        self.baseline = 0.0
        self.state = False

    def evaluate(self, signal: float) -> bool:
        if self.baseline == 0:
            self.baseline = signal
        else:
            self.baseline = (0.98 * self.baseline) + (0.02 * signal)

        high = self.baseline + (self.baseline * self.sensitivity)
        low = high * (1.0 - self.hysteresis)

        if self.state:
            self.state = signal >= low
        else:
            self.state = signal >= high
        return self.state

    def reset(self) -> None:
        self.baseline = 0.0
        self.state = False


class IrBlobDetector:
    def __init__(self, min_area: int, max_area: int) -> None:
        self.min_area = min_area
        self.max_area = max_area

    def find_blobs(self, frame) -> List[IrBlob]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        blobs: List[IrBlob] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if not self.min_area <= area <= self.max_area:
                continue
            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue
            cx = float(moments["m10"] / moments["m00"])
            cy = float(moments["m01"] / moments["m00"])
            mask = np.zeros(gray.shape, dtype="uint8")
            cv2.drawContours(mask, [contour], -1, 255, -1)
            intensity = float(cv2.mean(gray, mask=mask)[0])
            confidence = min(1.0, (intensity / 255.0) * 0.7 + (area / self.max_area) * 0.3)
            blobs.append(IrBlob(center=(cx, cy), area=area, intensity=intensity, confidence=confidence))
        blobs.sort(key=lambda blob: (blob.intensity * 0.7) + (blob.area * 0.3), reverse=True)
        return blobs


class Smoother:
    def __init__(self, factor: float) -> None:
        self.factor = factor
        self._value: Optional[np.ndarray] = None

    def update(self, value: tuple[float, float]) -> tuple[float, float]:
        current = np.array(value, dtype=np.float32)
        if self._value is None:
            self._value = current
        else:
            self._value = (1 - self.factor) * self._value + self.factor * current
        return float(self._value[0]), float(self._value[1])
