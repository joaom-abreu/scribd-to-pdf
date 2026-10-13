from pathlib import Path
from tempfile import NamedTemporaryFile

import img2pdf
from pypdf import PdfReader


def create_pdf(image_paths: list[Path], output_path: Path) -> Path:
    if not image_paths:
        raise ValueError("Nenhuma página foi fornecida para gerar o PDF.")

    expected_names = [
        f"page_{number:04d}.png"
        for number in range(1, len(image_paths) + 1)
    ]

    if [path.name for path in image_paths] != expected_names:
        raise ValueError("As páginas devem estar em sequência, começando em 1.")

    for image_path in image_paths:
        if not image_path.is_file():
            raise FileNotFoundError(f"Página não encontrada: {image_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile(
            dir=output_path.parent,
            suffix=".tmp.pdf",
            delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    try:
        with temporary_path.open("wb") as stream:
            img2pdf.convert(
                [str(path) for path in image_paths],
                outputstream=stream,
            )

        with temporary_path.open("rb") as stream:
            reader = PdfReader(stream)
            page_count = len(reader.pages)

        if page_count != len(image_paths):
            raise ValueError(
                f"PDF com {page_count} páginas; esperado: {len(image_paths)}."
            )

        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return output_path