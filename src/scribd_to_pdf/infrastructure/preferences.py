import json
from dataclasses import asdict, dataclass
from pathlib import Path

from scribd_to_pdf.domain.languages import DEFAULT_LANGUAGE, LANGUAGES
from scribd_to_pdf.infrastructure.directories import user_config_directory
from scribd_to_pdf.infrastructure.files import write_text_atomically

FILE_NAME = "preferences.json"
PRIVATE_DIRECTORY_MODE = 0o700


@dataclass(frozen=True)
class Preferences:
    destination_folder: str = ""
    ocr_enabled: bool = False
    ocr_languages: tuple[str, ...] = (DEFAULT_LANGUAGE,)
    export_text: bool = False
    compact_pdf: bool = False


def get_preferences_path() -> Path:
    return user_config_directory() / FILE_NAME


def load_preferences(path: Path | None = None) -> Preferences:
    try:
        data = json.loads((path or get_preferences_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Preferences()

    if not isinstance(data, dict):
        return Preferences()

    return Preferences(
        destination_folder=_parse_folder(data.get("destination_folder")),
        ocr_enabled=data.get("ocr_enabled") is True,
        ocr_languages=_parse_languages(data.get("ocr_languages")),
        export_text=data.get("export_text") is True,
        compact_pdf=data.get("compact_pdf") is True,
    )


def save_preferences(preferences: Preferences, path: Path | None = None) -> None:
    write_text_atomically(
        path or get_preferences_path(),
        json.dumps(asdict(preferences), ensure_ascii=False, indent=2) + "\n",
        directory_mode=PRIVATE_DIRECTORY_MODE,
    )


def _parse_folder(value: object) -> str:
    if isinstance(value, str) and "\0" not in value and Path(value).is_absolute():
        return value

    return ""


def _parse_languages(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return (DEFAULT_LANGUAGE,)

    languages = tuple(dict.fromkeys(
        code for code in value if isinstance(code, str) and code in LANGUAGES
    ))

    return languages if languages or not value else (DEFAULT_LANGUAGE,)
