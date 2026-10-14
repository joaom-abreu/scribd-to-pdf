from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from scribd_to_pdf.application.ports import (
    CaptureRepository,
    PageCapturer,
    PdfBuilder,
    ReadySignal,
    TextRecognizer,
)
from scribd_to_pdf.domain.cancellation import ShouldCancel, never_cancel, raise_if_cancelled
from scribd_to_pdf.domain.document import Document

CONVERSION_INTERRUPTED = "Conversão interrompida."


class CaptureMode(Enum):
    NEW = auto()
    RESUME = auto()
    REUSE = auto()


class Stage(Enum):
    CAPTURE = auto()
    PDF = auto()
    OCR = auto()

    @property
    def cancellable(self) -> bool:
        return self is not Stage.PDF


ProgressListener = Callable[[Stage, str], None]


@dataclass(frozen=True)
class ConversionRequest:
    document: Document
    output_path: Path
    mode: CaptureMode = CaptureMode.NEW
    ocr_language: str | None = None
    export_text: bool = False

    def __post_init__(self) -> None:
        if self.output_path.suffix.lower() != ".pdf":
            raise ValueError("O arquivo de saída deve ter a extensão .pdf.")

        if self.export_text and self.ocr_language is None:
            raise ValueError("Salvar o texto reconhecido exige OCR.")

    @property
    def text_path(self) -> Path | None:
        return self.output_path.with_suffix(".txt") if self.export_text else None


@dataclass(frozen=True)
class ConversionResult:
    pdf_path: Path
    text_path: Path | None = None


class OcrInterrupted(InterruptedError):
    def __init__(self, pdf_path: Path, message: str) -> None:
        super().__init__(message)
        self.pdf_path = pdf_path


@dataclass(frozen=True)
class DocumentConverter:
    captures: CaptureRepository
    capturer: PageCapturer
    pdf_builder: PdfBuilder
    text_recognizer: TextRecognizer
    default_output_folder: Path

    def output_path(
        self,
        document: Document,
        destination: Path | None = None,
        folder: Path | None = None,
    ) -> Path:
        if destination is not None:
            return destination.expanduser()

        directory = folder if folder is not None else self.default_output_folder
        return directory / f"{document.document_id}.pdf"

    def check_requirements(self, request: ConversionRequest) -> None:
        if request.ocr_language is not None:
            self.text_recognizer.check_available(request.ocr_language)

    def convert(
        self,
        request: ConversionRequest,
        *,
        on_progress: ProgressListener,
        wait_for_ready: ReadySignal,
        should_cancel: ShouldCancel = never_cancel,
    ) -> ConversionResult:
        image_paths = self._collect_pages(request, on_progress, wait_for_ready, should_cancel)
        raise_if_cancelled(should_cancel, CONVERSION_INTERRUPTED)

        on_progress(Stage.PDF, f"Gerando PDF com {len(image_paths)} páginas...")
        pdf_path = self.pdf_builder.build(image_paths, request.output_path).resolve()

        if request.ocr_language is None:
            return ConversionResult(pdf_path)

        text_path = request.text_path.resolve() if request.text_path is not None else None
        on_progress(Stage.OCR, f"Aplicando OCR ({request.ocr_language})...")

        try:
            self.text_recognizer.recognize(
                pdf_path,
                request.ocr_language,
                text_path=text_path,
                should_cancel=should_cancel,
            )
        except InterruptedError as error:
            raise OcrInterrupted(pdf_path, str(error)) from error

        return ConversionResult(pdf_path, text_path)

    def _collect_pages(
        self,
        request: ConversionRequest,
        on_progress: ProgressListener,
        wait_for_ready: ReadySignal,
        should_cancel: ShouldCancel,
    ) -> list[Path]:
        if request.mode is CaptureMode.REUSE:
            image_paths = self.captures.load_complete(request.document)
            on_progress(Stage.CAPTURE, f"Reutilizando {len(image_paths)} páginas salvas.")
            return image_paths

        return self.capturer.capture(
            request.document,
            resume=request.mode is CaptureMode.RESUME,
            wait_for_ready=wait_for_ready,
            on_status=lambda message: on_progress(Stage.CAPTURE, message),
            should_cancel=should_cancel,
        )
