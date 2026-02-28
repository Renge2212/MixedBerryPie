import contextlib
import math
import os
from typing import Any

from PyQt6.QtCore import (
    QEvent,
    QPoint,
    QRect,
    QRectF,
    QSize,
    QStandardPaths,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QIcon,
    QImage,
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
    QFontComboBox,
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
    QMenu,
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
from src.core.config import (
    AppSettings,
    MenuProfile,
    PieSlice,
    add_to_icon_history,
    load_icon_history,
    remove_from_icon_history,
)
from src.core.logger import get_logger
from src.core.utils import get_resource_path, is_dark_mode, resolve_icon_path

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
            renderer.render(painter)
            painter.end()
            return pixmap
        return None
    else:
        # Raster formats: png, jpg, ico, bmp, webp, etc.
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return None
        return pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )


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

    # Use QImage (thread-safe) instead of QIcon/QPixmap (GUI-thread only)
    icon_loaded = pyqtSignal(str, str, QImage)  # relative_path, name, image
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
            name = os.path.splitext(os.path.basename(filename))[0]

            # Use QImage which is thread-safe (QPixmap is NOT thread-safe)
            render_size = 64
            image = QImage(render_size, render_size, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)

            renderer = QSvgRenderer(path)
            if renderer.isValid():
                painter = QPainter(image)
                renderer.render(painter)
                painter.end()

                relative_path = f"icons/{filename}"
                self.icon_loaded.emit(relative_path, name, image)

        self.finished_loading.emit()

    def cancel(self):
        self._is_cancelled = True


