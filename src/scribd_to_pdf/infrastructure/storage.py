import json
from pathlib import Path

from scribd_to_pdf.application.conversion import ConversionError
from scribd_to_pdf.domain.document import Document

MANIFEST_NAME = "capture.json"


def default_captures_root() -> Path:
    return Path.home() / ".scribd-to-pdf" / "captures"


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

    def save_total_pages(self, total_pages: int) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps({"total_pages": total_pages}) + "\n", encoding="utf-8")

    def load_total_pages(self) -> int:
        if not self.manifest_path.is_file():
            raise ValueError(
                f"Não há captura registrada em {self.directory}. Faça uma nova captura."
            )

        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return int(manifest["total_pages"])
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError("O registro da captura está corrompido.") from error

    def load_complete_capture(self) -> list[Path]:
        total_pages = self.load_total_pages()

        for number in range(1, total_pages + 1):
            if not self.has_page(number):
                raise ValueError(
                    f"Captura incompleta: página ausente ou vazia: {self.page_path(number)}. "
                    "Retome a captura com --resume."
                )

        return self.page_paths(total_pages)


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
