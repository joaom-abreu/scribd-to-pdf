from pathlib import Path

from scribd_to_pdf.application.conversion import DocumentConverter
from scribd_to_pdf.infrastructure.ocr import OcrMyPdfRecognizer
from scribd_to_pdf.infrastructure.pdf import Img2PdfBuilder
from scribd_to_pdf.infrastructure.reader import PlaywrightPageCapturer
from scribd_to_pdf.infrastructure.storage import FileCaptureRepository, default_captures_root


def build_converter(captures_root: Path | None = None) -> DocumentConverter:
    root = captures_root.expanduser() if captures_root is not None else default_captures_root()
    captures = FileCaptureRepository(root)

    return DocumentConverter(
        captures=captures,
        capturer=PlaywrightPageCapturer(captures),
        pdf_builder=Img2PdfBuilder(),
        text_recognizer=OcrMyPdfRecognizer(),
        default_output_folder=Path.cwd(),
    )
