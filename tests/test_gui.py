import queue
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

from scribd_to_pdf import gui as gui_module
from scribd_to_pdf.gui import MODES, Application
from scribd_to_pdf.models import Document
from scribd_to_pdf.ocr import OcrError


@pytest.fixture
def application():
    # Exercita os eventos da GUI sem depender de um servidor gráfico.
    app = Application.__new__(Application)
    app.root = Mock()
    app.events = queue.Queue()
    app.ready_event = threading.Event()
    app.cancel_event = threading.Event()
    app.running = True
    app.closing = False
    app.last_pdf = None
    app.ocr_enabled = Mock()
    app.ocr_enabled.get.return_value = True
    app.ocr_language_buttons = []
    app.url = Mock()
    app.url.get.return_value = "https://www.scribd.com/document/123/livro"
    app.destination = Mock()
    app.destination.get.return_value = ""
    app.mode = Mock()
    app.mode.get.return_value = MODES[0]
    app._log = Mock()

    for name in (
        "url_entry", "destination_entry", "browse_button", "start_button",
        "ocr_button", "mode_box", "ready_button", "cancel_button",
        "open_pdf_button", "open_folder_button",
    ):
        setattr(app, name, Mock())

    return app


def test_ocr_event_enables_cancellation(application):
    application.events.put(("pdf", "Gerando PDF..."))
    application.events.put(("ocr", "Reconhecendo texto..."))

    application._poll()

    application.cancel_button.configure.assert_called_with(state="normal")
    assert application.running


def test_pending_ocr_event_does_not_undo_cancellation(application):
    application.events.put(("ocr", "Reconhecendo texto..."))
    application._cancel()

    application._poll()

    assert application.cancel_event.is_set()
    application.cancel_button.configure.assert_called_with(state="disabled")


def test_cancelled_ocr_keeps_pdf_accessible(application, tmp_path):
    pdf_path = tmp_path / "livro.pdf"
    pdf_path.write_bytes(b"PDF preservado")
    application.cancel_event.set()
    application.events.put(("ocr_cancelled", str(pdf_path)))

    application._poll()

    assert not application.running
    assert application.last_pdf == pdf_path
    application.open_pdf_button.configure.assert_called_with(state="normal")
    application.open_folder_button.configure.assert_called_with(state="normal")
    assert any(
        "preservado" in call.args[0]
        for call in application._log.call_args_list
    )


def test_missing_language_prevents_gui_start(application, tmp_path, monkeypatch):
    application.running = False
    previous_pdf = tmp_path / "anterior.pdf"
    application.last_pdf = previous_pdf
    application._get_ocr_language = Mock(return_value="por+fra")
    check = Mock(side_effect=OcrError("Falta o modelo Francês (fra)."))
    thread = Mock()
    showerror = Mock()
    monkeypatch.setattr(gui_module, "check_ocr_available", check)
    monkeypatch.setattr(gui_module.threading, "Thread", thread)
    monkeypatch.setattr(gui_module.messagebox, "showerror", showerror)

    application._start()

    check.assert_called_once_with("por+fra")
    thread.assert_not_called()
    assert not application.running
    assert application.last_pdf == previous_pdf
    assert "fra" in showerror.call_args.args[1]


@pytest.mark.parametrize("language", [None, "por+eng"])
def test_gui_preflight_runs_only_with_ocr(application, monkeypatch, language):
    application.running = False
    application.ocr_enabled.get.return_value = language is not None
    application._get_ocr_language = Mock(return_value=language)
    check = Mock(return_value="ocrmypdf")
    thread = Mock()
    showerror = Mock()
    monkeypatch.setattr(gui_module, "check_ocr_available", check)
    monkeypatch.setattr(gui_module.threading, "Thread", thread)
    monkeypatch.setattr(gui_module.messagebox, "showerror", showerror)

    application._start()

    if language is None:
        check.assert_not_called()
    else:
        check.assert_called_once_with(language)

    assert application.running
    thread.return_value.start.assert_called_once()
    assert thread.call_args.kwargs["args"][3] == language
    showerror.assert_not_called()


def test_worker_passes_cancellation_to_ocr(application, tmp_path, monkeypatch):
    pdf_path = tmp_path / "livro.pdf"
    document = Document("123", "https://www.scribd.com/document/123/livro")
    monkeypatch.setattr(gui_module, "load_capture", lambda *args: [Path("page.png")])

    def create_pdf(*args):
        pdf_path.write_bytes(b"PDF preservado")
        return pdf_path

    def cancel_ocr(path, *, language, should_cancel):
        assert path == pdf_path
        assert language == "por+eng"
        assert not should_cancel()
        application.cancel_event.set()
        assert should_cancel()
        raise InterruptedError("OCR interrompido.")

    monkeypatch.setattr(gui_module, "create_pdf", create_pdf)
    monkeypatch.setattr(gui_module, "add_ocr", cancel_ocr)

    application._convert(document, pdf_path, MODES[2], "por+eng")
    application._poll()

    assert application.last_pdf == pdf_path.resolve()
    assert pdf_path.read_bytes() == b"PDF preservado"
    application.open_pdf_button.configure.assert_called_with(state="normal")
