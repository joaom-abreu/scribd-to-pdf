from scribd_to_pdf.application.conversion import DocumentConverter
from scribd_to_pdf.infrastructure.ocr import OcrMyPdfRecognizer
from scribd_to_pdf.infrastructure.pdf import Img2PdfBuilder
from scribd_to_pdf.infrastructure.reader import PlaywrightPageCapturer
from scribd_to_pdf.infrastructure.storage import FileCaptureRepository


def build_converter() -> DocumentConverter:
    captures = FileCaptureRepository()

    return DocumentConverter(
        captures=captures,
        capturer=PlaywrightPageCapturer(captures),
        pdf_builder=Img2PdfBuilder(),
        text_recognizer=OcrMyPdfRecognizer(),
    )
