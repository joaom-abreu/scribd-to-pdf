import queue
import threading
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock

import pytest

from scribd_to_pdf.application.conversion import (
    CaptureMode,
    ConversionRequest,
    ConversionResult,
    DocumentConverter,
    OcrInterrupted,
    Stage,
)
from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.domain.languages import LANGUAGES
from scribd_to_pdf.infrastructure.preferences import Preferences
from scribd_to_pdf.infrastructure.storage import FileCaptureRepository
from scribd_to_pdf.ui import gui as gui_module
from scribd_to_pdf.ui.gui import Application

URL = "https://www.scribd.com/document/123/livro"
OCR_INTERRUPTED = "OCR interrompido. O PDF com as imagens foi preservado."
WIDGETS = (
    "url_entry",
    "destination_entry",
    "browse_button",
    "start_button",
    "ocr_button",
    "mode_box",
    "ready_button",
    "cancel_button",
    "open_pdf_button",
    "open_folder_button",
    "export_text_button",
    "compact_button",
)


def variable(value: object) -> Mock:
    mock = Mock()
    mock.get.return_value = value
    return mock


@pytest.fixture
def application(monkeypatch):
    app = Application.__new__(Application)
    app.root = Mock()
    app.converter = Mock(wraps=DocumentConverter(
        FileCaptureRepository(Path("capturas")), Mock(), Mock(), Mock(), Path("pdfs"),
    ))
    app.ui_calls = queue.Queue()
    app.ready_event = threading.Event()
    app.cancel_event = threading.Event()
    app.running = False
    app.closing = False
    app.last_pdf = None
    app.preferences = Preferences()
    app.destination_folder = None
    app.url = variable(URL)
    app.destination = variable("")
    app.mode = variable("Nova captura")
    app.ocr_enabled = variable(False)
    app.export_text = variable(False)
    app.compact = variable(False)
    app.ocr_languages = {code: variable(code == "por") for code in LANGUAGES}
    app.ocr_language_buttons = []
    app._log = Mock()

    for name in WIDGETS:
        setattr(app, name, Mock())

    monkeypatch.setattr(gui_module, "save_preferences", Mock())
    monkeypatch.setattr(gui_module.messagebox, "showerror", Mock())
    return app


@pytest.fixture
def thread(monkeypatch):
    mock = Mock()
    monkeypatch.setattr(gui_module.threading, "Thread", mock)
    return mock


def started_request(thread: Mock) -> ConversionRequest:
    thread.return_value.start.assert_called_once()
    return thread.call_args.kwargs["args"][0]


def logged(application) -> str:
    return "\n".join(call.args[0] for call in application._log.call_args_list)


def test_cancellation_is_disabled_while_building_pdf(application):
    application.running = True
    application._call_on_ui(application._on_progress, Stage.PDF, "Gerando PDF...")
    application._call_on_ui(application._on_progress, Stage.OCR, "Aplicando OCR...")

    application._poll()

    states = [call.kwargs["state"] for call in application.cancel_button.configure.call_args_list]
    assert states == ["disabled", "normal"]
    assert application.running


def test_pending_progress_does_not_undo_cancellation(application):
    application.running = True
    application._call_on_ui(application._on_progress, Stage.OCR, "Aplicando OCR...")
    application._cancel()

    application._poll()

    assert application.cancel_event.is_set()
    application.cancel_button.configure.assert_called_with(state="disabled")


def test_missing_language_prevents_start(application, thread):
    previous_pdf = Path("anterior.pdf")
    application.last_pdf = previous_pdf
    application.ocr_enabled.get.return_value = True
    application.converter.check_requirements.side_effect = ConversionError("Falta o modelo Francês (fra).")

    application._start()

    thread.assert_not_called()
    assert not application.running
    assert application.last_pdf == previous_pdf
    assert "fra" in gui_module.messagebox.showerror.call_args.args[1]


@pytest.mark.parametrize("ocr_enabled", [False, True])
def test_start_checks_requirements_and_starts_worker(application, thread, ocr_enabled):
    application.ocr_enabled.get.return_value = ocr_enabled
    application.ocr_languages["eng"].get.return_value = True

    application._start()

    request = started_request(thread)
    application.converter.check_requirements.assert_called_once_with(request)
    assert application.running
    assert request.ocr_language == ("por+eng" if ocr_enabled else None)
    assert request.mode is CaptureMode.NEW


def test_ocr_without_languages_shows_error(application, thread):
    application.ocr_enabled.get.return_value = True
    application.ocr_languages["por"].get.return_value = False

    application._start()

    thread.assert_not_called()
    assert "idioma" in gui_module.messagebox.showerror.call_args.args[1]


@pytest.mark.parametrize("remembered", [False, True])
def test_empty_destination_uses_document_id(application, thread, tmp_path, remembered):
    if remembered:
        application.destination_folder = tmp_path / "pdfs"

    application._start()

    expected = tmp_path / "pdfs" / "123.pdf" if remembered else Path("pdfs") / "123.pdf"
    assert started_request(thread).output_path == expected
    assert application.preferences.destination_folder == (str(tmp_path / "pdfs") if remembered else "")


def test_explicit_destination_overrides_saved_folder(application, thread, tmp_path):
    application.destination_folder = tmp_path / "pasta_antiga"
    chosen = tmp_path / "pasta_nova" / "meu_livro.pdf"
    application.destination.get.return_value = str(chosen)

    application._start()

    assert started_request(thread).output_path == chosen
    assert application.destination_folder == chosen.parent.resolve()
    assert application.preferences.destination_folder == str(chosen.parent.resolve())


