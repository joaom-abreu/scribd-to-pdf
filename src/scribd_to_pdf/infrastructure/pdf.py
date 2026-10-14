import io
from pathlib import Path

import img2pdf
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.infrastructure.files import atomic_target

COMPACT_JPEG_QUALITY = 85
PDF_ERRORS = (
    OSError,
    ValueError,
    PdfReadError,
    img2pdf.AlphaChannelError,
    img2pdf.ExifOrientationError,
    img2pdf.ImageOpenError,
    img2pdf.JpegColorspaceError,
    img2pdf.NegativeDimensionError,
    img2pdf.PdfTooLargeError,
    img2pdf.UnsupportedColorspaceError,
)


def count_pages(path: Path) -> int:
    with path.open("rb") as stream:
        return len(PdfReader(stream).pages)


def create_pdf(image_paths: list[Path], output_path: Path, *, compact: bool = False) -> Path:
    if not image_paths:
        raise ValueError("Nenhuma página foi fornecida para gerar o PDF.")

    missing = next((path for path in image_paths if not path.is_file()), None)

    if missing is not None:
        raise FileNotFoundError(f"Página não encontrada: {missing}")

    pages = [_compact_page(path) if compact else str(path) for path in image_paths]

    with atomic_target(output_path) as temporary:
        with temporary.open("wb") as stream:
            img2pdf.convert(pages, outputstream=stream)

        page_count = count_pages(temporary)

        if page_count != len(image_paths):
            raise ValueError(f"PDF com {page_count} páginas; esperado: {len(image_paths)}.")

    return output_path


def _compact_page(path: Path) -> str | bytes:
    buffer = io.BytesIO()

    with Image.open(path) as image:
        image.convert("RGB").save(buffer, "JPEG", quality=COMPACT_JPEG_QUALITY, optimize=True)

    jpeg = buffer.getvalue()
    return jpeg if len(jpeg) < path.stat().st_size else str(path)


class Img2PdfBuilder:
    def build(self, image_paths: list[Path], output_path: Path, *, compact: bool) -> Path:
        try:
            return create_pdf(image_paths, output_path, compact=compact)
        except PDF_ERRORS as error:
            raise ConversionError(f"Não foi possível gerar o PDF: {error}") from error
