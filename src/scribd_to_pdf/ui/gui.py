import queue
import threading
import tkinter as tk
from collections.abc import Callable
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from tkinter.scrolledtext import ScrolledText

from scribd_to_pdf.application.conversion import (
    CONVERSION_INTERRUPTED,
    CaptureMode,
    ConversionRequest,
    ConversionResult,
    DocumentConverter,
    OcrInterrupted,
    Stage,
)
from scribd_to_pdf.bootstrap import build_converter
from scribd_to_pdf.domain.cancellation import raise_if_cancelled
from scribd_to_pdf.domain.document import Document
from scribd_to_pdf.domain.languages import LANGUAGES
from scribd_to_pdf.infrastructure.opener import open_path
from scribd_to_pdf.infrastructure.preferences import Preferences, load_preferences, save_preferences

MODES = {
    "Nova captura": CaptureMode.NEW,
    "Retomar captura": CaptureMode.RESUME,
    "Usar captura completa": CaptureMode.REUSE,
}
POLL_INTERVAL_MS = 100
UI_FONT_SIZE = -28
LOG_FONT_SIZE = -24
LANGUAGE_COLUMNS = 3
READY_MESSAGE = (
    "No navegador, aguarde a capa e feche o aviso de privacidade.\n"
    "Depois, clique em Capturar páginas nesta janela."
)


def _state(enabled: bool) -> str:
    return "normal" if enabled else "disabled"


