import threading
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Protocol

from scribd_to_pdf.application.conversion import (
    CONVERSION_INTERRUPTED,
    CaptureMode,
    ConversionRequest,
    ConversionResult,
    DocumentConverter,
    OcrInterrupted,
    Stage,
)
from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.domain.cancellation import raise_if_cancelled
from scribd_to_pdf.domain.document import Document
from scribd_to_pdf.domain.languages import LANGUAGES
from scribd_to_pdf.infrastructure.preferences import Preferences

READY_MESSAGE = (
    "No navegador, aguarde a capa e feche avisos que ainda cubram o documento.\n"
    "Depois, clique em Capturar páginas nesta janela."
)

Task = Callable[[], None]


@dataclass(frozen=True)
class Form:
    url: str
    destination: str
    mode: CaptureMode
    compact: bool
    ocr_enabled: bool
    ocr_languages: tuple[str, ...]
    export_text: bool


class View(Protocol):
    def log(self, text: str) -> None: ...

    def show_error(self, title: str, message: str) -> None: ...

    def show_running(self, running: bool) -> None: ...

    def enable_ready(self, enabled: bool) -> None: ...

    def enable_cancel(self, enabled: bool) -> None: ...

    def enable_results(self, enabled: bool) -> None: ...

    def destroy(self) -> None: ...


class BackgroundRunner(Protocol):
    def __call__(self, task: Task, *, daemon: bool = False) -> None: ...


