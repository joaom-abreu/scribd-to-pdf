import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfReader, PdfWriter

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


def finished_process(returncode: int = 0):
    return SimpleNamespace(wait=lambda timeout=None: returncode)


def test_failed_ocr_preserves_pdf(pdf_path, monkeypatch):
    original = pdf_path.read_bytes()
    original_files = set(pdf_path.parent.iterdir())

    def fail(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial output")
        return finished_process(1)

    monkeypatch.setattr(ocr_module.subprocess, "Popen", fail)

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

        return finished_process()

    monkeypatch.setattr(ocr_module.subprocess, "Popen", invalid_output)

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

        return finished_process()

    monkeypatch.setattr(ocr_module.subprocess, "Popen", success)

    result = add_ocr(pdf_path, language="por+eng")

    assert result == pdf_path.resolve()
    assert pdf_path.read_bytes() != original
    assert PdfReader(pdf_path).metadata.title == "OCR concluído"
    assert set(pdf_path.parent.iterdir()) == original_files


def test_cancel_before_start_preserves_pdf(pdf_path, monkeypatch):
    original = pdf_path.read_bytes()
    original_files = set(pdf_path.parent.iterdir())

    def unexpected_start(*args, **kwargs):
        pytest.fail("O OCR não deveria iniciar após o cancelamento.")

    monkeypatch.setattr(ocr_module.subprocess, "Popen", unexpected_start)

    with pytest.raises(InterruptedError, match="preservado"):
        add_ocr(pdf_path, should_cancel=lambda: True)

    assert pdf_path.read_bytes() == original
    assert set(pdf_path.parent.iterdir()) == original_files


def test_cancel_before_replacement_preserves_pdf(pdf_path, monkeypatch):
    original = pdf_path.read_bytes()
    original_files = set(pdf_path.parent.iterdir())
    cancelled = threading.Event()
    real_reader = ocr_module.PdfReader

    def success(command, **kwargs):
        write_pdf(Path(command[-1]), pages=2)
        return finished_process()

    def read_and_cancel(stream):
        reader = real_reader(stream)

        if Path(stream.name).name == "searchable.pdf":
            cancelled.set()

        return reader

    monkeypatch.setattr(ocr_module.subprocess, "Popen", success)
    monkeypatch.setattr(ocr_module, "PdfReader", read_and_cancel)

    with pytest.raises(InterruptedError, match="preservado"):
        add_ocr(pdf_path, should_cancel=cancelled.is_set)

    assert pdf_path.read_bytes() == original
    assert set(pdf_path.parent.iterdir()) == original_files


@pytest.mark.parametrize("interrupt", [InterruptedError, KeyboardInterrupt])
def test_interrupt_stops_running_process_and_preserves_pdf(
        pdf_path,
        monkeypatch,
        interrupt,
):
    original = pdf_path.read_bytes()
    marker = pdf_path.parent / "started.txt"
    processes = []
    real_popen = subprocess.Popen
    deadline = time.monotonic() + 10
    script = textwrap.dedent("""
        import sys
        import time
        from pathlib import Path

        Path(sys.argv[1]).write_bytes(b"partial output")
        Path(sys.argv[2]).write_text("started")
        time.sleep(30)
    """)

    def start(command, **kwargs):
        if command[0] != "ocrmypdf":
            return real_popen(command, **kwargs)

        process = real_popen(
            [sys.executable, "-c", script, command[-1], str(marker)],
            **kwargs,
        )
        processes.append(process)
        return process

    def should_cancel():
        if marker.exists() or time.monotonic() >= deadline:
            if interrupt is KeyboardInterrupt:
                raise KeyboardInterrupt

            return True

        return False

    monkeypatch.setattr(ocr_module.subprocess, "Popen", start)

    with pytest.raises(interrupt):
        add_ocr(pdf_path, should_cancel=should_cancel)

    assert marker.exists(), "O processo de teste não chegou a iniciar."
    assert processes[0].poll() is not None
    assert pdf_path.read_bytes() == original
    assert not list(pdf_path.parent.glob("ocr-*"))


@pytest.mark.skipif(sys.platform != "linux", reason="Verifica processos no Linux.")
def test_cancel_stops_child_even_if_parent_exits_first(pdf_path, monkeypatch):
    original = pdf_path.read_bytes()
    marker = pdf_path.parent / "child.pid"
    real_popen = subprocess.Popen
    deadline = time.monotonic() + 10
    child_script = textwrap.dedent("""
        import os
        import signal
        import sys
        import time
        from pathlib import Path

        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        marker = Path(sys.argv[1])
        temporary_marker = marker.with_suffix(".tmp")
        temporary_marker.write_text(str(os.getpid()))
        temporary_marker.replace(marker)
        time.sleep(30)
    """)
    parent_script = textwrap.dedent("""
        import subprocess
        import sys
        import time
        from pathlib import Path

        subprocess.Popen([sys.executable, "-c", sys.argv[3], sys.argv[2]])
        Path(sys.argv[1]).write_bytes(b"partial output")
        time.sleep(30)
    """)

    def start(command, **kwargs):
        return real_popen(
            [
                sys.executable, "-c", parent_script,
                command[-1], str(marker), child_script,
            ],
            **kwargs,
        )

    monkeypatch.setattr(ocr_module.subprocess, "Popen", start)

    with pytest.raises(InterruptedError):
        add_ocr(
            pdf_path,
            should_cancel=lambda: marker.exists() or time.monotonic() >= deadline,
        )

    assert marker.exists(), "O processo filho não chegou a iniciar."
    child_pid = int(marker.read_text())
    stat = Path(f"/proc/{child_pid}/stat")
    stop_deadline = time.monotonic() + 3

    try:
        while True:
            try:
                data = stat.read_text()
            except (FileNotFoundError, ProcessLookupError):
                break

            state = data.rsplit(") ", 1)[1].split()[0]

            # Z e X já encerraram a execução. O sistema também pode
            # coletar o processo e remover /proc antes da leitura.
            if state in {"Z", "X"}:
                break

            if time.monotonic() >= stop_deadline:
                pytest.fail(
                    f"O processo filho {child_pid} não encerrou em 3 segundos. "
                    f"Último estado: {state}."
                )

            # Enviar SIGKILL não garante que o filho já terminou
            # quando o processo principal retorna.
            time.sleep(0.02)
    finally:
        # Evita deixar o processo de teste ativo se houver uma regressão.
        try:
            os.kill(child_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    assert pdf_path.read_bytes() == original
    assert not list(pdf_path.parent.glob("ocr-*"))
