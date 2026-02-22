# Translation Guide

MixedBerryPie supports multiple languages. We welcome contributions for new translations or improvements to existing ones!

## How it works

Translations are stored in the `resources/translations/` directory as `.ts` (Qt Translation Source) files.

- `messages_ja.ts`: Japanese translations.
- `messages_en.ts`: English translations (default).

The application uses the system's locale to automatically select the appropriate language.

## Contributing a new language

1. **Copy the template**: Copy `resources/translations/messages_en.ts` to `messages_[LANG_CODE].ts` (e.g., `messages_fr.ts` for French).
2. **Translate**: Open the file in a text editor or [Qt Linguist](https://doc.qt.io/qt-6/qtlinguist-index.html) and translate the `<translation>` tags.
3. **Internal verification**:
   - The app will automatically try to load the file if the filename matches your system language.
   - You can also force a language in settings to test.
4. **Submit a Pull Request**: Follow the [GitHub Flow](docs/project_management.md#ブランチ戦略github-flow) to submit your changes.

## Compiling (Advanced)

While not strictly required for contributors (the CI/CD handles this during release), `.ts` files are compiled into `.qm` files for the app to use. If you want to test the binary format locally, you can use:

```bash
lrelease resources/translations/messages_fr.ts
```

Thank you for helping us make MixedBerryPie accessible to everyone!
