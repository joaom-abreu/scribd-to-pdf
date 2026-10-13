import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from scribd_to_pdf.models import Document


MANIFEST_NAME = "capture.json"


def _page_paths(output_dir: Path, total_pages: int) -> list[Path]:
    if type(total_pages) is not int or total_pages < 1:
        raise ValueError("O total de páginas da captura é inválido.")

    paths = [
        output_dir / f"page_{number:04d}.png"
        for number in range(1, total_pages + 1)
    ]

    for path in paths:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(
                f"Captura incompleta: página ausente ou vazia: {path}"
            )

    return paths


def save_capture(
        document: Document,
        output_dir: Path,
        total_pages: int,
) -> None:
    _page_paths(output_dir, total_pages)

    manifest = {
        "version": 1,
        "document_id": document.document_id,
        "total_pages": total_pages,
    }

    with NamedTemporaryFile(
            dir=output_dir,
            suffix=".json.tmp",
            delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    try:
        temporary_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            )
        temporary_path.replace(output_dir / MANIFEST_NAME)
    finally:
        temporary_path.unlink(missing_ok=True)


def load_capture(document: Document, output_dir: Path) -> list[Path]:
    manifest_path = output_dir / MANIFEST_NAME

    if not manifest_path.is_file():
        raise ValueError(
            f"Não há captura completa registrada em {output_dir}. "
            "Execute sem --reuse."
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("O registro da captura está corrompido.") from error

    if (
            not isinstance(manifest, dict)
            or manifest.get("version") != 1
            or manifest.get("document_id") != document.document_id
    ):
        raise ValueError(
            "O registro da captura é inválido para este documento."
        )

    return _page_paths(output_dir, manifest.get("total_pages"))