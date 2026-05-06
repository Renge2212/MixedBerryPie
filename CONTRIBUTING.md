# Contributing to MixedBerryPie

Thank you for your interest in contributing to MixedBerryPie! We welcome contributions from everyone.

## ⚠️ Maintenance Policy

This is a **personal project**. While Pull Requests and Issues are welcome, please note the following:

- **Limited Maintenance**: Active updates and immediate responses to issues are not guaranteed. I maintain this project in my spare time.
- **Support**: High-priority bugs may be addressed, but feature requests might take a long time or stay open indefinitely.
- **Forking**: If you need immediate updates, new features, or want to take the project in a different direction, you are encouraged to **fork the repository** and continue development in your own repository.

---

## 🧪 Testing Policy

**Run tests before every commit.**
We have a consolidated test runner script. Please run it before finalizing any changes.

```powershell
./run_tests.ps1
```

If any tests fail, **DO NOT** commit or deploy until they are resolved.

## 🐛 Bug Fix Strategy

When fixing a bug, follow the "Test-First" approach:

1.  **Reproduce**: Create a minimal test case that reproduces the bug.
    *   This test should fail initially.
2.  **Fix**: Implement the fix.
3.  **Verify**: Run the test again. It should pass.
4.  **Regression Check**: Run `./run_tests.ps1` to ensure no other parts of the system were broken.

## 📂 Test Structure

Tests are located in the `tests/` directory:

*   `test_app.py`: High-level application logic.
*   `test_settings_ui.py`: Configuration UI logic.
*   `test_key_sequence_edit.py`: Key recording widget logic (Critical for shortcuts).
*   `test_hook_manager.py`: Low-level keyboard hooking logic.
*   `test_config.py`: Configuration loading/saving and migration.

## 🛡️ Critical Code Paths

Be extra careful when modifying these files, as they affect core input functionality:

*   `src/core/hook_manager.py` (Global keyboard hooks)
*   `src/ui/settings_ui.py` (Especially `KeySequenceEdit` class)

Any changes to `HookManager` MUST be verified with `test_hook_manager.py`.

## 📝 Commit Conventions

We follow the **Conventional Commits** specification to ensure a clean and readable history.

### Format

```text
<type>(<scope>): <subject>
```

### Types

*   `feat`: A new feature
*   `fix`: A bug fix
*   `docs`: Documentation only changes
*   `style`: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
*   `refactor`: A code change that neither fixes a bug nor adds a feature
*   `perf`: A code change that improves performance
*   `test`: Adding missing tests or correcting existing tests
*   `chore`: Changes to the build process or auxiliary tools and libraries such as documentation generation

### Example

```text
feat(ui): add new color picker for menu items
fix(core): resolve keyboard hook conflict with admin apps
docs: update installation guide
```

## 🔢 Versioning Policy

This project follows **Semantic Versioning** (https://semver.org). The version in `pyproject.toml` reflects what users receive — it is a contract with the outside world, not a changelog of every commit.

### Bump the version when

End-user behavior changes:

*   **MAJOR** (`x.0.0`): breaking changes (incompatible config, removed features, behavior users must adapt to)
*   **MINOR** (`1.x.0`): new user-visible features (additive, backward compatible)
*   **PATCH** (`1.5.x`): bug fixes or security patches that affect runtime behavior

### Do NOT bump for

Internal-only changes that do not alter what users get:

*   Updates to `[dependency-groups] dev` (linters, formatters, type stubs, test tools, security scanners)
*   CI / pre-commit / GitHub Actions changes
*   Tests, docs, refactors with no behavior change
*   Updates to production dependencies that do not change runtime behavior

When in doubt: would a user reading the changelog care? If no, do not bump.
