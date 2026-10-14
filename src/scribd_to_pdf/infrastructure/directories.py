import os
import sys
from pathlib import Path

APP_DIRECTORY = "scribd-to-pdf"


def user_config_directory() -> Path:
    if sys.platform == "win32":
        base = _absolute_path_from_env("APPDATA") or Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = _absolute_path_from_env("XDG_CONFIG_HOME") or Path.home() / ".config"

    return base / APP_DIRECTORY


def user_data_directory() -> Path:
    if sys.platform == "win32":
        base = _absolute_path_from_env("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = _absolute_path_from_env("XDG_DATA_HOME") or Path.home() / ".local" / "share"

    return base / APP_DIRECTORY


def _absolute_path_from_env(name: str) -> Path | None:
    value = os.environ.get(name, "")
    return Path(value) if value and Path(value).is_absolute() else None
