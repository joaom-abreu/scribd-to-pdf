import shutil
import subprocess
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


def add_ocr(pdf_path: Path, language: str = "por") -> Path:
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
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as error:
            raise OcrError(
                f"O OCR falhou (código {error.returncode}). "
                "O PDF anterior foi preservado. Confira as mensagens acima "
                "e os idiomas disponíveis com 'tesseract --list-langs'."
            ) from error

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

        temporary_path.replace(pdf_path)

    return pdf_path