# PieMenu Scripts

Descriptions and usage instructions for the scripts located in this directory.

## Core Pipeline Scripts

| Script | Description |
|---|---|
| `build.py` | Compiles the Python application into a standalone executable using PyInstaller. |
| `make_release.ps1` | A PowerShell script that runs the build and then creates an installer using Inno Setup 6. |

## Internationalization (i18n)

| Script | Description |
|---|---|
| `update_translations.py` | Scans the `src` directory for translatable strings (`self.tr()`) and updates `resources/translations/piemenu_ja.ts`. |
| `compile_translations.py` | Compiles the `.ts` translation source file into a binary `.qm` file that Qt can load at runtime. |
| `verify_translations.py` | Checks if there are missing translations or inconsistencies in the `.ts` files. |
| `apply_translations.py` | (Utility) May be used for batch applying translations from external sources. |
| `merge_translations.py` | (Utility) Merges multiple `.ts` files or handles conflicting entries. |
| `fix_ts_file.py` | (Utility) Fixes common XML structure issues in `.ts` files. |

## UI & Resources

| Script | Description |
|---|---|
| `generate_icons.py` | Generates or processes SVG/PNG icons for the menu. |
| `download_icons.py` | Fetches icons from external libraries (e.g., Lucide). |
| `verify_icon_resolution.py` | Ensures all referenced icons exist and have correct paths. |
| `verify_ui_imports.py` | Checks for broken imports or circular dependencies in UI files. |
| `verify_welcome_dialog.py` | Simple test runner for the onboarding dialog. |

## Maintenance

| Script | Description |
|---|---|
| `reset_config.py` | Deletes the local configuration file to restore application defaults. |