class Application:
    def __init__(self, root: tk.Tk, converter: DocumentConverter) -> None:
        self.root = root
        self.converter = converter
        self.ui_calls: queue.Queue[Callable[[], None]] = queue.Queue()
        self.ready_event = threading.Event()
        self.cancel_event = threading.Event()
        self.running = False
        self.closing = False
        self.last_pdf: Path | None = None
        self.preferences = load_preferences()
        self.destination_folder = (
            Path(self.preferences.destination_folder) if self.preferences.destination_folder else None
        )

        self._configure_window()
        self._create_variables()
        self._build_layout()
        self._log_welcome()
        self.url_entry.focus_set()
        root.after(POLL_INTERVAL_MS, self._poll)

    def _configure_window(self) -> None:
        width = min(1100, self.root.winfo_screenwidth() - 80)
        height = min(880, self.root.winfo_screenheight() - 100)

        self.root.title("Scribd to PDF")
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(width, 900), min(height, 600))
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.ui_font = tkfont.nametofont("TkDefaultFont", root=self.root).copy()
        self.ui_font.configure(size=UI_FONT_SIZE)
        self.log_font = tkfont.nametofont("TkFixedFont", root=self.root).copy()
        self.log_font.configure(size=LOG_FONT_SIZE)

        style = ttk.Style(self.root)
        style.configure("App.TButton", font=self.ui_font, padding=(16, 10))
        style.configure("App.TEntry", padding=(10, 8))
        style.configure("App.TCombobox", padding=(10, 8), arrowsize=26)
        style.configure("App.TCheckbutton", font=self.ui_font, padding=(0, 6))
        self.root.option_add("*TCombobox*Listbox.font", self.ui_font)

    def _create_variables(self) -> None:
        self.url = tk.StringVar(master=self.root)
        self.destination = tk.StringVar(master=self.root)
        self.mode = tk.StringVar(master=self.root, value=next(iter(MODES)))
        self.ocr_enabled = tk.BooleanVar(master=self.root, value=self.preferences.ocr_enabled)
        self.export_text = tk.BooleanVar(master=self.root, value=self.preferences.export_text)
        self.ocr_languages = {
            code: tk.BooleanVar(master=self.root, value=code in self.preferences.ocr_languages)
            for code in LANGUAGES
        }

    def _build_layout(self) -> None:
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill="both", expand=True)

        self._label(frame, "Link do documento")
        self.url_entry = self._entry(frame, self.url)
        self.url_entry.pack(fill="x", pady=(8, 16))

        self._label(frame, "Destino do PDF (opcional)")
        destination_row = ttk.Frame(frame)
        destination_row.pack(fill="x", pady=(8, 16))
        self.destination_entry = self._entry(destination_row, self.destination)
        self.destination_entry.pack(side="left", fill="x", expand=True)
        self.browse_button = self._button(destination_row, "Escolher...", self._browse)
        self.browse_button.pack(side="left", padx=(12, 0))

        self._label(frame, "Modo")
        self.mode_box = ttk.Combobox(
            frame,
            textvariable=self.mode,
            values=list(MODES),
            state="readonly",
            font=self.ui_font,
            style="App.TCombobox",
        )
        self.mode_box.pack(fill="x", pady=(8, 16))

        self._build_ocr_controls(frame)
        self._build_actions(frame)

        self.log = ScrolledText(
            frame,
            height=10,
            font=self.log_font,
            state="disabled",
            wrap="word",
            padx=12,
            pady=12,
        )
        self.log.vbar.configure(width=24)
        self.log.pack(fill="both", expand=True)

    def _build_ocr_controls(self, parent: ttk.Frame) -> None:
        area = ttk.Frame(parent)
        area.pack(fill="x", pady=(0, 16))

        self.ocr_button = self._checkbutton(
            area,
            "Adicionar texto pesquisável e selecionável (OCR)",
            self.ocr_enabled,
            command=self._update_ocr_controls,
        )
        self.ocr_button.pack(anchor="w")

        languages_frame = ttk.Frame(area)
        languages_frame.pack(fill="x")
        self.ocr_language_buttons = []

        for index, (code, name) in enumerate(LANGUAGES.items()):
            button = self._checkbutton(languages_frame, name, self.ocr_languages[code])
            button.grid(
                row=index // LANGUAGE_COLUMNS,
                column=index % LANGUAGE_COLUMNS,
                sticky="w",
                padx=(0, 20),
            )
            self.ocr_language_buttons.append(button)

        self.export_text_button = self._checkbutton(
            area,
            "Salvar também o texto reconhecido em .txt",
            self.export_text,
        )
        self.export_text_button.pack(anchor="w", pady=(4, 0))
        self._update_ocr_controls()

    def _build_actions(self, parent: ttk.Frame) -> None:
        conversion_row = ttk.Frame(parent)
        conversion_row.pack(fill="x", pady=(0, 16))
        self.start_button = self._button(conversion_row, "Iniciar", self._start)
        self.start_button.pack(side="left")
        self.ready_button = self._button(conversion_row, "Capturar páginas", self._continue, enabled=False)
        self.ready_button.pack(side="left", padx=12)
        self.cancel_button = self._button(conversion_row, "Interromper", self._cancel, enabled=False)
        self.cancel_button.pack(side="left")

        result_row = ttk.Frame(parent)
        result_row.pack(fill="x", pady=(0, 16))
        self.open_pdf_button = self._button(result_row, "Abrir PDF", self._open_pdf, enabled=False)
        self.open_pdf_button.pack(side="left")
        self.open_folder_button = self._button(result_row, "Abrir pasta", self._open_folder, enabled=False)
        self.open_folder_button.pack(side="left", padx=(12, 0))

    def _label(self, parent: tk.Misc, text: str) -> None:
        ttk.Label(parent, text=text, font=self.ui_font).pack(anchor="w")

    def _entry(self, parent: tk.Misc, variable: tk.StringVar) -> ttk.Entry:
        return ttk.Entry(parent, textvariable=variable, font=self.ui_font, style="App.TEntry")

    def _button(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        *,
        enabled: bool = True,
    ) -> ttk.Button:
        return ttk.Button(parent, text=text, command=command, state=_state(enabled), style="App.TButton")

    def _checkbutton(
        self,
        parent: tk.Misc,
        text: str,
        variable: tk.BooleanVar,
        command: Callable[[], None] | None = None,
    ) -> ttk.Checkbutton:
        return ttk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command,
            style="App.TCheckbutton",
        )

    def _log_welcome(self) -> None:
        self._log("Cole o link, escolha o modo e clique em Iniciar.")

        if self.destination_folder is None:
            self._log("Destino vazio usa output/ID/ID.pdf.")
            return

        self._log(f"Pasta lembrada: {self.destination_folder}")
        self._log("Destino vazio salva o PDF nessa pasta, usando o ID do documento como nome.")

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _update_ocr_controls(self) -> None:
        state = _state(self.ocr_enabled.get() and not self.running)
        self.export_text_button.configure(state=state)

        for button in self.ocr_language_buttons:
            button.configure(state=state)

    def _set_running(self, running: bool) -> None:
        self.running = running

        for widget in (
            self.url_entry,
            self.destination_entry,
            self.browse_button,
            self.start_button,
            self.ocr_button,
        ):
            widget.configure(state=_state(not running))

        self.mode_box.configure(state="disabled" if running else "readonly")
        self.ready_button.configure(state="disabled")
        self.cancel_button.configure(state=_state(running))
        self._update_ocr_controls()
        self._update_result_buttons()

    def _update_result_buttons(self) -> None:
        state = _state(self.last_pdf is not None and not self.running)
        self.open_pdf_button.configure(state=state)
        self.open_folder_button.configure(state=state)

    def _selected_languages(self) -> tuple[str, ...]:
        return tuple(code for code, variable in self.ocr_languages.items() if variable.get())

    def _selected_ocr_language(self) -> str | None:
        if not self.ocr_enabled.get():
            return None

        languages = self._selected_languages()

        if not languages:
            raise ValueError("Selecione pelo menos um idioma para o OCR.")

        return "+".join(languages)

    def _build_request(self) -> ConversionRequest:
        document = Document.from_url(self.url.get())
        destination = self.destination.get().strip()
        ocr_language = self._selected_ocr_language()

        return ConversionRequest(
            document=document,
            output_path=self.converter.output_path(
                document,
                Path(destination) if destination else None,
                self.destination_folder,
            ),
            mode=MODES[self.mode.get()],
            ocr_language=ocr_language,
            export_text=ocr_language is not None and self.export_text.get(),
        )

    def _browse(self) -> None:
        initial_directory = {"initialdir": str(self.destination_folder)} if self.destination_folder else {}
        selected = filedialog.asksaveasfilename(
            parent=self.root,
            title="Salvar PDF",
            initialfile="documento.pdf",
            defaultextension=".pdf",
            filetypes=[("Arquivo PDF", "*.pdf")],
            **initial_directory,
        )

        if selected:
            self.destination.set(selected)
            self._save_preferences()

    def _save_preferences(self) -> None:
        destination = self.destination.get().strip()

        try:
            if destination and Path(destination).suffix.lower() == ".pdf":
                self.destination_folder = Path(destination).expanduser().resolve().parent

            self.preferences = Preferences(
                destination_folder=str(self.destination_folder or ""),
                ocr_enabled=self.ocr_enabled.get(),
                ocr_languages=self._selected_languages(),
                export_text=self.export_text.get(),
            )
            save_preferences(self.preferences)
        except (OSError, ValueError, RuntimeError) as error:
            self._log(f"Não foi possível salvar as preferências: {error}")

    def _start(self) -> None:
        if self.running:
            return

        try:
            request = self._build_request()
            self.converter.check_requirements(request)
        except (ValueError, OSError, RuntimeError) as error:
            messagebox.showerror("Não foi possível iniciar", str(error), parent=self.root)
            return

        self._save_preferences()
        self.ready_event.clear()
        self.cancel_event.clear()
        self.last_pdf = None
        self._set_running(True)
        self._log_request(request)
        threading.Thread(target=self._convert, args=(request,)).start()

    def _log_request(self, request: ConversionRequest) -> None:
        self._log(f"\nDocumento: {request.document.document_id}")
        self._log(f"Destino: {request.output_path}")

        if request.ocr_language is None:
            self._log("OCR: desativado")
        else:
            names = (LANGUAGES.get(code, code) for code in request.ocr_language.split("+"))
            self._log("OCR: " + ", ".join(names))

        if request.text_path is not None:
            self._log(f"Texto: {request.text_path}")

    def _continue(self) -> None:
        self.ready_button.configure(state="disabled")
        self.ready_event.set()

    def _cancel(self) -> None:
        if not self.running:
            return

        self.cancel_event.set()
        self.ready_event.set()
        self.ready_button.configure(state="disabled")
        self.cancel_button.configure(state="disabled")
        self._log("Interrupção solicitada. Aguarde...")

    def _close(self) -> None:
        self._save_preferences()

        if self.running:
            self.closing = True
            self._cancel()
        else:
            self.root.destroy()

    def _open_pdf(self) -> None:
        if self.last_pdf is not None and not self.running:
            self._open_in_background(self.last_pdf)

    def _open_folder(self) -> None:
        if self.last_pdf is not None and not self.running:
            self._open_in_background(self.last_pdf.parent)

    def _open_in_background(self, path: Path) -> None:
        def open_or_report() -> None:
            try:
                open_path(path)
            except Exception as error:
                self._call_on_ui(self._on_open_failed, str(error))

        threading.Thread(target=open_or_report, daemon=True).start()

    def _call_on_ui(self, callback: Callable[..., None], *args: object) -> None:
        self.ui_calls.put(partial(callback, *args))

    def _convert(self, request: ConversionRequest) -> None:
        try:
            result = self.converter.convert(
                request,
                on_progress=partial(self._call_on_ui, self._on_progress),
                wait_for_ready=self._wait_for_ready,
                should_cancel=self.cancel_event.is_set,
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
        self.ready_event.wait()
        raise_if_cancelled(self.cancel_event.is_set, CONVERSION_INTERRUPTED)

    def _poll(self) -> None:
        while True:
            try:
                callback = self.ui_calls.get_nowait()
            except queue.Empty:
                break

            callback()

        if self.closing and not self.running:
            self.root.destroy()
            return

        self.root.after(POLL_INTERVAL_MS, self._poll)

    def _on_progress(self, stage: Stage, message: str) -> None:
        self._log(message)
        can_cancel = stage.cancellable and self.running and not self.cancel_event.is_set()
        self.cancel_button.configure(state=_state(can_cancel))

    def _on_waiting_for_ready(self) -> None:
        if not self.cancel_event.is_set():
            self._log(READY_MESSAGE)
            self.ready_button.configure(state="normal")

    def _on_finished(self, result: ConversionResult) -> None:
        self._finish(result.pdf_path)
        self._log(f"PDF salvo em: {result.pdf_path}")

        if result.text_path is not None:
            self._log(f"Texto salvo em: {result.text_path}")

    def _on_ocr_interrupted(self, interruption: OcrInterrupted) -> None:
        self._finish(interruption.pdf_path)
        self._log(str(interruption))
        self._log(f"PDF salvo em: {interruption.pdf_path}")
        self._log("Para aplicar OCR novamente, escolha Usar captura completa.")

    def _on_interrupted(self) -> None:
        self._finish(None)
        self._log(CONVERSION_INTERRUPTED)
        self._log("Para continuar, escolha Retomar captura.")

    def _on_failed(self, message: str) -> None:
        self._finish(None)
        self._log(f"Falha: {message}")
        self._show_error("Falha na conversão", message)

    def _on_open_failed(self, message: str) -> None:
        self._log(f"Falha ao abrir: {message}")
        self._show_error("Não foi possível abrir", message)

    def _finish(self, pdf_path: Path | None) -> None:
        self.last_pdf = pdf_path
        self._set_running(False)

    def _show_error(self, title: str, message: str) -> None:
        if not self.closing:
            messagebox.showerror(title, message, parent=self.root)


def main() -> None:
    root = tk.Tk()
    application = Application(root, build_converter())

    try:
        root.mainloop()
    finally:
        application.cancel_event.set()
        application.ready_event.set()


if __name__ == "__main__":
    main()
