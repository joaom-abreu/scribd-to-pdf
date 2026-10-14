import queue
import threading
from dataclasses import dataclass, field, replace
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
from scribd_to_pdf.infrastructure.preferences import Preferences
from scribd_to_pdf.infrastructure.storage import FileCaptureRepository
from scribd_to_pdf.ui.presenter import ConversionPresenter, Form

URL = "https://www.scribd.com/document/123/livro"
OCR_INTERRUPTED = "OCR interrompido. O PDF com as imagens foi preservado."
FORM = Form(
    url=URL,
    destination="",
    mode=CaptureMode.NEW,
    compact=False,
    ocr_enabled=False,
    ocr_languages=("por",),
    export_text=False,
)


@dataclass
class FakeView:
    messages: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)
    running: list[bool] = field(default_factory=list)
    ready: list[bool] = field(default_factory=list)
    cancel: list[bool] = field(default_factory=list)
    results: list[bool] = field(default_factory=list)
    destroyed: bool = False

    def log(self, text: str) -> None:
        self.messages.append(text)

    def show_error(self, title: str, message: str) -> None:
        self.errors.append((title, message))

    def show_running(self, running: bool) -> None:
        self.running.append(running)

    def enable_ready(self, enabled: bool) -> None:
        self.ready.append(enabled)

    def enable_cancel(self, enabled: bool) -> None:
        self.cancel.append(enabled)

    def enable_results(self, enabled: bool) -> None:
        self.results.append(enabled)

    def destroy(self) -> None:
        self.destroyed = True

    @property
    def logged(self) -> str:
        return "\n".join(self.messages)


@dataclass
class FakeRunner:
    tasks: list[tuple[object, bool]] = field(default_factory=list)

    def __call__(self, task, *, daemon: bool = False) -> None:
        self.tasks.append((task, daemon))

    def run_last(self) -> None:
        task, _ = self.tasks[-1]
        task()


@dataclass
class Harness:
    presenter: ConversionPresenter
    view: FakeView
    converter: Mock
    save: Mock
    open_path: Mock
    runner: FakeRunner
    ui_calls: queue.Queue

    def drain(self) -> None:
        while not self.ui_calls.empty():
            self.ui_calls.get_nowait()()

    def started_request(self) -> ConversionRequest:
        assert len(self.runner.tasks) == 1
        task, daemon = self.runner.tasks[0]
        assert daemon is False
        return task.args[0]


def build_harness(tmp_path: Path, preferences: Preferences | None = None) -> Harness:
    view = FakeView()
    converter = Mock(wraps=DocumentConverter(
        FileCaptureRepository(tmp_path / "capturas"), Mock(), Mock(), Mock(), tmp_path / "pdfs",
    ))
    converter.default_output_folder = tmp_path / "pdfs"
    save = Mock()
    open_path = Mock()
    runner = FakeRunner()
    ui_calls: queue.Queue = queue.Queue()
    presenter = ConversionPresenter(
        view,
        converter,
        preferences=preferences or Preferences(),
        save_preferences=save,
        open_path=open_path,
        dispatch=ui_calls.put,
        run_in_background=runner,
    )
    return Harness(presenter, view, converter, save, open_path, runner, ui_calls)


@pytest.fixture
def harness(tmp_path) -> Harness:
    return build_harness(tmp_path)


def finish_with(harness: Harness, **effects) -> None:
    harness.converter.convert = Mock(**effects)
    harness.presenter.start(FORM)
    harness.runner.run_last()
    harness.drain()


def test_welcome_shows_default_folder(harness, tmp_path):
    harness.presenter.welcome()

    assert f"Destino vazio salva ID.pdf em: {tmp_path / 'pdfs'}" in harness.view.logged


def test_welcome_shows_remembered_folder(tmp_path):
    harness = build_harness(tmp_path, Preferences(destination_folder=str(tmp_path / "lembrada")))

    harness.presenter.welcome()

    assert f"Pasta lembrada: {tmp_path / 'lembrada'}" in harness.view.logged


@pytest.mark.parametrize("ocr_enabled", [False, True])
def test_start_checks_requirements_and_starts_worker(harness, ocr_enabled):
    harness.presenter.start(replace(FORM, ocr_enabled=ocr_enabled, ocr_languages=("por", "eng")))

    request = harness.started_request()
    harness.converter.check_requirements.assert_called_once_with(request)
    assert harness.presenter.running
    assert harness.view.running == [True]
    assert harness.view.cancel == [True]
    assert request.ocr_language == ("por+eng" if ocr_enabled else None)
    assert request.mode is CaptureMode.NEW


