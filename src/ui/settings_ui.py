import contextlib
import math
import os
import winreg
from typing import Any

from PyQt6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QStyle,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core import config, i18n
from src.core.config import MenuProfile, PieSlice
from src.core.logger import get_logger
from src.core.utils import get_resource_path, resolve_icon_path

logger = get_logger(__name__)


def is_dark_mode():
    """Check Windows registry for dark mode preference."""
    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(
            registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except Exception:
        return True  # Default to dark


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
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(1)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.value_label = QLabel()
        self.value_label.setFixedWidth(60)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet(
            "font-weight: bold; background: rgba(0,0,0,0.1); border-radius: 4px; padding: 2px 4px;"
        )

        layout.addWidget(self.slider)
        layout.addWidget(self.value_label)
        self._update_label()

    def _on_slider_changed(self, index: int):
        self._current_index = index
        self._update_label()
        self.value_changed.emit(self.steps[index])

    def _update_label(self):
        val = self.steps[self._current_index]
        self.value_label.setText(f"{val}{self.suffix}")

    def value(self) -> int:
        return self.steps[self._current_index]

    def setValue(self, val: int):
        # Find closest step
        closest = min(range(len(self.steps)), key=lambda i: abs(self.steps[i] - val))
        self.slider.setValue(closest)


class IconLoaderThread(QThread):
    """Worker thread to load and render SVG icons asynchronously."""

    icon_loaded = pyqtSignal(str, str, QIcon)  # relative_path, name, icon
    finished_loading = pyqtSignal()

    def __init__(self, icons_dir: str, files: list[str], parent=None):
        super().__init__(parent)
        self.icons_dir = icons_dir
        self.files = files
        self._is_cancelled = False

    def run(self):
        for filename in self.files:
            if self._is_cancelled:
                break

            path = os.path.join(self.icons_dir, filename)
            name = os.path.splitext(filename)[0]

            # High quality render
            render_size = 64
            pixmap = QPixmap(render_size, render_size)
            pixmap.fill(Qt.GlobalColor.transparent)

            renderer = QSvgRenderer(path)
            if renderer.isValid():
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()

                icon = QIcon(pixmap)
                relative_path = f"icons/{filename}"
                self.icon_loaded.emit(relative_path, name, icon)

        self.finished_loading.emit()

    def cancel(self):
        self._is_cancelled = True


class IconPickerWidget(QDialog):
    """Dialog to select from preset icons with search functionality."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Select Icon"))
        self.setModal(True)
        self.resize(800, 600)
        self.selected_icon_path = None
        self._loader_thread: IconLoaderThread | None = None
        self._loaded_count = 0

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("Search icons..."))
        self.search_input.textChanged.connect(self._filter_icons)
        search_layout.addWidget(QLabel(self.tr("Search:")))
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Icon List (Grid Mode)
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setSpacing(5)
        # Fix grid size to ensure uniform layout
        self.list_widget.setGridSize(QSize(72, 80))
        self.list_widget.setIconSize(QSize(48, 48))
        self.list_widget.setWordWrap(True)
        self.list_widget.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)

        self._load_icons()

        btn_box = QHBoxLayout()
        self.status_label = QLabel(self.tr("{} icons loaded").format(self.list_widget.count()))
        btn_box.addWidget(self.status_label)
        btn_box.addStretch()

        ok_btn = QPushButton(self.tr("OK"))
        ok_btn.clicked.connect(self._confirm_selection)
        cancel_btn = QPushButton(self.tr("Cancel"))
        cancel_btn.clicked.connect(self.reject)

        btn_box.addWidget(ok_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def _load_icons(self):
        icons_dir = get_resource_path(os.path.join("resources", "icons"))
        if not os.path.exists(icons_dir):
            return

        files = [f for f in os.listdir(icons_dir) if f.lower().endswith(".svg")]
        files.sort()

        self.status_label.setText(self.tr("Loading icons..."))
        self.list_widget.clear()
        self._loaded_count = 0

        # Start background worker thread
        self._loader_thread = IconLoaderThread(icons_dir, files, self)
        self._loader_thread.icon_loaded.connect(self._on_icon_loaded)
        self._loader_thread.finished_loading.connect(self._on_loading_finished)
        self._loader_thread.start()

    def _on_icon_loaded(self, relative_path: str, name: str, icon: QIcon):
        item = QListWidgetItem(icon, name)
        item.setData(Qt.ItemDataRole.UserRole, relative_path)
        item.setToolTip(name)
        self.list_widget.addItem(item)

        self._loaded_count += 1
        # Update status periodically to prevent UI chugging
        if self._loaded_count % 50 == 0:
            self.status_label.setText(self.tr("Loaded {} icons...").format(self._loaded_count))

        # Immediately apply filter if one is typed
        current_filter = self.search_input.text().lower().strip()
        if current_filter and current_filter not in name.lower():
            item.setHidden(True)

    def _on_loading_finished(self):
        self.status_label.setText(self.tr("{} icons loaded").format(self._loaded_count))
        # Re-apply filter to be safe
        self._filter_icons(self.search_input.text())

    def reject(self):
        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.cancel()
            self._loader_thread.wait()  # Ensure thread stops safely
        super().reject()

    def _filter_icons(self, text):
        text = text.lower().strip()
        visible_count = 0

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item:
                continue
            if text in item.text().lower():
                item.setHidden(False)
                visible_count += 1
            else:
                item.setHidden(True)

        self.status_label.setText(self.tr("{} icons visible").format(visible_count))

    def _on_item_double_clicked(self, item):
        self.selected_icon_path = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _confirm_selection(self):
        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.cancel()
            self._loader_thread.wait()

        items = self.list_widget.selectedItems()
        if items:
            self.selected_icon_path = items[0].data(Qt.ItemDataRole.UserRole)
            self.accept()
        else:
            self.reject()


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
        self.table.itemDoubleClicked.connect(lambda item, col: self.accept())
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

    def _refresh_list(self):
        self.table.clear()
        from src.core.win32_input import get_open_windows

        windows = get_open_windows()

        for exe, title in windows:
            exe_item = QTreeWidgetItem([exe, title])
            # Store the preferred value (exe if available, else title)
            val = exe if exe else title
            exe_item.setData(0, Qt.ItemDataRole.UserRole, val)
            self.table.addTopLevelItem(exe_item)

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

    def __init__(self, item: PieSlice, parent=None):
        super().__init__(parent)
        self.item = item
        self.selected = False
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(50)

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        self.setLayout(layout)

        # Color indicator
        self.color_box = QFrame()
        self.color_box.setFixedSize(18, 18)
        self.color_box.setStyleSheet(
            f"background-color: {item.color}; border: 1px solid rgba(255,255,255,0.2); border-radius: 9px;"
        )  # Circle shape
        layout.addWidget(self.color_box)

        # Labels
        self.label_text = QLabel(item.label)
        self.label_text.setStyleSheet("font-weight: 500; font-size: 13px;")
        layout.addWidget(self.label_text, 1)

        self.action_text = QLabel(item.key)
        self.action_text.setStyleSheet(
            "font-family: 'Segoe UI Semibold', monospace; font-size: 11px;"
        )
        layout.addWidget(self.action_text)

        # Icon (if present)
        if item.icon_path:
            icon_label = QLabel()

            # Use QSvgRenderer for high quality even in settings
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.GlobalColor.transparent)

            resolved_path = resolve_icon_path(item.icon_path)
            renderer = QSvgRenderer(resolved_path)
            if renderer.isValid():
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()

                icon_label.setPixmap(
                    pixmap.scaled(
                        24,
                        24,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                layout.insertWidget(0, icon_label)

        self._update_style()

    def _update_style(self):
        with contextlib.suppress(RuntimeError):
            dark = is_dark_mode()
            if self.selected:
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
                    border-radius: 6px;
                    margin: 2px 5px;
                }}
                PieItemWidget:hover {{
                    background-color: {hover_bg};
                }}
                QLabel {{
                    color: {text_color};
                    background: transparent;
                }}
            """)
            self.action_text.setStyleSheet(
                f"color: {action_color}; background: transparent; padding: 2px 6px; border-radius: 4px; background-color: rgba(0,0,0,0.1);"
            )

    def setSelected(self, selected: bool) -> None:
        self.selected = selected
        with contextlib.suppress(RuntimeError):
            self._update_style()

    def mousePressEvent(self, event: Any) -> None:
        self.clicked.emit(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        self.double_clicked.emit(self)
        super().mouseDoubleClickEvent(event)


class PiePreviewWidget(QWidget):
    """A small widget that shows a live preview of the pie menu."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.menu_items: list[PieSlice] = []
        self.opacity_percent = 80
        self.setMinimumSize(220, 220)
        self.radius_inner = 25
        self.radius_outer = 85

    def update_opacity(self, opacity: int) -> None:
        self.opacity_percent = opacity
        self.update()

    def update_items(self, items: list[PieSlice]) -> None:
        self.menu_items = items
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        center_pos = QPoint(self.width() // 2, self.height() // 2)

        num_items = len(self.menu_items)
        if num_items == 0:
            # Draw empty state placeholder
            painter.setPen(QPen(QColor(128, 128, 128, 100), 1, Qt.PenStyle.DashLine))
            painter.drawEllipse(center_pos, self.radius_outer, self.radius_outer)
            painter.setPen(QColor(128, 128, 128, 150))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.tr("No Items"))
            return

        slice_span = 360 / num_items

        # Draw central glow
        glow = QRadialGradient(center_pos.x(), center_pos.y(), self.radius_outer + 10)
        glow.setColorAt(0, QColor(0, 0, 0, 30))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center_pos, self.radius_outer + 10, self.radius_outer + 10)

        for i, item in enumerate(self.menu_items):
            angle_start = (90 + slice_span / 2) - (i * slice_span)

            color = QColor(item.color)
            color.setAlpha(int(255 * self.opacity_percent / 100))

            rect_outer = QRectF(
                center_pos.x() - self.radius_outer,
                center_pos.y() - self.radius_outer,
                self.radius_outer * 2,
                self.radius_outer * 2,
            )

            rect_inner = QRectF(
                center_pos.x() - self.radius_inner,
                center_pos.y() - self.radius_inner,
                self.radius_inner * 2,
                self.radius_inner * 2,
            )

            sweep = -slice_span

            path = QPainterPath()
            path.arcMoveTo(rect_outer, angle_start)
            path.arcTo(rect_outer, angle_start, sweep)
            path.arcTo(rect_inner, angle_start + sweep, -sweep)
            path.closeSubpath()

            painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
            painter.setBrush(QBrush(color))
            painter.drawPath(path)

            # Draw micro label
            font = QFont("Segoe UI", 8, QFont.Weight.Bold)
            painter.setFont(font)

            mid_angle_deg = angle_start + sweep / 2
            mid_angle_rad = math.radians(mid_angle_deg)

            text_radius = (self.radius_inner + self.radius_outer) / 2
            tx = center_pos.x() + text_radius * math.cos(mid_angle_rad)
            ty = center_pos.y() - text_radius * math.sin(mid_angle_rad)

            fm = painter.fontMetrics()
            label = item.label[:6] + ".." if len(item.label) > 8 else item.label
            tw = fm.horizontalAdvance(label)

            painter.setPen(QColor(255, 255, 255))
            painter.drawText(int(tx - tw / 2), int(ty + fm.height() / 4), label)


class ItemEditorDialog(QDialog):
    def __init__(
        self,
        parent=None,
        item: PieSlice | None = None,
        hook_control=None,
        used_colors: list[str] | None = None,
        trigger_key: str | None = None,
    ):
        super().__init__(parent)
        self.item = item
        self.trigger_key = trigger_key
        self.icon_path = item.icon_path if item else None
        self.setWindowTitle("")  # Set in retranslateUi
        self.setModal(True)
        self.resize(500, 260)

        self.result_item: PieSlice | None = None
        self.used_colors = used_colors or []

        main_h_layout = QHBoxLayout()
        self.setLayout(main_h_layout)

        # Left side: Form
        form_container = QVBoxLayout()
        form_layout = QFormLayout()

        self.label_edit = QLineEdit(item.label if item else "")
        self.label_edit.setPlaceholderText(self.tr("e.g. Copy, Paste, Brush..."))
        self.label_edit.textChanged.connect(self._update_preview)
        self.lbl_label = QLabel()  # Store reference for retranslation
        form_layout.addRow(self.lbl_label, self.label_edit)

        # Action Type
        self.lbl_action_type = QLabel()
        self.action_type_combo = QComboBox()
        self.action_type_combo.addItems(["key", "url", "cmd"])
        current_type = item.action_type if item else "key"
        self.action_type_combo.setCurrentText(current_type)
        self.action_type_combo.currentTextChanged.connect(self._update_preview)
        form_layout.addRow(self.lbl_action_type, self.action_type_combo)

        self.key_edit = KeySequenceEdit(item.key if item else "")
        self.key_edit.textChanged.connect(self._update_preview)
        if hook_control:
            self.key_edit.recording_toggled.connect(hook_control)

        self.lbl_value = QLabel()
        form_layout.addRow(self.lbl_value, self.key_edit)

        self.color_btn = QPushButton()
        if item:
            self.current_color = item.color
        else:
            self.current_color = self._get_next_auto_color()

        self._update_color_btn()
        self.color_btn.clicked.connect(self.pick_color)

        self.lbl_color = QLabel()
        form_layout.addRow(self.lbl_color, self.color_btn)

        # Icon Selection
        icon_layout = QHBoxLayout()
        self.icon_preview_lbl = QLabel()
        self.icon_preview_lbl.setFixedSize(32, 32)
        self.icon_preview_lbl.setStyleSheet("border: 1px dashed gray;")
        self._update_icon_preview()

        self.btn_select_icon = QPushButton(self.tr("Select Icon"))
        self.btn_select_icon.clicked.connect(self.pick_icon)
        self.btn_clear_icon = QPushButton("X")
        self.btn_clear_icon.setFixedSize(24, 24)
        self.btn_clear_icon.clicked.connect(self.clear_icon)

        icon_layout.addWidget(self.icon_preview_lbl)
        icon_layout.addWidget(self.btn_select_icon)

        self.btn_preset_icon = QPushButton(self.tr("Presets"))
        self.btn_preset_icon.clicked.connect(self.pick_preset_icon)
        icon_layout.addWidget(self.btn_preset_icon)

        icon_layout.addWidget(self.btn_clear_icon)

        self.lbl_icon = QLabel()
        form_layout.addRow(self.lbl_icon, icon_layout)

        form_container.addLayout(form_layout)
        form_container.addStretch()

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.save_btn = QPushButton("OK")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.save)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        btn_box.addWidget(self.save_btn)
        btn_box.addWidget(self.cancel_btn)
        form_container.addLayout(btn_box)

        main_h_layout.addLayout(form_container, 2)

        # Right side: Preview
        preview_container = QVBoxLayout()
        self.lbl_preview = QLabel("Preview")
        preview_container.addWidget(self.lbl_preview, 0, Qt.AlignmentFlag.AlignCenter)
        self.preview_widget = PiePreviewWidget()
        self.preview_widget.setFixedSize(180, 180)
        self.preview_widget.radius_outer = 60
        self.preview_widget.radius_inner = 20
        preview_container.addWidget(self.preview_widget, 0, Qt.AlignmentFlag.AlignCenter)
        main_h_layout.addLayout(preview_container, 1)

        self._update_preview()
        self.retranslateUi()

    def retranslateUi(self):
        title = self.tr("Edit Item") if self.item else self.tr("Add Item")
        self.setWindowTitle(title)

        self.lbl_label.setText(self.tr("Label:"))
        self.lbl_action_type.setText(self.tr("Action Type:"))
        self.lbl_value.setText(self.tr("Value:"))
        self.lbl_color.setText(self.tr("Color:"))
        self.lbl_icon.setText(self.tr("Icon:"))

        self.save_btn.setText("OK")
        self.cancel_btn.setText(self.tr("Cancel"))
        self.lbl_preview.setText(self.tr("Preview"))

        # Update placeholders if needed
        self._update_preview()

    def _get_next_auto_color(self) -> str:
        """Select a distinct color that is not in used_colors."""
        # Material/Flat design palette
        palette = [
            "#FF5555",  # Red
            "#FF9955",  # Orange
            "#FFDD55",  # Yellow
            "#55FF55",  # Green
            "#55FFFF",  # Cyan
            "#5555FF",  # Blue
            "#FF55FF",  # Magenta
            "#AAAAAA",  # Grey
            "#FFFFFF",  # White
        ]

        # Filter used colors (case insensitive)
        used_upper = [c.upper() for c in self.used_colors]
        available = [c for c in palette if c.upper() not in used_upper]

        if available:
            return available[0]
        return palette[0]  # Fallback if all used

    def _update_color_btn(self):
        # Determine strict text color based on background luminance
        bg_color = QColor(self.current_color)
        brightness = (bg_color.red() * 299 + bg_color.green() * 587 + bg_color.blue() * 114) / 1000
        text_color = "black" if brightness > 128 else "white"

        self.color_btn.setStyleSheet(
            f"background-color: {self.current_color}; color: {text_color}; font-weight: bold; border-radius: 4px; padding: 5px;"
        )
        self.color_btn.setText(self.current_color)

    def _update_preview(self):
        label = self.label_edit.text() or "サンプル"
        # For preview, we show a dummy menu with 4 items including the current one
        temp_item = PieSlice(label=label, key="", color=self.current_color)
        placeholder = PieSlice(label="", key="", color="#444444")
        self.preview_widget.update_items([temp_item, placeholder, placeholder, placeholder])

        # Update placeholder based on type
        atype = self.action_type_combo.currentText()
        if atype == "url":
            self.key_edit.setMode("text")
            self.key_edit.setPlaceholderText("https://example.com")
        elif atype == "cmd":
            self.key_edit.setMode("text")
            self.key_edit.setPlaceholderText(self.tr("notepad.exe or C:\\Path\\To\\App.exe"))
        else:
            self.key_edit.setMode("key")
            self.key_edit.setPlaceholderText(self.tr("Click to record keys..."))

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.current_color), self, self.tr("Select Color"))
        if color.isValid():
            self.current_color = color.name().upper()
            self._update_color_btn()
            self._update_preview()

    def pick_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Icon"),
            "",
            self.tr("Image Files (*.png *.jpg *.jpeg *.ico *.svg);;All Files (*)"),
        )
        if file_path:
            self.icon_path = file_path
            self._update_icon_preview()

    def pick_preset_icon(self):
        dialog = IconPickerWidget(self)
        if dialog.exec():
            self.icon_path = dialog.selected_icon_path
            self._update_icon_preview()

    def clear_icon(self):
        self.icon_path = None
        self._update_icon_preview()

    def _update_icon_preview(self):
        if self.icon_path:
            # Use QSvgRenderer for preview
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.transparent)

            resolved_path = resolve_icon_path(self.icon_path)
            renderer = QSvgRenderer(resolved_path)
            if renderer.isValid():
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()

                self.icon_preview_lbl.setPixmap(
                    pixmap.scaled(
                        32,
                        32,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return

        self.icon_preview_lbl.clear()
        self.icon_preview_lbl.setText(self.tr("No Icon"))

    def save(self):
        label = self.label_edit.text().strip()
        key = self.key_edit.text().strip()
        action_type = self.action_type_combo.currentText()

        if not label:
            QMessageBox.warning(self, self.tr("Input Error"), self.tr("Please enter a label."))
            return
        if not key:
            QMessageBox.warning(self, self.tr("Input Error"), self.tr("Please set a value."))
            return

        # Validation: Check if key matches trigger key
        if action_type == "key" and self.trigger_key and key.lower() == self.trigger_key.lower():
            # Simple case-insensitive comparison
            QMessageBox.warning(
                self,
                self.tr("Input Error"),
                self.tr("Cannot set the same key as the global trigger key."),
            )
            return

        self.result_item = PieSlice(
            label=label,
            key=str(key),
            color=self.current_color,
            action_type=action_type,
            icon_path=self.icon_path,
        )
        self.accept()


class SettingsWindow(QWidget):
    """Main settings window for configuring MixedBerryPie profiles and preferences."""

    def __init__(
        self,
        on_save_callback: Any,
        on_suspend_hooks: Any | None = None,
        on_resume_hooks: Any | None = None,
    ) -> None:
        super().__init__()
        logger.info("Initializing settings window with adaptive theme")
        self.on_save_callback = on_save_callback
        self.on_suspend_hooks = on_suspend_hooks
        self.on_resume_hooks = on_resume_hooks

        self.is_dirty = False
        self.settings = config.AppSettings()
        # self.setWindowTitle set in retranslateUi
        self.resize(750, 600)  # Adjusted size for sidebar

        icon_path = get_resource_path(os.path.join("resources", "app_icon.ico"))
        self.setWindowIcon(QIcon(icon_path))

        self.profiles: list[MenuProfile] = []
        self.current_profile_idx = -1
        self.item_widgets: list[PieItemWidget] = []
        self.selected_item_widget: PieItemWidget | None = None  # Renamed from selected_widget

        main_layout = QHBoxLayout()  # Changed to QHBoxLayout for sidebar
        self.setLayout(main_layout)

        # --- Sidebar (Profile List) ---
        # --- Sidebar (Profile List) ---
        sidebar = QVBoxLayout()
        self.lbl_profiles = QLabel()
        sidebar.addWidget(self.lbl_profiles)
        self.profile_list = QListWidget()
        self.profile_list.currentRowChanged.connect(self.switch_profile)
        sidebar.addWidget(self.profile_list)

        plist_btns = QHBoxLayout()
        self.btn_add_p = QPushButton("Add")
        self.btn_add_p.clicked.connect(lambda: (self.add_profile(), self.set_dirty()))
        self.btn_del_p = QPushButton("Delete")
        self.btn_del_p.clicked.connect(lambda: (self.delete_profile(), self.set_dirty()))
        plist_btns.addWidget(self.btn_add_p)
        plist_btns.addWidget(self.btn_del_p)
        sidebar.addLayout(plist_btns)
        main_layout.addLayout(sidebar, 1)  # Give sidebar 1/4 of width

        # --- Content Area ---
        content = QVBoxLayout()
        self.tabs = QTabWidget()
        content.addWidget(self.tabs)

        # Tab 1: Menu Items
        menu_tab = QWidget()
        menu_layout = QVBoxLayout()
        menu_tab.setLayout(menu_layout)

        # Trigger Key
        # Trigger Key
        self.group_trigger = QGroupBox()  # Renamed from group_trigger
        trigger_layout = QFormLayout()
        self.trigger_input = KeySequenceEdit()
        self.trigger_input.textChanged.connect(self.on_trigger_changed)
        self.trigger_input.textChanged.connect(self.set_dirty)
        self.trigger_input.recording_toggled.connect(self.hook_control)

        self.lbl_global_hotkey = QLabel()
        trigger_layout.addRow(self.lbl_global_hotkey, self.trigger_input)

        # Target Apps Container
        self.target_apps_container = QFrame()
        self.target_apps_container.setMinimumHeight(32)
        self.target_apps_container.setStyleSheet("background-color: transparent;")
        self.target_apps_layout = FlowLayout(
            self.target_apps_container, margin=2, hspacing=4, vspacing=4
        )

        self.btn_pick_app = QPushButton()
        self.btn_pick_app.setFixedSize(28, 28)
        self.btn_pick_app.setCursor(Qt.CursorShape.PointingHandCursor)

        # Perfection alignment: Use a label inside the button's layout
        btn_inner_layout = QHBoxLayout(self.btn_pick_app)
        btn_inner_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_pick_label = QLabel("+")
        self.btn_pick_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_pick_label.setStyleSheet("font-size: 18px; background: transparent; border: none;")
        btn_inner_layout.addWidget(self.btn_pick_label)

        self.btn_pick_app.clicked.connect(self.pick_target_app)

        target_input_layout = QHBoxLayout()
        target_input_layout.setContentsMargins(0, 0, 0, 0)
        target_input_layout.addWidget(self.target_apps_container, 1)
        target_input_layout.addWidget(self.btn_pick_app)

        self.lbl_target_apps = QLabel()
        trigger_layout.addRow(self.lbl_target_apps, target_input_layout)

        self.group_trigger.setLayout(trigger_layout)
        menu_layout.addWidget(self.group_trigger)

        # Menu Items List
        self.group_items = QGroupBox()  # Added GroupBox for items
        self.group_items.setStyleSheet("QGroupBox { border: none; }")
        group_items_layout = QVBoxLayout()

        # Scroll Area for Items
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background-color: transparent;")
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(0)
        self.items_layout.setContentsMargins(5, 5, 5, 5)
        self.items_layout.addStretch()
        self.scroll_content.setLayout(self.items_layout)
        self.scroll_area.setWidget(self.scroll_content)

        group_items_layout.addWidget(self.scroll_area)

        # Buttons
        # Buttons
        item_btns = QHBoxLayout()  # Renamed from btn_layout
        self.btn_add_i = QPushButton("Add Item")  # Renamed from btn_add
        self.btn_add_i.clicked.connect(self.add_item)
        self.btn_edit_i = QPushButton("Edit")  # Renamed from btn_edit
        self.btn_edit_i.clicked.connect(self.edit_item)  # Connected to edit_item
        self.btn_del_i = QPushButton("Remove")  # Renamed from btn_remove
        self.btn_del_i.clicked.connect(self.remove_item)

        btn_reorder = QHBoxLayout()
        self.btn_up = QPushButton("↑")
        self.btn_up.setFixedWidth(40)
        self.btn_up.clicked.connect(self.move_up)
        self.btn_down = QPushButton("↓")
        self.btn_down.setFixedWidth(40)
        self.btn_down.clicked.connect(self.move_down)
        btn_reorder.addWidget(self.btn_up)
        btn_reorder.addWidget(self.btn_down)

        item_btns.addWidget(self.btn_add_i)
        item_btns.addWidget(self.btn_edit_i)
        item_btns.addWidget(self.btn_del_i)
        item_btns.addStretch()
        item_btns.addLayout(btn_reorder)
        group_items_layout.addLayout(item_btns)

        self.group_items.setLayout(group_items_layout)

        # Multi-column layout for items and preview
        items_h_layout = QHBoxLayout()
        items_h_layout.addWidget(self.group_items, 3)

        # Preview Section
        self.preview_group = QGroupBox("Live Preview")
        preview_layout = QVBoxLayout()
        self.preview_widget = PiePreviewWidget()
        preview_layout.addWidget(self.preview_widget, 0, Qt.AlignmentFlag.AlignCenter)
        preview_layout.addStretch()
        self.preview_group.setLayout(preview_layout)
        items_h_layout.addWidget(self.preview_group, 2)

        menu_layout.addLayout(items_h_layout)

        self.tabs.addTab(menu_tab, "")
        self.menu_tab_idx = self.tabs.indexOf(menu_tab)

        # Tab 2: Global Settings
        settings_tab = QWidget()
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(10)
        settings_tab.setLayout(settings_layout)

        # ── Group 1: 言語 ─────────────────────────────────────────
        self.group_language = QGroupBox()
        lang_form = QFormLayout()

        self.lbl_language = QLabel()
        self.combo_language = QComboBox()
        self.combo_language.addItem("Auto", "auto")
        self.combo_language.addItem("English", "en")
        self.combo_language.addItem("日本語", "ja")
        idx = self.combo_language.findData(self.settings.language)
        if idx >= 0:
            self.combo_language.setCurrentIndex(idx)
        self.combo_language.currentIndexChanged.connect(self.on_language_changed)
        self.combo_language.currentIndexChanged.connect(self.set_dirty)
        lang_form.addRow(self.lbl_language, self.combo_language)

        self.group_language.setLayout(lang_form)
        settings_layout.addWidget(self.group_language)

        # ── Group 2: 表示 ─────────────────────────────────────────
        self.group_adv = QGroupBox()
        adv_form = QFormLayout()

        # Menu size
        self.lbl_overlay_size = QLabel()
        self.overlay_size_spin = SteppedSlider(
            steps=[300, 350, 400, 450, 500, 600, 700, 800], suffix="px"
        )
        self.overlay_size_spin.setValue(self.settings.overlay_size)
        self.overlay_size_spin.value_changed.connect(self.set_dirty)
        adv_form.addRow(self.lbl_overlay_size, self.overlay_size_spin)

        # Menu opacity
        self.lbl_menu_opacity = QLabel()
        self.menu_opacity_slider = SteppedSlider(
            steps=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100], suffix="%"
        )
        self.menu_opacity_slider.setValue(self.settings.menu_opacity)
        self.menu_opacity_slider.value_changed.connect(self.set_dirty)
        self.menu_opacity_slider.value_changed.connect(self.preview_widget.update_opacity)
        adv_form.addRow(self.lbl_menu_opacity, self.menu_opacity_slider)

        # Auto-scale (placed right after menu opacity)
        self.lbl_auto_scale = QLabel()
        self.auto_scale_checkbox = QCheckBox()
        self.auto_scale_checkbox.setChecked(self.settings.auto_scale_with_menu)
        self.auto_scale_checkbox.stateChanged.connect(self.set_dirty)
        self.auto_scale_checkbox.stateChanged.connect(self._update_scale_visibility)
        adv_form.addRow(self.lbl_auto_scale, self.auto_scale_checkbox)

        # Icon size (hidden when auto-scale ON)
        self.lbl_icon_size = QLabel()
        self.icon_size_slider = SteppedSlider(steps=[16, 24, 32, 48, 64, 96, 128], suffix="px")
        self.icon_size_slider.setValue(self.settings.icon_size)
        self.icon_size_slider.value_changed.connect(self.set_dirty)
        self._row_icon_size = (self.lbl_icon_size, self.icon_size_slider)
        adv_form.addRow(self.lbl_icon_size, self.icon_size_slider)

        # Text size (hidden when auto-scale ON)
        self.lbl_text_size = QLabel()
        self.text_size_slider = SteppedSlider(steps=[7, 8, 9, 10, 11, 12, 14, 16, 18], suffix="pt")
        self.text_size_slider.setValue(self.settings.text_size)
        self.text_size_slider.value_changed.connect(self.set_dirty)
        self._row_text_size = (self.lbl_text_size, self.text_size_slider)
        adv_form.addRow(self.lbl_text_size, self.text_size_slider)

        self.group_adv.setLayout(adv_form)
        settings_layout.addWidget(self.group_adv)

        # ── Group 3: 動作 ─────────────────────────────────────────
        self.group_behavior = QGroupBox()
        behavior_form = QFormLayout()

        # Animations
        self.lbl_show_animations = QLabel()
        self.show_animations_checkbox = QCheckBox()
        self.show_animations_checkbox.setChecked(self.settings.show_animations)
        self.show_animations_checkbox.stateChanged.connect(self.set_dirty)
        behavior_form.addRow(self.lbl_show_animations, self.show_animations_checkbox)

        # Action delay
        self.lbl_action_delay = QLabel()
        self.action_delay_spin = SteppedSlider(
            steps=[0, 10, 30, 50, 80, 100, 150, 200, 300, 500], suffix="ms"
        )
        self.action_delay_spin.setValue(self.settings.action_delay_ms)
        self.action_delay_spin.value_changed.connect(self.set_dirty)
        behavior_form.addRow(self.lbl_action_delay, self.action_delay_spin)

        # Key sequence delay
        self.lbl_key_delay = QLabel()
        self.key_delay_spin = SteppedSlider(steps=[0, 10, 20, 50, 100], suffix="ms")
        self.key_delay_spin.setValue(self.settings.key_sequence_delay_ms)
        self.key_delay_spin.value_changed.connect(self.set_dirty)
        behavior_form.addRow(self.lbl_key_delay, self.key_delay_spin)

        self.group_behavior.setLayout(behavior_form)
        settings_layout.addWidget(self.group_behavior)

        # ── Group 4: トリガー動作 ─────────────────────────────────
        self.group_trigger_behavior = QGroupBox()
        trigger_behavior_layout = QFormLayout()

        self.replay_checkbox = QCheckBox()
        self.replay_checkbox.setChecked(self.settings.replay_unselected)
        self.replay_checkbox.stateChanged.connect(self.set_dirty)
        trigger_behavior_layout.addRow(self.replay_checkbox)

        self.lbl_long_press = QLabel()
        self.long_press_spin = SteppedSlider(
            steps=[0, 50, 100, 150, 200, 300, 500, 800, 1000, 1500, 2000], suffix="ms"
        )
        self.long_press_spin.setValue(self.settings.long_press_delay_ms)
        self.long_press_spin.value_changed.connect(self.set_dirty)
        trigger_behavior_layout.addRow(self.lbl_long_press, self.long_press_spin)

        self.group_trigger_behavior.setLayout(trigger_behavior_layout)
        settings_layout.addWidget(self.group_trigger_behavior)

        # ── Group 5: バックアップ ─────────────────────────────────
        self.group_backup = QGroupBox()
        backup_layout = QHBoxLayout()

        self.btn_export = QPushButton()
        self.btn_export.clicked.connect(self.export_settings)
        self.btn_import = QPushButton()
        self.btn_import.clicked.connect(self.import_settings)

        backup_layout.addWidget(self.btn_export)
        backup_layout.addWidget(self.btn_import)
        self.group_backup.setLayout(backup_layout)
        settings_layout.addWidget(self.group_backup)

        settings_layout.addStretch()

        self.tabs.addTab(settings_tab, "")
        self.settings_tab_idx = self.tabs.indexOf(settings_tab)

        # Apply initial visibility
        self._update_scale_visibility()

        # Bottom Save
        self.btn_save = QPushButton("Save & Apply")  # Renamed from btn_save
        self.btn_save.setFixedHeight(45)
        self._apply_save_btn_style()  # Re-apply style
        self.btn_save.clicked.connect(self.save_all)  # Connected to save_all
        content.addWidget(self.btn_save)

        self.item_btns_group = [
            self.btn_add_i,
            self.btn_edit_i,
            self.btn_del_i,
            self.btn_up,
            self.btn_down,
        ]
        for btn in self.item_btns_group:
            btn.clicked.connect(self.set_dirty)

        main_layout.addLayout(content, 3)  # Give content 3/4 of width
        self._apply_theme()  # Apply theme after all widgets are created

        # Connect profile renaming
        self.profile_list.itemDoubleClicked.connect(self.rename_profile)

        self.retranslateUi()
        self.load_data()

    def retranslateUi(self):
        self.setWindowTitle(self.tr("MixedBerryPie Settings"))

        # Sidebar
        self.lbl_profiles.setText(self.tr("Menu Profiles"))
        self.btn_add_p.setText(self.tr("Add"))
        self.btn_del_p.setText(self.tr("Delete"))
        self.btn_del_p.setToolTip(self.tr("Delete Profile"))

        # Tabs
        self.tabs.setTabText(self.menu_tab_idx, self.tr("Menu Items"))
        self.tabs.setTabText(self.settings_tab_idx, self.tr("General Settings"))

        # Trigger
        self.group_trigger.setTitle(self.tr("Trigger Key"))
        self.lbl_global_hotkey.setText(self.tr("Global Hotkey:"))
        self.lbl_target_apps.setText(self.tr("Target Apps:"))
        self.btn_pick_app.setToolTip(self.tr("Pick from running apps"))

        # Items
        self.group_items.setTitle(self.tr("Menu Items"))
        self.btn_add_i.setText(self.tr("Add Item"))
        self.btn_edit_i.setText(self.tr("Edit"))
        self.btn_del_i.setText(self.tr("Remove"))
        self.btn_up.setToolTip(self.tr("Move Up"))
        self.btn_down.setToolTip(self.tr("Move Down"))

        # Preview
        self.preview_group.setTitle(self.tr("Live Preview"))

        # Settings
        self.group_language.setTitle(self.tr("Language"))
        self.lbl_language.setText(self.tr("Language:"))

        self.group_adv.setTitle(self.tr("Display"))
        self.lbl_overlay_size.setText(self.tr("Menu Size:"))
        self.lbl_menu_opacity.setText(self.tr("Menu Opacity:"))
        self.lbl_auto_scale.setText(self.tr("Auto Scale:"))
        self.auto_scale_checkbox.setText(
            self.tr("Automatically adjust icons and text to menu size")
        )
        self.lbl_icon_size.setText(self.tr("Icon Size:"))
        self.lbl_text_size.setText(self.tr("Text Size:"))

        self.group_behavior.setTitle(self.tr("Behavior"))
        self.lbl_show_animations.setText(self.tr("Animations:"))
        self.show_animations_checkbox.setText(self.tr("Enable menu open/close animations"))
        self.lbl_action_delay.setText(self.tr("Execution Delay (ms):"))
        self.lbl_key_delay.setText(self.tr("Key Input Interval (ms):"))

        # Trigger Behavior
        self.group_trigger_behavior.setTitle(self.tr("Trigger Behavior"))
        self.replay_checkbox.setText(self.tr("Replay original key on cancel"))
        self.replay_checkbox.setToolTip(
            self.tr(
                "If enabled, releasing the trigger key without selecting an item will replay the original key input."
            )
        )
        self.lbl_long_press.setText(self.tr("Long Press Delay:"))
        self.long_press_spin.setToolTip(
            self.tr("Wait time before showing the menu (ms). 0 for immediate.")
        )

        # Backup
        self.group_backup.setTitle(self.tr("Backup & Restore"))
        self.btn_export.setText(self.tr("Export Settings"))
        self.btn_import.setText(self.tr("Import Settings"))

        self.btn_save.setText(self.tr("Save & Apply"))

    def on_language_changed(self, index):
        lang_code = self.combo_language.currentData()
        self.settings.language = lang_code
        from typing import cast

        app_inst = cast(QApplication, QApplication.instance())
        i18n.install_translator(app_inst, lang_code)
        self.retranslateUi()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def _update_scale_visibility(self):
        """Show/hide icon & text size rows based on auto_scale_with_menu state."""
        auto_on = self.auto_scale_checkbox.isChecked()
        for widget in (
            self.lbl_icon_size,
            self.icon_size_slider,
            self.lbl_text_size,
            self.text_size_slider,
        ):
            widget.setVisible(not auto_on)

    def hook_control(self, suspend: bool):
        """Handle request to suspend/resume hooks during key recording."""
        if suspend:
            if self.on_suspend_hooks:
                logger.info("Suspending hooks for recording")
                self.on_suspend_hooks()
        else:
            if self.on_resume_hooks:
                logger.info("Resuming hooks after recording")
                self.on_resume_hooks()

    def rename_profile(self, item):
        idx = self.profile_list.row(item)
        if idx == -1:
            return

        old_name = self.profiles[idx].name
        new_name, ok = QInputDialog.getText(
            self, self.tr("Rename Profile"), self.tr("New name:"), text=old_name
        )

        if ok and new_name and new_name != old_name:
            # Check for duplicates
            if any(p.name == new_name for p in self.profiles):
                QMessageBox.warning(
                    self, self.tr("Error"), self.tr("Profile '{}' already exists.").format(new_name)
                )
                return

            self.profiles[idx].name = new_name
            item.setText(new_name)
            logger.info(f"Profile renamed: {old_name} -> {new_name}")

    def set_dirty(self):
        self.is_dirty = True

    def _apply_theme(self):
        dark = is_dark_mode()

        main_bg = "#252525" if dark else "#f6f8fa"
        text_color = "#e0e0e0" if dark else "#24292f"
        card_bg = "#333" if dark else "#ffffff"
        border_clr = "#444" if dark else "#d0d7de"
        btn_bg = "#3d3d3d" if dark else "#f3f4f6"
        tab_inactive = "#2d2d2d" if dark else "#ebf0f4"
        scroll_bg = "#1e1e1e" if dark else "#ffffff"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {main_bg};
                color: {text_color};
                font-family: 'Segoe UI', system-ui, sans-serif;
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {border_clr};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QPushButton {{
                background-color: {btn_bg};
                border: 1px solid {border_clr};
                padding: 6px 12px;
                border-radius: 6px;
                color: {text_color};
            }}
            QPushButton:hover {{
                background-color: {"#4d4d4d" if dark else "#ffffff"};
                border: 1px solid {"#666" if dark else "#0078d4"};
            }}
            QLineEdit, QSpinBox {{
                background-color: {card_bg};
                border: 1px solid {border_clr};
                padding: 5px;
                color: {text_color};
                border-radius: 4px;
            }}
            QTabWidget::pane {{
                border: 1px solid {border_clr};
                background-color: {main_bg};
                border-radius: 4px;
            }}
            QTabBar::tab {{
                background: {tab_inactive};
                color: {text_color};
                padding: 10px 25px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background: {main_bg};
                border: 1px solid {border_clr};
                border-bottom-color: {main_bg};
            }}
            QListWidget {{
                background-color: {card_bg};
                border: 1px solid {border_clr};
                border-radius: 4px;
                color: {text_color};
            }}
            QListWidget::item:selected {{
                background-color: #0078d4;
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: {"#3d3d3d" if dark else "#e0f7fa"};
            }}
        """)
        self.scroll_area.setStyleSheet(
            f"background-color: {scroll_bg}; border: 1px solid {border_clr}; border-radius: 8px;"
        )

    def _apply_save_btn_style(self):
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2da44e;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2c974b;
            }
            QPushButton:pressed {
                background-color: #298e46;
            }
        """)

    def load_data(self) -> None:
        """Load settings and profiles from configuration."""
        logger.info("Loading settings data")
        self.profiles, self.settings = config.load_config()  # Load all profiles and global settings
        self.action_delay_spin.setValue(self.settings.action_delay_ms)
        self.overlay_size_spin.setValue(self.settings.overlay_size)
        self.menu_opacity_slider.setValue(getattr(self.settings, "menu_opacity", 80))
        self.preview_widget.update_opacity(getattr(self.settings, "menu_opacity", 80))
        self.icon_size_slider.setValue(self.settings.icon_size)
        self.text_size_slider.setValue(self.settings.text_size)
        self.show_animations_checkbox.setChecked(self.settings.show_animations)
        self.replay_checkbox.setChecked(self.settings.replay_unselected)
        self.long_press_spin.setValue(self.settings.long_press_delay_ms)
        self.auto_scale_checkbox.setChecked(self.settings.auto_scale_with_menu)
        self.key_delay_spin.setValue(getattr(self.settings, "key_sequence_delay_ms", 0))

        self.profile_list.clear()
        for p in self.profiles:
            self.profile_list.addItem(p.name)

        if self.profiles:
            self.profile_list.setCurrentRow(0)  # Select the first profile by default
        else:
            # If no profiles exist, create a default one
            self.add_profile(default_name="デフォルトプロファイル")

        self.is_dirty = False  # Reset dirty flag after loading

    def switch_profile(self, index: int) -> None:
        """Switch the currently edited profile."""
        if index < 0 or index >= len(self.profiles):
            return

        self.current_profile_idx = index
        p = self.profiles[index]
        self.trigger_input.setText(p.trigger_key)

        # Display list as tags
        targets = p.target_apps if p.target_apps else []
        self._update_app_tags(targets)

        self.update_item_list(p.items)
        self.preview_widget.update_items(p.items)

    def update_item_list(self, items: list[PieSlice]) -> None:
        """Update the UI list of pie items."""
        # Clear existing
        for w in self.item_widgets:
            try:
                w.hide()
                self.items_layout.removeWidget(w)
                w.deleteLater()
            except RuntimeError:
                pass
        self.item_widgets.clear()
        self.selected_item_widget = None

        # Re-add items
        for item in items:
            w = PieItemWidget(item)
            w.clicked.connect(self.on_item_clicked)
            w.double_clicked.connect(self.edit_item)
            self.item_widgets.append(w)
            # Insert before the stretch (which is at index count()-1)
            self.items_layout.insertWidget(self.items_layout.count() - 1, w)

        # Sync preview
        if hasattr(self, "preview_widget"):
            self.preview_widget.update_items(items)

    def on_item_clicked(self, widget):
        # Deselect previous
        if self.selected_item_widget:
            try:
                # Check if it's not the same widget and it still exists
                if self.selected_item_widget != widget:
                    self.selected_item_widget.setSelected(False)
            except (RuntimeError, AttributeError):
                # Wrapped C++ object was deleted
                pass

        self.selected_item_widget = widget
        if self.selected_item_widget:
            try:
                self.selected_item_widget.setSelected(True)
            except (RuntimeError, AttributeError):
                self.selected_item_widget = None

    def pick_target_app(self):
        """Open app picker and add the selected app."""
        dialog = AppPickerDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            app = dialog.get_selected_app()
            if app:
                self._add_app_tag(app)

    def _add_app_tag(self, app_name: str):
        """Add a single app tag if it doesn't exist."""
        if self.current_profile_idx == -1:
            return

        profile = self.profiles[self.current_profile_idx]
        if not profile.target_apps:
            profile.target_apps = []

        if app_name not in profile.target_apps:
            profile.target_apps.append(app_name)
            self._update_app_tags(profile.target_apps)
            self.set_dirty()

    def _update_app_tags(self, apps: list[str]):
        """Clear and rebuild the app tags in the UI."""
        # Clear existing layout items
        while self.target_apps_layout.count():
            child = self.target_apps_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add tags
        for app in apps:
            tag = AppTagWidget(app)
            tag.removed.connect(self._on_app_tag_removed)
            self.target_apps_layout.addWidget(tag)

    def _on_app_tag_removed(self, app_name: str):
        """Handle tag removal."""
        if self.current_profile_idx == -1:
            return

        profile = self.profiles[self.current_profile_idx]
        if profile.target_apps and app_name in profile.target_apps:
            profile.target_apps.remove(app_name)
            self._update_app_tags(profile.target_apps)
            self.set_dirty()

    def on_trigger_changed(self, text):
        if self.current_profile_idx != -1:
            self.profiles[self.current_profile_idx].trigger_key = text

    def add_profile(self, default_name=None):
        name, ok = QInputDialog.getText(
            self,
            "新規メニュープロファイル",
            "プロファイル名:",
            text=default_name if default_name else "",
        )
        if ok and name:
            # Check for duplicate names
            if any(p.name == name for p in self.profiles):
                QMessageBox.warning(
                    self,
                    "名前の重複",
                    f"プロファイル '{name}' は既に存在します。別の名前を指定してください。",
                )
                return

            new_p = MenuProfile(name=name, trigger_key="", items=[])
            self.profiles.append(new_p)
            self.profile_list.addItem(name)
            self.profile_list.setCurrentRow(len(self.profiles) - 1)

    def delete_profile(self):
        if len(self.profiles) <= 1:
            QMessageBox.warning(
                self,
                "エラー",
                "最後のプロファイルは削除できません。少なくとも1つのプロファイルが必要です。",
            )
            return
        idx = self.profile_list.currentRow()
        if idx != -1:
            reply = QMessageBox.question(
                self,
                "削除の確認",
                f"プロファイル '{self.profiles[idx].name}' を削除してもよろしいですか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.profiles.pop(idx)
                self.profile_list.takeItem(idx)
                # Select the previous item, or the first if the deleted was first
                if idx > 0:
                    self.profile_list.setCurrentRow(idx - 1)
                elif self.profiles:
                    self.profile_list.setCurrentRow(0)
                else:  # No profiles left, should not happen due to check above
                    self.trigger_input.setText("")
                    self.update_item_list([])

    def add_item(self):
        if self.current_profile_idx == -1:
            QMessageBox.warning(
                self, "プロファイル未選択", "まずプロファイルを選択または作成してください。"
            )
            return

        # Collect used colors
        current_items = self.profiles[self.current_profile_idx].items
        used_colors = [item.color for item in current_items]

        # Pass current trigger key for validation
        current_trigger = self.trigger_input.text()

        dialog = ItemEditorDialog(
            self,
            hook_control=self.hook_control,
            used_colors=used_colors,
            trigger_key=current_trigger,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_item:
            self.profiles[self.current_profile_idx].items.append(dialog.result_item)
            self.update_item_list(self.profiles[self.current_profile_idx].items)
            self.on_item_clicked(self.item_widgets[-1])  # Select the newly added item

    def edit_item(self):  # Renamed from edit_selected_item
        if not self.selected_item_widget:
            return

        try:
            # Safely get current index and item
            idx = self.item_widgets.index(self.selected_item_widget)
            item_to_edit = self.selected_item_widget.item
        except (RuntimeError, ValueError):
            self.selected_item_widget = None
            return

        # Pass current trigger key for validation
        current_trigger = self.trigger_input.text()

        dialog = ItemEditorDialog(
            self, item_to_edit, hook_control=self.hook_control, trigger_key=current_trigger
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_item:
            self.profiles[self.current_profile_idx].items[idx] = dialog.result_item
            self.update_item_list(self.profiles[self.current_profile_idx].items)
            self.on_item_clicked(self.item_widgets[idx])  # Re-select the edited item

    def remove_item(self):
        if not self.selected_item_widget:
            return

        try:
            idx = self.item_widgets.index(self.selected_item_widget)
            self.profiles[self.current_profile_idx].items.pop(idx)
            self.update_item_list(self.profiles[self.current_profile_idx].items)
        except (RuntimeError, ValueError):
            self.selected_item_widget = None
            # Refresh list anyway if we can't find the widget but one was 'selected'
            self.update_item_list(self.profiles[self.current_profile_idx].items)

    def move_up(self):
        if not self.selected_item_widget:
            return
        try:
            idx = self.item_widgets.index(self.selected_item_widget)
            if idx > 0:
                current_items = self.profiles[self.current_profile_idx].items
                current_items[idx], current_items[idx - 1] = (
                    current_items[idx - 1],
                    current_items[idx],
                )
                self.update_item_list(current_items)
                self.on_item_clicked(self.item_widgets[idx - 1])
        except (RuntimeError, ValueError):
            self.selected_item_widget = None

    def move_down(self) -> None:
        if not self.selected_item_widget:
            return
        try:
            idx = self.item_widgets.index(self.selected_item_widget)
            if idx < len(self.item_widgets) - 1:
                current_items = self.profiles[self.current_profile_idx].items
                current_items[idx], current_items[idx + 1] = (
                    current_items[idx + 1],
                    current_items[idx],
                )
                self.update_item_list(current_items)
                self.on_item_clicked(self.item_widgets[idx + 1])
        except (RuntimeError, ValueError):
            self.selected_item_widget = None

    def export_settings(self) -> None:
        """Export current settings to a JSON file."""
        import shutil

        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self, "設定のエクスポート", "mixedberrypie_settings.json", "JSON Files (*.json)"
        )

        if not file_path:
            return

        try:
            # Save strictly to verify current state is valid
            if not self.save_all_silent():
                return

            src = config.CONFIG_FILE
            shutil.copy(src, file_path)
            QMessageBox.information(
                self, "エクスポート完了", f"設定を以下にエクスポートしました:\n{file_path}"
            )
        except Exception as e:
            logger.error(f"Export failed: {e}")
            QMessageBox.critical(
                self, "エクスポート失敗", f"エクスポート中にエラーが発生しました:\n{e}"
            )

    def import_settings(self) -> None:
        """Import settings from a JSON file."""
        import shutil

        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self, "設定のインポート", "", "JSON Files (*.json)"
        )

        if not file_path:
            return

        reply = QMessageBox.question(
            self,
            "インポートの確認",
            "設定をインポートすると現在の設定が上書きされます。\n続行してもよろしいですか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Basic validation: try to load it
            with open(file_path, encoding="utf-8") as f:
                import json

                json.load(f)
                # Check for bare minimum structure (e.g. valid json)

            # Replace config file
            shutil.copy(file_path, config.CONFIG_FILE)

            # Reload
            self.load_data()
            self.on_save_callback()  # Notify app to reload
            QMessageBox.information(self, "インポート完了", "設定を正常にインポートしました。")
        except json.JSONDecodeError:
            QMessageBox.critical(
                self, "インポート失敗", "選択されたファイルは有効なJSON構成ではありません。"
            )
        except Exception as e:
            logger.error(f"Import failed: {e}")
            QMessageBox.critical(
                self, "インポート失敗", f"インポート中にエラーが発生しました:\n{e}"
            )

    def save_all_silent(self) -> bool:
        """Helper to save without succes message popup."""
        # Reuse logic from save_all but split it if needed.
        # For now, let's just call save_all and accept the popup,
        # or refactor save_all.
        # Refactoring save_all to be silent is better.
        return self._save_internal(show_success=False)

    def save_all(self) -> None:
        """Save settings and show success message."""
        self._save_internal(show_success=True)

    def _save_internal(self, show_success: bool = True) -> bool:
        logger.info("Saving settings")

        # Update global settings from UI elements
        self.settings.action_delay_ms = self.action_delay_spin.value()
        self.settings.overlay_size = self.overlay_size_spin.value()
        self.settings.menu_opacity = self.menu_opacity_slider.value()
        self.settings.icon_size = self.icon_size_slider.value()
        self.settings.text_size = self.text_size_slider.value()
        self.settings.show_animations = self.show_animations_checkbox.isChecked()
        self.settings.replay_unselected = self.replay_checkbox.isChecked()
        self.settings.long_press_delay_ms = self.long_press_spin.value()
        self.settings.auto_scale_with_menu = self.auto_scale_checkbox.isChecked()
        self.settings.key_sequence_delay_ms = self.key_delay_spin.value()

        # Validate all profiles before saving
        seen_keys: dict[str, str] = {}
        for profile in self.profiles:
            if not profile.trigger_key:
                QMessageBox.warning(
                    self,
                    "入力エラー",
                    f"プロファイル '{profile.name}' のトリガーキーが空です。設定してください。",
                )
                self.profile_list.setCurrentRow(self.profiles.index(profile))
                return False

            if profile.trigger_key in seen_keys:
                QMessageBox.warning(
                    self,
                    "入力エラー",
                    f"キー '{profile.trigger_key}' は '{profile.name}' と '{seen_keys[profile.trigger_key]}' の両方で使用されています。\n\n"
                    "トリガーキーは重複しないように設定してください。",
                )
                self.profile_list.setCurrentRow(self.profiles.index(profile))
                return False
            seen_keys[profile.trigger_key] = profile.name

        if config.save_config(self.profiles, self.settings):
            self.is_dirty = False
            if self.on_save_callback:
                self.on_save_callback()
            if show_success:
                QMessageBox.information(self, "成功", "設定を保存し適用しました！")
            logger.info("Settings saved successfully")
            return True
        else:
            QMessageBox.critical(self, "エラー", "設定の保存に失敗しました。")
            return False

    def closeEvent(self, event):
        if self.is_dirty:
            reply = QMessageBox.question(
                self,
                "未保存の変更",
                "未保存の変更があります。閉じる前に保存しますか？",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )

            if reply == QMessageBox.StandardButton.Save:
                self.save_all()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
