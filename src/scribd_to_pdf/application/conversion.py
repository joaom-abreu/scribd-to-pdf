from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from scribd_to_pdf.domain.cancellation import ShouldCancel, never_cancel, raise_if_cancelled
from scribd_to_pdf.domain.document import Document
from scribd_to_pdf.infrastructure.ocr import add_ocr, check_ocr_available
from scribd_to_pdf.infrastructure.pdf import create_pdf
from scribd_to_pdf.infrastructure.reader import capture_document
from scribd_to_pdf.infrastructure.storage import CaptureStore

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
    def __init__(self, pdf_path: Path) -> None:
        super().__init__("OCR interrompido. O PDF com as imagens foi preservado.")
        self.pdf_path = pdf_path


def resolve_output_path(
    document: Document,
    destination: Path | None = None,
    folder: Path | None = None,
) -> Path:
    if destination is not None:
        return destination.expanduser()

    directory = folder if folder is not None else CaptureStore(document).directory
    return directory / f"{document.document_id}.pdf"


def check_requirements(request: ConversionRequest) -> None:
    if request.ocr_language is not None:
        check_ocr_available(request.ocr_language)


def convert(
    request: ConversionRequest,
    *,
    on_progress: ProgressListener,
    wait_for_ready: Callable[[], None],
    should_cancel: ShouldCancel = never_cancel,
) -> ConversionResult:
    image_paths = _collect_pages(request, on_progress, wait_for_ready, should_cancel)
    raise_if_cancelled(should_cancel, CONVERSION_INTERRUPTED)

    on_progress(Stage.PDF, f"Gerando PDF com {len(image_paths)} páginas...")
    pdf_path = create_pdf(image_paths, request.output_path).resolve()

    if request.ocr_language is None:
        return ConversionResult(pdf_path)

    on_progress(Stage.OCR, f"Aplicando OCR ({request.ocr_language})...")

    try:
        add_ocr(
            pdf_path,
            request.ocr_language,
            should_cancel=should_cancel,
            export_text=request.export_text,
        )
    except InterruptedError as error:
        raise OcrInterrupted(pdf_path) from error

    return ConversionResult(
        pdf_path,
        pdf_path.with_suffix(".txt") if request.export_text else None,
    )


def _collect_pages(
    request: ConversionRequest,
    on_progress: ProgressListener,
    wait_for_ready: Callable[[], None],
    should_cancel: ShouldCancel,
) -> list[Path]:
    store = CaptureStore(request.document)

    if request.mode is CaptureMode.REUSE:
        image_paths = store.load_complete_capture()
        on_progress(Stage.CAPTURE, f"Reutilizando {len(image_paths)} páginas salvas.")
        return image_paths

    return capture_document(
        store,
        resume=request.mode is CaptureMode.RESUME,
        wait_for_ready=wait_for_ready,
        on_status=lambda message: on_progress(Stage.CAPTURE, message),
        should_cancel=should_cancel,
    )
