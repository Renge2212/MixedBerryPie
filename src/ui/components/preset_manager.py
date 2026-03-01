from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.config import COLOR_PRESETS, AppSettings

from .custom_widgets import FlowLayout


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
            btn.clicked.connect(lambda _, idx=i: self.edit_color(idx))

            # Tooltip for help
            btn.setToolTip(self.tr("Click to edit, Right-click to remove"))

            # Right click to remove
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, idx=i: self.remove_color(idx))

            self.colors_layout.addWidget(btn)

    def add_color(self):
        color = QColorDialog.getColor(QColor("#CCCCCC"), self)
        if color.isValid():
            self.result_colors.append(color.name().upper())
            self._refresh_colors()

    def edit_color(self, idx):
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
        dialog = PresetEditorDialog(self)
        if dialog.exec():
            name = dialog.result_name
            if name in self.settings.custom_presets or name in COLOR_PRESETS:
                QMessageBox.warning(self, self.tr("Error"), self.tr("Preset name already exists."))
                return
            self.settings.custom_presets[name] = dialog.result_colors
            self._refresh_list()

    def edit_preset(self):
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
