"""Update version in AppxManifest.xml and MixedBerryPie.iss from pyproject.toml.

Usage:
    python scripts/update_version.py            # reads version from pyproject.toml
    python scripts/update_version.py 1.2.0      # override with explicit version

This script is intended for CI/CD use and does NOT commit any changes.
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def get_version_from_pyproject() -> str:
    content = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not m:
        raise ValueError("Could not find version in pyproject.toml")
    return m.group(1)


def validate_tag_version(tag_version: str, pyproject_version: str) -> None:
    """Ensure git tag version matches pyproject.toml version."""
    if tag_version != pyproject_version:
        print(
            f"ERROR: Tag version '{tag_version}' does not match "
            f"pyproject.toml version '{pyproject_version}'."
        )
        print("Please update pyproject.toml before tagging.")
        sys.exit(1)
    print(f"[OK] Version verified: {tag_version}")


def update_appx_manifest(version: str) -> None:
    """Update Version in AppxManifest.xml (requires 4-part version: x.y.z.0)."""
    manifest_path = PROJECT_ROOT / "package" / "AppxManifest.xml"
    msix_version = f"{version}.0"  # MSIX requires 4 parts
    content = manifest_path.read_text(encoding="utf-8")
    updated = re.sub(r'Version="[^"]*"', f'Version="{msix_version}"', content)
    manifest_path.write_text(updated, encoding="utf-8")
    print(f"[OK] AppxManifest.xml -> Version={msix_version}")


def update_inno_setup(version: str) -> None:
    """Update version in MixedBerryPie.iss."""
    iss_path = PROJECT_ROOT / "MixedBerryPie.iss"
    if not iss_path.exists():
        print("[SKIP] MixedBerryPie.iss not found, skipping.")
        return
    content = iss_path.read_text(encoding="utf-8")
    updated = re.sub(
        r'(#define MyAppVersion\s*")[^"]*(")',
        rf"\g<1>{version}\g<2>",
        content,
    )
    iss_path.write_text(updated, encoding="utf-8")
    print(f"[OK] MixedBerryPie.iss -> MyAppVersion={version}")


def main() -> None:
    pyproject_version = get_version_from_pyproject()

    if len(sys.argv) >= 2:
        tag_version = sys.argv[1].lstrip("v")
        validate_tag_version(tag_version, pyproject_version)
        version = tag_version
    else:
        version = pyproject_version

    print(f"Applying version: {version}")
    update_appx_manifest(version)
    update_inno_setup(version)
    print("Done.")


if __name__ == "__main__":
    main()
