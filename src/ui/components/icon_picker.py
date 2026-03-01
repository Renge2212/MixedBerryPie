import os

from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QImage, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyle,
    QVBoxLayout,
)

from src.core.config import load_icon_history, remove_from_icon_history
from src.core.utils import get_resource_path, is_dark_mode, resolve_icon_path

from .custom_widgets import _render_icon_pixmap


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

    def accept(self):
        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.cancel()
            self._loader_thread.wait()
        super().accept()

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