def test_missing_language_prevents_start(harness):
    harness.presenter.last_pdf = Path("anterior.pdf")
    harness.converter.check_requirements.side_effect = ConversionError("Falta o modelo Francês (fra).")

    harness.presenter.start(replace(FORM, ocr_enabled=True, ocr_languages=("por", "fra")))

    assert harness.runner.tasks == []
    assert not harness.presenter.running
    assert harness.presenter.last_pdf == Path("anterior.pdf")
    assert "fra" in harness.view.errors[0][1]


@pytest.mark.parametrize(
    "form, message",
    [
        (replace(FORM, ocr_enabled=True, ocr_languages=()), "idioma"),
        (replace(FORM, url="https://example.com/document/1"), "scribd.com"),
        (replace(FORM, destination="livro.txt"), ".pdf"),
    ],
    ids=["ocr-sem-idioma", "link-invalido", "destino-sem-pdf"],
)
def test_invalid_form_shows_error(harness, form, message):
    harness.presenter.start(form)

    assert harness.runner.tasks == []
    assert message in harness.view.errors[0][1]


def test_start_is_ignored_while_running(harness):
    harness.presenter.start(FORM)
    harness.presenter.start(FORM)

    assert len(harness.runner.tasks) == 1


@pytest.mark.parametrize("remembered", [False, True])
def test_empty_destination_uses_document_id(tmp_path, remembered):
    folder = str(tmp_path / "lembrada") if remembered else ""
    harness = build_harness(tmp_path, Preferences(destination_folder=folder))

    harness.presenter.start(FORM)

    expected = tmp_path / ("lembrada" if remembered else "pdfs") / "123.pdf"
    assert harness.started_request().output_path == expected
    assert harness.presenter.preferences.destination_folder == folder


def test_explicit_destination_overrides_saved_folder(tmp_path):
    harness = build_harness(tmp_path, Preferences(destination_folder=str(tmp_path / "antiga")))
    chosen = tmp_path / "nova" / "meu_livro.pdf"

    harness.presenter.start(replace(FORM, destination=str(chosen)))

    assert harness.started_request().output_path == chosen
    assert harness.presenter.destination_folder == chosen.parent.resolve()
    assert harness.presenter.preferences.destination_folder == str(chosen.parent.resolve())


@pytest.mark.parametrize("ocr_enabled", [False, True])
def test_text_export_requires_ocr(harness, ocr_enabled):
    harness.presenter.start(replace(FORM, ocr_enabled=ocr_enabled, export_text=True))

    assert harness.started_request().export_text is ocr_enabled
    assert harness.presenter.preferences.export_text is True


def test_compact_choice_is_sent_and_remembered(harness):
    harness.presenter.start(replace(FORM, compact=True))

    assert harness.started_request().compact is True
    assert harness.presenter.preferences.compact_pdf is True
    assert "compactadas" in harness.view.logged


def test_save_failure_does_not_block_conversion(harness):
    harness.save.side_effect = PermissionError("Sem permissão.")

    harness.presenter.start(FORM)

    harness.started_request()
    assert harness.presenter.running
    assert "salvar as preferências" in harness.view.logged


@pytest.mark.parametrize("running", [False, True])
def test_close_saves_current_choices(harness, tmp_path, running):
    harness.presenter.running = running
    selected = tmp_path / "livros" / "livro.pdf"

    harness.presenter.close(replace(
        FORM,
        destination=str(selected),
        ocr_languages=("eng", "spa"),
        export_text=True,
    ))

    harness.save.assert_called_once_with(Preferences(
        destination_folder=str(selected.parent.resolve()),
        ocr_enabled=False,
        ocr_languages=("eng", "spa"),
        export_text=True,
    ))
    assert harness.presenter.closing is running
    assert harness.view.destroyed is not running


def test_chosen_destination_is_remembered(tmp_path):
    harness = build_harness(tmp_path, Preferences(destination_folder=str(tmp_path / "antiga")))
    selected = tmp_path / "nova" / "livro.pdf"

    harness.presenter.destination_chosen(replace(FORM, destination=str(selected)))

    assert harness.presenter.destination_folder == selected.parent.resolve()
    harness.save.assert_called_once()


