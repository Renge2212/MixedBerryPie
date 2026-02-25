"""Welcome dialog shown on first run.

Displays an onboarding guide explaining how to use the pie menu
with a modern, visually appealing design.
"""

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.core.logger import get_logger
from src.core.utils import is_dark_mode

logger = get_logger(__name__)


class WelcomeDialog(QDialog):
    """Welcome dialog for first-time users.

    Shows a step-by-step guide on how to use the pie menu
    with a modern, frameless design and gradient styling.
    """

    def __init__(self, parent: QDialog | None = None) -> None:
        """Initialize the welcome dialog.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(600, 500)
        self.setModal(True)

        dark = is_dark_mode()
        bg_color = "#1e1e1e" if dark else "#ffffff"
        title_color = "#ffffff" if dark else "#111111"
        sub_color = "#bbbbbb" if dark else "#555555"
        border_color = "#333333" if dark else "#e0e0e0"

        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

        # Background Frame
        self.frame = QFrame()
        self.frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 15px;
                border: 1px solid {border_color};
            }}
        """)
        frame_layout = QVBoxLayout()
        frame_layout.setSpacing(20)
        frame_layout.setContentsMargins(40, 40, 40, 40)
        self.frame.setLayout(frame_layout)
        layout.addWidget(self.frame)

        # Title
        title = QLabel(self.tr("Welcome to MixedBerryPie!"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: 26px; font-weight: bold; color: {title_color}; border: none;"
        )
        frame_layout.addWidget(title)

        # Subtitle
        subtitle = QLabel(
            self.tr("Boost your productivity with a modern, fast, and customizable radial menu.")
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"font-size: 15px; color: {sub_color}; margin-bottom: 20px; border: none;"
        )
        frame_layout.addWidget(subtitle)

        # Steps
        steps_layout = QVBoxLayout()
        steps_layout.setSpacing(15)

        self._add_step(
            steps_layout,
            "1️⃣ " + self.tr("Press & Hold"),
            self.tr("Hold your trigger key (Default: Ctrl+Space)"),
        )
        self._add_step(
            steps_layout,
            "2️⃣ " + self.tr("Move Mouse"),
            self.tr("Move cursor towards the action you want"),
        )
        self._add_step(
            steps_layout, "3️⃣ " + self.tr("Release"), self.tr("Release the key to execute!")
        )

        frame_layout.addLayout(steps_layout)

        frame_layout.addStretch()

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #eee; border: none; max-height: 1px;")
        frame_layout.addWidget(line)

        # Footer / Tip
        tip = QLabel(self.tr("You can access Settings from the System Tray icon."))
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet("font-size: 12px; color: #888; border: none; margin-top: 10px;")
        frame_layout.addWidget(tip)

        # Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.close_btn = QPushButton(self.tr("Get Started"))
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setFixedSize(220, 48)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 24px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.close_btn.clicked.connect(self._on_accept)

        btn_layout.addWidget(self.close_btn)
        btn_layout.addStretch()
        frame_layout.addLayout(btn_layout)

    def _on_accept(self) -> None:
        """Handle completion of the welcome dialog."""
        self.accept()

    def _add_step(self, layout: QVBoxLayout, title_text: str, desc_text: str) -> None:
        """Add a step to the welcome guide."""
        dark = is_dark_mode()
        title_color = "#ffffff" if dark else "#333333"
        desc_color = "#aaaaaa" if dark else "#666666"
        bg_color = "#2d2d2d" if dark else "#f7f7f7"

        title = QLabel(title_text)
        title.setStyleSheet(
            f"font-weight: bold; font-size: 16px; color: {title_color}; border: none;"
        )

        desc = QLabel(desc_text)
        desc.setStyleSheet(f"font-size: 14px; color: {desc_color}; border: none;")

        step_container = QFrame()
        step_container.setStyleSheet(
            f"background-color: {bg_color}; border-radius: 10px; padding: 10px; border: none;"
        )
        step_cont_layout = QVBoxLayout()
        step_cont_layout.addWidget(title)
        step_cont_layout.addWidget(desc)
        step_container.setLayout(step_cont_layout)

        layout.addWidget(step_container)

    def paintEvent(self, event: QEvent | None) -> None:
        """Handle paint events.

        Args:
            event: Paint event object

        Note:
            Drop shadow effect is simulated via translucent window.
            For simplicity, we rely on the frame border.
        """
        pass
