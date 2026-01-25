"""Mouse control helpers with platform-aware backends."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Tuple
import time
import platform
import subprocess
import ctypes

# Windows structures/constants for SendInput; safe to import on non-Windows.
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("_input",)
    _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUTUNION)]


INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000

from pynput.mouse import Button, Controller

from .config import CalibrationProfile

try:  # Optional on non-macOS platforms
    import Quartz  # type: ignore
except Exception:  # pragma: no cover - handled at runtime
    Quartz = None


@dataclass
class PointerSample:
    normalized: Tuple[float, float]
    screen: Tuple[int, int]


class _PointerBackend(Protocol):
    def move(self, x: int, y: int) -> None: ...

    def press(self, x: int, y: int) -> None: ...

    def release(self, x: int, y: int) -> None: ...


class _PynputBackend:
    def __init__(self) -> None:
        self._controller = Controller()

    def move(self, x: int, y: int) -> None:
        self._controller.position = (x, y)

    def press(self, x: int, y: int) -> None:
        self._controller.position = (x, y)
        self._controller.press(Button.left)

    def release(self, x: int, y: int) -> None:
        self._controller.position = (x, y)
        self._controller.release(Button.left)


class _LinuxBackend(_PynputBackend):
    def __init__(self) -> None:
        super().__init__()

    def move(self, x: int, y: int) -> None:
        """Move cursor using ydotool when available (Wayland-friendly)."""
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
                super().move(x, y)
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"[Pointer] ydotool failed: {e}, falling back to pynput")
            super().move(x, y)


class _MacBackend:
    def __init__(self) -> None:
        if Quartz is None:
            raise ImportError("Quartz (pyobjc-framework-Quartz) not available")
        self._Quartz = Quartz
        self._mouse_button = Quartz.kCGMouseButtonLeft
        self._event_tap = Quartz.kCGHIDEventTap
        self._move_event = Quartz.kCGEventMouseMoved
        self._down_event = Quartz.kCGEventLeftMouseDown
        self._up_event = Quartz.kCGEventLeftMouseUp

    def _post(self, event_type, x: int, y: int) -> None:
        event = self._Quartz.CGEventCreateMouseEvent(
            None,
            event_type,
            (float(x), float(y)),
            self._mouse_button,
        )
        self._Quartz.CGEventPost(self._event_tap, event)

    def move(self, x: int, y: int) -> None:
        self._post(self._move_event, x, y)

    def press(self, x: int, y: int) -> None:
        self._post(self._down_event, x, y)

    def release(self, x: int, y: int) -> None:
        self._post(self._up_event, x, y)


class _WindowsBackend:
    def __init__(self) -> None:
        if not hasattr(ctypes, "windll"):
            raise ImportError("ctypes.windll not available")
        self._user32 = ctypes.windll.user32
        self._extra = ctypes.c_ulong(0)
        self._update_metrics()

    def _update_metrics(self) -> None:
        width = self._user32.GetSystemMetrics(0) - 1
        height = self._user32.GetSystemMetrics(1) - 1
        self._width = max(1, width)
        self._height = max(1, height)

    def _normalize(self, x: int, y: int) -> tuple[int, int]:
        self._update_metrics()
        nx = int(x * 65535 / self._width)
        ny = int(y * 65535 / self._height)
        return (max(0, min(65535, nx)), max(0, min(65535, ny)))

    def _send(self, flags: int, x: int, y: int) -> None:
        nx, ny = self._normalize(x, y)
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi = MOUSEINPUT(nx, ny, 0, flags, 0, ctypes.pointer(self._extra))
        sent = self._user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if sent != 1:
            raise OSError("SendInput failed")

    def move(self, x: int, y: int) -> None:
        self._send(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, x, y)

    def press(self, x: int, y: int) -> None:
        self._send(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN, x, y)

    def release(self, x: int, y: int) -> None:
        self._send(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP, x, y)


class PointerDriver:
    def __init__(self, click_hold_ms: int, min_move_px: int = 5) -> None:
        self.click_hold_ms = click_hold_ms
        self.min_move_px = min_move_px
        self._click_active = False
        self._click_started = 0.0
        self._last_target: Optional[Tuple[int, int]] = None
        self._deadzone_skips = 0
        self._backend = self._select_backend()

    def _select_backend(self) -> _PointerBackend:
        system = platform.system()
        if system == "Darwin":
            try:
                print("[Pointer] Using macOS Quartz backend")
                return _MacBackend()
            except Exception as exc:
                print(f"[Pointer] Quartz backend unavailable: {exc}. Falling back to pynput")
                return _PynputBackend()
        if system == "Linux":
            print("[Pointer] Using Linux ydotool backend with pynput fallback")
            return _LinuxBackend()
        if system == "Windows":
            try:
                print("[Pointer] Using Windows SendInput backend")
                return _WindowsBackend()
            except Exception as exc:
                print(f"[Pointer] Windows backend unavailable: {exc}. Falling back to pynput")
                return _PynputBackend()
        print("[Pointer] Using default pynput backend")
        return _PynputBackend()

    def move(self, normalized: Tuple[float, float], calibration: CalibrationProfile) -> None:
        width, height = calibration.screen_size
        origin_x, origin_y = getattr(calibration, "screen_origin", (0, 0))
        x = int(normalized[0] * width) + origin_x
        y = int(normalized[1] * height) + origin_y

        if self._last_target is None:
            delta_to_target = (None, None)
            print(f"[Pointer] Target: ({x}, {y}), Last: None (first move)")
            try:
                self._backend.move(x, y)
            except Exception as exc:
                print(f"[Pointer] Backend move failed: {exc}. Falling back to pynput")
                self._backend = _PynputBackend()
                self._backend.move(x, y)
            self._last_target = (x, y)
            self._deadzone_skips = 0
            return

        dx = x - self._last_target[0]
        dy = y - self._last_target[1]
        delta_to_target = (abs(dx), abs(dy))
        print(f"[Pointer] Target: ({x}, {y}), Last: {self._last_target}, Delta: {delta_to_target}")

        # Use radial distance to decide whether to move so small diagonals are not overly suppressed.
        distance_sq = dx * dx + dy * dy
        if distance_sq > self.min_move_px * self.min_move_px:
            try:
                self._backend.move(x, y)
            except Exception as exc:
                print(f"[Pointer] Backend move failed: {exc}. Falling back to pynput")
                self._backend = _PynputBackend()
                self._backend.move(x, y)
            self._last_target = (x, y)
            self._deadzone_skips = 0
            print(f"[Pointer] Moved cursor to ({x}, {y})")
        else:
            # Allow an occasional move even inside the deadzone to avoid lock-in during jitter.
            if delta_to_target[0] > 0 or delta_to_target[1] > 0:
                self._deadzone_skips += 1
                if self._deadzone_skips >= 2:
                    try:
                        self._backend.move(x, y)
                    except Exception as exc:
                        print(f"[Pointer] Backend move failed inside deadzone: {exc}. Falling back to pynput")
                        self._backend = _PynputBackend()
                        self._backend.move(x, y)
                    self._last_target = (x, y)
                    self._deadzone_skips = 0
                    print(f"[Pointer] Moved cursor to ({x}, {y}) after deadzone skips")
                    return
            print(f"[Pointer] Skipped move - delta within {self.min_move_px}px threshold (skips={self._deadzone_skips})")

    def update_click(self, pressed: bool) -> None:
        now = time.time()
        target_x, target_y = self._last_target or (0, 0)
        if pressed and not self._click_active:
            try:
                self._backend.press(target_x, target_y)
            except Exception as exc:
                print(f"[Pointer] Backend press failed: {exc}. Falling back to pynput")
                self._backend = _PynputBackend()
                self._backend.press(target_x, target_y)
            self._click_active = True
            self._click_started = now
        elif not pressed and self._click_active:
            self._backend.release(target_x, target_y)
            self._click_active = False
        elif self._click_active and ((now - self._click_started) * 1000) >= self.click_hold_ms:
            self._backend.release(target_x, target_y)
            self._click_active = False
