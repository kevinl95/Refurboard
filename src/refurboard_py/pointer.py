"""Mouse control helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import time
import platform
import subprocess

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
        self._use_ydotool = platform.system() == "Linux"
        self._last_target = (0, 0)

    def _move_cursor_ydotool(self, x: int, y: int) -> None:
        """Move cursor using ydotool (Wayland-compatible on Linux)."""
        try:
            subprocess.run(['ydotool', 'mousemove', '--absolute', '-x', str(x), '-y', str(y)], 
                         check=False, capture_output=True, timeout=0.1)
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"[Pointer] ydotool failed: {e}, falling back to pynput")
            self.controller.position = (x, y)

    def move(self, normalized: Tuple[float, float], calibration: CalibrationProfile) -> None:
        width, height = calibration.screen_size
        origin_x, origin_y = getattr(calibration, "screen_origin", (0, 0))
        x = int(normalized[0] * width) + origin_x
        y = int(normalized[1] * height) + origin_y
        
        # Calculate delta from last target (not current position, as readback is unreliable)
        delta_to_target = (abs(x - self._last_target[0]), abs(y - self._last_target[1]))
        
        print(f"[Pointer] Target: ({x}, {y}), Last: {self._last_target}, Delta: {delta_to_target}")
        
        # Only move if we're more than 5 pixels away from last target
        if delta_to_target[0] > 5 or delta_to_target[1] > 5:
            if self._use_ydotool:
                self._move_cursor_ydotool(x, y)
                print(f"[Pointer] Moved cursor to ({x}, {y}) via ydotool")
            else:
                self.controller.position = (x, y)
                print(f"[Pointer] Moved cursor to ({x}, {y}) via pynput")
            self._last_target = (x, y)
        else:
            print(f"[Pointer] Skipped move - delta within 5px threshold")

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
