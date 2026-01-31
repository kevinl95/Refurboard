# Refurboard

![Refurboard logo](assets/logo.png)

Refurboard is a classroom-ready IR whiteboard controller that turns any USB webcam (or phone acting as a webcam through commercial apps such as **EpocCam**, **Reincubate Camo**, or **DroidCam**) into a Wiimote-style pointing surface. It features:

- **OpenCV IR blob tracking** tuned for off-the-shelf IR pens.
- **Adaptive intensity gating** so clicks only trigger when the IR beam clearly pierces ambient light.
- **Dear PyGui vertical control column**: a narrow, tall window with stacked widgets for camera selection, sensitivity sliders, calibration metrics, and status readouts.
- **Fullscreen calibration overlay** powered by a simple OpenCV window—no overlapping GUI layers, no permission prompts. The overlay runs on the monitor chosen at calibration time and stores that monitor’s origin/size for future sessions.
- **Cross-platform packaging** via PyInstaller (artifacts produced in CI for Linux, Windows, and macOS).

## Hardware & Setup

| Component | Notes |
|-----------|-------|
| **USB Webcam** | 720p+ sensor preferred. Add an IR-pass filter in front of the lens (or pick a ready-made IR-sensitive model). Phone webcams are supported via commercial apps that expose the feed over USB/Wi-Fi as a UVC device. |
| **IR Pens/Remotes** | Any 940 nm LED stylus works. Classroom deployments often repurpose Wii sensor-bar pens or build DIY LED pens. |
| **Host PC** | Linux: Wayland requires ydotoold + uinput access (see Linux pointer setup). X11 works via pynput/XTest with no extra steps. Windows uses SendInput; macOS uses Quartz (both bundled). |
| **Projection Surface** | TV, projector, or large monitor. The calibration overlay assumes a rectangular display but tolerates keystone adjustments via homography. |

## Stack Overview

- **Python 3.11+** managed by Poetry.
- **OpenCV** for camera capture, IR processing, and fullscreen calibration overlays.
- **NumPy** for homography math and smoothing.
- **Dear PyGui** for the slim, vertical control surface. Widgets follow a single-column layout to fit podium touchscreens or narrow monitors.
- **Pointer drivers**: ydotool on Linux/Wayland (needs uinput access); pynput/XTest on X11; SendInput on Windows; Quartz CGEvent on macOS.

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
4. **FoV / corner gain** – optional stretch controls to compensate for lens distortion or tight camera FoV.
5. **Calibration button** – opens a separate fullscreen OpenCV viewport with four corner targets offset slightly from each display edge. Hold the IR pen steady at each target until it auto-locks.
6. **Accuracy & quadrilateral summary** – reprojection error (RMS pixels) plus the recorded screen coordinates.
7. **Live status** – normalized pointer coordinates, IR blob intensity, and click state.

## Calibration Flow

1. Mount/aim the webcam so it can see the whole display and add the IR-pass filter in front of the lens (or cover the optics so only infrared leaks through).
2. Press **Start Calibration**.
3. A fullscreen OpenCV window appears on the active display. Tap each illuminated target clockwise. The detector samples the IR blob and advances once it is stable for ~10 frames.
4. The resulting four camera⇄screen pairs feed a homography with reprojection error shown back in the UI. Rerun if the error exceeds ~8 px.

The calibration overlay is intentionally independent of Dear PyGui. OpenCV's `cv2.namedWindow` + `cv2.setWindowProperty(..., cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)` approach works across Linux, macOS, and Windows without extra permissions. The monitor that shows the overlay is remembered (name/index, origin, size) and is the only monitor Refurboard moves the cursor on.

### Linux pointer control (Wayland/X11)

- X11: works out of the box via pynput/XTest.
- Wayland: install `ydotool` and ensure uinput access for your user:
  1) `sudo usermod -aG input $USER` then log out/in.
  2) Create udev rule:
	  ```
	  sudo tee /etc/udev/rules.d/70-uinput.rules >/dev/null <<'EOF'
	  KERNEL=="uinput", MODE="0660", GROUP="input", TAG+="uaccess", OPTIONS+="static_node=uinput"
	  EOF
	  sudo udevadm control --reload-rules
	  sudo udevadm trigger --subsystem-match=misc --attr-match=name=uinput
	  sudo modprobe uinput
	  ```
  3) Run ydotoold as a user service:
	  ```
	  mkdir -p ~/.config/systemd/user
	  cat > ~/.config/systemd/user/ydotool.service <<'EOF'
	  [Unit]
	  Description=ydotoold (user)
	  After=graphical-session.target

	  [Service]
	  Type=simple
	  Environment=XDG_RUNTIME_DIR=/run/user/%U
	  ExecStart=/usr/bin/ydotoold --socket-path /run/user/%U/.ydotool_socket
	  Restart=on-failure

	  [Install]
	  WantedBy=default.target
	  EOF
	  systemctl --user daemon-reload
	  systemctl --user enable --now ydotool.service
	  ```
  Verify `/run/user/$(id -u)/.ydotool_socket` exists. Refurboard will drive the cursor through this socket on Wayland.

