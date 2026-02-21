"""Configuration reader for MixedBerryPie project."""
import tomllib
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def read_pyproject_toml() -> dict:
    """Read and parse pyproject.toml."""
    project_root = get_project_root()
    toml_path = project_root / "pyproject.toml"
    
    with open(toml_path, "rb") as f:
        return tomllib.load(f)


def get_app_display_name() -> str:
    """Get the application display name from pyproject.toml."""
    try:
        data = read_pyproject_toml()
        # Get display name from tool.mixedberrypie.display_name
        display_name = data.get("tool", {}).get("mixedberrypie", {}).get("display_name")
        if display_name:
            return display_name
    except (KeyError, FileNotFoundError, tomllib.TOMLDecodeError) as e:
        print(f"Warning: Could not read display_name from pyproject.toml: {e}")
    
    # Fallback to default
    return "MixedBerryPie"


def get_app_name() -> str:
    """Get the application name (package name) from pyproject.toml."""
    try:
        data = read_pyproject_toml()
        return data.get("project", {}).get("name", "mixedberrypie")
    except (KeyError, FileNotFoundError, tomllib.TOMLDecodeError) as e:
        print(f"Warning: Could not read project name from pyproject.toml: {e}")
        return "mixedberrypie"


def get_app_version() -> str:
    """Get the application version from pyproject.toml."""
    try:
        data = read_pyproject_toml()
        return data.get("project", {}).get("version", "1.0.0")
    except (KeyError, FileNotFoundError, tomllib.TOMLDecodeError) as e:
        print(f"Warning: Could not read version from pyproject.toml: {e}")
        return "1.0.0"


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Get MixedBerryPie configuration values")
    parser.add_argument("--display-name", action="store_true", help="Get application display name")
    parser.add_argument("--app-name", action="store_true", help="Get application package name")
    parser.add_argument("--version", action="store_true", help="Get application version")
    parser.add_argument("--exe-name", action="store_true", help="Get executable name (display_name + .exe)")
    
    args = parser.parse_args()
    
    if args.display_name:
        print(get_app_display_name())
    elif args.app_name:
        print(get_app_name())
    elif args.version:
        print(get_app_version())
    elif args.exe_name:
        print(f"{get_app_display_name()}.exe")
    else:
        # Default: print all values
        print(f"Display Name: {get_app_display_name()}")
        print(f"App Name: {get_app_name()}")
        print(f"Version: {get_app_version()}")
