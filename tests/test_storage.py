from pathlib import Path

import pytest
from PIL import Image

from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.domain.document import Document
from scribd_to_pdf.infrastructure.storage import CaptureStore, FileCaptureRepository


@pytest.fixture
def document() -> Document:
    return Document.from_url(
        "https://www.scribd.com/document/629060068/the-metamorphosis-franz-kafka"
    )


@pytest.fixture
def store(tmp_path: Path, document: Document) -> CaptureStore:
    store = CaptureStore(document, root=tmp_path)
    store.directory.mkdir()

    for number in (3, 1, 2):
        with Image.new("RGB", (32, 48), color="white") as image:
            image.save(store.page_path(number))

    return store


def test_saves_and_loads_total_pages(store: CaptureStore):
    store.save_total_pages(3)

    assert store.manifest_path.read_text(encoding="utf-8") == '{"total_pages": 3}\n'
    assert store.load_total_pages() == 3


def test_saving_total_pages_creates_the_capture_folder(tmp_path: Path, document: Document):
    store = CaptureStore(document, root=tmp_path / "capturas")

    store.save_total_pages(5)

    assert store.load_total_pages() == 5


def test_reuse_keeps_order_and_ignores_extra_images(store: CaptureStore):
    store.page_path(4).write_bytes(store.page_path(1).read_bytes())
    store.save_total_pages(3)

    assert store.load_complete_capture() == [
        store.directory / "page_0001.png",
        store.directory / "page_0002.png",
        store.directory / "page_0003.png",
    ]


@pytest.mark.parametrize("damage", ["missing", "empty"])
def test_reuse_rejects_missing_or_empty_page(store: CaptureStore, damage: str):
    store.save_total_pages(3)
    second_page = store.page_path(2)

    if damage == "missing":
        second_page.unlink()
    else:
        second_page.write_bytes(b"")

    with pytest.raises(ValueError, match="page_0002.png"):
        store.load_complete_capture()


@pytest.mark.parametrize(
    "content",
    [b'{"total_pages": 3', b"\xff", b"[]", b"{}", b'{"total_pages": "tres"}'],
    ids=["truncated", "invalid-encoding", "not-an-object", "missing-total", "total-not-a-number"],
)
def test_rejects_corrupted_manifest(store: CaptureStore, content: bytes):
    store.manifest_path.write_bytes(content)

    with pytest.raises(ValueError, match="corrompido"):
        store.load_total_pages()


def test_rejects_capture_without_manifest(store: CaptureStore):
    with pytest.raises(ValueError, match="nova captura"):
        store.load_complete_capture()


def test_repository_reports_unusable_capture_as_conversion_error(tmp_path: Path, document: Document):
    repository = FileCaptureRepository(tmp_path)

    with pytest.raises(ConversionError, match="nova captura"):
        repository.load_complete(document)


def test_repository_returns_complete_capture(store: CaptureStore, tmp_path: Path, document: Document):
    store.save_total_pages(3)

    assert FileCaptureRepository(tmp_path).load_complete(document) == store.page_paths(3)
