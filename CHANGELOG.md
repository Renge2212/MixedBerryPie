# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
## [1.3.0] - 2026-03-01

Major update focusing on code quality, security, and advanced menu features.

### Added
- **Submenu Support**: Concentric and fan layouts for nested pie menus.
- **Dead Code Audit**: Integrated `vulture` into the development workflow using `pre-commit`.
- **Security Auditing**: Added `bandit` and `pip-audit` for automated security checks.
- **Complexity Analysis**: Integrated `xenon` and expanded `Ruff` complexity rules.
- **Improved UI**: Icon and text display order refinement; 2-line label limit for better alignment.

### Changed
- Refined logging: Suppressed console output below `WARNING` level for a cleaner user experience.
- Code Refactoring: Optimized various internal segments (e.g., using `max()` and `elif`).
- Updated project path management to use `AppData` consistently.

### Fixed
- Error where the label line counter was not displayed immediately on dialog initialization.
- Inconsistent version strings across the codebase.

---

[1.1.0] - 2026-02-22

Initial stable release after major refactoring and CI/CD integration.

### Added
- Professional CI/CD pipeline with GitHub Actions.
- Automated release builds for `.exe` (Inno Setup) and `.msix` (Store).
- Security auditing with `pip-audit` and CodeQL.
- Maintenance policy, Privacy policy, and Security policy.
- GitHub Flow branch strategy documentation.
- Issue Templates for Bug Reports and Feature Requests.
- Support for contextual profiles and advanced actions.

### Changed
- Improved UI aesthetics with better colors and transparency.
- Optimized keyboard hook performance and reliability.
- Updated README and developer documentation.

### Removed
- Unused Startup Manager (WinRT dependency) for better compatibility and cleaner code.
- Various temporary debug files.
