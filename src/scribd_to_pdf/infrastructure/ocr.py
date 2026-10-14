import os
import shutil
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf.errors import PdfReadError

from scribd_to_pdf.domain.cancellation import ShouldCancel, never_cancel, raise_if_cancelled
from scribd_to_pdf.domain.languages import DEFAULT_LANGUAGE, describe_language, normalize_languages
from scribd_to_pdf.infrastructure.pdf import count_pages

OCR_INTERRUPTED = "OCR interrompido. O PDF com as imagens foi preservado."
LIST_LANGUAGES_TIMEOUT_SECONDS = 5
POLL_INTERVAL_SECONDS = 0.2
STOP_TIMEOUT_SECONDS = 3
LANGUAGE_LIST_HEADER = "List of available languages"


class OcrError(RuntimeError):
    pass


@dataclass(frozen=True)
class _OcrOutputs:
    directory: Path
    export_text: bool

    @property
    def pdf(self) -> Path:
        return self.directory / "searchable.pdf"

    @property
    def text(self) -> Path | None:
        return self.directory / "recognized.txt" if self.export_text else None

    @property
    def previous_text(self) -> Path:
        return self.directory / "previous.txt"


def check_ocr_available(language: str = DEFAULT_LANGUAGE) -> str:
    codes = set(normalize_languages(language).split("+"))
    executable = _find_executable("ocrmypdf", "Instale OCRmyPDF e os idiomas do Tesseract; veja o README.")
    installed = _installed_languages()
    missing = sorted(codes - installed)

    if missing:
        raise OcrError(
            "Faltam modelos de idioma do Tesseract: "
            + ", ".join(describe_language(code) for code in missing)
            + f".\nIdiomas instalados: {', '.join(sorted(installed)) or 'nenhum'}.\n"
            "Instale os modelos indicados ou selecione somente idiomas instalados. "
            "Confira a instalação com 'tesseract --list-langs'."
        )

    return executable


def add_ocr(
    pdf_path: Path,
    language: str = DEFAULT_LANGUAGE,
    *,
    text_path: Path | None = None,
    should_cancel: ShouldCancel = never_cancel,
) -> Path:
    raise_if_cancelled(should_cancel, OCR_INTERRUPTED)
    executable = check_ocr_available(language)
    pdf_path = pdf_path.resolve()
    expected_pages = count_pages(pdf_path)

    with TemporaryDirectory(prefix="ocr-", dir=pdf_path.parent) as directory:
        outputs = _OcrOutputs(Path(directory), export_text=text_path is not None)
        command = _build_command(executable, normalize_languages(language), pdf_path, outputs)

        _run(command, should_cancel)
        _validate(outputs, expected_pages)
        raise_if_cancelled(should_cancel, OCR_INTERRUPTED)

        try:
            _publish(outputs, pdf_path, text_path)
        except OSError as error:
            raise OcrError(
                "Não foi possível salvar o resultado do OCR. O PDF anterior foi preservado."
            ) from error

    return pdf_path


def _find_executable(command: str, hint: str) -> str:
    executable = shutil.which(command)

    if executable is None:
        raise OcrError(f"O comando '{command}' não foi encontrado. {hint}")

    return executable


def _installed_languages() -> set[str]:
    executable = _find_executable("tesseract", "Instale o Tesseract e os modelos dos idiomas escolhidos.")
    check_installation = "Verifique a instalação com 'tesseract --list-langs'."

    try:
        result = subprocess.run(
            [executable, "--list-langs"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=LIST_LANGUAGES_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise OcrError(f"A consulta dos idiomas do Tesseract demorou demais. {check_installation}") from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        raise OcrError(
            f"Não foi possível consultar os idiomas do Tesseract (código {error.returncode}).\n{detail}".strip()
        ) from error
    except OSError as error:
        raise OcrError(f"Não foi possível executar o Tesseract. {check_installation}") from error

    lines = (line.strip() for line in result.stdout.splitlines())
    return {line for line in lines if line and not line.startswith(LANGUAGE_LIST_HEADER)}


def _build_command(executable: str, language: str, source: Path, outputs: _OcrOutputs) -> list[str]:
    command = [executable, "--language", language, "--output-type", "pdf", "--optimize", "0"]

    if outputs.text is not None:
        command += ["--sidecar", str(outputs.text)]

    return [*command, str(source), str(outputs.pdf)]


def _run(command: list[str], should_cancel: ShouldCancel) -> None:
    raise_if_cancelled(should_cancel, OCR_INTERRUPTED)
    process = subprocess.Popen(command, start_new_session=os.name == "posix")

    try:
        returncode = _wait(process, should_cancel)
    except BaseException:
        _stop(process)
        raise

    if returncode != 0:
        raise OcrError(
            f"O OCR falhou (código {returncode}). O PDF anterior foi preservado. "
            "Confira as mensagens acima e os idiomas disponíveis com 'tesseract --list-langs'."
        )


def _wait(process: subprocess.Popen, should_cancel: ShouldCancel) -> int:
    while True:
        raise_if_cancelled(should_cancel, OCR_INTERRUPTED)

        try:
            return process.wait(timeout=POLL_INTERVAL_SECONDS)
        except subprocess.TimeoutExpired:
            pass


def _stop(process: subprocess.Popen) -> None:
    if os.name == "posix":
        _stop_process_group(process)
    else:
        _stop_process_tree(process)


def _stop_process_group(process: subprocess.Popen) -> None:
    _signal_group(process, signal.SIGTERM)

    try:
        process.wait(timeout=STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    finally:
        _signal_group(process, signal.SIGKILL)

    process.wait()


def _signal_group(process: subprocess.Popen, signal_number: int) -> None:
    try:
        os.killpg(process.pid, signal_number)
    except ProcessLookupError:
        pass


def _stop_process_tree(process: subprocess.Popen) -> None:
    try:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=STOP_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass

    if process.poll() is None:
        process.kill()

    process.wait()


def _validate(outputs: _OcrOutputs, expected_pages: int) -> None:
    try:
        page_count = count_pages(outputs.pdf)
    except (OSError, PdfReadError) as error:
        raise OcrError("O OCR não gerou um PDF válido. O PDF anterior foi preservado.") from error

    if page_count != expected_pages:
        raise OcrError("A quantidade de páginas mudou durante o OCR. O PDF anterior foi preservado.")

    if outputs.text is None:
        return

    try:
        outputs.text.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise OcrError(
            "O OCR não gerou um TXT válido. O PDF e o TXT anteriores foram preservados."
        ) from error


def _publish(outputs: _OcrOutputs, pdf_path: Path, text_path: Path | None) -> None:
    if outputs.text is None or text_path is None:
        outputs.pdf.replace(pdf_path)
        return

    had_text = text_path.exists()

    if had_text:
        shutil.copy2(text_path, outputs.previous_text)

    outputs.text.replace(text_path)

    try:
        outputs.pdf.replace(pdf_path)
    except OSError:
        if had_text:
            outputs.previous_text.replace(text_path)
        else:
            text_path.unlink(missing_ok=True)
        raise


class OcrMyPdfRecognizer:
    def check_available(self, language: str) -> None:
        check_ocr_available(language)

    def recognize(
        self,
        pdf_path: Path,
        language: str,
        *,
        text_path: Path | None,
        should_cancel: ShouldCancel,
    ) -> None:
        add_ocr(pdf_path, language, text_path=text_path, should_cancel=should_cancel)
