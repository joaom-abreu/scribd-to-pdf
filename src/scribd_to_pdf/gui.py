import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from tkinter import font as tkfont

from scribd_to_pdf.browser import inspect_document
from scribd_to_pdf.cache import load_capture
from scribd_to_pdf.models import Document
from scribd_to_pdf.pdf import create_pdf
from scribd_to_pdf.scribd import parse_document_url


MODES = ("Nova captura", "Retomar captura", "Usar captura completa")


class Application:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.ready_event = threading.Event()
        self.cancel_event = threading.Event()
        self.running = False
        self.closing = False

        root.title("Scribd to PDF")
        width = min(1100, root.winfo_screenwidth() - 80)
        height = min(740, root.winfo_screenheight() - 100)
        root.geometry(f"{width}x{height}")
        root.minsize(min(width, 900), min(height, 600))
        root.protocol("WM_DELETE_WINDOW", self._close)

        self.ui_font = tkfont.Font(
            root=root,
            family="DejaVu Sans",
            size=-28,
        )
        self.log_font = tkfont.Font(
            root=root,
            family="DejaVu Sans Mono",
            size=-24,
        )

        style = ttk.Style(root)
        style.configure(
            "App.TButton",
            font=self.ui_font,
            padding=(16, 10),
        )
        style.configure("App.TEntry", padding=(10, 8))
        style.configure(
            "App.TCombobox",
            padding=(10, 8),
            arrowsize=26,
        )
        root.option_add("*TCombobox*Listbox.font", self.ui_font)

        self.url = tk.StringVar()
        self.destination = tk.StringVar()
        self.mode = tk.StringVar(value=MODES[0])

        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Link do documento",
            font=self.ui_font,
        ).pack(anchor="w")

        self.url_entry = ttk.Entry(
            frame,
            textvariable=self.url,
            font=self.ui_font,
            style="App.TEntry",
        )
        self.url_entry.pack(fill="x", pady=(8, 16))

        ttk.Label(
            frame,
            text="Destino do PDF (vazio usa output/ID/ID.pdf)",
            font=self.ui_font,
        ).pack(anchor="w")

        destination_row = ttk.Frame(frame)
        destination_row.pack(fill="x", pady=(8, 16))
        self.destination_entry = ttk.Entry(
            destination_row,
            textvariable=self.destination,
            font=self.ui_font,
            style="App.TEntry",
        )
        self.destination_entry.pack(side="left", fill="x", expand=True)

        self.browse_button = ttk.Button(
            destination_row,
            text="Escolher...",
            command=self._browse,
            style="App.TButton",
        )
        self.browse_button.pack(side="left", padx=(12, 0))

        ttk.Label(
            frame,
            text="Modo",
            font=self.ui_font,
        ).pack(anchor="w")

        self.mode_box = ttk.Combobox(
            frame,
            textvariable=self.mode,
            values=MODES,
            state="readonly",
            font=self.ui_font,
            style="App.TCombobox",
        )
        self.mode_box.pack(fill="x", pady=(8, 16))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(0, 16))

        self.start_button = ttk.Button(
            buttons,
            text="Iniciar",
            command=self._start,
            style="App.TButton",
        )
        self.start_button.pack(side="left")

        self.ready_button = ttk.Button(
            buttons,
            text="Capturar páginas",
            command=self._continue,
            state="disabled",
            style="App.TButton",
        )
        self.ready_button.pack(side="left", padx=12)

        self.cancel_button = ttk.Button(
            buttons,
            text="Interromper",
            command=self._cancel,
            state="disabled",
            style="App.TButton",
        )
        self.cancel_button.pack(side="left")

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

        self._log("Cole o link, escolha o modo e clique em Iniciar.")
        self.url_entry.focus_set()
        root.after(100, self._poll)

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_running(self, running: bool) -> None:
        self.running = running
        state = "disabled" if running else "normal"

        for widget in (
                self.url_entry,
                self.destination_entry,
                self.browse_button,
                self.start_button,
        ):
            widget.configure(state=state)

        self.mode_box.configure(
            state="disabled" if running else "readonly"
        )
        self.ready_button.configure(state="disabled")
        self.cancel_button.configure(
            state="normal" if running else "disabled"
        )

    def _browse(self) -> None:
        selected = filedialog.asksaveasfilename(
            parent=self.root,
            title="Salvar PDF",
            initialfile="documento.pdf",
            defaultextension=".pdf",
            filetypes=[("Arquivo PDF", "*.pdf")],
        )
        if selected:
            self.destination.set(selected)

    def _start(self) -> None:
        if self.running:
            return

        try:
            document = parse_document_url(self.url.get())
            destination = self.destination.get().strip()
            output_path = (
                Path(destination).expanduser()
                if destination
                else Path("output")
                     / document.document_id
                     / f"{document.document_id}.pdf"
            )

            if output_path.suffix.lower() != ".pdf":
                raise ValueError(
                    "O destino deve ser um arquivo com extensão .pdf."
                )
        except (ValueError, OSError, RuntimeError) as error:
            messagebox.showerror(
                "Dados inválidos",
                str(error),
                parent=self.root,
            )
            return

        mode = self.mode.get()
        self.ready_event.clear()
        self.cancel_event.clear()
        self._set_running(True)
        self._log(f"\nDocumento: {document.document_id}")
        self._log(f"Destino: {output_path}")

        threading.Thread(
            target=self._convert,
            args=(document, output_path, mode),
            daemon=False,
        ).start()

    def _continue(self) -> None:
        self.ready_button.configure(state="disabled")
        self.ready_event.set()

    def _cancel(self) -> None:
        if self.running:
            self.cancel_event.set()
            self.ready_event.set()
            self.ready_button.configure(state="disabled")
            self.cancel_button.configure(state="disabled")
            self._log("Interrompendo após a operação em andamento...")

    def _close(self) -> None:
        if self.running:
            self.closing = True
            self._cancel()
        else:
            self.root.destroy()

    def _status(self, text: str) -> None:
        self.events.put(("status", text))

    def _check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise InterruptedError("Conversão interrompida.")

    def _wait_for_ready(self) -> None:
        self.events.put((
            "ready",
            "No navegador, aguarde a capa e feche o aviso de privacidade.\n"
            "Depois, clique em Capturar páginas nesta janela.",
        ))
        self.ready_event.wait()
        self._check_cancelled()

    def _convert(
            self,
            document: Document,
            output_path: Path,
            mode: str,
    ) -> None:
        try:
            self._check_cancelled()

            if mode == MODES[2]:
                folder = Path("output") / document.document_id
                image_paths = load_capture(document, folder)
                self._status(
                    f"Reutilizando {len(image_paths)} páginas salvas."
                )
            else:
                image_paths = inspect_document(
                    document,
                    resume=mode == MODES[1],
                    on_status=self._status,
                    wait_for_ready=self._wait_for_ready,
                    should_cancel=self.cancel_event.is_set,
                )

            self._check_cancelled()
            self.events.put(("pdf", "Gerando PDF..."))
            pdf_path = create_pdf(image_paths, output_path)
            self.events.put(("done", str(pdf_path.resolve())))
        except InterruptedError:
            self.events.put(("cancelled", "Conversão interrompida."))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _poll(self) -> None:
        while True:
            try:
                kind, text = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "status":
                self._log(text)
            elif kind == "ready":
                if not self.cancel_event.is_set():
                    self._log(text)
                    self.ready_button.configure(state="normal")
            elif kind == "pdf":
                self._log(text)
                self.cancel_button.configure(state="disabled")
            else:
                self._set_running(False)

                if kind == "done":
                    self._log(f"PDF salvo em: {text}")
                elif kind == "cancelled":
                    self._log(text)
                    self._log("Para continuar, escolha Retomar captura.")
                elif kind == "error":
                    self._log(f"Falha: {text}")
                    if not self.closing:
                        messagebox.showerror(
                            "Falha na conversão",
                            text,
                            parent=self.root,
                        )

        if self.closing and not self.running:
            self.root.destroy()
            return

        self.root.after(100, self._poll)


def main() -> None:
    root = tk.Tk()
    application = Application(root)
    try:
        root.mainloop()
    finally:
        application.cancel_event.set()
        application.ready_event.set()


if __name__ == "__main__":
    main()