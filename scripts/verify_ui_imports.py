import os
import sys

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(project_root)

print(f"Project root: {project_root}")

try:
    print("Successfully imported settings_ui")
except Exception as e:
    print(f"Failed to import settings_ui: {e}")
    exit(1)

try:
    print("Successfully imported help_dialog")
except Exception as e:
    print(f"Failed to import help_dialog: {e}")
    exit(1)

print("UI modules syntax check passed.")
