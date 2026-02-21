import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.utils import resolve_icon_path


def verify():
    relative_path = "icons/pencil.svg"
    resolved = resolve_icon_path(relative_path)

    print(f"Input: {relative_path}")
    print(f"Resolved: {resolved}")

    if resolved and os.path.exists(resolved):
        print("SUCCESS: File exists.")
        sys.exit(0)
    else:
        print("FAILURE: File does not exist or resolution failed.")
        sys.exit(1)

if __name__ == "__main__":
    verify()
