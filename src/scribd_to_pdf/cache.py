import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from scribd_to_pdf.models import Document


MANIFEST_NAME = "capture.json"


def _validate_progress(
        total_pages: int,
        numbers: list[int] | set[int],
) -> set[int]:
    if type(total_pages) is not int or total_pages < 1:
        raise ValueError("O total de páginas da captura é inválido.")

    if not isinstance(numbers, (list, set)) or any(
            type(number) is not int or not 1 <= number <= total_pages
            for number in numbers
    ):
        raise ValueError("O registro contém números de página inválidos.")

    captured_pages = set(numbers)

    if len(captured_pages) != len(numbers):
        raise ValueError("O registro contém páginas duplicadas.")

    return captured_pages


def _page_paths(output_dir: Path, total_pages: int) -> list[Path]:
    _validate_progress(total_pages, set())

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


def save_progress(
        document: Document,
        output_dir: Path,
        total_pages: int,
        captured_pages: set[int],
) -> None:
    captured_pages = _validate_progress(total_pages, captured_pages)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "version": 2,
        "document_id": document.document_id,
        "total_pages": total_pages,
        "captured_pages": sorted(captured_pages),
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


def load_progress(
        document: Document,
        output_dir: Path,
) -> tuple[int, set[int]]:
    manifest_path = output_dir / MANIFEST_NAME

    if not manifest_path.is_file():
        raise ValueError(
            f"Não há captura registrada em {output_dir}. "
            "Execute o comando sem --resume ou --reuse."
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("O registro da captura está corrompido.") from error

    if (
            not isinstance(manifest, dict)
            or type(manifest.get("version")) is not int
            or manifest.get("version") not in (1, 2)
            or manifest.get("document_id") != document.document_id
    ):
        raise ValueError(
            "O registro da captura é inválido para este documento."
        )

    total_pages = manifest.get("total_pages")
    _validate_progress(total_pages, set())

    if manifest["version"] == 1:
        numbers = list(range(1, total_pages + 1))
    else:
        numbers = manifest.get("captured_pages")

    return total_pages, _validate_progress(total_pages, numbers)


def save_capture(
        document: Document,
        output_dir: Path,
        total_pages: int,
) -> None:
    _page_paths(output_dir, total_pages)
    save_progress(
        document,
        output_dir,
        total_pages,
        set(range(1, total_pages + 1)),
    )


def load_capture(document: Document, output_dir: Path) -> list[Path]:
    total_pages, captured_pages = load_progress(document, output_dir)

    if len(captured_pages) != total_pages:
        raise ValueError(
            "A captura está incompleta. Use --resume para continuar."
        )

    return _page_paths(output_dir, total_pages)