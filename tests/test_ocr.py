import subprocess
from pathlib import Path

import pytest
from pypdf import PdfWriter

from scribd_to_pdf import ocr as ocr_module
from scribd_to_pdf.ocr import OcrError, add_ocr


def write_pdf(path: Path, pages: int) -> None:
    writer = PdfWriter()

    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)

    with path.open("wb") as stream:
        writer.write(stream)


@pytest.fixture
def pdf_path(tmp_path, monkeypatch):
    path = tmp_path / "document.pdf"
    write_pdf(path, pages=2)

    monkeypatch.setattr(
        ocr_module,
        "check_ocr_available",
        lambda: "ocrmypdf",
    )

    return path


def test_failed_ocr_preserves_pdf(pdf_path, monkeypatch):
    original = pdf_path.read_bytes()
    original_files = set(pdf_path.parent.iterdir())

    def fail(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial output")
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(ocr_module.subprocess, "run", fail)

    with pytest.raises(OcrError):
        add_ocr(pdf_path, language="eng")

    assert pdf_path.read_bytes() == original
    assert set(pdf_path.parent.iterdir()) == original_files


@pytest.mark.parametrize("invalid_result", ["corrupt", "missing_page"])
def test_invalid_ocr_result_preserves_pdf(
        pdf_path,
        monkeypatch,
        invalid_result,
):
    original = pdf_path.read_bytes()
    original_files = set(pdf_path.parent.iterdir())

    def invalid_output(command, **kwargs):
        output = Path(command[-1])

        if invalid_result == "corrupt":
            output.write_bytes(b"not a PDF")
        else:
            write_pdf(output, pages=1)

        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(ocr_module.subprocess, "run", invalid_output)

    with pytest.raises(OcrError):
        add_ocr(pdf_path, language="eng")

    assert pdf_path.read_bytes() == original
    assert set(pdf_path.parent.iterdir()) == original_files