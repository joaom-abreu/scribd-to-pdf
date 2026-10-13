from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

import scribd_to_pdf.pdf as pdf_module
from scribd_to_pdf.pdf import create_pdf


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


def test_gera_pdf_com_todas_as_paginas_na_ordem(
        tmp_path: Path,
        page_images: list[Path],
):
    output = tmp_path / "destino" / "livro.pdf"

    result = create_pdf(page_images, output)

    assert result == output
    assert output.is_file()

    with output.open("rb") as stream:
        reader = PdfReader(stream)

        assert len(reader.pages) == len(PAGE_COLORS)

        actual_colors = [
            page.images[0].image.convert("RGB").getpixel((0, 0))
            for page in reader.pages
        ]

        assert actual_colors == list(PAGE_COLORS)


@pytest.mark.parametrize(
    "indices",
    [
        (1, 0, 2),
        (0, 2),
        (1,),
    ],
    ids=["ordem-invertida", "pagina-ausente", "inicio-na-pagina-2"],
)
def test_rejeita_sequencia_invalida(
        tmp_path: Path,
        page_images: list[Path],
        indices: tuple[int, ...],
):
    output = tmp_path / "livro.pdf"
    images = [page_images[index] for index in indices]

    with pytest.raises(ValueError):
        create_pdf(images, output)

    assert not output.exists()


def test_rejeita_lista_vazia(tmp_path: Path):
    output = tmp_path / "livro.pdf"

    with pytest.raises(ValueError):
        create_pdf([], output)

    assert not output.exists()


def test_rejeita_arquivo_de_pagina_inexistente(
        tmp_path: Path,
        page_images: list[Path],
):
    output = tmp_path / "livro.pdf"
    page_images[1].unlink()

    with pytest.raises(FileNotFoundError):
        create_pdf(page_images, output)

    assert not output.exists()


def test_falha_preserva_pdf_anterior_e_remove_temporario(
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