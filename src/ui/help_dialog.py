"""Help dialog showing keyboard shortcuts and usage instructions.

Displays comprehensive help information including:
- How to use the pie menu
- Configured shortcuts
- Current settings
- Tips and troubleshooting
"""

from typing import Any

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QTextBrowser, QVBoxLayout

from src.core import config
from src.core.version import __version__


class HelpDialog(QDialog):
    """Dialog window displaying help and usage information.

    Shows keyboard shortcuts, settings, tips, and troubleshooting information
    in a formatted HTML view with dark theme styling.
    """

    def __init__(self, parent: QDialog | None = None) -> None:
        """Initialize the help dialog.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        # Title set in retranslateUi
        self.setModal(False)
        self.resize(500, 600)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Title
        title = QLabel(f"MixedBerryPie v{__version__}")
        title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Help content
        self.help_text = QTextBrowser()
        self.help_text.setOpenExternalLinks(True)
        # Content set in retranslateUi
        layout.addWidget(self.help_text)

        # Close button
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)

        self.retranslateUi()

    def retranslateUi(self) -> None:
        """Update UI text with current translations."""
        self.setWindowTitle(self.tr("MixedBerryPie Help"))
        self.close_btn.setText(self.tr("Close"))
        self.help_text.setHtml(self._generate_help_html())

    def changeEvent(self, event: Any) -> None:
        """Handle language change events.

        Args:
            event: Qt event object
        """
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def _generate_help_html(self) -> str:
        """Generate HTML help content."""
        profiles, settings = config.load_config()

        # Use formatting from the first profile
        if profiles:
            profile = profiles[0]
            items = profile.items
            trigger_key = profile.trigger_key
        else:
            items = []
            trigger_key = "未設定"

        # Build shortcuts table
        shortcuts_html = ""
        for item in items:
            shortcuts_html += f"""
            <tr>
                <td style="padding: 5px;"><b>{item.label}</b></td>
                <td style="padding: 5px; font-family: monospace;">{item.key}</td>
                <td style="padding: 5px; background-color: {item.color}; width: 30px;"></td>
            </tr>
            """

        t_how_to_use = self.tr("How to Use")
        t_step1 = self.tr("Press Trigger Key:")
        t_step2 = self.tr("Pie menu will appear around the mouse cursor position")
        t_step3 = self.tr("Move mouse to select an item (highlighted)")
        t_step4 = self.tr("Release the trigger key to execute the selected action")
        t_step5 = self.tr(
            "Release without selection to replay original key (depending on settings)"
        )
        t_shortcuts = self.tr("Configured Shortcuts")
        t_default_profile = self.tr("Showing default profile")
        t_label = self.tr("Label")
        t_action = self.tr("Action")
        t_color = self.tr("Color")

        t_settings = self.tr("Current Settings")
        t_trigger_key = self.tr("Trigger Key:")
        t_action_delay = self.tr("Action Delay:")
        t_overlay_size = self.tr("Menu Size:")

        t_tips = self.tr("Tips")
        t_tip1_tray = self.tr("Right-click tray icon to open settings")
        t_tip2_cust = self.tr("Customize colors, labels, and shortcuts in settings")
        t_tip3_any = self.tr("MixedBerryPie works in all applications")
        t_tip4_logs = self.tr("Log file location:")
        t_tip5_trouble = self.tr("(For troubleshooting)")

        t_troubleshooting = self.tr("Troubleshooting")
        t_ts1_delay = self.tr(
            "If actions don't execute, try increasing the action delay in settings"
        )
        t_ts2_conflict = self.tr(
            "If trigger key doesn't respond, check for conflicts with other apps"
        )
        t_ts3_log = self.tr("Check the log file for detailed errors")

        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', 'Yu Gothic UI', sans-serif;
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    padding: 10px;
                }}
                h2 {{
                    color: #569cd6;
                    border-bottom: 1px solid #3c3c3c;
                    padding-bottom: 5px;
                    margin-top: 20px;
                }}
                h3 {{ color: #4ec9b0; margin-top: 20px; }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 10px 0;
                    background-color: #252526;
                }}
                th, td {{
                    text-align: left;
                    padding: 8px;
                    border: 1px solid #3c3c3c;
                }}
                th {{
                    background-color: #007acc;
                    color: white;
                }}
                tr:nth-child(even) {{
                    background-color: #2d2d30;
                }}
                code {{
                    background-color: #3c3c3c;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-family: Consolas, monospace;
                    color: #ce9178;
                }}
                .key {{
                    background-color: #007acc;
                    color: white;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                ul, ol {{ padding-left: 20px; }}
                li {{ margin-bottom: 5px; }}
                a {{ color: #3794ff; }}
            </style>
        </head>
        <body>
            <h2>📖 {t_how_to_use}</h2>
            <ol>
                <li>{t_step1} <span class="key">{trigger_key}</span></li>
                <li>{t_step2}</li>
                <li>{t_step3}</li>
                <li>{t_step4}</li>
                <li>{t_step5}</li>
            </ol>

            <h2>⌨️ {t_shortcuts}</h2>
            <p>※ {t_default_profile}</p>
            <table>
                <tr>
                    <th>{t_label}</th>
                    <th>{t_action}</th>
                    <th>{t_color}</th>
                </tr>
                {shortcuts_html}
            </table>

            <h2>⚙️ {t_settings}</h2>
            <ul>
                <li><b>{t_trigger_key}</b> <code>{trigger_key}</code></li>
                <li><b>{t_action_delay}</b> {settings.action_delay_ms}ms</li>
                <li><b>{t_overlay_size}</b> {settings.overlay_size}px</li>
            </ul>

            <h2>💡 {t_tips}</h2>
            <ul>
                <li>{t_tip1_tray}</li>
                <li>{t_tip2_cust}</li>
                <li>{t_tip3_any}</li>
                <li>{t_tip4_logs} <code>logs/mixedberrypie.log</code> {t_tip5_trouble}</li>
            </ul>

            <h2>🔧 {t_troubleshooting}</h2>
            <ul>
                <li>{t_ts1_delay}</li>
                <li>{t_ts2_conflict}</li>
                <li>{t_ts3_log}</li>
            </ul>
        </body>
        </html>
        """

        return html
