import os
from typing import Any

from PyQt6.QtCore import (
    QEvent,
    Qt,
    QTimer,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
)
from PyQt6.QtWidgets import (
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
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core import config, i18n
from src.core.config import (
    MenuProfile,
    PieSlice,
)
from src.core.logger import get_logger
from src.core.utils import get_resource_path, is_dark_mode

from .components.custom_widgets import (
    AppPickerDialog,
    AppTagWidget,
    ColorStripWidget,
    FlowLayout,
    KeySequenceEdit,
    PieItemWidget,
    SteppedSlider,
)
from .components.item_editor import ItemEditorDialog
from .components.pie_preview import PiePreviewWidget
from .components.preset_manager import PresetManagerDialog

logger = get_logger(__name__)


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

        # Sync preview with submenu context
        if hasattr(self, "preview_widget"):
            depth = len(self._nav_stack)
            parent_items_stack: list[list[PieSlice]] = []
            selected_indices: list[int] = []
            if depth > 0 and self.current_profile_idx != -1:
                root_items = self.profiles[self.current_profile_idx].items
                parent_items_stack.append(list(root_items))
                # Compute selected index at each ancestor level
                current_list: list[PieSlice] = root_items
                for ancestor in self._nav_stack:
                    try:
                        idx = current_list.index(ancestor)
                    except ValueError:
                        # Fallback: search by identity
                        idx = next((j for j, it in enumerate(current_list) if it is ancestor), 0)
                    selected_indices.append(idx)
                    # Build parent items stack for depths below current
                    if ancestor is not self._nav_stack[-1]:
                        parent_items_stack.append(list(ancestor.submenu_items))
                    current_list = list(ancestor.submenu_items)
            self.preview_widget.update_context(items, depth, parent_items_stack, selected_indices)

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
