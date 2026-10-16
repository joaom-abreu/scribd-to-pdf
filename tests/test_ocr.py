import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from pypdf import PdfReader, PdfWriter

from scribd_to_pdf.infrastructure import ocr as ocr_module
from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.infrastructure.files import DEFAULT_FILE_MODE
from scribd_to_pdf.infrastructure.ocr import OcrError, OcrMyPdfRecognizer, add_ocr, check_ocr_available

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
        lambda language="por": "ocrmypdf",
    )

    return path


def finished_process(command: list[str], returncode: int = 0) -> subprocess.CompletedProcess:
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, command)

    return subprocess.CompletedProcess(command, returncode)


@pytest.fixture
def installed_tools(monkeypatch):
    monkeypatch.setattr(
        ocr_module.shutil,
        "which",
        lambda command: f"/tools/{command}",
    )
    result = subprocess.CompletedProcess(
        ["tesseract", "--list-langs"],
        0,
        stdout=(
            'List of available languages in "/tessdata/" (5):\n'
            "deu\neng\nfra\npor\nspa\n"
        ),
        stderr="",
    )
    run = Mock(return_value=result)
    monkeypatch.setattr(ocr_module.subprocess, "run", run)
    return run


@pytest.mark.parametrize("language", ["por+eng+spa+fra+deu", " por + eng "])
def test_accepts_installed_languages(language, installed_tools):
    assert check_ocr_available(language) == "/tools/ocrmypdf"
    assert installed_tools.call_args.args[0] == ["/tools/tesseract", "--list-langs"]


def test_reports_all_missing_languages(installed_tools):
    installed_tools.return_value.stdout = (
        'List of available languages in "/tessdata/" (2):\n'
        "eng\npor\n"
    )

    with pytest.raises(OcrError) as error:
        check_ocr_available("por+fra+deu")

    message = str(error.value)
    assert "Francês (fra)" in message
    assert "Alemão (deu)" in message
    assert "Português (por)" not in message
    assert "Idiomas instalados: eng, por" in message


def test_reports_unknown_language(installed_tools):
    with pytest.raises(OcrError, match="modelo_inexistente"):
        check_ocr_available("modelo_inexistente")


@pytest.mark.parametrize("language", ["", " ", "por+", "+eng", "por++eng"])
def test_rejects_invalid_language_before_running_tesseract(language, installed_tools):
    with pytest.raises(ValueError):
        check_ocr_available(language)

    installed_tools.assert_not_called()


@pytest.mark.parametrize("missing", ["ocrmypdf", "tesseract"])
def test_reports_missing_executable(missing, installed_tools, monkeypatch):
    monkeypatch.setattr(
        ocr_module.shutil,
        "which",
        lambda command: None if command == missing else f"/tools/{command}",
    )

    with pytest.raises(OcrError, match=missing):
        check_ocr_available("por")

    installed_tools.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.TimeoutExpired(["tesseract", "--list-langs"], 5),
        subprocess.CalledProcessError(
            1,
            ["tesseract", "--list-langs"],
            stderr="Falha ao acessar tessdata.",
        ),
        FileNotFoundError("Tesseract indisponível."),
    ],
    ids=["timeout", "comando-falhou", "executavel-removido"],
)
def test_reports_language_query_failure(failure, installed_tools):
    installed_tools.side_effect = failure

    with pytest.raises(OcrError, match="Tesseract"):
        check_ocr_available("por")


def test_reports_empty_language_list(installed_tools):
    installed_tools.return_value.stdout = (
        'List of available languages in "/tessdata/" (0):\n'
    )

    with pytest.raises(OcrError, match="Idiomas instalados: nenhum"):
        check_ocr_available("por")


