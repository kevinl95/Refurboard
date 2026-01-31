"""Entry point for python -m refurboard_py and PyInstaller."""
import multiprocessing
import sys

# CRITICAL: On Windows, PyInstaller spawns child processes that re-execute
# the main script. freeze_support() must be called before ANY other imports
# or code to prevent the GUI from cloning itself when calibration starts.
if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    # Set multiprocessing start method to 'spawn' on all platforms for consistency
    # This is the default on Windows, but explicit is better
    if sys.platform != "win32":
        try:
            multiprocessing.set_start_method("spawn", force=False)
        except RuntimeError:
            pass  # Already set
    
    from refurboard_py.app import main
    main()
