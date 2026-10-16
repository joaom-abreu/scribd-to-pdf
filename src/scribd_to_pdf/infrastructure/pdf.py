import io
from pathlib import Path

import img2pdf
from PIL import Image

from scribd_to_pdf.application.conversion import ConversionError

COMPACT_JPEG_QUALITY = 85


def create_pdf(image_paths: list[Path], output_path: Path, *, compact: bool = False) -> Path:
    if not image_paths:
        raise ValueError("Nenhuma página foi fornecida para gerar o PDF.")

    missing = next((path for path in image_paths if not path.is_file()), None)

    if missing is not None:
        raise FileNotFoundError(f"Página não encontrada: {missing}")

    pages = [_compact_page(path) if compact else str(path) for path in image_paths]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("wb") as stream:
        img2pdf.convert(pages, outputstream=stream)

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
        except (OSError, ValueError, img2pdf.ImageOpenError) as error:
            raise ConversionError(f"Não foi possível gerar o PDF: {error}") from error
