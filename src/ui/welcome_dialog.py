"""Welcome dialog shown on first run.

Displays an onboarding guide explaining how to use the pie menu
with a modern, visually appealing design.
"""

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.core.logger import get_logger

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
        self.resize(600, 450)
        self.setModal(True)

        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

        # Background Frame
        self.frame = QFrame()
        self.frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border-radius: 15px;
                border: 1px solid #e0e0e0;
            }
        """)
        frame_layout = QVBoxLayout()
        frame_layout.setSpacing(20)
        frame_layout.setContentsMargins(40, 40, 40, 40)
        self.frame.setLayout(frame_layout)
        layout.addWidget(self.frame)

        # Title
        title = QLabel(self.tr("Welcome to MixedBerryPie!"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #333; border: none;")
        frame_layout.addWidget(title)

        # Subtitle
        subtitle = QLabel(
            self.tr("Boost your productivity with a modern, fast, and customizable radial menu.")
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 14px; color: #666; margin-bottom: 20px; border: none;")
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
        self.close_btn.setFixedSize(200, 45)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 22px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(self.close_btn)
        btn_layout.addStretch()
        frame_layout.addLayout(btn_layout)

    def _add_step(self, layout: QVBoxLayout, title_text: str, desc_text: str) -> None:
        """Add a step to the welcome guide.

        Args:
            layout: Layout to add the step to
            title_text: Step title (e.g., '1️⃣ Press & Hold')
            desc_text: Step description
        """
        QHBoxLayout()

        title = QLabel(title_text)
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #333; border: none;")

        desc = QLabel(desc_text)
        desc.setStyleSheet("font-size: 14px; color: #555; border: none;")

        step_container = QFrame()
        step_container.setStyleSheet(
            "background-color: #f9f9f9; border-radius: 8px; padding: 10px; border: none;"
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
