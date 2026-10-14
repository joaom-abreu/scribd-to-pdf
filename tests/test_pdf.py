import stat
import sys
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.infrastructure import pdf as pdf_module
from scribd_to_pdf.infrastructure.files import DEFAULT_FILE_MODE
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
        Img2PdfBuilder().build(page_images, tmp_path / "livro.pdf", compact=False)

    assert isinstance(error.value.__cause__, FileNotFoundError)
    assert not (tmp_path / "livro.pdf").exists()


def page_filters(path: Path) -> list[str]:
    with path.open("rb") as stream:
        return [
            str(image.get_object()["/Filter"])
            for page in PdfReader(stream).pages
            for image in page["/Resources"]["/XObject"].values()
        ]


@pytest.fixture
def mixed_pages(tmp_path: Path) -> list[Path]:
    illustration = tmp_path / "page_0001.png"
    text = tmp_path / "page_0002.png"

    with Image.radial_gradient("L").resize((512, 512)) as gradient, \
            Image.effect_noise((512, 512), 48) as noise:
        Image.merge("RGB", (gradient, noise, gradient.transpose(Image.Transpose.ROTATE_90))).save(illustration)

    with Image.new("RGB", (512, 512), color="white") as image:
        image.paste((0, 0, 0), (40, 40, 470, 44))
        image.save(text)

    return [illustration, text]


def test_compact_uses_jpeg_only_where_it_is_smaller(tmp_path: Path, mixed_pages: list[Path]):
    regular = create_pdf(mixed_pages, tmp_path / "normal.pdf")
    compact = create_pdf(mixed_pages, tmp_path / "compacto.pdf", compact=True)

    assert page_filters(regular) == ["/FlateDecode", "/FlateDecode"]
    assert page_filters(compact) == ["/DCTDecode", "/FlateDecode"]
    assert compact.stat().st_size < regular.stat().st_size
    assert count_pages(compact) == 2


def test_compact_keeps_captured_images(tmp_path: Path, mixed_pages: list[Path]):
    originals = [path.read_bytes() for path in mixed_pages]

    Img2PdfBuilder().build(mixed_pages, tmp_path / "livro.pdf", compact=True)

    assert [path.read_bytes() for path in mixed_pages] == originals


@pytest.mark.skipif(sys.platform == "win32", reason="Permissões POSIX.")
def test_pdf_permissions_follow_the_umask(tmp_path: Path, page_images: list[Path]):
    output = create_pdf(page_images, tmp_path / "livro.pdf")

    assert stat.S_IMODE(output.stat().st_mode) == DEFAULT_FILE_MODE
