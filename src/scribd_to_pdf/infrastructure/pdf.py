from pathlib import Path

import img2pdf
from pypdf import PdfReader

from scribd_to_pdf.infrastructure.files import atomic_target


def count_pages(path: Path) -> int:
    with path.open("rb") as stream:
        return len(PdfReader(stream).pages)


def create_pdf(image_paths: list[Path], output_path: Path) -> Path:
    if not image_paths:
        raise ValueError("Nenhuma página foi fornecida para gerar o PDF.")

    missing = next((path for path in image_paths if not path.is_file()), None)

    if missing is not None:
        raise FileNotFoundError(f"Página não encontrada: {missing}")

    with atomic_target(output_path) as temporary:
        with temporary.open("wb") as stream:
            img2pdf.convert([str(path) for path in image_paths], outputstream=stream)

        page_count = count_pages(temporary)

        if page_count != len(image_paths):
            raise ValueError(f"PDF com {page_count} páginas; esperado: {len(image_paths)}.")

    return output_path
