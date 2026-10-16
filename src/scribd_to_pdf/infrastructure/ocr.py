import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from scribd_to_pdf.application.conversion import ConversionError


class OcrError(ConversionError):
    pass


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

    with TemporaryDirectory(prefix="ocr-", dir=pdf_path.parent) as directory:
        searchable_pdf = Path(directory) / "searchable.pdf"
        recognized_text = Path(directory) / "recognized.txt"
        text_target = recognized_text if text_path is not None else None
        command = _build_command(executable, language, pdf_path, searchable_pdf, text_target)

        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as error:
            raise OcrError(
                f"O OCR falhou (código {error.returncode}). O PDF anterior foi preservado. "
                "Confira as mensagens acima e os idiomas disponíveis com 'tesseract --list-langs'."
            ) from error

        searchable_pdf.replace(pdf_path)

        if text_path is not None:
            recognized_text.replace(text_path)

    return pdf_path


def _build_command(
    executable: str,
    language: str,
    source: Path,
    target: Path,
    text_target: Path | None,
) -> list[str]:
    command = [executable, "--language", language, "--output-type", "pdf", "--optimize", "0"]

    if text_target is not None:
        command += ["--sidecar", str(text_target)]

    return [*command, str(source), str(target)]


class OcrMyPdfRecognizer:
    def check_available(self) -> None:
        check_ocr_available()

    def recognize(self, pdf_path: Path, language: str, *, text_path: Path | None) -> None:
        try:
            add_ocr(pdf_path, language, text_path=text_path)
        except OSError as error:
            raise OcrError(f"Não foi possível aplicar o OCR: {error}") from error
