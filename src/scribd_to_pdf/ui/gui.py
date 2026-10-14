import os
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from tkinter.scrolledtext import ScrolledText

from scribd_to_pdf.application.conversion import CaptureMode, DocumentConverter
from scribd_to_pdf.bootstrap import build_converter
from scribd_to_pdf.domain.languages import LANGUAGES
from scribd_to_pdf.infrastructure.opener import open_path
from scribd_to_pdf.infrastructure.preferences import load_preferences, save_preferences
from scribd_to_pdf.ui.presenter import ConversionPresenter, Form, Task
from scribd_to_pdf.ui.scaling import SCALE_VARIABLE, interface_scale, scaled

MODES = {
    "Nova captura": CaptureMode.NEW,
    "Retomar captura": CaptureMode.RESUME,
    "Usar captura completa": CaptureMode.REUSE,
}
POLL_INTERVAL_MS = 100
UI_FONT_PX = 15
LOG_FONT_PX = 14
WINDOW_SIZE = (860, 700)
MIN_WINDOW_SIZE = (640, 520)
SCREEN_MARGIN = (80, 100)
LANGUAGE_COLUMNS = 3


def _state(enabled: bool) -> str:
    return "normal" if enabled else "disabled"


def _run_in_background(task: Task, *, daemon: bool = False) -> None:
    threading.Thread(target=task, daemon=daemon).start()


