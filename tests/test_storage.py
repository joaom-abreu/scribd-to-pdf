import json
from pathlib import Path

import pytest
from PIL import Image

from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.domain.capture import CaptureProgress
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


def complete(total_pages: int) -> CaptureProgress:
    return CaptureProgress(total_pages, frozenset(range(1, total_pages + 1)))


def test_saves_and_loads_partial_progress(store: CaptureStore):
    store.save_progress(CaptureProgress(3, frozenset({1, 3})))

    assert store.load_progress() == CaptureProgress(3, frozenset({1, 3}))


def test_reuse_requires_complete_progress(store: CaptureStore):
    store.save_progress(CaptureProgress(3, frozenset({1, 3})))

    with pytest.raises(ValueError, match="incompleta"):
        store.load_complete_capture()


def test_reuse_keeps_order_and_ignores_extra_images(store: CaptureStore):
    store.page_path(4).write_bytes(store.page_path(1).read_bytes())
    store.save_progress(complete(3))

    assert store.load_complete_capture() == [
        store.directory / "page_0001.png",
        store.directory / "page_0002.png",
        store.directory / "page_0003.png",
    ]


@pytest.mark.parametrize("damage", ["missing", "empty"])
def test_reuse_rejects_missing_or_empty_page(store: CaptureStore, damage: str):
    store.save_progress(complete(3))
    second_page = store.page_path(2)

    if damage == "missing":
        second_page.unlink()
    else:
        second_page.write_bytes(b"")

    with pytest.raises(ValueError, match="page_0002.png"):
        store.load_complete_capture()


def test_rejects_progress_from_another_document(store: CaptureStore, tmp_path: Path):
    store.save_progress(CaptureProgress(3, frozenset({1})))
    other = Document("604958172", "https://www.scribd.com/document/604958172")
    other_store = CaptureStore(other, root=tmp_path)
    other_store.directory.mkdir()
    store.manifest_path.replace(other_store.manifest_path)

    with pytest.raises(ValueError, match="inválido"):
        other_store.load_progress()


@pytest.mark.parametrize(
    "content",
    [
        b'{"version": 2,',
        b"\xff",
        b"[]",
        b'{"version": 3, "document_id": "629060068", "total_pages": 3}',
        b'{"version": true, "document_id": "629060068", "total_pages": 3}',
        b'{"version": 2, "document_id": "629060068", "total_pages": 0, "captured_pages": []}',
        b'{"version": 2, "document_id": "629060068", "total_pages": 3, "captured_pages": [4]}',
        b'{"version": 2, "document_id": "629060068", "total_pages": 3, "captured_pages": [[1]]}',
    ],
    ids=[
        "truncated",
        "invalid-encoding",
        "not-an-object",
        "unknown-version",
        "boolean-version",
        "no-pages",
        "page-out-of-range",
        "unhashable-page",
    ],
)
def test_rejects_invalid_manifest(store: CaptureStore, content: bytes):
    store.manifest_path.write_bytes(content)

    with pytest.raises(ValueError):
        store.load_progress()


def test_rejects_capture_without_manifest(store: CaptureStore):
    with pytest.raises(ValueError, match="nova captura"):
        store.load_complete_capture()


def test_loads_legacy_manifest(store: CaptureStore, document: Document):
    store.manifest_path.write_text(
        json.dumps({"version": 1, "document_id": document.document_id, "total_pages": 3}),
        encoding="utf-8",
    )

    assert store.load_progress() == complete(3)
    assert store.load_complete_capture() == store.page_paths(3)


def test_progress_rejects_page_outside_total():
    with pytest.raises(ValueError):
        CaptureProgress(2, frozenset({3}))


def test_progress_adds_pages_without_mutating():
    progress = CaptureProgress(3)

    updated = progress.with_page(2)

    assert progress.captured_pages == frozenset()
    assert updated.captured_pages == frozenset({2})
    assert not updated.is_complete
    assert updated.with_page(1).with_page(3).is_complete


def test_repository_reports_unusable_capture_as_conversion_error(tmp_path: Path, document: Document):
    repository = FileCaptureRepository(tmp_path)

    with pytest.raises(ConversionError, match="nova captura"):
        repository.load_complete(document)


def test_repository_returns_complete_capture(store: CaptureStore, tmp_path: Path, document: Document):
    store.save_progress(complete(3))

    assert FileCaptureRepository(tmp_path).load_complete(document) == store.page_paths(3)
