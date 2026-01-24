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
    def __init__(self, click_hold_ms: int, min_move_px: int = 5) -> None:
        self.controller = Controller()
        self.click_hold_ms = click_hold_ms
        self.min_move_px = min_move_px
        self._click_active = False
        self._click_started = 0.0
        self._use_ydotool = platform.system() == "Linux"
        self._last_target = (0, 0)

    def _move_cursor_ydotool(self, x: int, y: int) -> None:
        """Move cursor using ydotool (Wayland-compatible on Linux)."""
        try:
            result = subprocess.run(
                ['ydotool', 'mousemove', '--absolute', '-x', str(x), '-y', str(y)],
                check=False,
                capture_output=True,
                timeout=0.1,
            )

            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='ignore').strip()
                stdout = result.stdout.decode('utf-8', errors='ignore').strip()
                print(f"[Pointer] ydotool returned {result.returncode}. stdout='{stdout}' stderr='{stderr}'. Falling back to pynput")
                self.controller.position = (x, y)
                return
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
        
        # Only move if we're beyond the jitter threshold
        if delta_to_target[0] > self.min_move_px or delta_to_target[1] > self.min_move_px:
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
