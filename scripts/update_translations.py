import os
import subprocess
import sys

# Path to the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
TRANSLATIONS_DIR = os.path.join(PROJECT_ROOT, "resources", "translations")
TS_FILE = os.path.join(TRANSLATIONS_DIR, "piemenu_ja.ts")

# Path to lupdate executable. uv run will ensure it's in the PATH if needed,
# or we can rely on pyside6-lupdate being available in the environment.
LUPDATE_EXE = "pyside6-lupdate"


def update_translations():
    print(f"Updating translations for {PROJECT_ROOT}...")

    # Construct the command
    # lupdate src -ts resources/translations/piemenu_ja.xml
    cmd = [
        LUPDATE_EXE,
        "-extensions",
        "py",
        "-no-obsolete",  # Optional: keep obsolete entries or remove them? Default usually keeps them marked.
        # Let's keep them for now to avoid losing work, or remove -no-obsolete to let it mark them.
        # Actually -no-obsolete REMOVES them. Let's NOT use it so we can see what happens.
        "-recursive",
        SRC_DIR,
        "-ts",
        TS_FILE,
    ]

    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        print("Successfully updated .ts file.")
    except subprocess.CalledProcessError as e:
        print(f"Error running lupdate: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        sys.exit(1)


if __name__ == "__main__":
    update_translations()
