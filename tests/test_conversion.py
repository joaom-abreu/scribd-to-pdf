from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

from scribd_to_pdf.application import conversion as conversion_module
from scribd_to_pdf.application.conversion import (
    CaptureMode,
    ConversionRequest,
    ConversionResult,
    OcrInterrupted,
    Stage,
    check_requirements,
    convert,
    resolve_output_path,
)
from scribd_to_pdf.domain.capture import CaptureProgress
from scribd_to_pdf.domain.document import Document
from scribd_to_pdf.infrastructure.pdf import count_pages
from scribd_to_pdf.infrastructure.storage import CaptureStore

DOCUMENT = Document("123", "https://www.scribd.com/document/123/livro")


@pytest.fixture
def saved_capture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CaptureStore:
    monkeypatch.chdir(tmp_path)
    store = CaptureStore(DOCUMENT)
    store.directory.mkdir(parents=True)

    for number in (1, 2):
        with Image.new("RGB", (32, 48), color="white") as image:
            image.save(store.page_path(number))

    store.save_progress(CaptureProgress(2, frozenset({1, 2})))
    return store


def run(request: ConversionRequest, **overrides) -> tuple[ConversionResult, list[tuple[Stage, str]]]:
    progress: list[tuple[Stage, str]] = []
    options = {
        "on_progress": lambda stage, message: progress.append((stage, message)),
        "wait_for_ready": Mock(),
        **overrides,
    }
    return convert(request, **options), progress


def test_reuse_builds_pdf_without_opening_browser(saved_capture, tmp_path, monkeypatch):
    capture = Mock()
    monkeypatch.setattr(conversion_module, "capture_document", capture)
    request = ConversionRequest(DOCUMENT, tmp_path / "livro.pdf", CaptureMode.REUSE)

    result, progress = run(request)

    capture.assert_not_called()
    assert result == ConversionResult((tmp_path / "livro.pdf").resolve())
    assert count_pages(result.pdf_path) == 2
    assert [stage for stage, _ in progress] == [Stage.CAPTURE, Stage.PDF]


@pytest.mark.parametrize("mode, resume", [(CaptureMode.NEW, False), (CaptureMode.RESUME, True)])
def test_capture_modes_use_the_browser(saved_capture, tmp_path, monkeypatch, mode, resume):
    capture = Mock(return_value=saved_capture.page_paths(2))
    monkeypatch.setattr(conversion_module, "capture_document", capture)
    wait_for_ready = Mock()

    run(ConversionRequest(DOCUMENT, tmp_path / "livro.pdf", mode), wait_for_ready=wait_for_ready)

    assert capture.call_args.kwargs["resume"] is resume
    assert capture.call_args.kwargs["wait_for_ready"] is wait_for_ready


@pytest.mark.parametrize("export_text", [False, True])
def test_ocr_runs_after_pdf_and_reports_text(saved_capture, tmp_path, monkeypatch, export_text):
    add_ocr = Mock()
    monkeypatch.setattr(conversion_module, "add_ocr", add_ocr)
    request = ConversionRequest(
        DOCUMENT,
        tmp_path / "livro.pdf",
        CaptureMode.REUSE,
        ocr_language="por+eng",
        export_text=export_text,
    )

    result, progress = run(request)

    pdf_path = (tmp_path / "livro.pdf").resolve()
    add_ocr.assert_called_once()
    assert add_ocr.call_args.args == (pdf_path, "por+eng")
    assert add_ocr.call_args.kwargs["export_text"] is export_text
    assert result.text_path == (pdf_path.with_suffix(".txt") if export_text else None)
    assert progress[-1][0] is Stage.OCR


def test_interrupted_ocr_reports_preserved_pdf(saved_capture, tmp_path, monkeypatch):
    monkeypatch.setattr(
        conversion_module,
        "add_ocr",
        Mock(side_effect=InterruptedError("OCR interrompido.")),
    )
    request = ConversionRequest(DOCUMENT, tmp_path / "livro.pdf", CaptureMode.REUSE, ocr_language="por")

    with pytest.raises(OcrInterrupted) as interruption:
        run(request)

    assert interruption.value.pdf_path == (tmp_path / "livro.pdf").resolve()
    assert interruption.value.pdf_path.is_file()


def test_cancellation_before_pdf_creates_nothing(saved_capture, tmp_path, monkeypatch):
    create_pdf = Mock()
    monkeypatch.setattr(conversion_module, "create_pdf", create_pdf)
    request = ConversionRequest(DOCUMENT, tmp_path / "livro.pdf", CaptureMode.REUSE)

    with pytest.raises(InterruptedError):
        run(request, should_cancel=lambda: True)

    create_pdf.assert_not_called()


@pytest.mark.parametrize(
    "output, ocr_language, export_text",
    [("livro.txt", None, False), ("livro.pdf", None, True)],
    ids=["not-a-pdf", "text-without-ocr"],
)
def test_request_rejects_invalid_options(output, ocr_language, export_text):
    with pytest.raises(ValueError):
        ConversionRequest(DOCUMENT, Path(output), ocr_language=ocr_language, export_text=export_text)


@pytest.mark.parametrize("ocr_language", [None, "por+eng"])
def test_requirements_are_checked_only_with_ocr(monkeypatch, ocr_language):
    check = Mock()
    monkeypatch.setattr(conversion_module, "check_ocr_available", check)

    check_requirements(ConversionRequest(DOCUMENT, Path("livro.pdf"), ocr_language=ocr_language))

    if ocr_language is None:
        check.assert_not_called()
    else:
        check.assert_called_once_with(ocr_language)


def test_output_path_prefers_destination_then_folder_then_capture_dir(tmp_path):
    destination = tmp_path / "escolhido.pdf"
    folder = tmp_path / "pdfs"

    assert resolve_output_path(DOCUMENT, destination, folder) == destination
    assert resolve_output_path(DOCUMENT, None, folder) == folder / "123.pdf"
    assert resolve_output_path(DOCUMENT) == Path("output") / "123" / "123.pdf"
