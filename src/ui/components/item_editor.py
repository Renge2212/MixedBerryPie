import os

from PyQt6.QtCore import QStandardPaths, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core import config
from src.core.config import MenuProfile, PieSlice, add_to_icon_history
from src.core.utils import resolve_icon_path

from .custom_widgets import KeySequenceEdit, _render_icon_pixmap
from .icon_picker import IconPickerWidget
from .pie_preview import PiePreviewWidget


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
        # Note: 'parent' might be a SettingsWindow or a deeper layout
        parent_with_combo = parent
        while parent_with_combo and not hasattr(parent_with_combo, "combo_color_mode"):
            if hasattr(parent_with_combo, "parent"):
                parent_with_combo = parent_with_combo.parent()
            else:
                break

        if parent_with_combo and hasattr(parent_with_combo, "combo_color_mode"):
            self.color_mode = parent_with_combo.combo_color_mode.currentData()
            self.global_unified_color = getattr(
                parent_with_combo, "_current_unified_color", "#448AFF"
            )
            self.global_palette: list[str] = getattr(
                parent_with_combo, "_get_current_palette", lambda: []
            )()
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

        self.label_edit = QPlainTextEdit(item.label if item else "")
        self.label_edit.setPlaceholderText(self.tr("e.g. Copy, Paste, Brush..."))
        self.label_edit.setFixedHeight(52)  # ~2 lines
        self.label_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._label_limit_guard = False
        self.label_edit.textChanged.connect(self._enforce_label_max_lines)
        self.label_edit.textChanged.connect(self._update_preview)

        # Line counter hint (e.g. "1/2行")
        self.lbl_line_count = QLabel()
        self.lbl_line_count.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_line_count.setStyleSheet("color: gray; font-size: 10px;")
        label_container = QVBoxLayout()
        label_container.setSpacing(1)
        label_container.setContentsMargins(0, 0, 0, 0)
        label_container.addWidget(self.label_edit)
        label_container.addWidget(self.lbl_line_count)
        label_widget = QWidget()
        label_widget.setLayout(label_container)

        self.lbl_label = QLabel()  # Store reference for retranslation
        form_layout.addRow(self.lbl_label, label_widget)

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
        self._enforce_label_max_lines()  # Initialize line counter display

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

    def _enforce_label_max_lines(self) -> None:
        """Truncate label to max 2 lines."""
        if self._label_limit_guard:
            return
        text = self.label_edit.toPlainText()
        lines = text.split("\n")
        if len(lines) > 2:
            self._label_limit_guard = True
            cursor = self.label_edit.textCursor()
            self.label_edit.setPlainText("\n".join(lines[:2]))
            # Restore cursor to end
            cursor.movePosition(cursor.MoveOperation.End)
            self.label_edit.setTextCursor(cursor)
            self._label_limit_guard = False
        # Update line counter
        current_lines = min(len(lines), 2)
        self.lbl_line_count.setText(self.tr("{0}/2 lines").format(current_lines))

    def _update_preview(self):
        label = self.label_edit.toPlainText() or "サンプル"
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
        label = self.label_edit.toPlainText().strip()
        action_type = self.action_type_combo.currentData()
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