class ConversionPresenter:
    def __init__(
        self,
        view: View,
        converter: DocumentConverter,
        *,
        preferences: Preferences,
        save_preferences: Callable[[Preferences], None],
        open_path: Callable[[Path], None],
        dispatch: Callable[[Task], None],
        run_in_background: BackgroundRunner,
    ) -> None:
        self._view = view
        self._converter = converter
        self._save = save_preferences
        self._open_path = open_path
        self._dispatch = dispatch
        self._run_in_background = run_in_background
        self._ready_event = threading.Event()
        self._cancel_event = threading.Event()
        self.preferences = preferences
        self.destination_folder = (
            Path(preferences.destination_folder) if preferences.destination_folder else None
        )
        self.running = False
        self.closing = False
        self.last_pdf: Path | None = None

    @property
    def can_destroy(self) -> bool:
        return self.closing and not self.running

    def welcome(self) -> None:
        self._view.log("Cole o link, escolha o modo e clique em Iniciar.")

        if self.destination_folder is None:
            self._view.log(f"Destino vazio salva ID.pdf em: {self._converter.default_output_folder}")
            return

        self._view.log(f"Pasta lembrada: {self.destination_folder}")
        self._view.log("Destino vazio salva o PDF nessa pasta, usando o ID do documento como nome.")

    def destination_chosen(self, form: Form) -> None:
        self._remember(form)

    def start(self, form: Form) -> None:
        if self.running:
            return

        try:
            request = self._build_request(form)
            self._converter.check_requirements(request)
        except (ValueError, OSError, ConversionError) as error:
            self._view.show_error("Não foi possível iniciar", str(error))
            return

        self._remember(form)
        self._ready_event.clear()
        self._cancel_event.clear()
        self.last_pdf = None
        self._set_running(True)
        self._log_request(request)
        self._run_in_background(partial(self._convert, request))

    def ready(self) -> None:
        self._view.enable_ready(False)
        self._ready_event.set()

    def cancel(self) -> None:
        if not self.running:
            return

        self._cancel_event.set()
        self._ready_event.set()
        self._view.enable_ready(False)
        self._view.enable_cancel(False)
        self._view.log("Interrupção solicitada. Aguarde...")

    def close(self, form: Form) -> None:
        self._remember(form)

        if self.running:
            self.closing = True
            self.cancel()
        else:
            self._view.destroy()

    def shutdown(self) -> None:
        self._cancel_event.set()
        self._ready_event.set()

    def open_pdf(self) -> None:
        if self.last_pdf is not None and not self.running:
            self._open_in_background(self.last_pdf)

    def open_folder(self) -> None:
        if self.last_pdf is not None and not self.running:
            self._open_in_background(self.last_pdf.parent)

    def _build_request(self, form: Form) -> ConversionRequest:
        document = Document.from_url(form.url)
        destination = form.destination.strip()
        ocr_language = self._ocr_language(form)

        return ConversionRequest(
            document=document,
            output_path=self._converter.output_path(
                document,
                Path(destination) if destination else None,
                self.destination_folder,
            ),
            mode=form.mode,
            ocr_language=ocr_language,
            export_text=ocr_language is not None and form.export_text,
            compact=form.compact,
        )

    def _ocr_language(self, form: Form) -> str | None:
        if not form.ocr_enabled:
            return None

        if not form.ocr_languages:
            raise ValueError("Selecione pelo menos um idioma para o OCR.")

        return "+".join(form.ocr_languages)

    def _remember(self, form: Form) -> None:
        destination = form.destination.strip()

        try:
            if destination and Path(destination).suffix.lower() == ".pdf":
                self.destination_folder = Path(destination).expanduser().resolve().parent

            self.preferences = Preferences(
                destination_folder=str(self.destination_folder or ""),
                ocr_enabled=form.ocr_enabled,
                ocr_languages=form.ocr_languages,
                export_text=form.export_text,
                compact_pdf=form.compact,
            )
            self._save(self.preferences)
        except (OSError, ValueError, RuntimeError) as error:
            self._view.log(f"Não foi possível salvar as preferências: {error}")

    def _log_request(self, request: ConversionRequest) -> None:
        self._view.log(f"\nDocumento: {request.document.document_id}")
        self._view.log(f"Destino: {request.output_path}")

        if request.compact:
            self._view.log("Páginas: compactadas em JPEG quando ficam menores")

        if request.ocr_language is None:
            self._view.log("OCR: desativado")
        else:
            names = (LANGUAGES.get(code, code) for code in request.ocr_language.split("+"))
            self._view.log("OCR: " + ", ".join(names))

        if request.text_path is not None:
            self._view.log(f"Texto: {request.text_path}")

    def _set_running(self, running: bool) -> None:
        self.running = running
        self._view.show_running(running)
        self._view.enable_ready(False)
        self._view.enable_cancel(running)
        self._view.enable_results(self.last_pdf is not None and not running)

    def _open_in_background(self, path: Path) -> None:
        def open_or_report() -> None:
            try:
                self._open_path(path)
            except Exception as error:
                self._call_on_ui(self._on_open_failed, str(error))

        self._run_in_background(open_or_report, daemon=True)

    def _call_on_ui(self, callback: Callable[..., None], *args: object) -> None:
        self._dispatch(partial(callback, *args))

    def _convert(self, request: ConversionRequest) -> None:
        try:
            result = self._converter.convert(
                request,
                on_progress=partial(self._call_on_ui, self._on_progress),
                wait_for_ready=self._wait_for_ready,
                should_cancel=self._cancel_event.is_set,
            )
        except OcrInterrupted as interruption:
            self._call_on_ui(self._on_ocr_interrupted, interruption)
        except InterruptedError:
            self._call_on_ui(self._on_interrupted)
        except Exception as error:
            self._call_on_ui(self._on_failed, str(error))
        else:
            self._call_on_ui(self._on_finished, result)

    def _wait_for_ready(self) -> None:
        self._call_on_ui(self._on_waiting_for_ready)
        self._ready_event.wait()
        raise_if_cancelled(self._cancel_event.is_set, CONVERSION_INTERRUPTED)

    def _on_progress(self, stage: Stage, message: str) -> None:
        self._view.log(message)
        self._view.enable_cancel(stage.cancellable and self.running and not self._cancel_event.is_set())

    def _on_waiting_for_ready(self) -> None:
        if not self._cancel_event.is_set():
            self._view.log(READY_MESSAGE)
            self._view.enable_ready(True)

    def _on_finished(self, result: ConversionResult) -> None:
        self._finish(result.pdf_path)
        self._view.log(f"PDF salvo em: {result.pdf_path}")

        if result.text_path is not None:
            self._view.log(f"Texto salvo em: {result.text_path}")

    def _on_ocr_interrupted(self, interruption: OcrInterrupted) -> None:
        self._finish(interruption.pdf_path)
        self._view.log(str(interruption))
        self._view.log(f"PDF salvo em: {interruption.pdf_path}")
        self._view.log("Para aplicar OCR novamente, escolha Usar captura completa.")

    def _on_interrupted(self) -> None:
        self._finish(None)
        self._view.log(CONVERSION_INTERRUPTED)
        self._view.log("Para continuar, escolha Retomar captura.")

    def _on_failed(self, message: str) -> None:
        self._finish(None)
        self._view.log(f"Falha: {message}")
        self._show_error("Falha na conversão", message)

    def _on_open_failed(self, message: str) -> None:
        self._view.log(f"Falha ao abrir: {message}")
        self._show_error("Não foi possível abrir", message)

    def _finish(self, pdf_path: Path | None) -> None:
        self.last_pdf = pdf_path
        self._set_running(False)

    def _show_error(self, title: str, message: str) -> None:
        if not self.closing:
            self._view.show_error(title, message)