class Application:
    def __init__(self, root: tk.Tk, converter: DocumentConverter) -> None:
        self.root = root
        self.ui_calls: queue.Queue[Task] = queue.Queue()
        self.running = False
        self.presenter = ConversionPresenter(
            self,
            converter,
            preferences=load_preferences(),
            save_preferences=save_preferences,
            open_path=open_path,
            dispatch=self.ui_calls.put,
            run_in_background=_run_in_background,
        )
        self.scale = interface_scale(root.winfo_fpixels("1i"), os.environ.get(SCALE_VARIABLE))

        self._configure_window()
        self._create_variables()
        self._build_layout()
        self.presenter.welcome()
        self.url_entry.focus_set()
        root.after(POLL_INTERVAL_MS, self._poll)

    def log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message, parent=self.root)

    def show_running(self, running: bool) -> None:
        self.running = running

        for widget in (
            self.url_entry,
            self.destination_entry,
            self.browse_button,
            self.start_button,
            self.ocr_button,
            self.compact_button,
        ):
            widget.configure(state=_state(not running))

        self.mode_box.configure(state="disabled" if running else "readonly")
        self._update_ocr_controls()

    def enable_ready(self, enabled: bool) -> None:
        self.ready_button.configure(state=_state(enabled))

    def enable_cancel(self, enabled: bool) -> None:
        self.cancel_button.configure(state=_state(enabled))

    def enable_results(self, enabled: bool) -> None:
        self.open_pdf_button.configure(state=_state(enabled))
        self.open_folder_button.configure(state=_state(enabled))

    def destroy(self) -> None:
        self.root.destroy()

    def _px(self, value: int) -> int:
        return scaled(value, self.scale)

    def _configure_window(self) -> None:
        screen_width = self.root.winfo_screenwidth() - SCREEN_MARGIN[0]
        screen_height = self.root.winfo_screenheight() - SCREEN_MARGIN[1]
        width = min(self._px(WINDOW_SIZE[0]), screen_width)
        height = min(self._px(WINDOW_SIZE[1]), screen_height)

        self.root.title("Scribd to PDF")
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(
            min(self._px(MIN_WINDOW_SIZE[0]), width),
            min(self._px(MIN_WINDOW_SIZE[1]), height),
        )
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.ui_font = tkfont.nametofont("TkDefaultFont", root=self.root).copy()
        self.ui_font.configure(size=-self._px(UI_FONT_PX))
        self.log_font = tkfont.nametofont("TkFixedFont", root=self.root).copy()
        self.log_font.configure(size=-self._px(LOG_FONT_PX))

        style = ttk.Style(self.root)
        style.configure("App.TButton", font=self.ui_font, padding=(self._px(12), self._px(6)))
        style.configure("App.TEntry", padding=(self._px(6), self._px(4)))
        style.configure("App.TCombobox", padding=(self._px(6), self._px(4)), arrowsize=self._px(14))
        style.configure(
            "App.TCheckbutton",
            font=self.ui_font,
            padding=(0, self._px(3)),
            indicatordiameter=self._px(13),
            indicatormargin=(0, self._px(2), self._px(6), self._px(2)),
        )
        self.root.option_add("*TCombobox*Listbox.font", self.ui_font)

    def _create_variables(self) -> None:
        preferences = self.presenter.preferences
        self.url = tk.StringVar(master=self.root)
        self.destination = tk.StringVar(master=self.root)
        self.mode = tk.StringVar(master=self.root, value=next(iter(MODES)))
        self.ocr_enabled = tk.BooleanVar(master=self.root, value=preferences.ocr_enabled)
        self.export_text = tk.BooleanVar(master=self.root, value=preferences.export_text)
        self.compact = tk.BooleanVar(master=self.root, value=preferences.compact_pdf)
        self.ocr_languages = {
            code: tk.BooleanVar(master=self.root, value=code in preferences.ocr_languages)
            for code in LANGUAGES
        }

    def _build_layout(self) -> None:
        frame = ttk.Frame(self.root, padding=self._px(16))
        frame.pack(fill="both", expand=True)

        self._label(frame, "Link do documento")
        self.url_entry = self._entry(frame, self.url)
        self.url_entry.pack(fill="x", pady=(self._px(4), self._px(12)))

        self._label(frame, "Destino do PDF (opcional)")
        destination_row = ttk.Frame(frame)
        destination_row.pack(fill="x", pady=(self._px(4), self._px(12)))
        self.destination_entry = self._entry(destination_row, self.destination)
        self.destination_entry.pack(side="left", fill="x", expand=True)
        self.browse_button = self._button(destination_row, "Escolher...", self._browse)
        self.browse_button.pack(side="left", padx=(self._px(8), 0))

        self._label(frame, "Modo")
        self.mode_box = ttk.Combobox(
            frame,
            textvariable=self.mode,
            values=list(MODES),
            state="readonly",
            font=self.ui_font,
            style="App.TCombobox",
        )
        self.mode_box.pack(fill="x", pady=(self._px(4), self._px(12)))

        self.compact_button = self._checkbutton(
            frame,
            "Compactar páginas com imagens (JPEG quando ficar menor)",
            self.compact,
        )
        self.compact_button.pack(anchor="w", pady=(0, self._px(6)))

        self._build_ocr_controls(frame)
        self._build_actions(frame)

        self.log_text = ScrolledText(
            frame,
            height=10,
            font=self.log_font,
            state="disabled",
            wrap="word",
            padx=self._px(8),
            pady=self._px(8),
        )
        self.log_text.vbar.configure(width=self._px(14))
        self.log_text.pack(fill="both", expand=True)

    def _build_ocr_controls(self, parent: ttk.Frame) -> None:
        area = ttk.Frame(parent)
        area.pack(fill="x", pady=(0, self._px(12)))

        self.ocr_button = self._checkbutton(
            area,
            "Adicionar texto pesquisável e selecionável (OCR)",
            self.ocr_enabled,
            command=self._update_ocr_controls,
        )
        self.ocr_button.pack(anchor="w")

        languages_frame = ttk.Frame(area)
        languages_frame.pack(fill="x", padx=(self._px(24), 0))
        self.ocr_language_buttons = []

        for index, (code, name) in enumerate(LANGUAGES.items()):
            button = self._checkbutton(languages_frame, name, self.ocr_languages[code])
            button.grid(
                row=index // LANGUAGE_COLUMNS,
                column=index % LANGUAGE_COLUMNS,
                sticky="w",
                padx=(0, self._px(16)),
            )
            self.ocr_language_buttons.append(button)

        self.export_text_button = self._checkbutton(
            area,
            "Salvar também o texto reconhecido em .txt",
            self.export_text,
        )
        self.export_text_button.pack(anchor="w", padx=(self._px(24), 0))
        self._update_ocr_controls()

    def _build_actions(self, parent: ttk.Frame) -> None:
        conversion_row = ttk.Frame(parent)
        conversion_row.pack(fill="x", pady=(0, self._px(8)))
        self.start_button = self._button(conversion_row, "Iniciar", self._start)
        self.start_button.pack(side="left")
        self.ready_button = self._button(conversion_row, "Capturar páginas", self.presenter.ready, enabled=False)
        self.ready_button.pack(side="left", padx=self._px(8))
        self.cancel_button = self._button(conversion_row, "Interromper", self.presenter.cancel, enabled=False)
        self.cancel_button.pack(side="left")

        result_row = ttk.Frame(parent)
        result_row.pack(fill="x", pady=(0, self._px(12)))
        self.open_pdf_button = self._button(result_row, "Abrir PDF", self.presenter.open_pdf, enabled=False)
        self.open_pdf_button.pack(side="left")
        self.open_folder_button = self._button(
            result_row, "Abrir pasta", self.presenter.open_folder, enabled=False,
        )
        self.open_folder_button.pack(side="left", padx=(self._px(8), 0))

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
            command=command or "",
            style="App.TCheckbutton",
        )

    def _update_ocr_controls(self) -> None:
        state = _state(self.ocr_enabled.get() and not self.running)
        self.export_text_button.configure(state=state)

        for button in self.ocr_language_buttons:
            button.configure(state=state)

    def _form(self) -> Form:
        return Form(
            url=self.url.get(),
            destination=self.destination.get(),
            mode=MODES[self.mode.get()],
            compact=self.compact.get(),
            ocr_enabled=self.ocr_enabled.get(),
            ocr_languages=tuple(code for code, variable in self.ocr_languages.items() if variable.get()),
            export_text=self.export_text.get(),
        )

    def _browse(self) -> None:
        folder = self.presenter.destination_folder
        selected = filedialog.asksaveasfilename(
            parent=self.root,
            title="Salvar PDF",
            initialdir=str(folder) if folder is not None else None,
            initialfile="documento.pdf",
            defaultextension=".pdf",
            filetypes=[("Arquivo PDF", "*.pdf")],
        )

        if selected:
            self.destination.set(selected)
            self.presenter.destination_chosen(self._form())

    def _start(self) -> None:
        self.presenter.start(self._form())

    def _close(self) -> None:
        self.presenter.close(self._form())

    def _poll(self) -> None:
        while True:
            try:
                callback = self.ui_calls.get_nowait()
            except queue.Empty:
                break

            callback()

        if self.presenter.can_destroy:
            self.root.destroy()
            return

        self.root.after(POLL_INTERVAL_MS, self._poll)


def main() -> None:
    root = tk.Tk()
    application = Application(root, build_converter())

    try:
        root.mainloop()
    finally:
        application.presenter.shutdown()


if __name__ == "__main__":
    main()