class IconPickerWidget(QDialog):
    """Dialog to select from preset icons with search functionality."""

    # ------------------------------------------------------------------ #
    # Category → list of icon-name prefixes (icon filename without .svg) #
    # ------------------------------------------------------------------ #
    # The dynamic list of categories will be generated based on the subdirectories
    # inside resources/icons.

    def __init__(self, parent=None, all_profiles=None):
        super().__init__(parent)
        self.all_profiles = all_profiles or []
        self.setWindowTitle(self.tr("Select Icon"))
        self.setModal(True)
        self.resize(860, 620)
        self.selected_icon_path = None
        self._loader_thread: IconLoaderThread | None = None
        self._loaded_count = 0

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── Top filter bar ──────────────────────────────────────────── #
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        # Category dropdown
        filter_layout.addWidget(QLabel(self.tr("Category:")))
        self.category_combo = QComboBox()
        self.category_combo.addItem(self.tr("All"), "All")
        self.category_combo.addItem(self.tr("User Icons"), "User Icons")  # history comes first

        # Dynamically discover directories as categories
        categories = []
        icons_dir = get_resource_path(os.path.join("resources", "icons"))
        if os.path.exists(icons_dir):
            for d in os.listdir(icons_dir):
                if os.path.isdir(os.path.join(icons_dir, d)):
                    categories.append(d)

        # Sort them and prioritize RengeIcon
        if "RengeIcon" in categories:
            categories.remove("RengeIcon")
            categories = ["RengeIcon", *sorted(categories)]
        else:
            categories = sorted(categories)

        for cat in categories:
            self.category_combo.addItem(self.tr(cat), cat)
        self.category_combo.setMinimumWidth(160)
        self.category_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.category_combo)

        filter_layout.addSpacing(16)

        # Text search
        filter_layout.addWidget(QLabel(self.tr("Search:")))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("Filter by name..."))
        self.search_input.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_input, 1)

        layout.addLayout(filter_layout)

        # Apply theme to filter bar
        dark = is_dark_mode()
        label_clr = "#bbbbbb" if dark else "#555555"
        self.setStyleSheet(f"""
            QDialog {{ background-color: {"#1e1e1e" if dark else "#ffffff"}; }}
            QLabel {{ color: {label_clr}; font-weight: bold; }}
            QComboBox, QLineEdit {{
                background-color: {"#252526" if dark else "#f6f8f9"};
                border: 1px solid {"#3c3c3c" if dark else "#d0d7de"};
                border-radius: 4px;
                padding: 4px;
                color: {"#cccccc" if dark else "#333333"};
            }}
        """)

        # ── Icon grid ───────────────────────────────────────────────── #
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.setSpacing(5)
        self.list_widget.setGridSize(QSize(72, 80))
        self.list_widget.setIconSize(QSize(48, 48))
        self.list_widget.setWordWrap(True)
        self.list_widget.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        # Fixed dark canvas so white-stroke SVG icons are always visible
        # regardless of Windows light/dark theme (same convention as VS Code,
        # Figma, etc. for icon pickers)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                color: #cccccc;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 4px;
            }
            QListWidget::item {
                color: #cccccc;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
        """)
        layout.addWidget(self.list_widget)

        # ── Bottom bar ──────────────────────────────────────────────── #
        btn_box = QHBoxLayout()
        self.status_label = QLabel(self.tr("Loading icons..."))
        btn_box.addWidget(self.status_label)
        btn_box.addStretch()

        ok_btn = QPushButton(self.tr("OK"))
        ok_btn.clicked.connect(self._confirm_selection)
        cancel_btn = QPushButton(self.tr("Cancel"))
        cancel_btn.clicked.connect(self.reject)

        btn_box.addWidget(ok_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

        self._load_icons()

    # ------------------------------------------------------------------ #
    # Category matching                                                    #
    # ------------------------------------------------------------------ #
    def _get_category_for_name(self, name: str) -> str | None:
        return "Misc"

    def _load_icons(self):
        icons_dir = get_resource_path(os.path.join("resources", "icons"))
        if not os.path.exists(icons_dir):
            return

        files = []
        for root, _, filenames in os.walk(icons_dir):
            for f in filenames:
                if f.lower().endswith(".svg"):
                    rel_path = os.path.relpath(os.path.join(root, f), icons_dir).replace("\\", "/")
                    files.append(rel_path)
        files.sort()

        self.status_label.setText(self.tr("Loading icons..."))
        self.list_widget.clear()
        self._loaded_count = 0

        # Start background worker thread
        self._loader_thread = IconLoaderThread(icons_dir, files, self)
        self._loader_thread.icon_loaded.connect(self._on_icon_loaded)
        self._loader_thread.finished_loading.connect(self._on_loading_finished)
        self._loader_thread.start()

    def _on_icon_loaded(self, relative_path: str, name: str, image: QImage):
        # Convert QImage -> QPixmap -> QIcon on the main thread (GUI-thread safe)
        pixmap = QPixmap.fromImage(image)
        icon = QIcon(pixmap)
        item = QListWidgetItem(icon, name)
        item.setData(Qt.ItemDataRole.UserRole, relative_path)

        # Store category in UserRole+1 for fast filtering
        parts = relative_path.split("/")
        category = parts[1] if len(parts) > 2 else self._get_category_for_name(name)

        item.setData(Qt.ItemDataRole.UserRole + 1, category)
        item.setToolTip(name)
        self.list_widget.addItem(item)

        self._loaded_count += 1
        if self._loaded_count % 50 == 0:
            self.status_label.setText(self.tr("Loaded {} icons...").format(self._loaded_count))

        # Apply current filters immediately to new item
        self._apply_filter_to_item(item)

    def _on_loading_finished(self):
        self._load_history_items()
        self._apply_filters()

    def _load_history_items(self):
        """Prepend history (recent) items to the list from saved icon_history.json."""
        history = load_icon_history()
        for path in reversed(history):  # reversed so most-recent ends up at index 0
            resolved = resolve_icon_path(path)
            if not resolved or not os.path.exists(resolved):
                continue
            name = os.path.splitext(os.path.basename(resolved))[0]
            pixmap = _render_icon_pixmap(resolved, 64)
            if pixmap is None:
                pixmap = QPixmap(64, 64)
                pixmap.fill(Qt.GlobalColor.transparent)
            icon = QIcon(pixmap)
            item = QListWidgetItem(icon, name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setData(Qt.ItemDataRole.UserRole + 1, "User Icons")
            item.setToolTip(resolved)
            self.list_widget.insertItem(0, item)  # insert at top

    def reject(self):
        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.cancel()
            self._loader_thread.wait()
        super().reject()

    def _apply_filter_to_item(self, item: QListWidgetItem):
        """Evaluate both filters for a single item."""
        text = self.search_input.text().lower().strip()
        cat_id = self.category_combo.currentData()
        name = item.text().lower()
        item_cat = item.data(Qt.ItemDataRole.UserRole + 1)  # str | None

        if cat_id == "All":
            cat_match = True
        elif cat_id == "User Icons":
            cat_match = item_cat == "User Icons"
        else:
            cat_match = item_cat == cat_id

        text_match = (not text) or (text in name)
        item.setHidden(not (cat_match and text_match))

    def _apply_filters(self):
        """Re-apply both filters to all items and update status label."""
        visible = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item:
                self._apply_filter_to_item(item)
                if not item.isHidden():
                    visible += 1
        self.status_label.setText(self.tr("{} icons visible").format(visible))

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

    def _show_context_menu(self, pos):
        """Show deletion menu for user-added icons."""
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        item_cat = item.data(Qt.ItemDataRole.UserRole + 1)
        if item_cat != "User Icons":
            return

        menu = QMenu(self)
        delete_action = QAction(self.tr("Delete from Library"), self)
        # SP_TrashIcon might not be available on all platforms, SP_DialogDiscardButton is a safe alternative
        style = self.style()
        if style:
            delete_action.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton))
        delete_action.triggered.connect(self._delete_selected_icon)
        menu.addAction(delete_action)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def _is_icon_in_use(self, path: str) -> bool:
        """Check if any profile uses this icon path."""
        target_abs = os.path.abspath(resolve_icon_path(path) or path)
        for p in self.all_profiles:
            for item in p.items:
                if item.icon_path:
                    # Resolve to absolute for comparison
                    resolved = resolve_icon_path(item.icon_path)
                    if (
                        resolved
                        and os.path.exists(resolved)
                        and os.path.abspath(resolved) == target_abs
                    ):
                        return True
        return False

    def _delete_selected_icon(self):
        """Confirm and remove icon from both disk and history."""
        item = self.list_widget.currentItem()
        if not item:
            return

        path = item.data(Qt.ItemDataRole.UserRole)
        target_abs = os.path.abspath(resolve_icon_path(path) or path)

        # Check if in use
        if self._is_icon_in_use(path):
            title = self.tr("Icon in Use")
            msg = self.tr(
                "This icon is currently assigned to one or more menu items.\n\nIf you delete it, those items will lose their icon image. Are you sure you want to proceed?"
            )
            reply = QMessageBox.warning(
                self,
                title,
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
        else:
            title = self.tr("Delete Icon")
            msg = self.tr("Are you sure you want to delete this icon from your library?")
            reply = QMessageBox.question(
                self,
                title,
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
        if reply == QMessageBox.StandardButton.Yes:
            remove_from_icon_history(path)

            # Clean up all profile items (In-place update of references)
            for p in self.all_profiles:
                for pi in p.items:
                    if pi.icon_path:
                        resolved_pi = resolve_icon_path(pi.icon_path)
                        if resolved_pi and os.path.abspath(resolved_pi) == target_abs:
                            pi.icon_path = None

            # Clean up parent's current state if it's an ItemEditorDialog editing this icon
            parent = self.parent()
            while parent:
                if hasattr(parent, "icon_path"):
                    parent_resolved = (
                        resolve_icon_path(parent.icon_path) if parent.icon_path else None
                    )
                    if parent_resolved and os.path.abspath(parent_resolved) == target_abs:
                        parent.icon_path = None
                        if hasattr(parent, "_update_icon_preview"):
                            parent._update_icon_preview()
                parent = parent.parent()

            # Remove from UI list
            self.list_widget.takeItem(self.list_widget.row(item))
            self._apply_filters()

    def keyPressEvent(self, event):
        """Handle Delete key for quick removal."""
        if event.key() == Qt.Key.Key_Delete:
            item = self.list_widget.currentItem()
            if item and item.data(Qt.ItemDataRole.UserRole + 1) == "User Icons":
                self._delete_selected_icon()
                return
        super().keyPressEvent(event)


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

    def __init__(self, item: PieSlice, parent=None, color_mode="individual"):
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
        if color_mode != "individual":
            self.color_box.setVisible(False)

        # Labels
        self.label_text = QLabel(item.label)
        self.label_text.setStyleSheet("font-weight: 500; font-size: 13px;")
        layout.addWidget(self.label_text, 1)

        self.action_text = QLabel(item.key if item.action_type != "submenu" else self.tr("Submenu"))
        self.action_text.setStyleSheet(
            "font-family: 'Segoe UI Semibold', monospace; font-size: 11px;"
        )
        layout.addWidget(self.action_text)

        if item.action_type == "submenu":
            self.btn_enter = QPushButton(self.tr("Enter ➔"))
            self.btn_enter.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_enter.setStyleSheet("font-size: 11px; padding: 2px 8px; font-weight: bold;")
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
                QLabel#pieItemIcon {{
                    background-color: {"rgba(30,30,30,0.4)" if dark else "rgba(30, 30, 30, 0.8)"};
                    border-radius: 4px;
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

    def _on_enter_clicked(self):
        self.enter_submenu.emit(self)


class PiePreviewWidget(QWidget):
    """A small widget that shows a live preview of the pie menu."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.menu_items: list[PieSlice] = []
        self.opacity_percent = 80
        self.color_mode = "individual"
        self.unified_color = "#448AFF"
        self.selected_preset = "Mixed Berry"
        self.current_palette: list[str] = []
        self.setMinimumSize(220, 220)
        self.radius_inner = 25
        self.radius_outer = 85

    def update_opacity(self, opacity: int) -> None:
        self.opacity_percent = opacity
        self.update()

    def update_items(self, items: list[PieSlice]) -> None:
        self.menu_items = items
        self.update()

    def update_unified_color(
        self, mode: str, color: str, preset: str, palette: list[str] | None = None
    ) -> None:
        self.color_mode = mode
        self.unified_color = color
        self.selected_preset = preset
        self.current_palette = palette or []
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

            effective_color_str = item.color
            if self.color_mode == "unified":
                effective_color_str = self.unified_color
            elif self.color_mode == "preset":
                palette = self.current_palette
                if palette:
                    color_idx = i % len(palette)
                    # Adjacency fix for circular menus
                    if num_items > 1 and i == num_items - 1 and color_idx == 0 and len(palette) > 1:
                        color_idx = (color_idx + 1) % len(palette)
                    effective_color_str = palette[color_idx]
                else:
                    effective_color_str = "#CCCCCC"

            color = QColor(effective_color_str)
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


class ItemEditorDialog(QDialog):
    def __init__(
        self,
        parent=None,
        item: PieSlice | None = None,
        hook_control=None,
        used_colors: list[str] | None = None,
        trigger_key: str | None = None,
        all_profiles: list[MenuProfile] | None = None,
    ):
        super().__init__(parent)
        self.item = item
        self.all_profiles = all_profiles or []
        self.trigger_key = trigger_key
        self.icon_path = item.icon_path if item else None
        self.setWindowTitle("")  # Set in retranslateUi
        self.setModal(True)
        self.resize(500, 260)

        self.result_item: PieSlice | None = None
        self.used_colors = used_colors or []

        # Color mode settings from global UI state (live)
        if hasattr(parent, "combo_color_mode"):
            self.color_mode = parent.combo_color_mode.currentData()
            self.global_unified_color = getattr(parent, "_current_unified_color", "#448AFF")
            self.global_palette: list[str] = getattr(parent, "_get_current_palette", lambda: [])()
        elif hasattr(parent, "settings"):
            settings = parent.settings
            if settings:
                self.color_mode = getattr(settings, "color_mode", "individual")
                self.global_unified_color = getattr(settings, "unified_color", "#448AFF")
            else:
                self.color_mode = "individual"
                self.global_unified_color = "#448AFF"
            self.global_palette = []
        else:
            self.color_mode = "individual"
            self.global_unified_color = "#448AFF"
            self.global_palette = []

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
        # Mapping of internal type to display name
        self.type_display_map = {
            "key": self.tr("Key Input"),
            "url": self.tr("Open URL"),
            "cmd": self.tr("Run Command"),
            "submenu": self.tr("Submenu"),
        }
        for internal_type, display_name in self.type_display_map.items():
            self.action_type_combo.addItem(display_name, internal_type)

        current_type = item.action_type if item else "key"
        index = self.action_type_combo.findData(current_type)
        if index >= 0:
            self.action_type_combo.setCurrentIndex(index)

        self.action_type_combo.currentIndexChanged.connect(self._update_preview)
        form_layout.addRow(self.lbl_action_type, self.action_type_combo)

        self.key_edit = KeySequenceEdit(item.key if item else "")
        self.key_edit.textChanged.connect(self._update_preview)
        if hook_control:
            self.key_edit.recording_toggled.connect(hook_control)

        self.submenu_hint_label = QLabel(
            self.tr("Nested items can be added after saving this item.")
        )
        self.submenu_hint_label.setStyleSheet("color: #888; font-style: italic;")
        self.submenu_hint_label.setVisible(False)

        self.lbl_value = QLabel()

        self.value_layout = QHBoxLayout()
        self.value_layout.setContentsMargins(0, 0, 0, 0)
        self.value_layout.addWidget(self.key_edit)
        self.value_layout.addWidget(self.submenu_hint_label)

        form_layout.addRow(self.lbl_value, self.value_layout)

        self.color_btn = QPushButton()
        if item:
            self.current_color = item.color
        else:
            self.current_color = self._get_next_auto_color()

        self._update_color_btn()
        self.color_btn.clicked.connect(self.pick_color)

        self.lbl_color = QLabel()
        form_layout.addRow(self.lbl_color, self.color_btn)

        # Hide color if not in individual mode
        if self.color_mode != "individual":
            self.lbl_color.setVisible(False)
            self.color_btn.setVisible(False)

        # Icon Selection
        icon_layout = QHBoxLayout()
        icon_layout.setSpacing(6)

        # Preview box — large enough to show both icons and "no icon" text
        self.icon_preview_lbl = QLabel()
        self.icon_preview_lbl.setFixedSize(48, 48)
        self.icon_preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_preview_lbl.setStyleSheet(
            "background-color: #1e1e1e; border: 1px dashed rgba(128,128,128,0.6); border-radius: 4px;"
            " color: rgba(128,128,128,0.8); font-size: 10px;"
        )
        # self._update_icon_preview() moved down to after preview_widget is created

        # Buttons
        self.btn_select_icon = QPushButton(self.tr("Browse..."))
        self.btn_select_icon.setToolTip(self.tr("Choose an image file from disk"))
        self.btn_select_icon.clicked.connect(self.pick_icon)

        self.btn_preset_icon = QPushButton(self.tr("Presets / Recent..."))
        self.btn_preset_icon.setToolTip(
            self.tr("Pick from built-in presets or recently used icons")
        )
        self.btn_preset_icon.clicked.connect(self.pick_preset_icon)

        self.btn_clear_icon = QPushButton(self.tr("Clear"))
        self.btn_clear_icon.setToolTip(self.tr("Remove icon"))
        self.btn_clear_icon.setEnabled(bool(self.icon_path))
        self.btn_clear_icon.clicked.connect(self.clear_icon)

        btn_icon_group = QHBoxLayout()
        btn_icon_group.setSpacing(4)
        btn_icon_group.addWidget(self.btn_select_icon)
        btn_icon_group.addWidget(self.btn_preset_icon)
        btn_icon_group.addWidget(self.btn_clear_icon)

        icon_layout.addWidget(self.icon_preview_lbl)
        icon_layout.addSpacing(4)
        icon_layout.addLayout(btn_icon_group)
        icon_layout.addStretch()

        self.lbl_icon = QLabel()
        form_layout.addRow(self.lbl_icon, icon_layout)

        form_container.addLayout(form_layout)
        form_container.addStretch()

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.save_btn = QPushButton(self.tr("OK"))
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
        # Sync with global mode
        self.preview_widget.update_unified_color(
            self.color_mode, self.global_unified_color, "", palette=self.global_palette
        )
        preview_container.addWidget(self.preview_widget, 0, Qt.AlignmentFlag.AlignCenter)
        main_h_layout.addLayout(preview_container, 1)

        self._update_icon_preview()  # This will also call _update_preview()
        self.retranslateUi()

    def retranslateUi(self):
        title = self.tr("Edit Item") if self.item else self.tr("Add Item")
        self.setWindowTitle(title)

        self.lbl_label.setText(self.tr("Label:"))
        self.lbl_action_type.setText(self.tr("Action Type:"))
        self.lbl_value.setText(self.tr("Value:"))
        self.lbl_color.setText(self.tr("Color:"))
        self.lbl_icon.setText(self.tr("Icon:"))

        self.save_btn.setText(self.tr("OK"))
        self.cancel_btn.setText(self.tr("Cancel"))
        self.lbl_preview.setText(self.tr("Preview"))

        self.btn_select_icon.setText(self.tr("Browse..."))
        self.btn_select_icon.setToolTip(self.tr("Choose an image file from disk"))
        self.btn_preset_icon.setText(self.tr("Presets / Recent..."))
        self.btn_preset_icon.setToolTip(
            self.tr("Pick from built-in presets or recently used icons")
        )
        self.btn_clear_icon.setText(self.tr("Clear"))
        self.btn_clear_icon.setToolTip(self.tr("Remove icon"))

        # Sync the circular visualization preview for all cases
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
        temp_item = PieSlice(
            label=label, key="", color=self.current_color, icon_path=self.icon_path
        )
        placeholder = PieSlice(label="", key="", color="#444444")
        self.preview_widget.update_items([temp_item, placeholder, placeholder, placeholder])

        # Update placeholder based on type
        atype = self.action_type_combo.currentData()
        if atype == "submenu":
            self.key_edit.setVisible(False)
            self.submenu_hint_label.setVisible(True)
            self.lbl_value.setText(self.tr("Submenu:"))
        else:
            self.key_edit.setVisible(True)
            self.submenu_hint_label.setVisible(False)
            self.lbl_value.setText(self.tr("Value:"))
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
        # Default to Pictures folder
        pics = QStandardPaths.standardLocations(QStandardPaths.StandardLocation.PicturesLocation)
        initial_dir = pics[0] if pics else ""

        # If we have an existing icon NOT in the internal user_icons dir,
        # we can follow its directory. Otherwise, stick to Pictures.
        if self.icon_path and os.path.exists(self.icon_path):
            current_abs = os.path.abspath(self.icon_path)
            user_icons_abs = os.path.abspath(config.USER_ICONS_DIR)
            if not current_abs.startswith(user_icons_abs):
                initial_dir = os.path.dirname(self.icon_path)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Icon"),
            initial_dir,
            self.tr("Image Files (*.png *.jpg *.jpeg *.ico *.svg);;All Files (*)"),
        )
        if file_path:
            # Assetize icon and update current path
            history = add_to_icon_history(file_path)
            if history:
                self.icon_path = history[0]
            else:
                self.icon_path = file_path
            self._update_icon_preview()

    def pick_preset_icon(self):
        dialog = IconPickerWidget(self, all_profiles=self.all_profiles)
        if dialog.exec():
            self.icon_path = dialog.selected_icon_path
            self._update_icon_preview()

    def clear_icon(self):
        self.icon_path = None
        self._update_icon_preview()

    def _update_icon_preview(self):
        if self.icon_path:
            resolved_path = resolve_icon_path(self.icon_path)
            pixmap = _render_icon_pixmap(resolved_path, 48)
            if pixmap is not None:
                # Scale to fit inside 48x48 while keeping aspect ratio
                self.icon_preview_lbl.setPixmap(
                    pixmap.scaled(
                        44,
                        44,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.icon_preview_lbl.setToolTip(self.icon_path)
                if btn := getattr(self, "btn_clear_icon", None):
                    btn.setEnabled(True)
            else:
                self.icon_preview_lbl.clear()
                self.icon_preview_lbl.setText(self.tr("No\nIcon"))
                self.icon_preview_lbl.setToolTip("")
                if btn := getattr(self, "btn_clear_icon", None):
                    btn.setEnabled(False)
        else:
            self.icon_preview_lbl.clear()
            self.icon_preview_lbl.setText(self.tr("No\nIcon"))
            self.icon_preview_lbl.setToolTip("")
            if btn := getattr(self, "btn_clear_icon", None):
                btn.setEnabled(False)

    def save(self):
        label = self.label_edit.text().strip()
        action_type = self.action_type_combo.currentText()
        key = "" if action_type == "submenu" else self.key_edit.text().strip()

        if not label:
            QMessageBox.warning(self, self.tr("Input Error"), self.tr("Please enter a label."))
            return
        if action_type != "submenu" and not key:
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

        # Preserve existing submenu_items if editing an existing submenu item
        existing_submenus = []
        if self.item and getattr(self.item, "submenu_items", None) is not None:
            existing_submenus = self.item.submenu_items

        self.result_item = PieSlice(
            label=label,
            key=str(key),
            color=self.current_color,
            action_type=action_type,
            icon_path=self.icon_path,
            submenu_items=existing_submenus,
        )
        self.accept()


class PresetEditorDialog(QDialog):
    """Dialog to name a preset and pick its colors."""

    def __init__(self, parent=None, name: str = "", colors: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Edit Preset") if name else self.tr("New Preset"))
        self.setMinimumWidth(400)
        self.colors = colors or ["#CCCCCC"]
        self.result_name = name
        self.result_colors = self.colors.copy()

        layout = QVBoxLayout()
        self.setLayout(layout)

        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText(self.tr("Preset Name"))
        form.addRow(self.tr("Name:"), self.name_edit)
        layout.addLayout(form)

        layout.addWidget(QLabel(self.tr("Colors:")))
        self.colors_layout = FlowLayout()
        self.colors_container = QWidget()
        self.colors_container.setLayout(self.colors_layout)
        layout.addWidget(self.colors_container)

        self._refresh_colors()

        btn_add_color = QPushButton(self.tr("Add Color"))
        btn_add_color.clicked.connect(self.add_color)
        layout.addWidget(btn_add_color)

        buttons = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_ok.clicked.connect(self.save)
        self.btn_cancel = QPushButton(self.tr("Cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(self.btn_ok)
        buttons.addWidget(self.btn_cancel)
        layout.addLayout(buttons)

    def _refresh_colors(self):
        # Clear layout
        while self.colors_layout.count():
            item = self.colors_layout.takeAt(0)
            if w := item.widget():
                w.deleteLater()

        for i, color in enumerate(self.result_colors):
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setStyleSheet(
                f"background-color: {color}; border: 1px solid #888; border-radius: 4px;"
            )
            btn.clicked.connect(lambda checked, idx=i: self.edit_color(idx))

            # Tooltip for help
            btn.setToolTip(self.tr("Click to edit, Right-click to remove"))

            # Right click to remove
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, idx=i: self.remove_color(idx))

            self.colors_layout.addWidget(btn)

    def add_color(self):
        from PyQt6.QtWidgets import QColorDialog

        color = QColorDialog.getColor(QColor("#CCCCCC"), self)
        if color.isValid():
            self.result_colors.append(color.name().upper())
            self._refresh_colors()

    def edit_color(self, idx):
        from PyQt6.QtWidgets import QColorDialog

        color = QColorDialog.getColor(QColor(self.result_colors[idx]), self)
        if color.isValid():
            self.result_colors[idx] = color.name().upper()
            self._refresh_colors()

    def remove_color(self, idx):
        if len(self.result_colors) > 1:
            self.result_colors.pop(idx)
            self._refresh_colors()

    def save(self):
        self.result_name = self.name_edit.text().strip()
        if not self.result_name:
            QMessageBox.warning(self, self.tr("Input Error"), self.tr("Please enter a name."))
            return
        self.accept()


class PresetManagerDialog(QDialog):
    """Dialog to list, add, edit, and delete custom presets."""

    def __init__(self, parent, settings: AppSettings):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Manage Color Presets"))
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.settings = settings

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.list = QListWidget()
        layout.addWidget(self.list)

        self._refresh_list()

        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton(self.tr("Add"))
        self.btn_add.clicked.connect(self.add_preset)
        self.btn_edit = QPushButton(self.tr("Edit"))
        self.btn_edit.clicked.connect(self.edit_preset)
        self.btn_delete = QPushButton(self.tr("Delete"))
        self.btn_delete.clicked.connect(self.delete_preset)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.btn_close = QPushButton(self.tr("Close"))
        self.btn_close.clicked.connect(self.accept)
        layout.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignRight)

    def _refresh_list(self):
        from src.core.config import COLOR_PRESETS

        self.list.clear()

        # Built-in (Read-only)
        for name in COLOR_PRESETS:
            item = QListWidgetItem(name)
            # Use data to mark as built-in
            item.setData(Qt.ItemDataRole.UserRole, True)
            item.setForeground(QColor("#888"))
            self.list.addItem(item)

        # Custom
        for name in self.settings.custom_presets:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, False)
            self.list.addItem(item)

    def add_preset(self):
        from src.core.config import COLOR_PRESETS

        dialog = PresetEditorDialog(self)
        if dialog.exec():
            name = dialog.result_name
            if name in self.settings.custom_presets or name in COLOR_PRESETS:
                QMessageBox.warning(self, self.tr("Error"), self.tr("Preset name already exists."))
                return
            self.settings.custom_presets[name] = dialog.result_colors
            self._refresh_list()

    def edit_preset(self):
        from src.core.config import COLOR_PRESETS

        item = self.list.currentItem()
        if not item or item.data(Qt.ItemDataRole.UserRole):  # Is built-in
            return

        name = item.text()
        colors = self.settings.custom_presets.get(name)
        dialog = PresetEditorDialog(self, name, colors)
        if dialog.exec():
            new_name = dialog.result_name
            if new_name != name and (
                new_name in self.settings.custom_presets or new_name in COLOR_PRESETS
            ):
                QMessageBox.warning(self, self.tr("Error"), self.tr("Preset name already exists."))
                return

            if new_name != name:
                del self.settings.custom_presets[name]
            self.settings.custom_presets[new_name] = dialog.result_colors
            self._refresh_list()

    def delete_preset(self):
        item = self.list.currentItem()
        if not item or item.data(Qt.ItemDataRole.UserRole):
            return

        name = item.text()
        if (
            QMessageBox.question(
                self, self.tr("Confirm Delete"), self.tr("Delete preset '{}'?").format(name)
            )
            == QMessageBox.StandardButton.Yes
            and name in self.settings.custom_presets
        ):
            del self.settings.custom_presets[name]
            self._refresh_list()


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
        self.resize(900, 750)  # Increased size for better visibility of list and tab contents

        icon_path = get_resource_path(os.path.join("resources", "app_icon.ico"))
        self.setWindowIcon(QIcon(icon_path))

        self.profiles: list[MenuProfile] = []
        self.current_profile_idx = -1
        self._nav_stack: list[PieSlice] = []  # Stack of submenus currently navigated into
        self.item_widgets: list[PieItemWidget] = []
        self.selected_item_widget: PieItemWidget | None = None  # Renamed from selected_widget

        main_layout = QHBoxLayout()  # Changed to QHBoxLayout for sidebar
        self.setLayout(main_layout)

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
        self.group_trigger = QGroupBox()
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
        self.group_items = QGroupBox()
        self.group_items.setStyleSheet("QGroupBox { border: none; }")
        group_items_layout = QVBoxLayout()

        # Breadcrumb navigation for submenus
        self.breadcrumb_layout = QHBoxLayout()
        self.btn_nav_up = QPushButton("⬆ Back")
        self.btn_nav_up.clicked.connect(self.navigate_up)
        self.btn_nav_up.setVisible(False)
        self.lbl_breadcrumb = QLabel("Root:")
        self.lbl_breadcrumb.setStyleSheet("font-weight: bold; color: #888;")
        self.breadcrumb_layout.addWidget(self.btn_nav_up)
        self.breadcrumb_layout.addWidget(self.lbl_breadcrumb)
        self.breadcrumb_layout.addStretch()
        group_items_layout.addLayout(self.breadcrumb_layout)

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
        item_btns = QHBoxLayout()
        self.btn_add_i = QPushButton("Add Item")
        self.btn_add_i.clicked.connect(self.add_item)
        self.btn_edit_i = QPushButton("Edit")
        self.btn_edit_i.clicked.connect(self.edit_item)
        self.btn_del_i = QPushButton("Remove")
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
        self.preview_widget.update_unified_color(
            self.settings.color_mode, self.settings.unified_color, self.settings.selected_preset
        )
        preview_layout.addWidget(self.preview_widget, 0, Qt.AlignmentFlag.AlignCenter)
        preview_layout.addStretch()
        self.preview_group.setLayout(preview_layout)
        items_h_layout.addWidget(self.preview_group, 2)

        menu_layout.addLayout(items_h_layout)

        self.tabs.addTab(menu_tab, "")
        self.menu_tab_idx = self.tabs.indexOf(menu_tab)

        # Tab 2: Appearance
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout()
        appearance_layout.setSpacing(10)
        appearance_tab.setLayout(appearance_layout)

        # Tab 3: Behavior
        behavior_tab = QWidget()
        behavior_layout = QVBoxLayout()
        behavior_layout.setSpacing(10)
        behavior_tab.setLayout(behavior_layout)

        # Tab 4: System
        system_tab = QWidget()
        system_layout = QVBoxLayout()
        system_layout.setSpacing(10)
        system_tab.setLayout(system_layout)

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
        system_layout.addWidget(self.group_language)

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

        # Text Outline
        self.lbl_text_outline = QLabel()
        self.text_outline_checkbox = QCheckBox()
        self.text_outline_checkbox.setChecked(self.settings.enable_text_outline)
        self.text_outline_checkbox.stateChanged.connect(self.set_dirty)
        adv_form.addRow(self.lbl_text_outline, self.text_outline_checkbox)

        # Dynamic Text Color
        self.lbl_dynamic_text = QLabel()
        self.dynamic_text_checkbox = QCheckBox()
        self.dynamic_text_checkbox.setChecked(self.settings.dynamic_text_color)
        self.dynamic_text_checkbox.stateChanged.connect(self.set_dirty)
        adv_form.addRow(self.lbl_dynamic_text, self.dynamic_text_checkbox)

        # Dim Background
        self.lbl_dim_bg = QLabel()
        self.dim_bg_checkbox = QCheckBox()
        self.dim_bg_checkbox.setChecked(self.settings.dim_background)
        self.dim_bg_checkbox.stateChanged.connect(self.set_dirty)
        adv_form.addRow(self.lbl_dim_bg, self.dim_bg_checkbox)

        # Color Mode
        self.lbl_color_mode = QLabel()
        self.combo_color_mode = QComboBox()
        self.combo_color_mode.addItem("Individual Colors", "individual")
        self.combo_color_mode.addItem("Unified Color", "unified")
        self.combo_color_mode.addItem("Color Presets", "preset")

        idx = self.combo_color_mode.findData(self.settings.color_mode)
        if idx >= 0:
            self.combo_color_mode.setCurrentIndex(idx)

        self.combo_color_mode.currentIndexChanged.connect(self.set_dirty)
        self.combo_color_mode.currentIndexChanged.connect(self._update_color_mode_visibility)

        # Unified Color Picker (Sub-option)
        self.btn_unified_color = QPushButton()
        self.btn_unified_color.setFixedWidth(40)
        self.btn_unified_color.clicked.connect(self.pick_unified_color)
        self._current_unified_color = self.settings.unified_color
        self._update_unified_color_btn_style()

        # Preset Picker (Sub-option)

        self.preset_visual = ColorStripWidget()
        self.btn_manage_presets = QPushButton()
        self.btn_manage_presets.clicked.connect(self.manage_presets)

        self.combo_preset = QComboBox()
        self._refresh_preset_list()

        idx_p = self.combo_preset.findData(self.settings.selected_preset)
        if idx_p >= 0:
            self.combo_preset.setCurrentIndex(idx_p)

        color_mode_layout = QHBoxLayout()
        color_mode_layout.addWidget(self.combo_color_mode)
        color_mode_layout.addWidget(self.btn_unified_color)
        color_mode_layout.addWidget(self.combo_preset)
        color_mode_layout.addWidget(self.preset_visual)
        color_mode_layout.addWidget(self.btn_manage_presets)
        color_mode_layout.addStretch()
        adv_form.addRow(self.lbl_color_mode, color_mode_layout)

        # Connect signals
        self.combo_color_mode.currentIndexChanged.connect(self.set_dirty)
        self.combo_color_mode.currentIndexChanged.connect(self._update_color_mode_visibility)
        self.combo_color_mode.currentIndexChanged.connect(self._on_color_mode_ui_changed)
        self.combo_preset.currentIndexChanged.connect(self.set_dirty)
        self.combo_preset.currentIndexChanged.connect(self._on_color_mode_ui_changed)

        # Font Family
        self.lbl_font_family = QLabel()
        self.font_family_combo = QFontComboBox()
        self.font_family_combo.setCurrentFont(QFont(self.settings.font_family))
        self.font_family_combo.currentFontChanged.connect(self.set_dirty)
        adv_form.addRow(self.lbl_font_family, self.font_family_combo)

        # Animations (Moved to Appearance)
        self.lbl_show_animations = QLabel()
        self.show_animations_checkbox = QCheckBox()
        self.show_animations_checkbox.setChecked(self.settings.show_animations)
        self.show_animations_checkbox.stateChanged.connect(self.set_dirty)
        adv_form.addRow(self.lbl_show_animations, self.show_animations_checkbox)

        self.group_adv.setLayout(adv_form)
        appearance_layout.addWidget(self.group_adv)
        appearance_layout.addStretch()

        # ── Group 3: 動作 ─────────────────────────────────────────
        self.group_behavior = QGroupBox()
        behavior_form = QFormLayout()

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
        behavior_layout.addWidget(self.group_behavior)

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
        behavior_layout.addWidget(self.group_trigger_behavior)
        behavior_layout.addStretch()

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
        system_layout.addWidget(self.group_backup)
        system_layout.addStretch()

        self.tabs.addTab(appearance_tab, "")
        self.appearance_tab_idx = self.tabs.indexOf(appearance_tab)

        self.tabs.addTab(behavior_tab, "")
        self.behavior_tab_idx = self.tabs.indexOf(behavior_tab)

        self.tabs.addTab(system_tab, "")
        self.system_tab_idx = self.tabs.indexOf(system_tab)

        # Apply initial visibility
        self._update_scale_visibility()
        self._update_color_mode_visibility()

        # Bottom Save Row
        self.btn_save = QPushButton("Save & Apply")
        self.btn_save.setFixedHeight(45)
        self.btn_save.setEnabled(False)  # Initial state is disabled (no changes yet)
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
        self.tabs.setTabText(self.menu_tab_idx, self.tr("Profiles"))
        self.tabs.setTabText(self.appearance_tab_idx, self.tr("Appearance"))
        self.tabs.setTabText(self.behavior_tab_idx, self.tr("Behavior"))
        self.tabs.setTabText(self.system_tab_idx, self.tr("System"))

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
        self.lbl_text_outline.setText(self.tr("Text Outline:"))
        self.text_outline_checkbox.setText(self.tr("Add dark outline to menu text for visibility"))
        self.lbl_dynamic_text.setText(self.tr("Dynamic Text Color:"))
        self.dynamic_text_checkbox.setText(self.tr("Auto-switch text to black on bright items"))
        self.lbl_dim_bg.setText(self.tr("Dim Background:"))
        self.dim_bg_checkbox.setText(self.tr("Darken the screen behind the menu"))
        self.lbl_font_family.setText(self.tr("Font Family:"))

        self.lbl_color_mode.setText(self.tr("Color Mode:"))
        self.combo_color_mode.setItemText(0, self.tr("Individual Colors"))
        self.combo_color_mode.setItemText(1, self.tr("Unified Color"))
        self.combo_color_mode.setItemText(2, self.tr("Color Presets"))
        self.btn_unified_color.setToolTip(self.tr("Change Unified Color"))
        self.combo_preset.setToolTip(self.tr("Select a Color Palette"))
        self.btn_manage_presets.setText(self.tr("Edit Presets..."))

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

    def set_dirty(self, *args, **kwargs):
        if getattr(self, "_is_loading", False):
            return
        self.is_dirty = True
        if hasattr(self, "btn_save"):
            self.btn_save.setEnabled(True)
            self.btn_save.setText(self.tr("Save & Apply"))

    def _apply_theme(self):
        dark = is_dark_mode()

        main_bg = "#1e1e1e" if dark else "#ffffff"
        text_color = "#e0e0e0" if dark else "#24292f"
        card_bg = "#252526" if dark else "#f6f8fa"
        border_clr = "#3c3c3c" if dark else "#e1e4e8"
        btn_bg = "#333333" if dark else "#f3f4f6"
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
        dark = is_dark_mode()
        disabled_bg = "#444444" if dark else "#e1e4e8"
        disabled_fg = "#888888" if dark else "#a3aab2"
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: #2da44e;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #2c974b;
            }}
            QPushButton:pressed {{
                background-color: #298e46;
            }}
            QPushButton:disabled {{
                background-color: {disabled_bg};
                color: {disabled_fg};
            }}
        """)

    def load_data(self) -> None:
        """Load settings and profiles from configuration."""
        self._is_loading = True
        logger.info("Loading settings data")
        self.profiles, self.settings = config.load_config()  # Load all profiles and global settings
        self.action_delay_spin.setValue(self.settings.action_delay_ms)
        self.overlay_size_spin.setValue(self.settings.overlay_size)
        self.menu_opacity_slider.setValue(self.settings.menu_opacity)
        self.preview_widget.update_opacity(self.settings.menu_opacity)
        self.icon_size_slider.setValue(self.settings.icon_size)
        self.text_size_slider.setValue(self.settings.text_size)
        self.text_outline_checkbox.setChecked(self.settings.enable_text_outline)
        self.dynamic_text_checkbox.setChecked(self.settings.dynamic_text_color)
        self.dim_bg_checkbox.setChecked(self.settings.dim_background)
        self.font_family_combo.setCurrentFont(QFont(self.settings.font_family))
        self.show_animations_checkbox.setChecked(self.settings.show_animations)
        self.replay_checkbox.setChecked(self.settings.replay_unselected)
        self.long_press_spin.setValue(self.settings.long_press_delay_ms)
        self.auto_scale_checkbox.setChecked(self.settings.auto_scale_with_menu)
        self._update_scale_visibility()  # Ensure rows are hidden/shown
        self.key_delay_spin.setValue(getattr(self.settings, "key_sequence_delay_ms", 0))

        # Language
        lang_idx = self.combo_language.findData(self.settings.language)
        if lang_idx >= 0:
            self.combo_language.setCurrentIndex(lang_idx)

        # Color Mode & Presets
        self._current_unified_color = self.settings.unified_color
        self._update_unified_color_btn_style()

        # Update mode combo
        idx = self.combo_color_mode.findData(self.settings.color_mode)
        if idx >= 0:
            self.combo_color_mode.setCurrentIndex(idx)

        # Refresh custom presets from data
        self._refresh_preset_list()

        # Update visual strip and preview
        self._on_color_mode_ui_changed()
        self._update_color_mode_visibility()

        self.profile_list.clear()
        for p in self.profiles:
            self.profile_list.addItem(p.name)

        if self.profiles:
            self.profile_list.setCurrentRow(0)  # Select the first profile by default
        else:
            # If no profiles exist, create a default one
            self.add_profile(default_name="デフォルトプロファイル")

        self.is_dirty = False  # Reset dirty flag after loading
        self._is_loading = False
        if hasattr(self, "btn_save"):
            self.btn_save.setEnabled(False)
            self.btn_save.setText(self.tr("Save & Apply"))

    def current_items(self) -> list[PieSlice]:
        """Returns the list of items based on current navigation depth."""
        if self._nav_stack:
            return self._nav_stack[-1].submenu_items
        if self.current_profile_idx != -1 and self.current_profile_idx < len(self.profiles):
            return self.profiles[self.current_profile_idx].items
        return []

    def switch_profile(self, index: int) -> None:
        """Switch the currently edited profile."""
        if index < 0 or index >= len(self.profiles):
            return

        self.current_profile_idx = index
        self._nav_stack.clear()

        p = self.profiles[index]
        self.trigger_input.setText(p.trigger_key)

        # Display list as tags
        targets = p.target_apps if p.target_apps else []
        self._update_app_tags(targets)

        self.update_breadcrumb_ui()
        self.update_item_list()

    def update_breadcrumb_ui(self):
        """Update breadcrumb label and back button visibility."""
        if not self._nav_stack:
            self.btn_nav_up.setVisible(False)
            if self.current_profile_idx != -1:
                pname = self.profiles[self.current_profile_idx].name
                self.lbl_breadcrumb.setText(f"Root ({pname})")
            else:
                self.lbl_breadcrumb.setText("Root")
        else:
            self.btn_nav_up.setVisible(True)
            path_names = [s.label for s in self._nav_stack]
            self.lbl_breadcrumb.setText("Root > " + " > ".join(path_names))

    def enter_submenu(self, widget: PieItemWidget):
        """Navigate one level down into a submenu item."""
        if widget.item.action_type == "submenu":
            self._nav_stack.append(widget.item)
            self.update_breadcrumb_ui()
            self.update_item_list()

    def navigate_up(self):
        """Navigate one level up to the parent menu."""
        if self._nav_stack:
            self._nav_stack.pop()
            self.update_breadcrumb_ui()
            self.update_item_list()

    def update_item_list(self, override_items: list[PieSlice] | None = None) -> None:
        """Update the UI list of pie items based on current context."""
        items = override_items if override_items is not None else self.current_items()

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
        color_mode = (
            self.combo_color_mode.currentData()
            if hasattr(self, "combo_color_mode")
            else getattr(self.settings, "color_mode", "individual")
        )
        for item in items:
            w = PieItemWidget(item, color_mode=color_mode)
            w.clicked.connect(self.on_item_clicked)
            w.double_clicked.connect(self.edit_item)
            w.enter_submenu.connect(self.enter_submenu)
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
        items = self.current_items()
        used_colors = [item.color for item in items]

        # Pass current trigger key for validation
        current_trigger = self.trigger_input.text()

        dialog = ItemEditorDialog(
            self,
            hook_control=self.hook_control,
            used_colors=used_colors,
            trigger_key=current_trigger,
            all_profiles=self.profiles,
        )
        dialog.exec()
        if dialog.result_item:
            items.append(dialog.result_item)
            self.set_dirty()

        # Even if cancelled, icons might have been deleted from library
        self.update_item_list()
        if items:
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
            self,
            item_to_edit,
            hook_control=self.hook_control,
            trigger_key=current_trigger,
            all_profiles=self.profiles,
        )
        dialog.exec()
        if dialog.result_item:
            items = self.current_items()
            items[idx] = dialog.result_item
            self.set_dirty()

        # Even if cancelled, icons might have been deleted from library
        self.update_item_list()
        self.on_item_clicked(self.item_widgets[idx])  # Re-select the edited item

    def remove_item(self):
        if not self.selected_item_widget:
            return

        try:
            idx = self.item_widgets.index(self.selected_item_widget)
            items = self.current_items()
            items.pop(idx)
            self.update_item_list()
            self.set_dirty()
        except (RuntimeError, ValueError):
            self.selected_item_widget = None
            # Refresh list anyway if we can't find the widget but one was 'selected'
            self.update_item_list()

    def move_up(self):
        if not self.selected_item_widget:
            return
        try:
            idx = self.item_widgets.index(self.selected_item_widget)
            if idx > 0:
                current_items = self.current_items()
                current_items[idx], current_items[idx - 1] = (
                    current_items[idx - 1],
                    current_items[idx],
                )
                self.update_item_list()
                self.on_item_clicked(self.item_widgets[idx - 1])
                self.set_dirty()
        except (RuntimeError, ValueError):
            self.selected_item_widget = None

    def move_down(self) -> None:
        if not self.selected_item_widget:
            return
        try:
            idx = self.item_widgets.index(self.selected_item_widget)
            if idx < len(self.item_widgets) - 1:
                current_items = self.current_items()
                current_items[idx], current_items[idx + 1] = (
                    current_items[idx + 1],
                    current_items[idx],
                )
                self.update_item_list()
                self.on_item_clicked(self.item_widgets[idx + 1])
                self.set_dirty()
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
        self.settings.enable_text_outline = self.text_outline_checkbox.isChecked()
        self.settings.dynamic_text_color = self.dynamic_text_checkbox.isChecked()
        self.settings.dim_background = self.dim_bg_checkbox.isChecked()
        self.settings.font_family = self.font_family_combo.currentFont().family()
        self.settings.show_animations = self.show_animations_checkbox.isChecked()
        self.settings.replay_unselected = self.replay_checkbox.isChecked()
        self.settings.long_press_delay_ms = self.long_press_spin.value()
        self.settings.auto_scale_with_menu = self.auto_scale_checkbox.isChecked()
        self.settings.key_sequence_delay_ms = self.key_delay_spin.value()
        self.settings.color_mode = self.combo_color_mode.currentData()
        self.settings.unified_color = self._current_unified_color
        self.settings.selected_preset = self.combo_preset.currentData()
        self.settings.language = self.combo_language.currentData()

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
                self.btn_save.setEnabled(False)
                original_text = self.tr("Save & Apply")
                self.btn_save.setText(self.tr("✓ Saved successfully"))

                # Restore text after 3 seconds
                def restore_text():
                    if not self.btn_save.isEnabled() and self.btn_save.text() == self.tr(
                        "✓ Saved successfully"
                    ):
                        self.btn_save.setText(original_text)

                QTimer.singleShot(3000, restore_text)
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

    def pick_unified_color(self) -> None:
        """Open a color dialog to select the unified menu color."""
        from PyQt6.QtWidgets import QColorDialog

        color = QColorDialog.getColor(
            QColor(self._current_unified_color), self, self.tr("Select Unified Color")
        )
        if color.isValid():
            self._current_unified_color = color.name()
            self._update_unified_color_btn_style()
            self._on_color_mode_ui_changed()
            self.set_dirty()

    def _update_unified_color_btn_style(self) -> None:
        """Update the background color of the unified color button."""
        self.btn_unified_color.setStyleSheet(
            f"background-color: {self._current_unified_color}; border: 1px solid #888;"
        )

    def _update_color_mode_visibility(self) -> None:
        """Show/hide sub-options based on the selected color mode."""
        mode = self.combo_color_mode.currentData()
        self.btn_unified_color.setVisible(mode == "unified")
        self.combo_preset.setVisible(mode == "preset")
        self.preset_visual.setVisible(mode == "preset")
        self.btn_manage_presets.setVisible(mode == "preset")

    def _on_color_mode_ui_changed(self) -> None:
        """Sync preview and visual strip with current color mode UI state."""
        mode = self.combo_color_mode.currentData()
        palette = self._get_current_palette() if mode == "preset" else []
        self.preset_visual.set_palette(palette)

        self.preview_widget.update_unified_color(
            mode,
            self._current_unified_color,
            self.combo_preset.currentData(),
            palette=palette,
        )

        # Update item list to hide/show individual color boxes
        self.update_item_list()

    def _refresh_preset_list(self) -> None:
        """Populate the preset combo box with merged built-in and custom presets."""
        from src.core.config import COLOR_PRESETS

        self.combo_preset.blockSignals(True)
        self.combo_preset.clear()

        # Merge built-in and custom
        for name in COLOR_PRESETS:
            self.combo_preset.addItem(name, name)
        for name in self.settings.custom_presets:
            self.combo_preset.addItem(f"★ {name}", name)

        # Try to restore selection
        idx = self.combo_preset.findData(self.settings.selected_preset)
        if idx >= 0:
            self.combo_preset.setCurrentIndex(idx)
        else:
            self.combo_preset.setCurrentIndex(0)
        self.combo_preset.blockSignals(False)

    def _get_current_palette(self) -> list[str]:
        """Get the color palette for the currently selected preset."""
        preset_name = self.combo_preset.currentData()
        if not preset_name:
            return []

        from src.core.config import COLOR_PRESETS

        if preset_name in COLOR_PRESETS:
            return COLOR_PRESETS[preset_name]
        return self.settings.custom_presets.get(preset_name, [])

    def manage_presets(self) -> None:
        """Open the preset manager dialog."""
        dialog = PresetManagerDialog(self, self.settings)
        if dialog.exec():
            self._refresh_preset_list()
            self._on_color_mode_ui_changed()
            self.set_dirty()