def test_cancellation_is_disabled_while_building_pdf(harness):
    harness.presenter.start(FORM)
    harness.view.cancel.clear()
    harness.ui_calls.put(lambda: harness.presenter._on_progress(Stage.PDF, "Gerando PDF..."))
    harness.ui_calls.put(lambda: harness.presenter._on_progress(Stage.OCR, "Aplicando OCR..."))

    harness.drain()

    assert harness.view.cancel == [False, True]


def test_pending_progress_does_not_undo_cancellation(harness):
    harness.presenter.start(FORM)
    harness.ui_calls.put(lambda: harness.presenter._on_progress(Stage.OCR, "Aplicando OCR..."))
    harness.presenter.cancel()

    harness.drain()

    assert harness.view.cancel[-1] is False
    assert "Interrupção solicitada" in harness.view.logged


@pytest.mark.parametrize("text_saved", [False, True])
def test_finished_conversion_enables_result_buttons(harness, tmp_path, text_saved):
    pdf_path = tmp_path / "livro.pdf"
    result = ConversionResult(pdf_path, pdf_path.with_suffix(".txt") if text_saved else None)

    finish_with(harness, return_value=result)

    assert not harness.presenter.running
    assert harness.presenter.last_pdf == pdf_path
    assert harness.view.results[-1] is True
    assert f"PDF salvo em: {pdf_path}" in harness.view.logged
    assert ("Texto salvo em:" in harness.view.logged) is text_saved


def test_interrupted_ocr_keeps_pdf_accessible(harness, tmp_path):
    pdf_path = tmp_path / "livro.pdf"

    finish_with(harness, side_effect=OcrInterrupted(pdf_path, OCR_INTERRUPTED))

    assert harness.presenter.last_pdf == pdf_path
    assert harness.view.results[-1] is True
    assert "preservado" in harness.view.logged
    assert "Usar captura completa" in harness.view.logged


def test_interrupted_capture_suggests_resume(harness):
    finish_with(harness, side_effect=InterruptedError("Captura interrompida."))

    assert harness.presenter.last_pdf is None
    assert "Retomar captura" in harness.view.logged
    assert harness.view.errors == []


@pytest.mark.parametrize("closing", [False, True])
def test_failure_shows_error_unless_closing(harness, closing):
    harness.presenter.closing = closing

    finish_with(harness, side_effect=ConversionError("Falha simulada."))

    assert not harness.presenter.running
    assert "Falha: Falha simulada." in harness.view.logged
    assert bool(harness.view.errors) is not closing
    assert harness.presenter.can_destroy is closing


def test_open_pdf_runs_in_background_and_reports_failure(harness, tmp_path):
    harness.presenter.last_pdf = tmp_path / "livro.pdf"
    harness.open_path.side_effect = OSError("xdg-open ausente")

    harness.presenter.open_folder()
    task, daemon = harness.runner.tasks[0]
    task()
    harness.drain()

    harness.open_path.assert_called_once_with(tmp_path)
    assert daemon is True
    assert harness.view.errors == [("Não foi possível abrir", "xdg-open ausente")]


def test_open_pdf_is_ignored_without_result(harness):
    harness.presenter.open_pdf()

    assert harness.runner.tasks == []


def test_waiting_for_ready_enables_capture_button(harness):
    harness.presenter.running = True
    worker = threading.Thread(target=harness.presenter._wait_for_ready)
    worker.start()

    harness.ui_calls.get(timeout=1)()
    assert harness.view.ready == [True]
    harness.presenter.ready()
    worker.join(1)

    assert not worker.is_alive()


def test_cancel_while_waiting_interrupts_worker(harness):
    harness.presenter.running = True
    errors = []

    def wait():
        try:
            harness.presenter._wait_for_ready()
        except InterruptedError as error:
            errors.append(error)

    worker = threading.Thread(target=wait)
    worker.start()
    harness.presenter.cancel()
    worker.join(1)

    assert len(errors) == 1


def test_shutdown_releases_waiting_worker(harness):
    worker = threading.Thread(target=lambda: pytest.raises(InterruptedError, harness.presenter._wait_for_ready))
    worker.start()

    harness.presenter.shutdown()
    worker.join(1)

    assert not worker.is_alive()
