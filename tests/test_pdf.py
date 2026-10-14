from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.infrastructure import pdf as pdf_module
from scribd_to_pdf.infrastructure.pdf import Img2PdfBuilder, count_pages, create_pdf

PAGE_COLORS = (
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
)


@pytest.fixture
def page_images(tmp_path: Path) -> list[Path]:
    paths = []

    for number, color in enumerate(PAGE_COLORS, start=1):
        path = tmp_path / f"page_{number:04d}.png"

        with Image.new("RGB", (32, 48), color=color) as image:
            image.save(path)

        paths.append(path)

    return paths


def test_creates_pdf_with_every_page_in_order(tmp_path: Path, page_images: list[Path]):
    output = tmp_path / "destino" / "livro.pdf"

    result = create_pdf(page_images, output)

    assert result == output
    assert count_pages(output) == len(PAGE_COLORS)

    with output.open("rb") as stream:
        actual_colors = [
            page.images[0].image.convert("RGB").getpixel((0, 0))
            for page in PdfReader(stream).pages
        ]

    assert actual_colors == list(PAGE_COLORS)


def test_rejects_empty_page_list(tmp_path: Path):
    output = tmp_path / "livro.pdf"

    with pytest.raises(ValueError):
        create_pdf([], output)

    assert not output.exists()


def test_rejects_missing_page_file(tmp_path: Path, page_images: list[Path]):
    output = tmp_path / "livro.pdf"
    page_images[1].unlink()

    with pytest.raises(FileNotFoundError, match="page_0002.png"):
        create_pdf(page_images, output)

    assert not output.exists()


def test_failure_keeps_previous_pdf_and_removes_temporary_file(
    tmp_path: Path,
    page_images: list[Path],
    monkeypatch: pytest.MonkeyPatch,
):
    output = tmp_path / "livro.pdf"
    create_pdf(page_images, output)
    previous_pdf = output.read_bytes()
    previous_files = set(tmp_path.iterdir())

    def failing_convert(*args, **kwargs):
        kwargs["outputstream"].write(b"PDF incompleto")
        raise RuntimeError("Falha simulada")

    monkeypatch.setattr(pdf_module.img2pdf, "convert", failing_convert)

    with pytest.raises(RuntimeError, match="Falha simulada"):
        create_pdf(page_images, output)

    assert output.read_bytes() == previous_pdf
    assert set(tmp_path.iterdir()) == previous_files


def test_builder_reports_failures_as_conversion_error(tmp_path: Path, page_images: list[Path]):
    page_images[1].unlink()

    with pytest.raises(ConversionError, match="page_0002.png") as error:
        Img2PdfBuilder().build(page_images, tmp_path / "livro.pdf")

    assert isinstance(error.value.__cause__, FileNotFoundError)
    assert not (tmp_path / "livro.pdf").exists()