def test_missing_language_preserves_pdf_and_skips_ocr(
        pdf_path,
        installed_tools,
        monkeypatch,
):
    original = pdf_path.read_bytes()
    original_files = set(pdf_path.parent.iterdir())
    installed_tools.return_value.stdout = (
        'List of available languages in "/tessdata/" (1):\npor\n'
    )
    monkeypatch.setattr(ocr_module, "check_ocr_available", check_ocr_available)

    with pytest.raises(OcrError, match="Francês"):
        add_ocr(pdf_path, language="por+fra")

    assert installed_tools.call_count == 1
    assert pdf_path.read_bytes() == original
    assert set(pdf_path.parent.iterdir()) == original_files


def test_failed_ocr_preserves_pdf(pdf_path, monkeypatch):
    original = pdf_path.read_bytes()
    original_files = set(pdf_path.parent.iterdir())

    def fail(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial output")
        return finished_process(command, 1)

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

        return finished_process(command)

    monkeypatch.setattr(ocr_module.subprocess, "run", invalid_output)

    with pytest.raises(OcrError):
        add_ocr(pdf_path, language="eng")

    assert pdf_path.read_bytes() == original
    assert set(pdf_path.parent.iterdir()) == original_files


def test_successful_ocr_replaces_pdf(pdf_path, monkeypatch):
    original = pdf_path.read_bytes()
    original_files = set(pdf_path.parent.iterdir())

    def success(command, **kwargs):
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.add_blank_page(width=200, height=200)
        writer.add_metadata({"/Title": "OCR concluído"})

        with Path(command[-1]).open("wb") as stream:
            writer.write(stream)

        return finished_process(command)

    monkeypatch.setattr(ocr_module.subprocess, "run", success)

    result = add_ocr(pdf_path, language="por+eng")

    assert result == pdf_path.resolve()
    assert pdf_path.read_bytes() != original
    assert PdfReader(pdf_path).metadata.title == "OCR concluído"
    assert set(pdf_path.parent.iterdir()) == original_files


@pytest.mark.parametrize("export_text", [False, True])
def test_interrupted_ocr_preserves_previous_files(pdf_path, monkeypatch, export_text):
    text_path = pdf_path.with_suffix(".txt")
    text_path.write_text("Texto anterior.", encoding="utf-8")
    original = pdf_path.read_bytes()
    original_files = set(pdf_path.parent.iterdir())

    def interrupt(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial output")
        raise KeyboardInterrupt

    monkeypatch.setattr(ocr_module.subprocess, "run", interrupt)

    with pytest.raises(KeyboardInterrupt):
        add_ocr(pdf_path, text_path=text_path if export_text else None)

    assert pdf_path.read_bytes() == original
    assert text_path.read_text(encoding="utf-8") == "Texto anterior."
    assert set(pdf_path.parent.iterdir()) == original_files


def simulate_export(command, text: str = "Texto reconhecido."):
    write_pdf(Path(command[-1]), pages=2)
    text_path = Path(command[command.index("--sidecar") + 1])
    text_path.write_text(text, encoding="utf-8")
    return finished_process(command)


@pytest.mark.parametrize(
    "previous, recognized",
    [(None, "Ação, francês e português.\n\fPágina 2."), ("Texto antigo.", "Texto novo."), (None, "")],
)
def test_export_saves_txt_next_to_pdf(pdf_path, monkeypatch, previous, recognized):
    text_path = pdf_path.with_suffix(".txt")

    if previous is not None:
        text_path.write_text(previous, encoding="utf-8")

    monkeypatch.setattr(
        ocr_module.subprocess, "run",
        lambda command, **kwargs: simulate_export(command, recognized),
    )

    assert add_ocr(pdf_path, text_path=text_path) == pdf_path.resolve()
    assert text_path.read_text(encoding="utf-8") == recognized
    assert len(PdfReader(pdf_path).pages) == 2
    assert set(pdf_path.parent.iterdir()) == {pdf_path, text_path}


@pytest.mark.parametrize(
    "failure",
    ["missing_text", "invalid_encoding", "failed", "corrupt_pdf", "missing_page"],
)
def test_invalid_export_preserves_previous_files(pdf_path, monkeypatch, failure):
    text_path = pdf_path.with_suffix(".txt")
    text_path.write_text("Texto anterior.", encoding="utf-8")
    original_pdf = pdf_path.read_bytes()
    original_text = text_path.read_bytes()
    original_files = set(pdf_path.parent.iterdir())

    def start(command, **kwargs):
        simulate_export(command)
        temporary_text = Path(command[command.index("--sidecar") + 1])

        if failure == "missing_text":
            temporary_text.unlink()
        elif failure == "invalid_encoding":
            temporary_text.write_bytes(b"\xff")
        elif failure == "corrupt_pdf":
            Path(command[-1]).write_bytes(b"not a PDF")
        elif failure == "missing_page":
            write_pdf(Path(command[-1]), pages=1)

        return finished_process(command, 1 if failure == "failed" else 0)

    monkeypatch.setattr(ocr_module.subprocess, "run", start)

    with pytest.raises(OcrError):
        add_ocr(pdf_path, text_path=text_path)

    assert pdf_path.read_bytes() == original_pdf
    assert text_path.read_bytes() == original_text
    assert set(pdf_path.parent.iterdir()) == original_files


@pytest.mark.parametrize("previous_text", [False, True])
@pytest.mark.parametrize("failed_output", ["recognized.txt", "searchable.pdf"])
def test_publish_failure_restores_previous_files(
        pdf_path, monkeypatch, previous_text, failed_output,
):
    text_path = pdf_path.with_suffix(".txt")

    if previous_text:
        text_path.write_text("Texto anterior.", encoding="utf-8")

    original_pdf = pdf_path.read_bytes()
    original_files = set(pdf_path.parent.iterdir())
    real_replace = Path.replace

    def fail_replace(path, target):
        if path.name == failed_output:
            raise PermissionError("Falha simulada ao salvar.")

        return real_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_replace)
    monkeypatch.setattr(
        ocr_module.subprocess, "run",
        lambda command, **kwargs: simulate_export(command),
    )

    with pytest.raises(OcrError):
        add_ocr(pdf_path, text_path=text_path)

    assert pdf_path.read_bytes() == original_pdf
    assert set(pdf_path.parent.iterdir()) == original_files

    if previous_text:
        assert text_path.read_text(encoding="utf-8") == "Texto anterior."


def test_disabled_export_keeps_existing_text(pdf_path, monkeypatch):
    text_path = pdf_path.with_suffix(".txt")
    text_path.write_text("Texto editado pelo usuário.", encoding="utf-8")

    def start(command, **kwargs):
        assert "--sidecar" not in command
        write_pdf(Path(command[-1]), pages=2)
        return finished_process(command)

    monkeypatch.setattr(ocr_module.subprocess, "run", start)

    add_ocr(pdf_path)

    assert text_path.read_text(encoding="utf-8") == "Texto editado pelo usuário."
    assert set(pdf_path.parent.iterdir()) == {pdf_path, text_path}


def test_recognizer_reports_unreadable_pdf_as_conversion_error(pdf_path):
    pdf_path.unlink()

    with pytest.raises(ConversionError, match="OCR"):
        OcrMyPdfRecognizer().recognize(pdf_path, "por", text_path=None)


@pytest.mark.skipif(sys.platform == "win32", reason="Permissões POSIX.")
def test_ocr_outputs_follow_the_umask(pdf_path, monkeypatch):
    text_path = pdf_path.with_suffix(".txt")

    def private_outputs(command, **kwargs):
        simulate_export(command)
        Path(command[-1]).chmod(0o600)
        Path(command[command.index("--sidecar") + 1]).chmod(0o600)
        return finished_process(command)

    monkeypatch.setattr(ocr_module.subprocess, "run", private_outputs)

    add_ocr(pdf_path, text_path=text_path)

    assert stat.S_IMODE(pdf_path.stat().st_mode) == DEFAULT_FILE_MODE
    assert stat.S_IMODE(text_path.stat().st_mode) == DEFAULT_FILE_MODE
