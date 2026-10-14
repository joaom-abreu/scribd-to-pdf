import json
from pathlib import Path

import pytest

from scribd_to_pdf import preferences as preferences_module
from scribd_to_pdf.preferences import (
    Preferences,
    get_preferences_path,
    load_preferences,
    save_preferences,
)


@pytest.mark.parametrize(
    "platform, variable, setting, base_parts",
    [
        ("linux", "XDG_CONFIG_HOME", None, (".config",)),
        ("linux", "XDG_CONFIG_HOME", "absolute", ("custom",)),
        ("linux", "XDG_CONFIG_HOME", "relative", (".config",)),
        ("win32", "APPDATA", "absolute", ("custom",)),
        ("win32", "APPDATA", None, ("AppData", "Roaming")),
        ("darwin", "XDG_CONFIG_HOME", None, ("Library", "Application Support")),
    ],
)
def test_preferences_path_uses_user_config_directory(
        tmp_path,
        monkeypatch,
        platform,
        variable,
        setting,
        base_parts,
):
    monkeypatch.setattr(preferences_module.sys, "platform", platform)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    if setting == "absolute":
        monkeypatch.setenv(variable, str(tmp_path / "custom"))
    elif setting == "relative":
        monkeypatch.setenv(variable, "relative-config")
    else:
        monkeypatch.delenv(variable, raising=False)

    assert get_preferences_path() == (
        tmp_path.joinpath(*base_parts) / "scribd-to-pdf" / "preferences.json"
    )


def test_missing_file_uses_defaults_without_creating_files(tmp_path):
    path = tmp_path / "config" / "preferences.json"

    assert load_preferences(path) == Preferences()
    assert not path.parent.exists()


@pytest.mark.parametrize("content", [b"{invalid", b"[]", b"null", b"false", b"17", b"\xff"])
def test_invalid_file_uses_defaults(tmp_path, content):
    path = tmp_path / "preferences.json"
    path.write_bytes(content)

    assert load_preferences(path) == Preferences()


def test_preferences_survive_reload_from_another_working_directory(tmp_path, monkeypatch):
    path = tmp_path / "config" / "preferences.json"
    preferences = Preferences(
        destination_folder=str(tmp_path / "Leituras da mãe"),
        ocr_enabled=True,
        ocr_languages=("por", "eng", "fra"),
    )
    monkeypatch.setattr(preferences_module, "get_preferences_path", lambda: path)

    save_preferences(preferences)
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)

    assert load_preferences() == preferences
    assert set(path.parent.iterdir()) == {path}


def test_empty_language_selection_is_preserved(tmp_path):
    path = tmp_path / "preferences.json"
    preferences = Preferences(ocr_enabled=True, ocr_languages=())

    save_preferences(preferences, path)

    assert load_preferences(path) == preferences


@pytest.mark.parametrize(
    "selected, expected",
    [(["fra", "fra", "unknown", 7], ("fra",)), (["unknown"], ("por",))],
)
def test_invalid_fields_are_filtered(tmp_path, selected, expected):
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({
        "destination_folder": "relative/path",
        "ocr_enabled": "true",
        "ocr_languages": selected,
    }), encoding="utf-8")

    assert load_preferences(path) == Preferences(ocr_languages=expected)


def test_unreadable_file_uses_defaults(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise PermissionError("Sem permissão.")

    monkeypatch.setattr(Path, "read_text", fail)

    assert load_preferences(tmp_path / "preferences.json") == Preferences()


def test_save_failure_keeps_previous_preferences_and_removes_temporary_file(
        tmp_path,
        monkeypatch,
):
    path = tmp_path / "config" / "preferences.json"
    save_preferences(Preferences(), path)
    original = path.read_bytes()

    def fail(*args, **kwargs):
        raise PermissionError("Sem permissão para substituir.")

    monkeypatch.setattr(Path, "replace", fail)

    with pytest.raises(PermissionError):
        save_preferences(Preferences(ocr_enabled=True), path)

    assert path.read_bytes() == original
    assert set(path.parent.iterdir()) == {path}
