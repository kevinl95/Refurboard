# Technical Documentation

This page covers the technical details for developers and IT administrators who want to understand Refurboard's internals, contribute to the project, or troubleshoot advanced issues.

## Software Stack

- **Python 3.11+** managed by Poetry.
- **OpenCV + NumPy** for capture, blob analysis, and homography math.
- **Dear PyGui** for the main control column (420 px wide, stacked widgets).
- **Pointer drivers**: ydotool on Linux/Wayland (needs uinput); pynput/XTest on X11; SendInput on Windows; Quartz CGEvent on macOS.
- **PyInstaller** for single-file binaries.

## Architecture Overview

Refurboard uses OpenCV-based IR blob detection with adaptive brightness gating. The system:

1. Captures frames from any UVC-compatible camera (USB webcam or phone-as-webcam).
2. Detects IR blobs above a learned intensity threshold.
3. Maps blob coordinates through a 3×3 homography matrix to screen coordinates.
4. Drives the system cursor via platform-specific pointer backends.

The Dear PyGui control surface is intentionally tall and narrow for lecterns and portrait displays. The fullscreen calibration viewport uses pure OpenCV (no nested toolkits, no window chrome) for consistent behavior across platforms.

## Dear PyGui Layout (Columnar UI)

The app window vertical stack contains:

1. **Logo header** – uses the PNG assets in `/assets` for brand consistency.
2. **Camera picker** – dropdown listing USB/phone webcams plus a refresh button.
3. **Sensitivity sliders** – IR gain and click hysteresis with safe defaults but adjustable live.
4. **Calibration button** – launches the fullscreen OpenCV viewport on the active display.
5. **Accuracy summary** – RMS reprojection error displayed after calibration.
6. **Live preview** – shows the camera feed with detected IR blobs highlighted.

## Configuration File

- Stored via PlatformDirs (e.g., `~/.local/share/Refurboard/refurboard.config.json` on Linux).
- Contains the active camera ID; detection knobs (sensitivity, hysteresis, smoothing, jitter deadzone `min_move_px`); and the latest calibration quadrilateral plus monitor name/index and origin.
- Safe to edit between sessions; the UI writes whenever you tweak sliders or complete calibration.

## Installation from Source

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

## Linux Pointer Control (Wayland/X11)

### X11
Works out of the box via pynput/XTest. No additional setup required.

### Wayland
Install `ydotool` and ensure uinput access:

**1. Add user to input group:**
```bash
sudo usermod -aG input $USER
# Log out and back in for this to take effect
```

**2. Create udev rule for uinput access:**
```bash
sudo tee /etc/udev/rules.d/70-uinput.rules >/dev/null <<'EOF'
KERNEL=="uinput", MODE="0660", GROUP="input", TAG+="uaccess", OPTIONS+="static_node=uinput"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=misc --attr-match=name=uinput
sudo modprobe uinput
```

**3. Run ydotoold as a user service:**
```bash
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

Verify `/run/user/$(id -u)/.ydotool_socket` exists. Refurboard drives the cursor through this socket on Wayland.

## Testing & Packaging

```bash
poetry run pytest                      # run unit tests
poetry run pyinstaller --clean refurboard.spec  # build single-file binary
```

GitHub Actions run tests plus PyInstaller builds on Ubuntu, Windows, and macOS. The spec bundles OpenCV libs, logo assets, and Quartz modules on macOS.

## Advanced Troubleshooting

| Symptom | Fix |
|---------|-----|
| **Cursor wobbles** | Increase smoothing or `min_move_px` in config; reduce camera gain; ensure tripod stability. |
| **Clicks misfire** | Raise sensitivity or hysteresis so weak reflections keep the click gate open. |
| **Calibration error > 10 px** | Re-run calibration after re-aiming the camera; ensure camera sees every corner and minimize bright IR reflections. |
| **Pointer on wrong monitor** | Re-run calibration on the intended display; the app remembers that monitor. |
| **Wayland: cursor does not move** | Ensure `ydotoold` user service is running and `/run/user/$(id -u)/.ydotool_socket` exists; add user to `input`, apply the udev rule for `/dev/uinput`, reload `uinput`. |

## Contributing

Contributions are welcome! Please see the [GitHub repository](https://github.com/kevinl95/Refurboard) for issues and pull requests.
