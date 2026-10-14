from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from scribd_to_pdf.domain.cancellation import ShouldCancel
from scribd_to_pdf.domain.document import Document

StatusListener = Callable[[str], None]
ReadySignal = Callable[[], None]


class CaptureRepository(Protocol):
    def directory(self, document: Document) -> Path: ...

    def load_complete(self, document: Document) -> list[Path]: ...


class PageCapturer(Protocol):
    def capture(
        self,
        document: Document,
        *,
        resume: bool,
        wait_for_ready: ReadySignal,
        on_status: StatusListener,
        should_cancel: ShouldCancel,
    ) -> list[Path]: ...


class PdfBuilder(Protocol):
    def build(self, image_paths: list[Path], output_path: Path) -> Path: ...


class TextRecognizer(Protocol):
    def check_available(self, language: str) -> None: ...

    def recognize(
        self,
        pdf_path: Path,
        language: str,
        *,
        text_path: Path | None,
        should_cancel: ShouldCancel,
    ) -> None: ...
