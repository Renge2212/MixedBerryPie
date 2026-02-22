# Translation Guide

MixedBerryPie supports multiple languages. We welcome contributions for new translations or improvements to existing ones!

## How it works

Translations are stored in the `resources/translations/` directory as `.ts` (Qt Translation Source) files.

- `piemenu_ja.ts`: Japanese translations.
- `piemenu_en.ts`: English translations (generated from source).

The application uses the `lrelease` tool to compile these into `.qm` files for use at runtime.

## Translation Workflow (for Developers)

We use an automated system to keep translations in sync with the source code.

### 1. Extract Strings from Source
When you add or change UI strings using `self.tr("...")`, run the following script to update the `.ts` files:

```bash
uv run python scripts/update_translations.py
```
This script runs `lupdate` to scan the `src/` directory and synchronizes all `.ts` files. It also ensures the XML format remains clean and standard.

### 2. Add/Update Translations
Open `resources/translations/piemenu_ja.ts` and fill in the `<translation>` tags. We recommend using [Qt Linguist](https://doc.qt.io/qt-6/qtlinguist-index.html) for a better experience, but any text editor works.

### 3. Verify Translations
Run the check script to ensure there are no missing or unfinished translations:

```bash
uv run python scripts/check_translations.py
```

### 4. Compile to Binary
Compile the `.ts` files into `.qm` files to test them in the application:

```bash
# In Windows (inside .venv)
.\.venv\Lib\site-packages\PySide6\lrelease.exe resources\translations\piemenu_ja.ts
```

## Contributing a new language

1. **Copy the template**: Copy `resources/translations/piemenu_ja.ts` to `piemenu_[LANG_CODE].ts` (e.g., `piemenu_fr.ts`).
2. **Translate**: Use Qt Linguist or a text editor to translate the strings.
3. **Internal verification**: The app will automatically try to load the file based on the system language or the "Language" setting.
4. **Submit a Pull Request**: Follow the [GitHub Flow](docs/project_management.md#ブランチ戦略github-flow) to submit your changes.

Thank you for helping us make MixedBerryPie accessible to everyone!
