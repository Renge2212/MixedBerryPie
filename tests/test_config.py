import json

from src.core.config import AppSettings, MenuProfile, PieSlice, load_config, save_config


def test_load_config_missing_file(tmp_path, monkeypatch):
    """Test loading config when file doesn't exist - should create defaults"""
    # Point CONFIG_FILE to a non-existent file in tmp_path
    config_file = tmp_path / "menu_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))

    profiles, _settings = load_config()

    assert len(profiles) == 1
    assert profiles[0].name == "Default"
    assert config_file.exists()


def test_load_config_existing_file(tmp_path, monkeypatch):
    """Test loading existing config file (new multi-profile format)"""
    config_file = tmp_path / "menu_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))

    test_profiles = [
        MenuProfile(
            name="Profile1",
            trigger_key="ctrl+a",
            items=[PieSlice(label="Test1", key="x", color="#FF0000")],
        ),
        MenuProfile(name="Profile2", trigger_key="ctrl+b", items=[]),
    ]
    test_settings = AppSettings()

    # We need to manually save first or mock the file content
    # Since save_config also uses CONFIG_FILE, it should work with the patch
    save_config(test_profiles, test_settings)

    profiles, _settings = load_config()

    assert len(profiles) == 2
    assert profiles[0].name == "Profile1"
    assert profiles[1].trigger_key == "ctrl+b"


def test_load_config_v2_migration(tmp_path, monkeypatch):
    """Test migration from schema version 2 (single trigger) to 3 (multi profile)"""
    config_file = tmp_path / "menu_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))

    v2_data = {
        "schema_version": 2,
        "trigger_key": "tab",
        "items": [{"label": "Undo", "key": "ctrl+z", "color": "#FF5555"}],
        "settings": {"action_delay_ms": 75},
    }

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(v2_data, f)

    profiles, settings = load_config()

    assert len(profiles) == 1
    assert profiles[0].name == "Default"
    assert profiles[0].trigger_key == "tab"
    assert settings.action_delay_ms == 75
    # Verify new fields defaulted correctly
    assert settings.replay_unselected is False
    assert settings.long_press_delay_ms == 0


def test_load_config_corrupted_json(tmp_path, monkeypatch):
    """Test loading corrupted JSON - should return defaults"""
    config_file = tmp_path / "menu_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))

    with open(config_file, "w", encoding="utf-8") as f:
        f.write("{invalid json content")

    profiles, _settings = load_config()

    assert len(profiles) == 1
    assert profiles[0].name == "Default"


def test_save_config_success(tmp_path, monkeypatch):
    """Test saving config successfully"""
    config_file = tmp_path / "menu_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))

    test_profiles = [MenuProfile(name="Save", trigger_key="f1", items=[])]
    test_settings = AppSettings()

    result = save_config(test_profiles, test_settings)

    assert result is True
    assert config_file.exists()

    # Verify saved content
    with open(config_file, encoding="utf-8") as f:
        data = json.load(f)

    assert data["schema_version"] == 5
    assert len(data["profiles"]) == 1
    assert data["profiles"][0]["name"] == "Save"


def test_config_roundtrip(tmp_path, monkeypatch):
    """Test save and load roundtrip preserves data"""
    config_file = tmp_path / "menu_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))

    original_profiles = [
        MenuProfile(name="ProfileA", trigger_key="a", items=[PieSlice("L1", "k1", "#111")]),
        MenuProfile(name="ProfileB", trigger_key="b", items=[]),
    ]
    original_settings = AppSettings(action_delay_ms=100)

    save_config(original_profiles, original_settings)
    loaded_profiles, loaded_settings = load_config()

    assert len(loaded_profiles) == 2
    assert loaded_profiles[0].name == "ProfileA"
    assert loaded_profiles[0].items[0].label == "L1"
    assert loaded_settings.action_delay_ms == 100


def test_config_target_apps_list(tmp_path, monkeypatch):
    """Verify that target_apps list is preserved during save/load."""
    config_file = tmp_path / "menu_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))

    target_apps = ["notepad.exe", "Chrome", "Discord"]
    profile = MenuProfile(name="Apps", trigger_key="f3", items=[], target_apps=target_apps)

    save_config([profile], AppSettings())
    loaded_profiles, _ = load_config()

    assert len(loaded_profiles) == 1
    assert loaded_profiles[0].target_apps == target_apps


