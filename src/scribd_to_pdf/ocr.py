import os
import shutil
import signal
import subprocess
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class OcrError(RuntimeError):
    pass


def check_ocr_available() -> str:
    executable = shutil.which("ocrmypdf")
    if executable is None:
        raise OcrError(
            "O comando 'ocrmypdf' não foi encontrado. "
            "Instale OCRmyPDF e os idiomas do Tesseract; veja o README."
        )
    return executable


def _check_cancelled(should_cancel: Callable[[], bool] | None) -> None:
    if should_cancel is not None and should_cancel():
        raise InterruptedError(
            "OCR interrompido. O PDF com as imagens foi preservado."
        )


def _stop_ocr(process: subprocess.Popen) -> None:
    if os.name == "posix":
        # OCRmyPDF inicia outros processos, como o Tesseract.
        # A sessão própria permite encerrar todo o grupo.
        def signal_group(value: int) -> None:
            try:
                os.killpg(process.pid, value)
            except ProcessLookupError:
                pass

        signal_group(signal.SIGTERM)

        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        finally:
            # Encerra também filhos que não responderam ao SIGTERM,
            # mesmo que o processo principal já tenha terminado.
            signal_group(signal.SIGKILL)

        process.wait()
        return

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    if process.poll() is None:
        process.terminate()

    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _run_ocr(
        command: list[str],
        should_cancel: Callable[[], bool] | None,
) -> None:
    _check_cancelled(should_cancel)
    process = subprocess.Popen(
        command,
        start_new_session=os.name == "posix",
    )

    try:
        while True:
            _check_cancelled(should_cancel)

            try:
                returncode = process.wait(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue

        _check_cancelled(should_cancel)
    except BaseException:
        _stop_ocr(process)
        raise

    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, command)


def add_ocr(
        pdf_path: Path,
        language: str = "por",
        *,
        should_cancel: Callable[[], bool] | None = None,
) -> Path:
    _check_cancelled(should_cancel)
    executable = check_ocr_available()
    language = language.strip()

    if not language or any(not part.strip() for part in language.split("+")):
        raise ValueError(
            "Informe um idioma válido, como por, eng, spa, fra, deu "
            "ou uma combinação como por+eng."
        )

    pdf_path = pdf_path.resolve()

    with pdf_path.open("rb") as stream:
        original_page_count = len(PdfReader(stream).pages)

    with TemporaryDirectory(prefix="ocr-", dir=pdf_path.parent) as directory:
        temporary_path = Path(directory) / "searchable.pdf"

        command = [
            executable,
            "--language", language,
            "--output-type", "pdf",
            "--optimize", "0",
            str(pdf_path),
            str(temporary_path),
        ]

        try:
            _run_ocr(command, should_cancel)
        except subprocess.CalledProcessError as error:
            raise OcrError(
                f"O OCR falhou (código {error.returncode}). "
                "O PDF anterior foi preservado. Confira as mensagens acima "
                "e os idiomas disponíveis com 'tesseract --list-langs'."
            ) from error

        _check_cancelled(should_cancel)

        try:
            with temporary_path.open("rb") as stream:
                page_count = len(PdfReader(stream).pages)
        except (OSError, PdfReadError) as error:
            raise OcrError(
                "O OCR não gerou um PDF válido. O PDF anterior foi preservado."
            ) from error

        if page_count != original_page_count:
            raise OcrError(
                "A quantidade de páginas mudou durante o OCR. "
                "O PDF anterior foi preservado."
            )

        _check_cancelled(should_cancel)
        temporary_path.replace(pdf_path)

    return pdf_path
