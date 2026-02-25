"""Help dialog showing keyboard shortcuts and usage instructions.

Displays comprehensive help information including:
- How to use the pie menu
- Configured shortcuts
- Current settings
- Tips and troubleshooting
"""

import html as html_module
from typing import Any

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QTextBrowser, QVBoxLayout

from src.core import config
from src.core.utils import is_dark_mode
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

        # Cache config for display
        self.profiles, self.settings = config.load_config()

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
        profiles = self.profiles
        settings = self.settings

        # Theme colors based on system preference
        dark = is_dark_mode()
        bg_color = "#1e1e1e" if dark else "#ffffff"
        text_color = "#d4d4d4" if dark else "#333333"
        header_color = "#569cd6" if dark else "#005a9e"
        sub_header_color = "#4ec9b0" if dark else "#0078d4"
        table_bg = "#252526" if dark else "#ffffff"
        table_border = "#3c3c3c" if dark else "#cccccc"
        row_even = "#2d2d30" if dark else "#f9f9f9"
        code_bg = "#3c3c3c" if dark else "#eeeeee"
        code_color = "#ce9178" if dark else "#a31515"
        link_color = "#3794ff" if dark else "#0066cc"

        # Build profiles summary
        profiles_html = ""
        for p in profiles:
            apps = (
                html_module.escape(", ".join(p.target_apps)) if p.target_apps else self.tr("Global")
            )
            profiles_html += (
                f"<li><b>{html_module.escape(p.name)}</b>: "
                f"<code>{html_module.escape(p.trigger_key)}</code> ({apps})</li>"
            )

        # Build shortcuts table (for the first profile)
        shortcuts_html = ""
        if profiles:
            p = profiles[0]
            for item in p.items:
                safe_label = html_module.escape(item.label)
                safe_key = html_module.escape(item.key)
                # color は既知の hex 形式 (#RRGGBB) のみ許可
                safe_color = (
                    item.color if item.color.startswith("#") and len(item.color) <= 9 else "#888888"
                )
                shortcuts_html += f"""
                <tr>
                    <td style="padding: 5px;"><b>{safe_label}</b></td>
                    <td style="padding: 5px; font-family: monospace;">{safe_key}</td>
                    <td style="padding: 5px; background-color: {safe_color}; width: 30px;"></td>
                </tr>
                """

        # Translations
        t_usage = self.tr("How to Use")
        t_profiles = self.tr("Menu Profiles")
        t_shortcuts = self.tr("Default Profile Items")
        t_settings = self.tr("Global Settings")
        t_tips = self.tr("Tips & Tricks")
        t_trouble = self.tr("Troubleshooting")

        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', 'Yu Gothic UI', sans-serif;
                    background-color: {bg_color};
                    color: {text_color};
                    padding: 10px;
                    line-height: 1.4;
                }}
                h2 {{
                    color: {header_color};
                    border-bottom: 1px solid {table_border};
                    padding-bottom: 5px;
                    margin-top: 24px;
                }}
                h3 {{ color: {sub_header_color}; margin-top: 20px; }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 10px 0;
                    background-color: {table_bg};
                }}
                th, td {{
                    text-align: left;
                    padding: 8px;
                    border: 1px solid {table_border};
                }}
                th {{
                    background-color: #007acc;
                    color: white;
                }}
                tr:nth-child(even) {{
                    background-color: {row_even};
                }}
                code {{
                    background-color: {code_bg};
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-family: Consolas, monospace;
                    color: {code_color};
                }}
                .key {{
                    background-color: #007acc;
                    color: white;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 0.9em;
                }}
                ul, ol {{ padding-left: 20px; }}
                li {{ margin-bottom: 6px; }}
                a {{ color: {link_color}; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                .hint {{ font-style: italic; font-size: 0.9em; opacity: 0.8; }}
            </style>
        </head>
        <body>
            <h2>📖 {t_usage}</h2>
            <ol>
                <li>{self.tr("Press and hold your trigger key.")}</li>
                <li>{self.tr("Move mouse towards the item you want to select.")}</li>
                <li>{self.tr("Release the key to execute the action.")}</li>
            </ol>
            <p class="hint">※ {self.tr("If you release without moving, the original key might be replayed (see settings).")}</p>

            <h2>🗂️ {t_profiles}</h2>
            <p>{self.tr("You can define multiple profiles with different trigger keys and target applications.")}</p>
            <ul>
                {profiles_html}
            </ul>

            <h2>⌨️ {t_shortcuts}</h2>
            <table>
                <tr>
                    <th>{self.tr("Label")}</th>
                    <th>{self.tr("Action")}</th>
                    <th>{self.tr("Color")}</th>
                </tr>
                {shortcuts_html}
            </table>

            <h2>✨ {self.tr("Icons & Customization")}</h2>
            <ul>
                <li><b>{self.tr("Presets")}:</b> {self.tr("Choose from 1000+ curated icons sorted by categories.")}</li>
                <li><b>{self.tr("History")}:</b> {self.tr("Recently used external images are saved in the 'Recent' category.")}</li>
                <li><b>{self.tr("Dark Grid")}:</b> {self.tr("The icon picker uses a dark background so white icons are always visible.")}</li>
            </ul>

            <h2>⚙️ {t_settings}</h2>
            <ul>
                <li><b>{self.tr("Action Delay")}:</b> {settings.action_delay_ms}ms</li>
                <li><b>{self.tr("Menu Opacity")}:</b> {settings.menu_opacity}%</li>
                <li><b>{self.tr("Auto Scale")}:</b> {"Yes" if settings.auto_scale_with_menu else "No"}</li>
            </ul>

            <h2>💡 {t_tips}</h2>
            <ul>
                <li>{self.tr("Right-click the system tray icon to access settings.")}</li>
                <li>{self.tr("You can export/import settings as JSON files for backup.")}</li>
                <li>{self.tr("Use 'Target Apps' to limit a profile to specific software (e.g., Photoshop only).")}</li>
            </ul>

            <h2>🔧 {t_trouble}</h2>
            <ul>
                <li>{self.tr("If shortcuts don't trigger, check if another app is using the same hotkey.")}</li>
                <li>{self.tr("Try increasing 'Key Input Interval' if some apps miss keystrokes.")}</li>
            </ul>
        </body>
        </html>
        """
        return html
