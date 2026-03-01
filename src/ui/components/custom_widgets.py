import contextlib
import os
from typing import Any

from PyQt6.QtCore import (
    QEvent,
    QMimeData,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QDrag,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.config import PieSlice
from src.core.logger import get_logger
from src.core.utils import is_dark_mode, resolve_icon_path

logger = get_logger(__name__)


def _render_icon_pixmap(path: str | None, size: int) -> QPixmap | None:
    """Render an icon from path to a QPixmap, supporting SVG and raster formats.

    Args:
        path: Absolute path to the icon file (SVG or any Qt-supported raster format).
        size: Target square size in pixels.

    Returns:
        Scaled QPixmap, or None if path is invalid or file cannot be loaded.
    """
    if not path or not os.path.exists(path):
        return None

    if path.lower().endswith(".svg"):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(path)
        if renderer.isValid():
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            renderer.render(painter)
            painter.end()
            return pixmap
        return None
    else:
        # Standard raster icon (PNG, JPG, ICO, etc.) processing
        from PyQt6.QtGui import QIcon

        return QIcon(path).pixmap(size, size)


class KeySequenceEdit(QLineEdit):
    """Custom QLineEdit for recording key sequences."""

    recording_toggled = pyqtSignal(bool)

    def __init__(self, key_str: str = "") -> None:
        super().__init__(key_str)
        self.mode = "key"  # 'key' or 'text'
        self.setIsRecording(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def setMode(self, mode: str) -> None:
        """Set the edit mode ('key' or 'text')."""
        if self.mode == mode:
            return

        self.mode = mode
        if mode == "text":
            self.setReadOnly(False)
            self.setPlaceholderText(self.tr("Enter text..."))
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
            # Reset style to default
            dark = is_dark_mode()
            bg = "#333" if dark else "#f9f9f9"
            border = "#555" if dark else "#ccc"
            text = "#fff" if dark else "#000"
            self.setStyleSheet(
                f"QLineEdit {{ background-color: {bg}; border: 1px solid {border}; color: {text}; border-radius: 4px; }}"
            )
            self.setIsRecording(False)
        else:
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            self.setIsRecording(False)

    def setIsRecording(self, recording: bool) -> None:
        """Set the recording state and update UI."""
        if self.mode == "text":
            return  # No recording in text mode

        if getattr(self, "recording", None) != recording:
            self.recording = recording
            self.recording_toggled.emit(recording)

        self.recording = recording
        dark = is_dark_mode()
        if recording:
            self.setPlaceholderText(self.tr("Press keys..."))
            bg = "#4a1515" if dark else "#ffe0e0"
            border = "#ff5555"
            text = "#ffcccc" if dark else "#d00000"
            self.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {bg};
                    border: 2px solid {border};
                    color: {text};
                    font-weight: bold;
                }}
            """)
        else:
            self.setPlaceholderText(self.tr("Click to record keys"))
            bg = "#333" if dark else "#f9f9f9"
            border = "#555" if dark else "#ccc"
            text = "#fff" if dark else "#000"
            hover_bg = "#3d3d3d" if dark else "#e0f7fa"
            self.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {bg};
                    border: 1px solid {border};
                    color: {text};
                    border-radius: 4px;
                }}
                QLineEdit:hover {{
                    background-color: {hover_bg};
                    border: 1px solid #0078d4;
                }}
            """)

    def mousePressEvent(self, event):
        if self.mode == "text":
            super().mousePressEvent(event)
            return

        self.setIsRecording(True)
        self.setText("")
        self.setFocus()
        event.accept()

    def event(self, event):
        if (
            self.recording
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Tab
        ):
            self.keyPressEvent(event)
            return True
        return super().event(event)

    def focusOutEvent(self, event):
        if self.mode == "key":
            self.setIsRecording(False)
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if self.mode == "text":
            super().keyPressEvent(event)
            return

        if not event or not self.recording:
            return

        key = event.key()
        modifiers = event.modifiers()
        event.accept()

        if key == Qt.Key.Key_Escape:
            self.setIsRecording(False)
            self.setText("")
            self.clearFocus()
            return

        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.setText("")
            self.setIsRecording(False)
            self.clearFocus()
            return

        is_modifier = key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta)

        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("windows")

        text = QKeySequence(key).toString().lower()
        key_map = {"return": "enter", "escape": "esc", "space": "space"}
        text = key_map.get(text, text)

        # Only append text if it's not a modifier key that was already handled
        if text and not is_modifier:
            parts.append(text)
        elif is_modifier and not parts:
            # Fallback for when only a modifier is pressed and we want to show it
            if key == Qt.Key.Key_Control:
                parts.append("ctrl")
            elif key == Qt.Key.Key_Shift:
                parts.append("shift")
            elif key == Qt.Key.Key_Alt:
                parts.append("alt")
            elif key == Qt.Key.Key_Meta:
                parts.append("windows")

        final_key = "+".join(parts)
        self.setText(final_key)

        # Only finalize if a non-modifier key was pressed
        if not is_modifier:
            self.setIsRecording(False)
            self.clearFocus()


