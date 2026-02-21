"""Reset config script - deletes the user config file so defaults are restored on next run."""
import os
import shutil

APP_NAME = "MixedBerryPie"
APPDATA = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
CONFIG_DIR = os.path.join(APPDATA, APP_NAME)
CONFIG_FILE = os.path.join(CONFIG_DIR, "menu_config.json")

def reset():
    if os.path.exists(CONFIG_FILE):
        backup = CONFIG_FILE + ".bak"
        shutil.copy(CONFIG_FILE, backup)
        os.remove(CONFIG_FILE)
        print(f"Deleted: {CONFIG_FILE}")
        print(f"Backup:  {backup}")
    else:
        print(f"Config file not found: {CONFIG_FILE}")
        print("Nothing to delete.")

if __name__ == "__main__":
    reset()
