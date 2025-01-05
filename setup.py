import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine-tuning.
build_exe_options = {
    "packages": ["os", "qrcode", "base64", "cv2", "numpy", "flask", "kivy"],
    "include_files": [("assets", "assets"), ("client", "client")],
    "excludes": []
}

# Base is set to "Win32GUI" for Windows to avoid the console window.
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="Refurboard",
    version="0.1",
    description="Turn any old smart phone into an interactive whiteboard",
    options={"build_exe": build_exe_options},
    executables=[Executable("main.py", base=base, icon="assets/logo.png")]
)