class SteppedSlider(QWidget):
    """A slider that snaps to a fixed list of preset values."""

    value_changed = pyqtSignal(int)

    def __init__(self, steps: list[int], suffix: str = "", parent=None):
        super().__init__(parent)
        self.steps = steps
        self.suffix = suffix
        self._current_index = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, len(steps) - 1)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(1)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.value_label = QLabel()
        self.value_label.setFixedWidth(40)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self.slider)
        layout.addWidget(self.value_label)
        self._update_label()

    def _on_slider_changed(self, index: int):
        self._current_index = index
        self._update_label()
        self.value_changed.emit(self.value())

    def _update_label(self):
        self.value_label.setText(f"{self.value()}{self.suffix}")

    def value(self) -> int:
        return self.steps[self._current_index]

    def setValue(self, val: int):
        if val in self.steps:
            self.slider.setValue(self.steps.index(val))
        else:
            # Find closest
            closest = min(self.steps, key=lambda x: abs(x - val))
            self.slider.setValue(self.steps.index(closest))


class FlowLayout(QLayout):
    """Standard FlowLayout implementation for Qt."""

    def __init__(self, parent=None, margin=-1, hspacing=-1, vspacing=-1):
        super().__init__(parent)
        self._hspacing = hspacing
        self._vspacing = vspacing
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        del self._items[:]

    def addItem(self, item):
        self._items.append(item)

    def horizontalSpacing(self):
        if self._hspacing >= 0:
            return self._hspacing
        else:
            return self.smartSpacing(QStyle.PixelMetric.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self._vspacing >= 0:
            return self._vspacing
        else:
            return self.smartSpacing(QStyle.PixelMetric.PM_LayoutVerticalSpacing)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def smartSpacing(self, pm: QStyle.PixelMetric) -> int:
        parent = self.parent()
        if parent is None:
            return -1
        if isinstance(parent, QWidget):
            style = parent.style()
            if style:
                return style.pixelMetric(pm, None, parent)
        if isinstance(parent, QLayout):
            return parent.spacing()
        return -1

    def _doLayout(self, rect, test_only):
        m = self.contentsMargins()
        left, top, right, bottom = m.left(), m.top(), m.right(), m.bottom()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._items:
            widget = item.widget()
            space_x = self.horizontalSpacing()
            style = widget.style()
            if space_x == -1 and style:
                space_x = style.pixelMetric(QStyle.PixelMetric.PM_LayoutHorizontalSpacing)
            space_y = self.verticalSpacing()
            if space_y == -1 and style:
                space_y = style.pixelMetric(QStyle.PixelMetric.PM_LayoutVerticalSpacing)

            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + bottom


class AppTagWidget(QFrame):
    """A small label showing a target app with a remove button."""

    removed = pyqtSignal(str)

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.text = text
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName("AppTag")

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(5)
        self.setLayout(layout)

        self.label = QLabel(text)
        layout.addWidget(self.label)

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(lambda: self.removed.emit(self.text))
        layout.addWidget(self.close_btn)

        self._apply_style()

    def _apply_style(self):
        dark = is_dark_mode()
        bg = "#444" if dark else "#e1e4e8"
        border = "#666" if dark else "#d1d5da"
        self.setStyleSheet(
            f"""
            QFrame#AppTag {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
                font-size: 11px;
                padding-bottom: 1px;
            }}
            QPushButton {{
                background: transparent;
                border: none;
                color: #888;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
                margin-top: -2px;
            }}
            QPushButton:hover {{
                color: #ff5555;
            }}
        """
        )


class AppPickerDialog(QDialog):
    """Dialog to pick from running applications."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Select App"))
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.lbl_info = QLabel(
            self.tr("Select an application from the running windows to add it to target apps.")
        )
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)

        self.table = QTreeWidget()
        self.table.setColumnCount(2)
        self.table.setHeaderLabels([self.tr("Process"), self.tr("Window Title")])
        header = self.table.header()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setRootIsDecorated(False)
        self.table.setIndentation(0)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Remove focus rectangle
        self.table.itemDoubleClicked.connect(lambda *_: self.accept())
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton(self.tr("Refresh"))
        self.btn_refresh.clicked.connect(self._refresh_list)
        self.btn_cancel = QPushButton(self.tr("Cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton(self.tr("Add Selected"))
        self.btn_ok.clicked.connect(self.accept)
        self.btn_ok.setStyleSheet("background-color: #2da44e; color: white; font-weight: bold;")

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

        self.selected_app = None
        self._refresh_list()

    def _refresh_list(self) -> None:
        self.table.clear()
        try:
            from src.core.win32_input import get_open_windows

            windows = get_open_windows()
            for exe_name, title in windows:
                item = QTreeWidgetItem([exe_name, title])
                item.setData(0, Qt.ItemDataRole.UserRole, exe_name)
                self.table.addTopLevelItem(item)
        except Exception as e:
            logger.error(f"Failed to list open windows: {e}")

    def accept(self):
        items = self.table.selectedItems()
        if items:
            # Item 0 is the QTreeWidgetItem, role data is at column 0
            self.selected_app = items[0].data(0, Qt.ItemDataRole.UserRole)
            super().accept()
        else:
            QMessageBox.warning(
                self,
                self.tr("Selection Required"),
                self.tr("Please select an application from the list."),
            )

    def get_selected_app(self):
        return self.selected_app


class PieItemWidget(QFrame):
    """Custom widget representing a single pie menu item in the list."""

    clicked = pyqtSignal(object)
    double_clicked = pyqtSignal(object)
    enter_submenu = pyqtSignal(object)
    item_dropped = pyqtSignal(object, object, str)  # source, target, action

    def __init__(self, item: PieSlice, parent=None, color_mode="individual"):
        super().__init__(parent)
        self.item = item
        self.selected = False
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(64)
        self.setAcceptDrops(False)
        self._drag_start_pos: QPoint | None = None
        self._is_dragging_me = False

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)
        self.setLayout(layout)

        # Color indicator
        self.color_box = QFrame()
        self.color_box.setFixedSize(18, 18)
        self.color_box.setStyleSheet(
            f"background-color: {item.color}; border: 1px solid rgba(255,255,255,0.2); border-radius: 9px;"
        )  # Circle shape
        layout.addWidget(self.color_box)
        if color_mode != "individual":
            self.color_box.setVisible(False)

        # Labels
        self.label_text = QLabel(item.label)
        self.label_text.setStyleSheet("font-weight: 500; font-size: 14px;")
        layout.addWidget(self.label_text, 1)

        self.action_text = QLabel(item.key if item.action_type != "submenu" else self.tr("Submenu"))
        self.action_text.setStyleSheet(
            "font-family: 'Segoe UI Semibold', monospace; font-size: 12px;"
        )
        layout.addWidget(self.action_text)

        if item.action_type == "submenu":
            self.btn_enter = QPushButton(self.tr("Enter ➔"))
            self.btn_enter.setObjectName("enterSubmenuBtn")
            self.btn_enter.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_enter.clicked.connect(self._on_enter_clicked)
            layout.addWidget(self.btn_enter)

        # Icon (if present)
        if item.icon_path:
            icon_label = QLabel()
            resolved_path = resolve_icon_path(item.icon_path)
            pixmap = _render_icon_pixmap(resolved_path, 24)
            if pixmap is not None:
                icon_label.setPixmap(pixmap)
                # Give icon a slight dark background for visibility of light icons
                icon_label.setObjectName("pieItemIcon")
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_label.setFixedSize(28, 28)
                layout.insertWidget(0, icon_label)

        self._update_style()

    def _update_style(self):
        with contextlib.suppress(RuntimeError):
            dark = is_dark_mode()
            if self._is_dragging_me:
                # Use semi-transparent colors during drag to indicate "lifting"
                bg_color = "rgba(45, 45, 45, 0.4)" if dark else "rgba(200, 200, 200, 0.6)"
                border_color = "rgba(0, 120, 212, 0.5)"
                text_color = "#999"
                action_color = "#aaa"
            elif self.selected:
                bg_color = "rgba(0, 120, 212, 0.8)"
                border_color = "#0078d4"
                text_color = "white"
                action_color = "#e0eefe"
            else:
                bg_color = "rgba(45, 45, 45, 0.5)" if dark else "rgba(255, 255, 255, 0.9)"
                border_color = "rgba(255, 255, 255, 0.1)" if dark else "rgba(0, 0, 0, 0.1)"
                text_color = "#e0e0e0" if dark else "#333"
                action_color = "#888"

            hover_bg = (
                "rgba(0, 120, 212, 0.9)"
                if self.selected
                else ("rgba(60, 60, 60, 0.8)" if dark else "rgba(230, 240, 250, 0.8)")
            )

            self.setStyleSheet(f"""
                PieItemWidget {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 10px;
                    margin: 4px 6px;
                }}
                PieItemWidget:hover {{
                    background-color: {hover_bg};
                }}
                QLabel {{
                    color: {text_color};
                    background: transparent;
                }}
                QLabel#pieItemIcon {{
                    background-color: {"rgba(30,30,30,0.4)" if dark else "rgba(30, 30, 30, 0.8)"};
                    border-radius: 4px;
                }}
                QPushButton#enterSubmenuBtn {{
                    font-size: 13px;
                    padding: 8px 20px;
                    font-weight: bold;
                    color: white;
                    background-color: rgba(0, 120, 212, 0.4);
                    border: 1px solid rgba(0, 120, 212, 0.6);
                    border-radius: 6px;
                }}
                QPushButton#enterSubmenuBtn:hover {{
                    background-color: rgba(0, 120, 212, 0.9);
                    border: 1px solid #0078d4;
                }}
                QPushButton#enterSubmenuBtn:pressed {{
                    background-color: #005a9e;
                }}
            """)
            self.action_text.setStyleSheet(
                f"color: {action_color}; background: transparent; padding: 2px 6px; border-radius: 4px; background-color: rgba(0,0,0,0.1);"
            )

    def setSelected(self, selected: bool) -> None:
        self.selected = selected
        with contextlib.suppress(RuntimeError):
            self._update_style()

    def mouseDoubleClickEvent(self, event: Any) -> None:
        self.double_clicked.emit(self)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        self.clicked.emit(self)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton) or not self._drag_start_pos:
            return
        if (
            event.pos() - self._drag_start_pos
        ).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText("pie_item_drag")
        drag.setMimeData(mime)

        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.position().toPoint())

        self._is_dragging_me = True
        self.hide()
        self._update_style()
        drag.exec(Qt.DropAction.MoveAction)
        self._is_dragging_me = False
        self.show()
        self._update_style()

    def _on_enter_clicked(self):
        self.enter_submenu.emit(self)


class ColorStripWidget(QWidget):
    """A small widget that shows a series of color blocks to visualize a palette."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color_palette: list[str] = []
        self.setFixedWidth(120)
        self.setFixedHeight(18)

    def set_palette(self, palette: list[str]) -> None:
        self.color_palette = palette
        self.update()

    def paintEvent(self, event):
        if not self.color_palette:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        n = len(self.color_palette)
        w = self.width() / n
        h = self.height()

        for i, color_str in enumerate(self.color_palette):
            color = QColor(color_str)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            # Rounded corners for the strip
            rect = QRectF(i * w, 0, w, h)
            if n == 1:
                painter.drawRoundedRect(rect, 4, 4)
            elif i == 0:
                # Round left only (fake it with a path or just use rect and round the whole strip container?)
                # Simplest: draw a path or just use drawRect for middle ones.
                path = QPainterPath()
                path.addRoundedRect(rect, 4, 4)
                painter.fillPath(path, QBrush(color))
                # Cover right part to make it square
                painter.fillRect(int(i * w + w / 2), 0, int(w / 2 + 1), int(h), color)
            elif i == n - 1:
                path = QPainterPath()
                path.addRoundedRect(rect, 4, 4)
                painter.fillPath(path, QBrush(color))
                # Cover left part
                painter.fillRect(int(i * w), 0, int(w / 2 + 1), int(h), color)
            else:
                painter.fillRect(rect, color)


class PlaceholderWidget(QFrame):
    """A drop indicator line used to show where a dragged item will land."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(16, 0, -16, 0)

        color = QColor("#0078d4")
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 2, 2)