def test_config_recursive_submenus(tmp_path, monkeypatch):
    """Verify that PieSlice nested submenu_items are preserved during save/load."""
    config_file = tmp_path / "menu_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))

    nested_slice = PieSlice(
        label="Sub2",
        key="sub",
        color="#00FF00",
        action_type="command",
        submenu_items=[PieSlice(label="Deep", key="x", color="#111")],
    )

    parent_slice = PieSlice(
        label="Sub1", key="sub", color="#FFF", action_type="submenu", submenu_items=[nested_slice]
    )

    profile = MenuProfile(name="SubmenuTest", trigger_key="f4", items=[parent_slice])

    save_config([profile], AppSettings())
    loaded_profiles, _ = load_config()

    assert len(loaded_profiles) == 1
    assert len(loaded_profiles[0].items) == 1

    loaded_parent = loaded_profiles[0].items[0]
    assert loaded_parent.label == "Sub1"
    assert loaded_parent.action_type == "submenu"
    assert len(loaded_parent.submenu_items) == 1

    loaded_child = loaded_parent.submenu_items[0]
    assert loaded_child.label == "Sub2"
    assert len(loaded_child.submenu_items) == 1

    loaded_deep = loaded_child.submenu_items[0]
    assert loaded_deep.label == "Deep"
    assert len(loaded_deep.submenu_items) == 0


def _use_tmp_config(tmp_path, monkeypatch):
    config_file = tmp_path / "menu_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))
    return config_file


def test_load_config_skips_malformed_profile_and_keeps_others(tmp_path, monkeypatch):
    """One bad profile entry must not throw away the user's whole config."""
    config_file = _use_tmp_config(tmp_path, monkeypatch)
    data = {
        "schema_version": 5,
        "profiles": [
            {"name": "Mine", "trigger_key": "alt+q", "items": [{"label": "x", "key": "a"}]},
            "oops",
            {"name": "Broken items", "trigger_key": "f2", "items": "not a list"},
        ],
        "settings": {"first_run": False, "overlay_size": 500},
    }
    config_file.write_text(json.dumps(data), encoding="utf-8")

    profiles, settings = load_config()

    assert [p.name for p in profiles] == ["Mine", "Broken items"]
    assert profiles[0].items[0].label == "x"
    assert profiles[1].items == []
    assert settings.overlay_size == 500
    assert settings.first_run is False
    assert list(tmp_path.glob("menu_config.json.*.backup")), "original should be backed up"


def test_load_config_unreadable_file_is_not_first_run(tmp_path, monkeypatch):
    """Falling back to defaults must not trigger the welcome dialog.

    The welcome dialog saves the config, which would overwrite the user's
    (recoverable) file with the defaults.
    """
    config_file = _use_tmp_config(tmp_path, monkeypatch)
    config_file.write_text("{invalid json", encoding="utf-8")

    _, settings = load_config()

    assert settings.first_run is False
    assert list(tmp_path.glob("menu_config.json.*.backup"))


def test_load_config_unexpected_error_backs_up(tmp_path, monkeypatch):
    config_file = _use_tmp_config(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "src.core.config._parse_profile", lambda _p: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    config_file.write_text(
        json.dumps({"schema_version": 5, "profiles": [{"name": "A"}]}), encoding="utf-8"
    )

    profiles, settings = load_config()

    assert profiles[0].name == "Default"
    assert settings.first_run is False
    assert list(tmp_path.glob("menu_config.json.*.backup"))


def test_load_config_legacy_list_with_submenus_and_unknown_keys(tmp_path, monkeypatch):
    config_file = _use_tmp_config(tmp_path, monkeypatch)
    legacy = [
        {
            "label": "Parent",
            "key": "",
            "color": "#fff",
            "unknown_field": 1,
            "submenu_items": [{"label": "Child", "key": "c", "color": "#000"}],
        }
    ]
    config_file.write_text(json.dumps(legacy), encoding="utf-8")

    profiles, _ = load_config()

    parent = profiles[0].items[0]
    assert parent.label == "Parent"
    assert isinstance(parent.submenu_items[0], PieSlice)
    assert parent.submenu_items[0].label == "Child"


def test_default_profiles_are_not_shared(tmp_path, monkeypatch):
    """Editing loaded defaults in place must not change the module defaults."""
    from src.core import config

    _use_tmp_config(tmp_path, monkeypatch)
    profiles, _ = load_config()
    profiles[0].items[0].icon_path = None
    profiles[0].items.clear()

    assert config.DEFAULT_PROFILES[0].items
    assert config.DEFAULT_PROFILES[0].items[0].icon_path is not None
