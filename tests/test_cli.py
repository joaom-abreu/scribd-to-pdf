from pathlib import Path
from unittest.mock import Mock

import pytest

from scribd_to_pdf.application.conversion import CaptureMode, ConversionResult
from scribd_to_pdf.infrastructure.ocr import OcrError
from scribd_to_pdf.ui import cli as cli_module

URL = "https://www.scribd.com/document/123/livro"


@pytest.fixture
def convert(monkeypatch, tmp_path):
    result = ConversionResult(tmp_path / "livro.pdf")
    mock = Mock(return_value=result)
    monkeypatch.setattr(cli_module, "convert", mock)
    return mock


@pytest.fixture
def check_requirements(monkeypatch):
    mock = Mock()
    monkeypatch.setattr(cli_module, "check_requirements", mock)
    return mock


@pytest.mark.parametrize("mode", [[], ["--reuse"], ["--resume"]])
def test_missing_language_stops_before_conversion(convert, check_requirements, capsys, mode):
    check_requirements.side_effect = OcrError("Falta o modelo Francês (fra).")

    with pytest.raises(SystemExit) as error:
        cli_module.main([URL, *mode, "--ocr", "--ocr-language", "por+fra"])

    assert error.value.code == 1
    assert check_requirements.call_args.args[0].ocr_language == "por+fra"
    convert.assert_not_called()
    assert "fra" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments, mode",
    [([], CaptureMode.NEW), (["--resume"], CaptureMode.RESUME), (["--reuse"], CaptureMode.REUSE)],
)
def test_flags_select_capture_mode(convert, check_requirements, arguments, mode):
    cli_module.main([URL, *arguments])

    assert convert.call_args.args[0].mode is mode


@pytest.mark.parametrize("ocr, export_text", [(False, False), (True, False), (True, True)])
def test_builds_request_from_arguments(convert, check_requirements, capsys, tmp_path, ocr, export_text):
    output = tmp_path / "livro.pdf"
    text_path = output.with_suffix(".txt") if export_text else None
    convert.return_value = ConversionResult(output, text_path)
    arguments = [URL, "-o", str(output), "--ocr-language", "por+eng"]
    arguments += ["--ocr"] if ocr else []
    arguments += ["--export-text"] if export_text else []

    cli_module.main(arguments)

    request = convert.call_args.args[0]
    assert request.output_path == output
    assert request.ocr_language == ("por+eng" if ocr else None)
    assert request.export_text is export_text

    messages = capsys.readouterr().out
    assert f"PDF salvo em: {output}" in messages
    assert ("Texto salvo em:" in messages) is export_text


def test_default_output_uses_capture_folder(convert, check_requirements):
    cli_module.main([URL])

    assert convert.call_args.args[0].output_path == Path("output") / "123" / "123.pdf"


def test_export_requires_ocr_before_anything_runs(convert, check_requirements, capsys):
    with pytest.raises(SystemExit) as error:
        cli_module.main([URL, "--export-text"])

    assert error.value.code == 2
    assert "--export-text exige --ocr" in capsys.readouterr().err
    check_requirements.assert_not_called()
    convert.assert_not_called()


@pytest.mark.parametrize("arguments", [["https://example.com/document/1"], [URL, "-o", "livro.txt"]])
def test_invalid_input_exits_with_error(convert, check_requirements, capsys, arguments):
    with pytest.raises(SystemExit) as error:
        cli_module.main(arguments)

    assert error.value.code == 1
    assert capsys.readouterr().err.startswith("Erro:")
    convert.assert_not_called()


def test_keyboard_interrupt_exits_with_130(convert, check_requirements, capsys):
    convert.side_effect = KeyboardInterrupt

    with pytest.raises(SystemExit) as error:
        cli_module.main([URL])

    assert error.value.code == 130
    assert "interrompida" in capsys.readouterr().err
