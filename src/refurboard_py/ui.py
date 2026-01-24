"""Dear PyGui front-end for the Refurboard controller."""
from __future__ import annotations

from pathlib import Path
from typing import List, TYPE_CHECKING

import numpy as np
import dearpygui.dearpygui as dpg

from .config import CalibrationPoint

if TYPE_CHECKING:
    from .app import RefurboardApp

MAIN_WINDOW = "refurboard_main_window"
CONTENT_WINDOW = "refurboard_content"
STATUS_TEXT = "refurboard_status"
ACCURACY_TEXT = "refurboard_accuracy"
QUAD_CANVAS = "refurboard_quad_canvas"
CAMERA_COMBO = "refurboard_camera_combo"
SENSITIVITY_SLIDER = "refurboard_sensitivity"
HYSTERESIS_SLIDER = "refurboard_hysteresis"
FOV_SLIDER = "refurboard_fov"
GAIN_TL = "refurboard_gain_tl"
GAIN_TR = "refurboard_gain_tr"
GAIN_BR = "refurboard_gain_br"
GAIN_BL = "refurboard_gain_bl"

VIEWPORT_WIDTH = 560
VIEWPORT_HEIGHT = 1024
CONTROL_WIDTH = 420
SIDE_PADDING = int((VIEWPORT_WIDTH - CONTROL_WIDTH) / 2)
CANVAS_WIDTH = CONTROL_WIDTH
CANVAS_HEIGHT = 280
CANVAS_MARGIN = 14
FONT_SCALE = 2.0
ERROR_MODAL = "refurboard_error_modal"


def launch(app: RefurboardApp) -> None:
    dpg.create_context()
    dpg.set_global_font_scale(FONT_SCALE)

    dpg.create_viewport(title="Refurboard", width=VIEWPORT_WIDTH, height=VIEWPORT_HEIGHT)
    
    # Set window icon
    logo_path = Path(__file__).parent.parent.parent / "assets" / "logo.ico"
    if logo_path.exists():
        dpg.set_viewport_small_icon(str(logo_path))
        dpg.set_viewport_large_icon(str(logo_path))
    
    # Create error modal (hidden by default)
    with dpg.window(
        tag=ERROR_MODAL,
        label="Camera Error",
        modal=True,
        show=False,
        no_resize=True,
        width=400,
        height=180,
    ):
        dpg.add_text("Unable to open camera!", color=(255, 100, 100))
        dpg.add_spacer(height=10)
        dpg.add_text("The selected camera could not be opened.", wrap=380)
        dpg.add_text("Please check:", wrap=380)
        dpg.add_text("  • Camera is connected", wrap=380)
        dpg.add_text("  • No other app is using it", wrap=380)
        dpg.add_text("  • Correct camera selected", wrap=380)
        dpg.add_spacer(height=10)
        dpg.add_button(
            label="OK",
            width=380,
            callback=lambda: dpg.configure_item(ERROR_MODAL, show=False),
        )
    
    with dpg.window(
        tag=MAIN_WINDOW,
        label="Refurboard",
        width=VIEWPORT_WIDTH,
        height=VIEWPORT_HEIGHT,
        no_resize=True,
        no_move=True,
        no_title_bar=True,
    ):
        dpg.add_spacer(height=22)
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=SIDE_PADDING)
            with dpg.group(tag=CONTENT_WINDOW):
                _build_controls(app)
            dpg.add_spacer(width=SIDE_PADDING)

    dpg.set_primary_window(MAIN_WINDOW, True)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    
    # Show error modal if camera failed to start
    if app.camera_failed:
        dpg.configure_item(ERROR_MODAL, show=True)
    
    _schedule_refresh(app)
    dpg.start_dearpygui()
    dpg.destroy_context()


