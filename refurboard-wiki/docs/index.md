# Refurboard Field Guide

Refurboard resurrects classroom projectors with a modern Python toolchain. Point a USB webcam—or a phone streaming video through commercial webcam apps like **Camo**, **EpocCam**, or **DroidCam**—at your display, aim an IR pen, and let OpenCV translate those light trails into mouse movement. The new stack replaces the legacy .NET client with:

- OpenCV-based IR blob detection with adaptive brightness gating.
- Dear PyGui control surface that is intentionally tall and narrow for lecterns and portrait displays.
- Fullscreen OpenCV calibration viewport (no nested toolkits, no window chrome).
- Cross-platform packaging through Poetry + PyInstaller with CI artifacts for Windows, macOS, and Linux.

![Refurboard UI column](../assets/logo.png)

## Hardware Checklist

| Item | Details |
|------|---------|
| **IR pen / Wii-style stylus** | Any 940 nm LED with a momentary button. Classroom packs from Wii-era whiteboard kits work perfectly. |
| **Camera** | IR-capable USB webcam or phone-as-webcam via commercial apps. Add an external IR-pass filter (or use ready-built “night vision” cams). 720p @ 30 FPS is sufficient. |
| **Host OS** | Linux/X11 for zero-permission pointer control via pynput (XTest). Windows/macOS builds are supported via the same UI and detection stack. |
| **Display** | Projector, TV, or monitor. Calibration assumes a rectangular surface but compensates for keystone with a 3×3 homography. |

## Software Stack

- **Python 3.11+** managed by Poetry.
- **OpenCV + NumPy** for capture, blob analysis, and homography math.
- **Dear PyGui** for the main control column (420 px wide, stacked widgets).
- **pynput** for pointer control (Linux first; future drivers plug into the same abstraction).
- **PyInstaller** for single-file binaries.

## Installation

```bash
# Clone repository
git clone https://github.com/kevinl95/Refurboard.git
cd Refurboard

# Install dependencies
poetry install

# Launch the control surface
poetry run refurboard
```

Poetry downloads all runtime dependencies (OpenCV, Dear PyGui, pynput, etc.) and exposes a console script named `refurboard`.

## Dear PyGui Layout (Columnar UI)

The app window is intentionally tall and narrow to sit beside slide decks or OBS scenes. The vertical stack contains:

1. **Logo header** – uses the PNG assets in `/assets` for brand consistency.
2. **Camera picker** – dropdown listing USB/phone webcams plus a refresh button.
3. **Sensitivity sliders** – IR gain and click hysteresis with safe defaults (0.65 / 0.15) but adjustable live.
4. **Calibration button** – launches the fullscreen OpenCV viewport on the active display.
5. **Accuracy summary** – RMS reprojection error, plus the four collected corner coordinates rendered as a quadrilateral readout.
6. **Live telemetry** – normalized pointer coordinates, IR blob intensity, and click state text.

## Calibration Walkthrough

1. Position the camera (or phone-as-webcam feed) so the entire display fits in frame.
2. Click **Start Calibration**. Refurboard opens a borderless fullscreen OpenCV window.
3. Four circular targets appear clockwise. Hold the IR pen steady on each target; once the blob is stable for ~10 frames, the point locks automatically.
4. After all four points, Refurboard computes a homography and reports RMS error. Re-run if the error exceeds ~8 pixels.

Because the overlay is an OpenCV window, it works uniformly across Linux, Windows, and macOS without Dear PyGui quirks.

## Using Phones as Webcams

Commercial apps expose phones as UVC devices; pick whichever your district approves:

- **Reincubate Camo** (USB/Wi-Fi, iOS + Android) – crisp output and stable drivers.
- **Elgato EpocCam** (USB/Wi-Fi, iOS + Android) – simple, widely adopted.
- **DroidCam** (USB/Wi-Fi, Android + desktop agent) – mature and inexpensive.

Tips:

- Prefer USB tethering to avoid Wi-Fi latency.
- Lock exposure/ISO inside the app so IR brightness stays predictable.
- Mount the phone firmly (tripod, clamp) and disable auto-focus hunting.

## Configuration File

- Stored via PlatformDirs (e.g., `~/.local/share/Refurboard/refurboard.config.json`).
- Contains the active camera ID, detection knobs (sensitivity, hysteresis, smoothing), and the latest calibration quadrilateral (camera pixels, screen pixels, normalized coordinates).
- Safe to edit between sessions; the UI writes whenever you tweak sliders or complete calibration.

## Testing & Packaging

```bash
poetry run pytest          # run unit tests
poetry run pyinstaller -F -n refurboard src/refurboard_py/app.py  # build single-file binary
```

GitHub Actions now run tests plus PyInstaller builds on Ubuntu, Windows, and macOS while leaving the existing documentation deployment workflow untouched.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| **Cursor wobbles** | Increase smoothing factor (config JSON) or reduce camera gain. Ensure tripod stability. |
| **Clicks misfire** | Raise sensitivity slider or hysteresis so weak reflections keep the click gate open. |
| **Calibration error > 10 px** | Re-run calibration after re-aiming the camera; ensure camera sees every corner and no bright IR reflections exist. |
| **Pointer stuck at screen edge** | Recalibrate with the camera centered; check that phone/webcam feed is not mirrored unless you explicitly set `mirror=true` in config. |

## Next Steps

- Extend the pointer abstraction with native macOS/Windows drivers.
- Add FoV overlays and per-corner gain adjustments.
- Expand wiki with printable classroom posters for IR pen care and alignment tips.
