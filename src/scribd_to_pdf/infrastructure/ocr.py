import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf.errors import PdfReadError

from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.infrastructure.files import DEFAULT_FILE_MODE
from scribd_to_pdf.infrastructure.pdf import count_pages


class OcrError(ConversionError):
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


def check_ocr_available() -> str:
    executable = shutil.which("ocrmypdf")

    if executable is None:
        raise OcrError(
            "O comando 'ocrmypdf' não foi encontrado. Instale o OCRmyPDF e os idiomas do Tesseract; veja o README."
        )

    return executable


def add_ocr(
    pdf_path: Path,
    language: str,
    *,
    text_path: Path | None = None,
) -> Path:
    executable = check_ocr_available()
    pdf_path = pdf_path.resolve()
    expected_pages = count_pages(pdf_path)

    with TemporaryDirectory(prefix="ocr-", dir=pdf_path.parent) as directory:
        outputs = _OcrOutputs(Path(directory), export_text=text_path is not None)
        command = _build_command(executable, language, pdf_path, outputs)

        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as error:
            raise OcrError(
                f"O OCR falhou (código {error.returncode}). O PDF anterior foi preservado. "
                "Confira as mensagens acima e os idiomas disponíveis com 'tesseract --list-langs'."
            ) from error

        _validate(outputs, expected_pages)

        try:
            _publish(outputs, pdf_path, text_path)
        except OSError as error:
            raise OcrError(
                "Não foi possível salvar o resultado do OCR. O PDF anterior foi preservado."
            ) from error

    return pdf_path


def _build_command(executable: str, language: str, source: Path, outputs: _OcrOutputs) -> list[str]:
    command = [executable, "--language", language, "--output-type", "pdf", "--optimize", "0"]

    if outputs.text is not None:
        command += ["--sidecar", str(outputs.text)]

    return [*command, str(source), str(outputs.pdf)]


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
    outputs.pdf.chmod(DEFAULT_FILE_MODE)

    if outputs.text is None or text_path is None:
        outputs.pdf.replace(pdf_path)
        return

    outputs.text.chmod(DEFAULT_FILE_MODE)
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
    def check_available(self) -> None:
        check_ocr_available()

    def recognize(self, pdf_path: Path, language: str, *, text_path: Path | None) -> None:
        try:
            add_ocr(pdf_path, language, text_path=text_path)
        except (OSError, PdfReadError) as error:
            raise OcrError(f"Não foi possível aplicar o OCR: {error}") from error
