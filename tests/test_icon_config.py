from src.core.config import AppSettings, MenuProfile, PieSlice, load_config, save_config


def test_save_and_load_icon_path(tmp_path, monkeypatch):
    """Test that icon_path is correctly saved and loaded."""
    # Setup temporary config file
    config_file = tmp_path / "test_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))

    icon_path = "C:/path/to/icon.png"
    item = PieSlice(label="Icon Item", key="ctrl+i", color="#FFFFFF", icon_path=icon_path)
    profile = MenuProfile(name="Test Profile", trigger_key="ctrl+space", items=[item])

    # Save
    save_config([profile], AppSettings())

    # Load
    loaded_profiles, _ = load_config()
    loaded_item = loaded_profiles[0].items[0]

    assert loaded_item.label == "Icon Item"
    assert loaded_item.icon_path == icon_path


def test_save_and_load_icon_size(tmp_path, monkeypatch):
    """Test that icon_size is correctly saved and loaded in AppSettings."""
    # Setup temporary config file
    config_file = tmp_path / "test_config.json"
    monkeypatch.setattr("src.core.config.CONFIG_FILE", str(config_file))
    monkeypatch.setattr("src.core.config.CONFIG_DIR", str(tmp_path))

    settings = AppSettings(icon_size=64)
    profiles: list[MenuProfile] = []

    # Save
    save_config(profiles, settings)

    # Load
    _, loaded_settings = load_config()

    assert loaded_settings.icon_size == 64
