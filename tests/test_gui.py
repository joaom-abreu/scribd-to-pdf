import queue
import threading
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock

import pytest

from scribd_to_pdf import gui as gui_module
from scribd_to_pdf.gui import MODES, Application
from scribd_to_pdf.models import Document
from scribd_to_pdf.ocr import OcrError
from scribd_to_pdf.preferences import Preferences


@pytest.fixture
def application(monkeypatch):
    # Exercita os eventos da GUI sem depender de um servidor gráfico.
    app = Application.__new__(Application)
    app.root = Mock()
    app.events = queue.Queue()
    app.ready_event = threading.Event()
    app.cancel_event = threading.Event()
    app.running = True
    app.closing = False
    app.last_pdf = None
    app.preferences = Preferences()
    app.destination_folder = None
    app.ocr_enabled = Mock()
    app.ocr_enabled.get.return_value = True
    app.ocr_languages = {}

    for code in gui_module.OCR_LANGUAGES.values():
        variable = Mock()
        variable.get.return_value = code == "por"
        app.ocr_languages[code] = variable

    monkeypatch.setattr(gui_module, "save_preferences", Mock())
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


@pytest.mark.parametrize("remembered", [False, True])
def test_empty_destination_uses_document_id(application, tmp_path, monkeypatch, remembered):
    application.running = False
    application.ocr_enabled.get.return_value = False
    application._get_ocr_language = Mock(return_value=None)

    if remembered:
        application.destination_folder = tmp_path / "pdfs"

    thread = Mock()
    monkeypatch.setattr(gui_module.threading, "Thread", thread)

    application._start()

    expected = (
        tmp_path / "pdfs" / "123.pdf"
        if remembered
        else Path("output") / "123" / "123.pdf"
    )
    assert thread.call_args.kwargs["args"][1] == expected
    assert application.preferences.destination_folder == (
        str(tmp_path / "pdfs") if remembered else ""
    )


def test_explicit_destination_overrides_saved_folder(application, tmp_path, monkeypatch):
    application.running = False
    application.destination_folder = tmp_path / "pasta_antiga"
    chosen = tmp_path / "pasta_nova" / "meu_livro.pdf"
    application.destination.get.return_value = str(chosen)
    application.ocr_enabled.get.return_value = False
    application._get_ocr_language = Mock(return_value=None)
    thread = Mock()
    monkeypatch.setattr(gui_module.threading, "Thread", thread)

    application._start()

    assert thread.call_args.kwargs["args"][1] == chosen
    assert application.destination_folder == chosen.parent.resolve()
    assert application.preferences.destination_folder == str(chosen.parent.resolve())


@pytest.mark.parametrize("running", [False, True])
def test_close_saves_current_choices(application, tmp_path, running):
    application.running = running
    selected_path = tmp_path / "livros" / "livro.pdf"
    application.destination.get.return_value = str(selected_path)
    application.ocr_enabled.get.return_value = False

    for code, variable in application.ocr_languages.items():
        variable.get.return_value = code in {"eng", "spa"}

    application._close()

    expected = Preferences(
        destination_folder=str(selected_path.parent.resolve()),
        ocr_enabled=False,
        ocr_languages=("eng", "spa"),
    )
    gui_module.save_preferences.assert_called_once_with(expected)

    if running:
        assert application.closing
        assert application.cancel_event.is_set()
        application.root.destroy.assert_not_called()
    else:
        application.root.destroy.assert_called_once()


def test_save_failure_does_not_block_conversion(application, monkeypatch):
    application.running = False
    application.ocr_enabled.get.return_value = False
    application._get_ocr_language = Mock(return_value=None)
    gui_module.save_preferences.side_effect = PermissionError("Sem permissão.")
    thread = Mock()
    monkeypatch.setattr(gui_module.threading, "Thread", thread)

    application._start()

    assert application.running
    thread.return_value.start.assert_called_once()
    assert any(
        "salvar as preferências" in call.args[0]
        for call in application._log.call_args_list
    )


def test_browse_reuses_folder_and_remembers_selection(application, tmp_path, monkeypatch):
    interpreter = tk.Tcl()
    application.destination = tk.StringVar(master=interpreter)
    application.destination_folder = tmp_path / "pasta_antiga"
    selected_path = tmp_path / "pasta_nova" / "livro.pdf"
    dialog = Mock(return_value=str(selected_path))
    monkeypatch.setattr(gui_module.filedialog, "asksaveasfilename", dialog)

    application._browse()

    assert dialog.call_args.kwargs["initialdir"] == str(tmp_path / "pasta_antiga")
    assert application.destination.get() == str(selected_path)
    assert application.destination_folder == selected_path.parent.resolve()
    gui_module.save_preferences.assert_called_once()
