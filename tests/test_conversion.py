from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

from scribd_to_pdf.application.conversion import (
    CaptureMode,
    ConversionRequest,
    ConversionResult,
    DocumentConverter,
)
from scribd_to_pdf.domain.capture import CaptureProgress
from scribd_to_pdf.domain.document import Document
from scribd_to_pdf.infrastructure.pdf import Img2PdfBuilder, count_pages
from scribd_to_pdf.infrastructure.storage import CaptureStore, FileCaptureRepository

DOCUMENT = Document("123", "https://www.scribd.com/document/123/livro")


@dataclass(frozen=True)
class Harness:
    converter: DocumentConverter
    store: CaptureStore
    capturer: Mock
    pdf_builder: Mock
    text_recognizer: Mock


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    captures = FileCaptureRepository(tmp_path / "capturas")
    store = captures.store(DOCUMENT)
    store.directory.mkdir(parents=True)

    for number in (1, 2):
        with Image.new("RGB", (32, 48), color="white") as image:
            image.save(store.page_path(number))

    store.save_progress(CaptureProgress(2, frozenset({1, 2})))
    capturer = Mock()
    pdf_builder = Mock(wraps=Img2PdfBuilder())
    text_recognizer = Mock()

    return Harness(
        DocumentConverter(captures, capturer, pdf_builder, text_recognizer, tmp_path / "pdfs"),
        store,
        capturer,
        pdf_builder,
        text_recognizer,
    )


def run(
        harness: Harness,
        request: ConversionRequest,
        **overrides,
) -> tuple[ConversionResult, list[str]]:
    progress: list[str] = []
    options = {
        "on_progress": progress.append,
        "wait_for_ready": Mock(),
        **overrides,
    }
    return harness.converter.convert(request, **options), progress


def test_reuse_builds_pdf_without_opening_browser(harness, tmp_path):
    request = ConversionRequest(DOCUMENT, tmp_path / "livro.pdf", CaptureMode.REUSE)

    result, progress = run(harness, request)

    harness.capturer.capture.assert_not_called()
    assert result == ConversionResult((tmp_path / "livro.pdf").resolve())
    assert count_pages(result.pdf_path) == 2
    assert progress == ["Reutilizando 2 páginas salvas.", "Gerando PDF com 2 páginas..."]


@pytest.mark.parametrize("mode, resume", [(CaptureMode.NEW, False), (CaptureMode.RESUME, True)])
def test_capture_modes_use_the_browser(harness, tmp_path, mode, resume):
    harness.capturer.capture.return_value = harness.store.page_paths(2)
    wait_for_ready = Mock()

    run(harness, ConversionRequest(DOCUMENT, tmp_path / "livro.pdf", mode), wait_for_ready=wait_for_ready)

    assert harness.capturer.capture.call_args.args == (DOCUMENT,)
    assert harness.capturer.capture.call_args.kwargs["resume"] is resume
    assert harness.capturer.capture.call_args.kwargs["wait_for_ready"] is wait_for_ready


@pytest.mark.parametrize("compact", [False, True])
def test_compact_option_reaches_pdf_builder(harness, tmp_path, compact):
    request = ConversionRequest(DOCUMENT, tmp_path / "livro.pdf", CaptureMode.REUSE, compact=compact)

    _, progress = run(harness, request)

    assert harness.pdf_builder.build.call_args.kwargs["compact"] is compact
    assert ("PDF compacto" in progress[-1]) is compact


def test_capture_status_is_forwarded_to_progress(harness, tmp_path):
    def capture(document, *, on_status, **kwargs):
        on_status("Capturando página 1 de 2...")
        return harness.store.page_paths(2)

    harness.capturer.capture.side_effect = capture

    _, progress = run(harness, ConversionRequest(DOCUMENT, tmp_path / "livro.pdf"))

    assert progress[0] == "Capturando página 1 de 2..."


@pytest.mark.parametrize("export_text", [False, True])
def test_ocr_runs_after_pdf_and_reports_text(harness, tmp_path, export_text):
    request = ConversionRequest(
        DOCUMENT,
        tmp_path / "livro.pdf",
        CaptureMode.REUSE,
        ocr_language="por+eng",
        export_text=export_text,
    )

    result, progress = run(harness, request)

    pdf_path = (tmp_path / "livro.pdf").resolve()
    text_path = pdf_path.with_suffix(".txt") if export_text else None
    recognize = harness.text_recognizer.recognize
    recognize.assert_called_once()
    assert recognize.call_args.args == (pdf_path, "por+eng")
    assert recognize.call_args.kwargs["text_path"] == text_path
    assert result.text_path == text_path
    assert progress[-1] == "Aplicando OCR (por+eng)..."


@pytest.mark.parametrize(
    "output, ocr_language, export_text",
    [("livro.txt", None, False), ("livro.pdf", None, True)],
    ids=["not-a-pdf", "text-without-ocr"],
)
def test_request_rejects_invalid_options(output, ocr_language, export_text):
    with pytest.raises(ValueError):
        ConversionRequest(DOCUMENT, Path(output), ocr_language=ocr_language, export_text=export_text)


@pytest.mark.parametrize("ocr_language", [None, "por+eng"])
def test_requirements_are_checked_only_with_ocr(harness, ocr_language):
    harness.converter.check_requirements(
        ConversionRequest(DOCUMENT, Path("livro.pdf"), ocr_language=ocr_language),
    )

    if ocr_language is None:
        harness.text_recognizer.check_available.assert_not_called()
    else:
        harness.text_recognizer.check_available.assert_called_once_with(ocr_language)


def test_output_path_prefers_destination_then_folder_then_default_folder(harness, tmp_path):
    destination = tmp_path / "escolhido.pdf"
    folder = tmp_path / "lembrada"
    converter = harness.converter

    assert converter.output_path(DOCUMENT, destination, folder) == destination
    assert converter.output_path(DOCUMENT, None, folder) == folder / "123.pdf"
    assert converter.output_path(DOCUMENT) == tmp_path / "pdfs" / "123.pdf"
