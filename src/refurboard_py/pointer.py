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
    """Linux backend using ydotool for Wayland cursor control.
    
    Uses RELATIVE movements to avoid mouse acceleration issues with absolute mode.
    ydotool's absolute mode requires disabling mouse acceleration, which we don't
    want to force on users. We track position internally since pynput cannot read
    cursor position on Wayland.
    """
    
    def __init__(self) -> None:
        super().__init__()
        self._has_ydotool = self._check_ydotool()
        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None
        if self._has_ydotool:
            print("[Pointer] Using Linux ydotool backend (relative mode)")
        else:
            print("[Pointer] ydotool not found, falling back to pynput (may not work on Wayland)")

    def _check_ydotool(self) -> bool:
        """Check if ydotool is available."""
        try:
            result = subprocess.run(
                ['which', 'ydotool'],
                capture_output=True,
                timeout=1.0,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def move(self, x: int, y: int) -> None:
        """Move cursor using ydotool RELATIVE positioning.
        
        We use relative mode because absolute mode requires disabling mouse
        acceleration globally, which affects normal mouse use. Position is
        tracked internally since pynput cannot read cursor position on Wayland.
        """
        if not self._has_ydotool:
            super().move(x, y)
            return
        
        # First move - establish cursor at the correct position
        # Since we can't know where cursor currently is on Wayland, we reset to (0,0)
        # by moving a large negative delta, then move to our target position
        if self._last_x is None or self._last_y is None:
            print(f"[Pointer] First detection at ({x}, {y}) - resetting cursor position")
            try:
                # Move far negative to ensure we hit (0,0) regardless of current position
                # Most screens are under 8K resolution, so -10000 should be enough
                subprocess.run(
                    ['ydotool', 'mousemove', '-x', '-10000', '-y', '-10000'],
                    check=False, capture_output=True, timeout=0.1,
                )
                # Small delay to ensure the reset takes effect
                time.sleep(0.01)
                # Now move to the actual target position from (0,0)
                result = subprocess.run(
                    ['ydotool', 'mousemove', '-x', str(x), '-y', str(y)],
                    check=False, capture_output=True, timeout=0.1,
                )
                if result.returncode == 0:
                    self._last_x = x
                    self._last_y = y
                    print(f"[Pointer] Cursor initialized at ({x}, {y})")
                else:
                    print(f"[Pointer] Failed to initialize cursor position")
            except Exception as e:
                print(f"[Pointer] Error initializing cursor: {e}")
            return
        
        # Calculate delta from our tracked position
        dx = x - self._last_x
        dy = y - self._last_y
        
        # Skip tiny movements (jitter suppression)
        if abs(dx) <= 1 and abs(dy) <= 1:
            return
        
        try:
            # Use relative movement (no --absolute flag)
            result = subprocess.run(
                ['ydotool', 'mousemove', '-x', str(dx), '-y', str(dy)],
                check=False,
                capture_output=True,
                timeout=0.1,
            )
            if result.returncode == 0:
                self._last_x = x
                self._last_y = y
            else:
                stderr = result.stderr.decode('utf-8', errors='ignore').strip()
                print(f"[Pointer] ydotool failed: {stderr}")
                # Fallback to pynput
                super().move(x, y)
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"[Pointer] ydotool failed: {e}, using pynput")
            super().move(x, y)

    def press(self, x: int, y: int) -> None:
        """Press at position."""
        self.move(x, y)
        if self._has_ydotool:
            try:
                subprocess.run(
                    ['ydotool', 'click', '0xC0'], # Left button down
                    check=False, capture_output=True, timeout=0.1
                )
            except Exception:
                super().press(x, y)
        else:
            super().press(x, y)

    def release(self, x: int, y: int) -> None:
        """Release at position."""
        self.move(x, y)
        if self._has_ydotool:
            try:
                subprocess.run(
                    ['ydotool', 'click', '0xC1'], # Left button up
                    check=False, capture_output=True, timeout=0.1
                )
            except Exception:
                super().release(x, y)
        else:
            super().release(x, y)


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

    def reset_position(self) -> None:
        """Clear the last known position so the next pen detection starts fresh."""
        self._last_target = None
        self._deadzone_skips = 0

    def move(self, normalized: Tuple[float, float], calibration: CalibrationProfile) -> None:
        """Move cursor to position. In mirrored mode, coords are relative to primary display (0,0)."""
        width, height = calibration.screen_size
        # In mirrored mode, always use origin (0,0) regardless of what's stored
        # This ensures cursor stays within primary display bounds
        x = int(normalized[0] * width)
        y = int(normalized[1] * height)

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