def _build_controls(app: RefurboardApp) -> None:
    dpg.add_text("Camera Input", color=(230, 230, 230))
    dpg.add_combo(
        items=_camera_labels(app),
        tag=CAMERA_COMBO,
        width=CONTROL_WIDTH,
        default_value=_camera_label_for(app, app.config.camera.device_id),
        callback=_on_camera_selected,
        user_data=app,
    )
    dpg.add_button(
        label="Refresh Cameras",
        width=CONTROL_WIDTH,
        callback=lambda: _refresh_cameras(app),
    )
    dpg.add_spacer(height=16)

    dpg.add_text("IR Sensitivity", color=(230, 230, 230))
    dpg.add_slider_float(
        tag=SENSITIVITY_SLIDER,
        width=CONTROL_WIDTH,
        min_value=0.2,
        max_value=1.5,
        default_value=app.config.detection.sensitivity,
        callback=_on_sensitivity_changed,
        user_data=app,
    )
    dpg.add_text("Click Smoothing", color=(230, 230, 230))
    dpg.add_slider_float(
        tag=HYSTERESIS_SLIDER,
        width=CONTROL_WIDTH,
        min_value=0.05,
        max_value=0.4,
        default_value=app.config.detection.hysteresis,
        callback=_on_hysteresis_changed,
        user_data=app,
    )
    dpg.add_spacer(height=12)
    dpg.add_text("FoV / Corner Gain", color=(230, 230, 230))
    dpg.add_slider_float(
        tag=FOV_SLIDER,
        width=CONTROL_WIDTH,
        min_value=0.8,
        max_value=1.25,
        default_value=getattr(app.config.detection, "fov_scale", 1.0),
        format="FoV scale: %.3f",
        callback=_on_fov_changed,
        user_data=app,
    )
    with dpg.group(horizontal=True):
        dpg.add_slider_float(
            tag=GAIN_TL,
            label="TL",
            width=int(CONTROL_WIDTH / 2 - 8),
            min_value=0.8,
            max_value=1.25,
            default_value=app.config.detection.corner_gain.get("top_left", 1.0),
            format="%.3f",
            callback=_on_gain_changed,
            user_data=(app, "top_left"),
        )
        dpg.add_slider_float(
            tag=GAIN_TR,
            label="TR",
            width=int(CONTROL_WIDTH / 2 - 8),
            min_value=0.8,
            max_value=1.25,
            default_value=app.config.detection.corner_gain.get("top_right", 1.0),
            format="%.3f",
            callback=_on_gain_changed,
            user_data=(app, "top_right"),
        )
    with dpg.group(horizontal=True):
        dpg.add_slider_float(
            tag=GAIN_BL,
            label="BL",
            width=int(CONTROL_WIDTH / 2 - 8),
            min_value=0.8,
            max_value=1.25,
            default_value=app.config.detection.corner_gain.get("bottom_left", 1.0),
            format="%.3f",
            callback=_on_gain_changed,
            user_data=(app, "bottom_left"),
        )
        dpg.add_slider_float(
            tag=GAIN_BR,
            label="BR",
            width=int(CONTROL_WIDTH / 2 - 8),
            min_value=0.8,
            max_value=1.25,
            default_value=app.config.detection.corner_gain.get("bottom_right", 1.0),
            format="%.3f",
            callback=_on_gain_changed,
            user_data=(app, "bottom_right"),
        )
    dpg.add_spacer(height=20)
    dpg.add_button(
        label="Start Calibration",
        width=CONTROL_WIDTH,
        height=56,
        callback=lambda: app.run_calibration(),
    )
    dpg.add_spacer(height=24)
    dpg.add_text("Calibration Accuracy", color=(230, 230, 230))
    dpg.add_text("Not calibrated", tag=ACCURACY_TEXT, wrap=CONTROL_WIDTH)
    dpg.add_spacer(height=12)
    dpg.add_text("Quadrilateral Preview", color=(230, 230, 230))
    with dpg.drawlist(width=CANVAS_WIDTH, height=CANVAS_HEIGHT, tag=QUAD_CANVAS):
        pass
    dpg.add_spacer(height=24)
    dpg.add_text("Status", color=(230, 230, 230))
    dpg.add_text("Waiting for frames...", tag=STATUS_TEXT, wrap=CONTROL_WIDTH)


def _schedule_refresh(app: "RefurboardApp") -> None:
    def _tick() -> None:
        _refresh_status(app)
    
    # Use a recurring frame callback that schedules itself relative to current frame
    def _recurring_tick() -> None:
        _tick()
        if dpg.is_dearpygui_running():
            # Schedule next tick for 1 frame from now
            dpg.set_frame_callback(dpg.get_frame_count() + 1, _recurring_tick)
    
    _recurring_tick()


def _load_logo_texture():
    root = Path(__file__).resolve().parents[2]
    asset = root / "assets" / "logo.png"
    if not asset.exists():
        return None
    image = Image.open(asset).convert("RGBA")
    width, height = image.size
    data = np.frombuffer(image.tobytes(), dtype=np.uint8) / 255.0
    with dpg.texture_registry():
        return dpg.add_static_texture(width, height, data.tolist())


def _camera_labels(app: RefurboardApp) -> List[str]:
    return [_camera_label(desc) for desc in app.get_devices()]


def _camera_label(desc) -> str:
    if desc.resolution:
        width, height = desc.resolution
        return f"{desc.device_id} · {desc.label} ({width}x{height})"
    return f"{desc.device_id} · {desc.label}"


def _camera_label_for(app: RefurboardApp, device_id: int) -> str:
    for desc in app.devices:
        if desc.device_id == device_id:
            return _camera_label(desc)
    return f"Camera {device_id}"


