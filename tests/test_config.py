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

    assert data["schema_version"] == 4
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
