"""Mouse control helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import time

from pynput.mouse import Button, Controller

from .config import CalibrationProfile


@dataclass
class PointerSample:
    normalized: Tuple[float, float]
    screen: Tuple[int, int]


class PointerDriver:
    def __init__(self, click_hold_ms: int) -> None:
        self.controller = Controller()
        self.click_hold_ms = click_hold_ms
        self._click_active = False
        self._click_started = 0.0

    def move(self, normalized: Tuple[float, float], calibration: CalibrationProfile) -> None:
        width, height = calibration.screen_size
        origin_x, origin_y = getattr(calibration, "screen_origin", (0, 0))
        x = int(normalized[0] * width) + origin_x
        y = int(normalized[1] * height) + origin_y
        self.controller.position = (x, y)

    def update_click(self, pressed: bool) -> None:
        now = time.time()
        if pressed and not self._click_active:
            self.controller.press(Button.left)
            self._click_active = True
            self._click_started = now
        elif not pressed and self._click_active:
            self.controller.release(Button.left)
            self._click_active = False
        elif self._click_active and ((now - self._click_started) * 1000) >= self.click_hold_ms:
            # Safety: release and re-press if we overstayed.
            self.controller.release(Button.left)
            self._click_active = False
