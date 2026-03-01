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

        # Translations for HTML content
        t_usage_1 = self.tr("Press and hold your trigger key.")
        t_usage_2 = self.tr("Move mouse towards the item you want to select.")
        t_usage_3 = self.tr("Release the key to execute the action.")
        t_usage_hint = self.tr(
            "If you release without moving, the original key might be replayed (see settings)."
        )

        t_profiles_desc = self.tr(
            "You can define multiple profiles with different trigger keys and target applications."
        )

        t_label = self.tr("Label")
        t_action = self.tr("Action")
        t_color = self.tr("Color")

        t_icons_title = self.tr("Icons & Customization")
        t_icons_presets = self.tr("Presets")
        t_icons_presets_desc = self.tr("Choose from 1000+ curated icons sorted by categories.")
        t_icons_history = self.tr("History")
        t_icons_history_desc = self.tr(
            "Recently used external images are saved in the 'Recent' category."
        )
        t_icons_grid = self.tr("Dark Grid")
        t_icons_grid_desc = self.tr(
            "The icon picker uses a dark background so white icons are always visible."
        )

        t_set_delay = self.tr("Action Delay")
        t_set_opacity = self.tr("Menu Opacity")
        t_set_auto = self.tr("Auto Scale")

        t_tips_1 = self.tr("Right-click the system tray icon to access settings.")
        t_tips_2 = self.tr("You can export/import settings as JSON files for backup.")
        t_tips_3 = self.tr(
            "Use 'Target Apps' to limit a profile to specific software (e.g., Photoshop only)."
        )

        t_trouble_1 = self.tr(
            "If shortcuts don't trigger, check if another app is using the same hotkey."
        )
        t_trouble_2 = self.tr("Try increasing 'Key Input Interval' if some apps miss keystrokes.")

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
                <li>{t_usage_1}</li>
                <li>{t_usage_2}</li>
                <li>{t_usage_3}</li>
            </ol>
            <p class="hint">※ {t_usage_hint}</p>

            <h2>🗂️ {t_profiles}</h2>
            <p>{t_profiles_desc}</p>
            <ul>
                {profiles_html}
            </ul>

            <h2>⌨️ {t_shortcuts}</h2>
            <table>
                <tr>
                    <th>{t_label}</th>
                    <th>{t_action}</th>
                    <th>{t_color}</th>
                </tr>
                {shortcuts_html}
            </table>

            <h2>✨ {t_icons_title}</h2>
            <ul>
                <li><b>{t_icons_presets}:</b> {t_icons_presets_desc}</li>
                <li><b>{t_icons_history}:</b> {t_icons_history_desc}</li>
                <li><b>{t_icons_grid}:</b> {t_icons_grid_desc}</li>
            </ul>

            <h2>⚙️ {t_settings}</h2>
            <ul>
                <li><b>{t_set_delay}:</b> {settings.action_delay_ms}ms</li>
                <li><b>{t_set_opacity}:</b> {settings.menu_opacity}%</li>
                <li><b>{t_set_auto}:</b> {"Yes" if settings.auto_scale_with_menu else "No"}</li>
            </ul>

            <h2>💡 {t_tips}</h2>
            <ul>
                <li>{t_tips_1}</li>
                <li>{t_tips_2}</li>
                <li>{t_tips_3}</li>
            </ul>

            <h2>🔧 {t_trouble}</h2>
            <ul>
                <li>{t_trouble_1}</li>
                <li>{t_trouble_2}</li>
            </ul>
        </body>
        </html>
        """
        return html