@pytest.mark.parametrize("ocr_enabled", [False, True])
def test_text_export_requires_ocr(application, thread, ocr_enabled):
    application.ocr_enabled.get.return_value = ocr_enabled
    application.export_text.get.return_value = True

    application._start()

    assert started_request(thread).export_text is ocr_enabled
    assert application.preferences.export_text is True


def test_compact_choice_is_sent_and_remembered(application, thread):
    application.compact.get.return_value = True

    application._start()

    assert started_request(thread).compact is True
    assert application.preferences.compact_pdf is True
    assert "compactadas" in logged(application)


def test_save_failure_does_not_block_conversion(application, thread):
    gui_module.save_preferences.side_effect = PermissionError("Sem permissão.")

    application._start()

    started_request(thread)
    assert application.running
    assert "salvar as preferências" in logged(application)


@pytest.mark.parametrize("running", [False, True])
def test_close_saves_current_choices(application, tmp_path, running):
    application.running = running
    selected_path = tmp_path / "livros" / "livro.pdf"
    application.destination.get.return_value = str(selected_path)
    application.export_text.get.return_value = True

    for code, language in application.ocr_languages.items():
        language.get.return_value = code in {"eng", "spa"}

    application._close()

    gui_module.save_preferences.assert_called_once_with(Preferences(
        destination_folder=str(selected_path.parent.resolve()),
        ocr_enabled=False,
        ocr_languages=("eng", "spa"),
        export_text=True,
    ))

    if running:
        assert application.closing
        assert application.cancel_event.is_set()
        application.root.destroy.assert_not_called()
    else:
        application.root.destroy.assert_called_once()


def test_browse_reuses_folder_and_remembers_selection(application, tmp_path, monkeypatch):
    application.destination = tk.StringVar(master=tk.Tcl())
    application.destination_folder = tmp_path / "pasta_antiga"
    selected_path = tmp_path / "pasta_nova" / "livro.pdf"
    dialog = Mock(return_value=str(selected_path))
    monkeypatch.setattr(gui_module.filedialog, "asksaveasfilename", dialog)

    application._browse()

    assert dialog.call_args.kwargs["initialdir"] == str(tmp_path / "pasta_antiga")
    assert application.destination.get() == str(selected_path)
    assert application.destination_folder == selected_path.parent.resolve()
    gui_module.save_preferences.assert_called_once()


@pytest.mark.parametrize("ocr_enabled, running", [(False, False), (True, False), (True, True)])
def test_text_export_control_requires_idle_ocr(application, ocr_enabled, running):
    application.ocr_enabled.get.return_value = ocr_enabled
    application.running = running

    application._update_ocr_controls()

    application.export_text_button.configure.assert_called_with(
        state="normal" if ocr_enabled and not running else "disabled",
    )


@pytest.mark.parametrize("text_saved", [False, True])
def test_finished_conversion_enables_result_buttons(application, monkeypatch, tmp_path, text_saved):
    pdf_path = tmp_path / "livro.pdf"
    result = ConversionResult(pdf_path, pdf_path.with_suffix(".txt") if text_saved else None)
    convert = Mock(return_value=result)
    application.converter.convert = convert
    application.running = True

    application._convert(Mock())
    application._poll()

    assert convert.call_args.kwargs["should_cancel"] == application.cancel_event.is_set
    assert not application.running
    assert application.last_pdf == pdf_path
    application.open_pdf_button.configure.assert_called_with(state="normal")
    assert f"PDF salvo em: {pdf_path}" in logged(application)
    assert ("Texto salvo em:" in logged(application)) is text_saved


def test_interrupted_ocr_keeps_pdf_accessible(application, monkeypatch, tmp_path):
    pdf_path = tmp_path / "livro.pdf"
    application.converter.convert = Mock(side_effect=OcrInterrupted(pdf_path, OCR_INTERRUPTED))
    application.running = True

    application._convert(Mock())
    application._poll()

    assert not application.running
    assert application.last_pdf == pdf_path
    application.open_folder_button.configure.assert_called_with(state="normal")
    assert "preservado" in logged(application)
    assert "Texto salvo em:" not in logged(application)


def test_interrupted_capture_suggests_resume(application, monkeypatch):
    application.converter.convert = Mock(side_effect=InterruptedError("Captura interrompida."))
    application.running = True

    application._convert(Mock())
    application._poll()

    assert application.last_pdf is None
    assert "Retomar captura" in logged(application)
    gui_module.messagebox.showerror.assert_not_called()


def test_failure_shows_error_unless_closing(application, monkeypatch):
    application.converter.convert = Mock(side_effect=ValueError("Falha simulada."))
    application.running = True

    application._convert(Mock())
    application._poll()

    assert not application.running
    assert "Falha simulada." in gui_module.messagebox.showerror.call_args.args[1]


def test_waiting_for_ready_enables_capture_button(application):
    application.running = True
    worker = threading.Thread(target=application._wait_for_ready)
    worker.start()

    application.ui_calls.get(timeout=1)()
    application.ready_button.configure.assert_called_with(state="normal")
    application._continue()
    worker.join(1)

    assert not worker.is_alive()


def test_cancel_while_waiting_interrupts_worker(application):
    application.running = True
    errors = []

    def wait():
        try:
            application._wait_for_ready()
        except InterruptedError as error:
            errors.append(error)

    worker = threading.Thread(target=wait)
    worker.start()
    application._cancel()
    worker.join(1)

    assert len(errors) == 1
