# PieMenu Scripts

Descriptions and usage instructions for the scripts located in this directory.

## Core Pipeline Scripts

| Script | Description |
|---|---|
| `build.py` | Compiles the Python application into a standalone executable using PyInstaller. |
| `setup.ps1` | PowerShell script to set up a new developer environment. |
| `make_release.ps1` | PowerShell script that runs the MSVC build and creates a setup installer. |
| `package_msix.ps1` | PowerShell script to package the build as a Windows Store MSIX app. |
| `sign_msix_local.ps1` | Creates and signs with a local test certificate for MSIX sideload testing. |
| `install_cert.ps1` | Helper script to quickly install the test certificate to the trusted root store. |

## Internationalization (i18n)

| Script | Description |
|---|---|
| `update_translations.py` | Scans the `src` directory for translatable strings (`self.tr()`) and updates `resources/translations/piemenu_ja.ts`. |
| `compile_translations.py` | Compiles the `.ts` translation source file into a binary `.qm` file that Qt can load at runtime. |
| `check_translations.py` | Scans the `.ts` XML for `<translation type="unfinished">` or empty strings. |
| `verify_translations.py` | Runtime check using `QTranslator` to ensure hardcoded essential strings are translated correctly. |

## UI & Resources

| Script | Description |
|---|---|
| `generate_icons.py` | Generates or processes SVG/PNG icons for the menu. |
| `download_icons.py` | Fetches icons from external libraries (e.g., Lucide). |
| `convert_icon.py` | Converts external SVGs or raster images into the standardized SVG format format. |
| `curate_icons.py` | Utility to process massive icon sets and extract commonly used software icons. |
| `verify_icon_resolution.py` | Ensures all referenced icons exist and have correct paths. |
| `verify_ui_imports.py` | Checks for broken imports or circular dependencies in UI files. |
| `verify_welcome_dialog.py` | Simple test runner for the onboarding dialog. |

## Maintenance

| Script | Description |
|---|---|
| `reset_config.py` | Deletes the local configuration file to restore application defaults. |
| `config_reader.py` | A utility to inspect and read the local JSON configuration file safely. |
| `update_version.py` | Bumps application versions across config, manifest, and setup scripts based on arguments. |
