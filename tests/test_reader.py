from pathlib import Path
from unittest.mock import Mock

import pytest
from playwright.sync_api import Error as PlaywrightError

from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.domain.document import Document
from scribd_to_pdf.infrastructure import reader as reader_module
from scribd_to_pdf.infrastructure.reader import PlaywrightPageCapturer
from scribd_to_pdf.infrastructure.storage import FileCaptureRepository

DOCUMENT = Document("123", "https://www.scribd.com/document/123/livro")


def capture(tmp_path: Path) -> list[Path]:
    return PlaywrightPageCapturer(FileCaptureRepository(tmp_path)).capture(
        DOCUMENT,
        resume=False,
        wait_for_ready=Mock(),
        on_status=Mock(),
        should_cancel=lambda: False,
    )


def test_capturer_uses_the_document_store(tmp_path, monkeypatch):
    capture_document = Mock(return_value=[tmp_path / "page_0001.png"])
    monkeypatch.setattr(reader_module, "capture_document", capture_document)

    assert capture(tmp_path) == [tmp_path / "page_0001.png"]
    assert capture_document.call_args.args[0].directory == tmp_path / "123"


@pytest.mark.parametrize(
    "failure, message",
    [
        (PlaywrightError("Timeout 30000ms exceeded."), "Falha no navegador: Timeout 30000ms exceeded."),
        (ValueError("O contador de páginas apresentou valores inválidos."), "contador de páginas"),
        (PermissionError("Sem permissão."), "Sem permissão."),
    ],
    ids=["playwright", "valor-invalido", "arquivo"],
)
def test_capturer_reports_failures_as_conversion_error(tmp_path, monkeypatch, failure, message):
    monkeypatch.setattr(reader_module, "capture_document", Mock(side_effect=failure))

    with pytest.raises(ConversionError, match=message) as error:
        capture(tmp_path)

    assert error.value.__cause__ is failure


def test_capturer_keeps_interruptions(tmp_path, monkeypatch):
    interruption = InterruptedError("Captura interrompida.")
    monkeypatch.setattr(reader_module, "capture_document", Mock(side_effect=interruption))

    with pytest.raises(InterruptedError) as error:
        capture(tmp_path)

    assert error.value is interruption
