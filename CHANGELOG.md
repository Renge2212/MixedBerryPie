# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-22

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
