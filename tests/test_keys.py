import pytest

from src.core.keys import normalize_key_combo, normalize_key_name, split_key_combo


@pytest.mark.parametrize(
    ("combo", "expected"),
    [
        ("ctrl+z", ["ctrl", "z"]),
        ("Ctrl+Shift+PgUp", ["ctrl", "shift", "page_up"]),
        ("ctrl+del", ["ctrl", "delete"]),
        ("win+space", ["windows", "space"]),
        ("ctrl++", ["ctrl", "plus"]),
        ("+", ["plus"]),
        ("ctrl+plus", ["ctrl", "plus"]),
        ("return", ["enter"]),
        ("", []),
        ("  ", []),
    ],
)
def test_split_key_combo(combo, expected):
    assert split_key_combo(combo) == expected


def test_normalize_key_combo_makes_equivalent_spellings_equal():
    assert normalize_key_combo("Ctrl+PgUp") == normalize_key_combo("ctrl+page_up")
    assert normalize_key_combo("esc") == normalize_key_combo("Escape")


def test_normalize_key_name_passthrough():
    assert normalize_key_name("F5") == "f5"
    assert normalize_key_name("a") == "a"
