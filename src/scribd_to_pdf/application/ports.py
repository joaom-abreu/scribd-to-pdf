from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from scribd_to_pdf.domain.document import Document

ProgressListener = Callable[[str], None]
ReadySignal = Callable[[], None]


class CaptureRepository(Protocol):
    def load_complete(self, document: Document) -> list[Path]: ...


class PageCapturer(Protocol):
    def capture(
        self,
        document: Document,
        *,
        resume: bool,
        wait_for_ready: ReadySignal,
        on_status: ProgressListener,
    ) -> list[Path]: ...


class PdfBuilder(Protocol):
    def build(self, image_paths: list[Path], output_path: Path, *, compact: bool) -> Path: ...


class TextRecognizer(Protocol):
    def check_available(self) -> None: ...

    def recognize(self, pdf_path: Path, language: str, *, text_path: Path | None) -> None: ...
