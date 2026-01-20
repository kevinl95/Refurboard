# Refurboard (Python Edition)

![Refurboard logo](assets/logo.png)

Refurboard is a classroom-ready IR whiteboard controller that turns any USB webcam (or phone acting as a webcam through commercial apps such as **EpocCam**, **Reincubate Camo**, or **DroidCam**) into a Wiimote-style pointing surface. It features:

- **OpenCV IR blob tracking** tuned for off-the-shelf IR pens.
- **Adaptive intensity gating** so clicks only trigger when the IR beam clearly pierces ambient light.
- **Dear PyGui vertical control column**: a narrow, tall window with stacked widgets for camera selection, sensitivity sliders, calibration metrics, and status readouts.
- **Fullscreen calibration overlay** powered by a simple OpenCV window—no overlapping GUI layers, no permission prompts.
- **Cross-platform packaging** via PyInstaller (artifacts produced in CI for Linux, Windows, and macOS).

## Hardware & Setup

| Component | Notes |
|-----------|-------|
| **USB Webcam** | 720p+ sensor preferred. Add an IR-pass filter in front of the lens (or pick a ready-made IR-sensitive model). Phone webcams are supported via commercial apps that expose the feed over USB/Wi-Fi as a UVC device. |
| **IR Pens/Remotes** | Any 940 nm LED stylus works. Classroom deployments often repurpose Wii sensor-bar pens or build DIY LED pens. |
| **Host PC** | Linux (X11) is the primary target today; Windows and macOS builds are supported through the same Python codepath. |
| **Projection Surface** | TV, projector, or large monitor. The calibration overlay assumes a rectangular display but tolerates keystone adjustments via homography. |

## Stack Overview

- **Python 3.11+** managed by Poetry.
- **OpenCV** for camera capture, IR processing, and fullscreen calibration overlays.
- **NumPy** for homography math and smoothing.
- **Dear PyGui** for the slim, vertical control surface. Widgets follow a single-column layout to fit podium touchscreens or narrow monitors.
- **pynput (XTest)** for zero-permission cursor control on X11 desktops; Windows/macOS drivers will follow the same abstraction.

## Quick Start

```bash
# 1. Install Poetry (https://python-poetry.org/docs/#installation)
# 2. Clone and install dependencies
poetry install

# 3. Launch Refurboard
poetry run refurboard
```

### What the UI Shows

The Dear PyGui window is intentionally tall and narrow (≈420px wide). From top to bottom:

1. **Logo header** – pulled from `assets/logo.png` for consistency with documentation and shortcuts.
2. **Camera dropdown** – choose among detected USB/phone webcams; refresh if you plug in a new device.
3. **Sensitivity sliders** – IR detection gain and click hysteresis, tuned with sensible defaults.
4. **Calibration button** – opens a separate fullscreen OpenCV viewport with four corner targets offset slightly from each display edge. Hold the IR pen steady at each target until it auto-locks.
5. **Accuracy & quadrilateral summary** – reprojection error (RMS pixels) plus the recorded screen coordinates.
6. **Live status** – normalized pointer coordinates, IR blob intensity, and click state.

## Calibration Flow

1. Mount/aim the webcam so it can see the whole display and add the IR-pass filter in front of the lens (or cover the optics so only infrared leaks through).
2. Press **Start Calibration**.
3. A fullscreen OpenCV window appears on the active display. Tap each illuminated target clockwise. The detector samples the IR blob and advances once it is stable for ~10 frames.
4. The resulting four camera⇄screen pairs feed a homography with reprojection error shown back in the UI. Rerun if the error exceeds ~8 px.

The calibration overlay is intentionally independent of Dear PyGui. OpenCV's `cv2.namedWindow` + `cv2.setWindowProperty(..., cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)` approach works across Linux, macOS, and Windows without extra permissions.

## Configuration

- Stored at `${XDG_DATA_HOME:-~/.local/share}/Refurboard/refurboard.config.json` (PlatformDirs takes care of Windows/macOS equivalents).
- Contains camera settings, detection knobs, and the most recent calibration quadrilateral.
- You can safely edit the JSON when Refurboard is closed; the UI writes back whenever you adjust sensitivity or finish calibration.

## Packaging & CI

PyInstaller specs (invoked via Poetry) bundle the app per-OS. GitHub Actions now:

1. Keep the existing deployment workflow intact for the website/wiki.
2. Add matrix jobs that run `poetry run pytest` and build PyInstaller artifacts for Linux, Windows, and macOS.

Local packaging mirrors CI:

```bash
poetry run pyinstaller -F -n refurboard src/refurboard_py/app.py
```

Artifacts land in `dist/` and can be copied to classroom laptops.

## Testing

```bash
poetry run pytest
```

Unit tests currently cover configuration round-trips; additional tests for detection heuristics, calibration math, and UI controllers are welcome.

## Wiki Refresh

Long-form deployment guides live in `refurboard-wiki/`. Update those pages with:

- Phone-to-webcam recommendations (commercial apps, USB vs Wi-Fi latency tips).
- Vertical layout reference art pulled from the `assets/` directory.
- Step-by-step calibration walkthroughs plus troubleshooting for ambient IR noise.

## License

Apache License 2.0 (see [LICENSE](LICENSE)).
