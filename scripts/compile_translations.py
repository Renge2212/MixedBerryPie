import os
import subprocess
import sys

# Path to the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATIONS_DIR = os.path.join(PROJECT_ROOT, "resources", "translations")
TS_FILE = os.path.join(TRANSLATIONS_DIR, "piemenu_ja.ts")
QM_FILE = os.path.join(TRANSLATIONS_DIR, "piemenu_ja.qm")

# Path to lrelease executable.
LRELEASE_EXE = "pyside6-lrelease"


def compile_translations():
    print(f"Compiling translations for {PROJECT_ROOT}...")

    # Construct the command
    cmd = [LRELEASE_EXE, TS_FILE, "-qm", QM_FILE]

    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        print(f"Successfully compiled .qm file: {QM_FILE}")
    except subprocess.CalledProcessError as e:
        print(f"Error running lrelease: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        sys.exit(1)


if __name__ == "__main__":
    compile_translations()
