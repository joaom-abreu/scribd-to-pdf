import json
from pathlib import Path

import pytest
from PIL import Image

from scribd_to_pdf.cache import (
    load_capture,
    load_progress,
    save_capture,
    save_progress,
)
from scribd_to_pdf.scribd import parse_document_url


@pytest.fixture
def document():
    return parse_document_url(
        "https://www.scribd.com/document/629060068/the-metamorphosis-franz-kafka"
    )


@pytest.fixture
def capture_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "captura"
    directory.mkdir()

    for number in (3, 1, 2):
        path = directory / f"page_{number:04d}.png"

        with Image.new("RGB", (32, 48), color="white") as image:
            image.save(path)

    return directory


def test_salva_e_recupera_progresso_parcial(document, capture_dir: Path):
    save_progress(document, capture_dir, 3, {1, 3})

    total_pages, captured_pages = load_progress(document, capture_dir)

    assert total_pages == 3
    assert captured_pages == {1, 3}


def test_reutilizacao_exige_registro_completo(document, capture_dir: Path):
    save_progress(document, capture_dir, 3, {1, 3})

    with pytest.raises(ValueError):
        load_capture(document, capture_dir)


def test_reutilizacao_respeita_ordem_e_ignora_imagens_extras(
        document,
        capture_dir: Path,
):
    first_page = capture_dir / "page_0001.png"
    extra_page = capture_dir / "page_0004.png"
    extra_page.write_bytes(first_page.read_bytes())

    save_capture(document, capture_dir, 3)

    image_paths = load_capture(document, capture_dir)

    assert image_paths == [
        capture_dir / "page_0001.png",
        capture_dir / "page_0002.png",
        capture_dir / "page_0003.png",
        ]


@pytest.mark.parametrize("damage", ["ausente", "vazia"])
def test_reutilizacao_rejeita_pagina_ausente_ou_vazia(
        document,
        capture_dir: Path,
        damage: str,
):
    save_capture(document, capture_dir, 3)
    second_page = capture_dir / "page_0002.png"

    if damage == "ausente":
        second_page.unlink()
    else:
        second_page.write_bytes(b"")

    with pytest.raises(ValueError):
        load_capture(document, capture_dir)


def test_rejeita_registro_de_outro_documento(document, capture_dir: Path):
    save_progress(document, capture_dir, 3, {1})

    other_document = parse_document_url(
        "https://www.scribd.com/document/604958172/O-Osso-de-Uma-Analise"
    )

    with pytest.raises(ValueError):
        load_progress(other_document, capture_dir)


def test_rejeita_registro_corrompido(document, capture_dir: Path):
    metadata_path = capture_dir / "capture.json"
    metadata_path.write_text('{"version": 2,', encoding="utf-8")

    with pytest.raises(ValueError):
        load_progress(document, capture_dir)


def test_rejeita_captura_sem_registro(document, capture_dir: Path):
    with pytest.raises(ValueError):
        load_capture(document, capture_dir)


def test_carrega_captura_do_formato_antigo(document, capture_dir: Path):
    metadata = {
        "version": 1,
        "document_id": document.document_id,
        "total_pages": 3,
    }

    metadata_path = capture_dir / "capture.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    assert load_progress(document, capture_dir) == (3, {1, 2, 3})
    assert load_capture(document, capture_dir) == [
        capture_dir / "page_0001.png",
        capture_dir / "page_0002.png",
        capture_dir / "page_0003.png",
        ]