def _on_camera_selected(sender, app_data, user_data: RefurboardApp | None) -> None:
    if user_data is None:
        return
    label = dpg.get_value(sender)
    if not label:
        return
    try:
        device_id = int(label.split(" · ")[0])
    except (ValueError, IndexError):
        return
    success = user_data.select_camera(device_id)
    if not success:
        dpg.configure_item(ERROR_MODAL, show=True)


def _on_sensitivity_changed(sender, app_data, user_data: RefurboardApp | None) -> None:
    if user_data is None:
        return
    try:
        value = float(app_data)
    except (TypeError, ValueError):
        return
    user_data.update_sensitivity(value)


def _on_hysteresis_changed(sender, app_data, user_data: RefurboardApp | None) -> None:
    if user_data is None:
        return
    try:
        value = float(app_data)
    except (TypeError, ValueError):
        return
    user_data.update_hysteresis(value)


def _on_fov_changed(sender, app_data, user_data: RefurboardApp | None) -> None:
    if user_data is None:
        return
    try:
        value = float(app_data)
    except (TypeError, ValueError):
        return
    user_data.update_fov_scale(value)


def _on_gain_changed(sender, app_data, user_data) -> None:
    if not isinstance(user_data, tuple) or len(user_data) != 2:
        return
    app, corner = user_data
    if app is None:
        return
    try:
        value = float(app_data)
    except (TypeError, ValueError):
        return
    app.update_corner_gain(corner, value)


def _refresh_cameras(app: RefurboardApp) -> None:
    dpg.configure_item(CAMERA_COMBO, items=_camera_labels(app))
    dpg.set_value(CAMERA_COMBO, _camera_label_for(app, app.config.camera.device_id))


def _refresh_status(app: RefurboardApp) -> None:
    status = app.get_status()
    pointer = status.get("pointer")
    pointer_text = f"Pointer: {pointer[0]:.3f}, {pointer[1]:.3f}" if pointer else "Pointer: —"
    blob_text = f"Blob intensity: {status['blob_intensity']:.1f}"
    click_text = "Click: active" if status["click_active"] else "Click: idle"
    dpg.set_value(STATUS_TEXT, f"{pointer_text}\n{blob_text}\n{click_text}")
    error = status.get("calibration_error")
    if error is None:
        dpg.set_value(ACCURACY_TEXT, "Not calibrated")
    else:
        dpg.set_value(ACCURACY_TEXT, f"{error:.2f}px RMS")
    _update_quad_canvas(app)


def _update_quad_canvas(app: RefurboardApp) -> None:
    if not dpg.does_item_exist(QUAD_CANVAS):
        return
    dpg.delete_item(QUAD_CANVAS, children_only=True)
    background = (90, 90, 90, 255)
    dpg.draw_rectangle(
        (CANVAS_MARGIN, CANVAS_MARGIN),
        (CANVAS_WIDTH - CANVAS_MARGIN, CANVAS_HEIGHT - CANVAS_MARGIN),
        color=background,
        thickness=2,
        parent=QUAD_CANVAS,
    )
    calibration = app.config.calibration
    if not calibration or not calibration.points:
        dpg.draw_text(
            (
                CANVAS_WIDTH / 2 - 120,
                CANVAS_HEIGHT / 2 - 18,
            ),
            "Awaiting calibration",
            color=(190, 190, 190, 255),
            size=26,
            parent=QUAD_CANVAS,
        )
        return
    # Get camera frame dimensions to show actual captured distortion
    all_camera_x = [p.camera_px[0] for p in calibration.points]
    all_camera_y = [p.camera_px[1] for p in calibration.points]
    cam_min_x, cam_max_x = min(all_camera_x), max(all_camera_x)
    cam_min_y, cam_max_y = min(all_camera_y), max(all_camera_y)
    cam_width = cam_max_x - cam_min_x
    cam_height = cam_max_y - cam_min_y
    
    if cam_width <= 0 or cam_height <= 0:
        return

    def to_canvas(point: CalibrationPoint) -> tuple[float, float]:
        # Map camera_px to canvas to show actual captured positions
        normalized_x = (point.camera_px[0] - cam_min_x) / cam_width
        normalized_y = (point.camera_px[1] - cam_min_y) / cam_height
        x = CANVAS_MARGIN + normalized_x * (CANVAS_WIDTH - 2 * CANVAS_MARGIN)
        y = CANVAS_MARGIN + normalized_y * (CANVAS_HEIGHT - 2 * CANVAS_MARGIN)
        return float(x), float(y)

    projected = [to_canvas(p) for p in calibration.points]
    if len(projected) >= 4:
        dpg.draw_polyline(
            projected + [projected[0]],
            color=(30, 144, 255, 255),
            thickness=3,
            parent=QUAD_CANVAS,
        )
        for px, py in projected:
            dpg.draw_circle((px, py), 6, fill=(255, 255, 255, 255), color=(0, 0, 0, 0), parent=QUAD_CANVAS)
