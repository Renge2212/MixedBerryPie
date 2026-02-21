import os
import shutil
import sys

from config_reader import get_app_display_name  # type: ignore


def build_executable():
    print("==> Starting Pie Menu build process...")

    app_name = get_app_display_name()

    # Ensure we are in the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    # Check if the application is currently running
    import contextlib

    with contextlib.suppress(Exception):
        import subprocess

        # Check for the application in task list
        # S602, S607: Use full path to tasklist and avoid shell=True if possible
        system_root = os.environ.get("SYSTEMROOT", "C:\\Windows")
        tasklist_path = os.path.join(system_root, "System32", "tasklist.exe")
        exe_name = f"{app_name}.exe"
        output = subprocess.check_output(
            [tasklist_path, "/FI", f"IMAGENAME eq {exe_name}"], startupinfo=None
        ).decode("cp932", errors="ignore")
        if exe_name in output:
            print(f"\n[WARNING] {exe_name} is currently running.")
            print("Please close the application from the system tray before building.")
            sys.exit(1)

    # Cleanup previous builds
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            print(f"[CLEAN] Attempting to remove {folder}...")
            try:
                # Use a more aggressive cleanup or a simple try/except
                shutil.rmtree(folder)
            except PermissionError as e:
                print(f"\n[ERROR] PERMISSION ERROR: Could not remove '{folder}'.")
                print(f"Details: {e}")
                print(
                    f"\nSuggestion: Ensure '{app_name}.exe' is not running and no folder is open in an explorer window."
                )
                sys.exit(1)
            except Exception as e:
                print(f"Warning: Could not fully clean {folder}: {e}")

    # PyInstaller command
    # --onefile: Create a single executable
    # --windowed: No console window (GUI app)
    # --name: Name of the output file
    # --collect-all: Ensure all PyQt6/keyboard modules are included
    # --add-data: Include version/metadata if needed (not needed for current structure)

    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        f"--name={app_name}",
        "--clean",
        "--add-data=resources;resources",
        "--icon=resources/app_icon.ico",
        "run.py",
    ]

    print(f"[RUN] Running command: {' '.join(cmd)}")

    try:
        # Run pyinstaller via 'uv run' to ensure environment is correct
        # RUF005: Use unpacking instead of concatenation
        uv_path = shutil.which("uv") or "uv"
        subprocess.check_call([uv_path, "run", *cmd])
        print("\n[OK] Build successful! The executable can be found in the 'dist' folder.")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Build failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    build_executable()