### macOS Gatekeeper (unidentified developer warning)

Since Refurboard is not signed with an Apple Developer certificate, macOS will block it by default. To run the app:

**Method 1: Right-click to Open (recommended)**
1. Right-click (or Control-click) on `Refurboard.app`
2. Select **Open** from the context menu
3. Click **Open** in the dialog that appears
4. The app will now run and be remembered for future launches

**Method 2: System Settings**
1. Try to open the app normally (it will be blocked)
2. Open **System Settings** > **Privacy & Security**
3. Scroll down and find the message about Refurboard being blocked
4. Click **Open Anyway**
5. Enter your password if prompted

**Method 3: Terminal (advanced)**
```bash
# Remove the quarantine attribute from the downloaded app
xattr -cr /path/to/Refurboard.app
```

After using any method, macOS will remember your choice and the app will open normally in the future.

### macOS Accessibility Permission (required for cursor control)

macOS requires explicit user permission for apps to control the cursor. Unlike Camera access, **this cannot be prompted automatically** — you must manually grant it:

1. Open **System Settings** > **Privacy & Security** > **Accessibility**
2. Click the **+** button (you may need to unlock with your password)
3. Navigate to and select **Refurboard.app**
4. Ensure the toggle next to Refurboard is **enabled**

**Why is this required?** Accessibility permissions allow apps to control the entire system (mouse, keyboard, other apps). Apple considers this too sensitive to allow apps to request via a popup — users must make a deliberate choice to grant it.

**Symptom if not granted:** Refurboard will track the IR pen (you'll see coordinates updating in the UI) but the system cursor won't move.

## Configuration

- Stored at `${XDG_DATA_HOME:-~/.local/share}/Refurboard/refurboard.config.json` (PlatformDirs takes care of Windows/macOS equivalents).
- Contains camera settings; detection knobs (sensitivity, hysteresis, smoothing, jitter deadzone `min_move_px`, FoV scale, per-corner gain); and the most recent calibration quadrilateral plus monitor name/index and origin.
- You can safely edit the JSON when Refurboard is closed; the UI writes back whenever you adjust sensitivity or finish calibration.

## Packaging & CI

PyInstaller specs (invoked via Poetry) bundle the app per-OS. GitHub Actions:

1. Keep the existing deployment workflow intact for the website/wiki.
2. Add matrix jobs that run `poetry run pytest` and build PyInstaller artifacts for Linux, Windows, and macOS.

Local packaging mirrors CI using the included spec:

```bash
# ensure dev deps are present (pyinstaller + pyobjc on macOS)
poetry install --with dev

# build single-file binary
poetry run pyinstaller --clean refurboard.spec
```

Artifacts land in `dist/` and can be copied to classroom laptops. The spec bundles OpenCV shared libs, Quartz (macOS), and logo assets.

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

### Build/publish the wiki

```bash
# From repo root
pip install mkdocs mkdocs-landing   # once, if not already installed
cd refurboard-wiki
mkdocs build                        # outputs to refurboard-wiki/site/
```

If the site is hosted elsewhere, copy/sync `refurboard-wiki/site/` to your host after building.

## Troubleshooting (quick)

| Symptom | Fix |
|---------|-----|
| Cursor wobbles | Increase smoothing factor or `min_move_px` in config; reduce camera gain; secure the camera mount. |
| Clicks misfire | Raise sensitivity or hysteresis so weak reflections do not latch clicks. |
| Calibration error > 10 px | Re-run calibration after re-aiming the camera; ensure all corners are visible and IR reflections are minimized. |
| Pointer on wrong monitor | Re-run calibration on the intended display; the app remembers that monitor. |
| Wayland: cursor does not move | Ensure `ydotoold` user service is running and `/run/user/$(id -u)/.ydotool_socket` exists; add user to `input`, apply the udev rule for `/dev/uinput`, and reload `uinput`. |

## License

Apache License 2.0 (see [LICENSE](LICENSE)).
