import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile


SUPPORTED_LANGUAGES = ("por", "eng", "spa", "fra", "deu")


@dataclass(frozen=True)
class Preferences:
    destination_folder: str = ""
    ocr_enabled: bool = False
    ocr_languages: tuple[str, ...] = ("por",)


def get_preferences_path() -> Path:
    home = Path.home()

    if sys.platform == "win32":
        configured = os.environ.get("APPDATA", "")
        base = (
            Path(configured)
            if configured and Path(configured).is_absolute()
            else home / "AppData" / "Roaming"
        )
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        configured = os.environ.get("XDG_CONFIG_HOME", "")
        base = (
            Path(configured)
            if configured and Path(configured).is_absolute()
            else home / ".config"
        )

    return base / "scribd-to-pdf" / "preferences.json"


def load_preferences(path: Path | None = None) -> Preferences:
    try:
        path = path if path is not None else get_preferences_path()
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return Preferences()

    if not isinstance(data, dict):
        return Preferences()

    folder = data.get("destination_folder", "")

    if (
        not isinstance(folder, str)
        or "\0" in folder
        or not Path(folder).is_absolute()
    ):
        folder = ""

    enabled = data.get("ocr_enabled", False)

    if not isinstance(enabled, bool):
        enabled = False

    selected = data.get("ocr_languages", ["por"])

    if isinstance(selected, list):
        languages = tuple(dict.fromkeys(
            code
            for code in selected
            if isinstance(code, str) and code in SUPPORTED_LANGUAGES
        ))

        if selected and not languages:
            languages = ("por",)
    else:
        languages = ("por",)

    return Preferences(
        destination_folder=folder,
        ocr_enabled=enabled,
        ocr_languages=languages,
    )


def save_preferences(preferences: Preferences, path: Path | None = None) -> None:
    path = path if path is not None else get_preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix="preferences-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(asdict(preferences), stream, ensure_ascii=False, indent=2)
            stream.write("\n")

        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
