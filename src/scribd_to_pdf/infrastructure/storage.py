import json
from pathlib import Path

from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.domain.capture import CaptureProgress
from scribd_to_pdf.domain.document import Document
from scribd_to_pdf.infrastructure.directories import user_data_directory
from scribd_to_pdf.infrastructure.files import write_text_atomically

CAPTURES_DIRECTORY = "captures"
MANIFEST_NAME = "capture.json"
LEGACY_VERSION = 1
MANIFEST_VERSION = 2
INVALID_MANIFEST = "O registro da captura é inválido para este documento."


def default_captures_root() -> Path:
    return user_data_directory() / CAPTURES_DIRECTORY


class CaptureStore:
    def __init__(self, document: Document, root: Path) -> None:
        self.document = document
        self.directory = root / document.document_id

    @property
    def manifest_path(self) -> Path:
        return self.directory / MANIFEST_NAME

    def page_path(self, number: int) -> Path:
        return self.directory / f"page_{number:04d}.png"

    def page_paths(self, total_pages: int) -> list[Path]:
        return [self.page_path(number) for number in range(1, total_pages + 1)]

    def has_page(self, number: int) -> bool:
        path = self.page_path(number)
        return path.is_file() and path.stat().st_size > 0

    def save_progress(self, progress: CaptureProgress) -> None:
        manifest = {
            "version": MANIFEST_VERSION,
            "document_id": self.document.document_id,
            "total_pages": progress.total_pages,
            "captured_pages": sorted(progress.captured_pages),
        }
        write_text_atomically(
            self.manifest_path,
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )

    def load_progress(self) -> CaptureProgress:
        if not self.manifest_path.is_file():
            raise ValueError(
                f"Não há captura registrada em {self.directory}. Faça uma nova captura."
            )

        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValueError("O registro da captura está corrompido.") from error

        return self._parse_manifest(manifest)

    def load_complete_capture(self) -> list[Path]:
        progress = self.load_progress()

        if not progress.is_complete:
            raise ValueError("A captura está incompleta. Retome a captura antes de reutilizá-la.")

        missing = [
            self.page_path(number)
            for number in range(1, progress.total_pages + 1)
            if not self.has_page(number)
        ]

        if missing:
            raise ValueError(f"Captura incompleta: página ausente ou vazia: {missing[0]}")

        return self.page_paths(progress.total_pages)

    def _parse_manifest(self, manifest: object) -> CaptureProgress:
        if not isinstance(manifest, dict) or manifest.get("document_id") != self.document.document_id:
            raise ValueError(INVALID_MANIFEST)

        total_pages = CaptureProgress(manifest.get("total_pages")).total_pages
        version = manifest.get("version")

        if type(version) is not int:
            raise ValueError(INVALID_MANIFEST)

        if version == LEGACY_VERSION:
            return CaptureProgress(total_pages, frozenset(range(1, total_pages + 1)))

        if version == MANIFEST_VERSION:
            return CaptureProgress(total_pages, _page_numbers(manifest.get("captured_pages")))

        raise ValueError(INVALID_MANIFEST)


def _page_numbers(value: object) -> frozenset[int]:
    if isinstance(value, list) and all(type(number) is int for number in value):
        return frozenset(value)

    raise ValueError("O registro contém números de página inválidos.")


class FileCaptureRepository:
    def __init__(self, root: Path) -> None:
        self._root = root

    def store(self, document: Document) -> CaptureStore:
        return CaptureStore(document, self._root)

    def load_complete(self, document: Document) -> list[Path]:
        try:
            return self.store(document).load_complete_capture()
        except (OSError, ValueError) as error:
            raise ConversionError(str(error)) from error
