import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtWidgets import QApplication, QLabel

from src.core.i18n import install_translator
from src.ui.welcome_dialog import WelcomeDialog


def verify():
    # Create headless application (or minimal)
    app = QApplication(sys.argv)

    # Force install Japanese translator
    print("Installing Japanese translator...")
    install_translator(app, "ja")

    print("Initializing WelcomeDialog...")
    dialog = WelcomeDialog()

    # Find all QLabels to check text
    labels = dialog.findChildren(QLabel)
    texts = [label.text() for label in labels]

    expected_substrings = [
        "Pie Menu へようこそ！",
        "長押し",
        "トリガーキーを押し続けます（デフォルト: Ctrl+Space）",
    ]

    missing = []
    print("\nVerifying translations...")
    for expected in expected_substrings:
        found = False
        for t in texts:
            if expected in t:
                found = True
                break
        if not found:
            missing.append(expected)

    if missing:
        print("\n❌ FAILED: Missing translations:")
        for m in missing:
            print(f" - {m}")
        print("\nFound texts in dialog:")
        for t in texts:
            print(f" - {t}")
        sys.exit(1)
    else:
        print("\n✅ SUCCESS: All expected Japanese translations found.")
        sys.exit(0)


if __name__ == "__main__":
    verify()
