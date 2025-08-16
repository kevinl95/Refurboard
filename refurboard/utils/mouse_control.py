"""
Cross-platform mouse control utilities
"""

try:
    from pynput import mouse
    MOUSE_CONTROL_AVAILABLE = True
except ImportError:
    print("Warning: pynput not available. Mouse control will be disabled.")
    print("Install pynput for mouse control functionality: pip install pynput")
    MOUSE_CONTROL_AVAILABLE = False


def move_mouse(x, y):
    """Cross-platform mouse movement using pynput"""
    if not MOUSE_CONTROL_AVAILABLE:
        print(f"Mouse would move to: ({x:.0f}, {y:.0f})")
        return
    
    try:
        mouse_controller = mouse.Controller()
        mouse_controller.position = (x, y)
    except Exception as e:
        print(f"Failed to move mouse: {e}")


def is_mouse_control_available():
    """Check if mouse control is available"""
    return MOUSE_CONTROL_AVAILABLE
