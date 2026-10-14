import sys
from pathlib import Path

import pytest

from scribd_to_pdf.infrastructure.directories import user_config_directory, user_data_directory
from scribd_to_pdf.infrastructure.storage import default_captures_root


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    for variable in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "APPDATA", "LOCALAPPDATA"):
        monkeypatch.delenv(variable, raising=False)

    return tmp_path


@pytest.mark.parametrize(
    "platform, variable, setting, base_parts",
    [
        ("linux", "XDG_DATA_HOME", None, (".local", "share")),
        ("linux", "XDG_DATA_HOME", "absolute", ("custom",)),
        ("linux", "XDG_DATA_HOME", "relative", (".local", "share")),
        ("win32", "LOCALAPPDATA", "absolute", ("custom",)),
        ("win32", "LOCALAPPDATA", None, ("AppData", "Local")),
        ("darwin", "XDG_DATA_HOME", "absolute", ("Library", "Application Support")),
    ],
)
def test_data_directory_follows_each_system(home, monkeypatch, platform, variable, setting, base_parts):
    monkeypatch.setattr(sys, "platform", platform)

    if setting == "absolute":
        monkeypatch.setenv(variable, str(home / "custom"))
    elif setting == "relative":
        monkeypatch.setenv(variable, "relative-data")

    assert user_data_directory() == home.joinpath(*base_parts) / "scribd-to-pdf"


@pytest.mark.parametrize(
    "platform, base_parts",
    [("linux", (".config",)), ("win32", ("AppData", "Roaming")), ("darwin", ("Library", "Application Support"))],
)
def test_config_directory_follows_each_system(home, monkeypatch, platform, base_parts):
    monkeypatch.setattr(sys, "platform", platform)

    assert user_config_directory() == home.joinpath(*base_parts) / "scribd-to-pdf"


def test_captures_live_in_the_data_directory(home, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    assert default_captures_root() == home / ".local" / "share" / "scribd-to-pdf" / "captures"
