import os
import sys

from PyQt6.QtCore import QCoreApplication, QTranslator


def verify_translations():
    app = QCoreApplication(sys.argv)

    qm_path = os.path.abspath(os.path.join("resources", "translations", "piemenu_ja.qm"))
    print(f"Checking translation file: {qm_path}")

    if not os.path.exists(qm_path):
        print("❌ .qm file not found")
        sys.exit(1)

    translator = QTranslator()
    if not translator.load(qm_path):
        print("❌ Failed to load .qm file")
        sys.exit(1)

    app.installTranslator(translator)

    # Test cases: context, source, expected
    test_cases = [
        ("PieMenuApp", "Settings", "設定"),
        ("PieMenuApp", "Exit PieMenu", "PieMenuを終了"),
        ("HelpDialog", "Close", "閉じる"),
        ("IconPickerWidget", "Select Icon", "アイコンを選択"),
        ("IconPickerWidget", "Search icons...", "アイコンを検索..."),
        ("ItemEditorDialog", "Cancel", "キャンセル"),
        ("SettingsWindow", "Menu Profiles", "メニュープロファイル"),
        ("HelpDialog", "How to Use", "使い方"),
        ("HelpDialog", "Settings", "設定"),
    ]

    all_passed = True
    for context, source, expected in test_cases:
        translated = app.translate(context, source)
        if translated == expected:
            print(f"✅ [{context}] '{source}' -> '{translated}'")
        else:
            print(f"❌ [{context}] '{source}' -> '{translated}' (Expected: '{expected}')")
            all_passed = False

    if all_passed:
        print("\nSUCCESS: All verified translations are correct.")
        sys.exit(0)
    else:
        print("\nFAILURE: Some translations are missing or incorrect.")
        sys.exit(1)


if __name__ == "__main__":
    # Ensure src is in path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    verify_translations()
