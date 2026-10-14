import os
import shutil
import signal
import subprocess
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class OcrError(RuntimeError):
    pass


LANGUAGE_NAMES = {
    "por": "Português",
    "eng": "Inglês",
    "spa": "Espanhol",
    "fra": "Francês",
    "deu": "Alemão",
}


def _normalize_language(language: str) -> str:
    parts = [part.strip() for part in language.split("+")]

    if not all(parts):
        raise ValueError(
            "Informe um idioma válido, como por, eng, spa, fra, deu "
            "ou uma combinação como por+eng."
        )

    return "+".join(parts)


def _installed_languages() -> set[str]:
    executable = shutil.which("tesseract")

    if executable is None:
        raise OcrError(
            "O comando 'tesseract' não foi encontrado. "
            "Instale o Tesseract e os modelos dos idiomas escolhidos."
        )

    try:
        result = subprocess.run(
            [executable, "--list-langs"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except subprocess.TimeoutExpired as error:
        raise OcrError(
            "A consulta dos idiomas do Tesseract demorou mais de 5 segundos. "
            "Verifique a instalação com 'tesseract --list-langs'."
        ) from error
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        message = (
            f"Não foi possível consultar os idiomas do Tesseract "
            f"(código {error.returncode})."
        )

        if detail:
            message += f"\n{detail}"

        raise OcrError(message) from error
    except OSError as error:
        raise OcrError(
            "Não foi possível executar o Tesseract. "
            "Verifique a instalação com 'tesseract --list-langs'."
        ) from error

    return {
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.strip().startswith("List of available languages")
    }


def check_ocr_available(language: str = "por") -> str:
    language = _normalize_language(language)
    executable = shutil.which("ocrmypdf")
    if executable is None:
        raise OcrError(
            "O comando 'ocrmypdf' não foi encontrado. "
            "Instale OCRmyPDF e os idiomas do Tesseract; veja o README."
        )

    installed = _installed_languages()
    missing = sorted(set(language.split("+")) - installed)

    if missing:
        labels = [
            f"{LANGUAGE_NAMES[code]} ({code})"
            if code in LANGUAGE_NAMES
            else code
            for code in missing
        ]
        available = ", ".join(sorted(installed)) or "nenhum"

        raise OcrError(
            "Faltam modelos de idioma do Tesseract: "
            + ", ".join(labels)
            + f".\nIdiomas instalados: {available}.\n"
            "Instale os modelos indicados ou selecione somente idiomas instalados. "
            "Confira a instalação com 'tesseract --list-langs'."
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


def _publish_ocr_outputs(
        temporary_pdf: Path,
        pdf_path: Path,
        temporary_text: Path | None,
        should_cancel: Callable[[], bool] | None,
) -> None:
    if temporary_text is None:
        _check_cancelled(should_cancel)
        temporary_pdf.replace(pdf_path)
        return

    text_path = pdf_path.with_suffix(".txt")
    backup: Path | None = None

    try:
        if text_path.exists():
            with NamedTemporaryFile(
                dir=text_path.parent,
                prefix=f".{text_path.name}.",
                suffix=".bak",
                delete=False,
            ) as stream:
                backup = Path(stream.name)

            shutil.copy2(text_path, backup)

        _check_cancelled(should_cancel)
        temporary_text.replace(text_path)
    except BaseException:
        if backup is not None:
            backup.unlink(missing_ok=True)
        raise

    try:
        temporary_pdf.replace(pdf_path)
    except BaseException:
        try:
            if backup is not None:
                backup.replace(text_path)
            else:
                text_path.unlink(missing_ok=True)
        except OSError as error:
            if backup is not None:
                raise OcrError(
                    "O PDF anterior foi preservado, mas não foi possível "
                    "restaurar o TXT. O texto anterior está guardado em: "
                    f"{backup}"
                ) from error

            raise OcrError(
                "O PDF anterior foi preservado, mas não foi possível "
                f"remover o novo TXT: {text_path}"
            ) from error

        raise

    if backup is not None:
        try:
            backup.unlink(missing_ok=True)
        except OSError:
            # PDF e TXT já foram salvos; uma falha na limpeza do backup
            # não deve transformar o resultado completo em erro.
            pass


def add_ocr(
        pdf_path: Path,
        language: str = "por",
        *,
        should_cancel: Callable[[], bool] | None = None,
        export_text: bool = False,
) -> Path:
    _check_cancelled(should_cancel)
    language = _normalize_language(language)
    executable = check_ocr_available(language)

    pdf_path = pdf_path.resolve()

    with pdf_path.open("rb") as stream:
        original_page_count = len(PdfReader(stream).pages)

    with TemporaryDirectory(prefix="ocr-", dir=pdf_path.parent) as directory:
        temporary_path = Path(directory) / "searchable.pdf"
        temporary_text = Path(directory) / "recognized.txt" if export_text else None

        command = [
            executable,
            "--language", language,
            "--output-type", "pdf",
            "--optimize", "0",
        ]

        if temporary_text is not None:
            command.extend(["--sidecar", str(temporary_text)])

        command.extend([str(pdf_path), str(temporary_path)])

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

        if temporary_text is not None:
            try:
                with temporary_text.open("r", encoding="utf-8") as stream:
                    for _ in stream:
                        _check_cancelled(should_cancel)
            except InterruptedError:
                raise
            except (OSError, UnicodeError) as error:
                raise OcrError(
                    "O OCR não gerou um TXT válido. "
                    "O PDF e o TXT anteriores foram preservados."
                ) from error

        try:
            _publish_ocr_outputs(
                temporary_path, pdf_path, temporary_text, should_cancel,
            )
        except InterruptedError:
            raise
        except OSError as error:
            raise OcrError(
                "Não foi possível salvar o resultado do OCR. "
                "O PDF anterior foi preservado."
            ) from error

    return pdf_path
