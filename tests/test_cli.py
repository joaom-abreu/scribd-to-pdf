from functools import partial
from pathlib import Path
from unittest.mock import Mock

import pytest

from scribd_to_pdf.application.conversion import CaptureMode, ConversionResult, DocumentConverter
from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.infrastructure.storage import FileCaptureRepository
from scribd_to_pdf.ui import cli as cli_module

URL = "https://www.scribd.com/document/123/livro"


@pytest.fixture
def converter(tmp_path):
    real = DocumentConverter(FileCaptureRepository(tmp_path / "capturas"), Mock(), Mock(), Mock(), tmp_path / "pdfs")
    mock = Mock(wraps=real)
    mock.convert.return_value = ConversionResult(tmp_path / "livro.pdf")
    return mock


@pytest.fixture
def converter_factory(converter):
    return Mock(return_value=converter)


@pytest.fixture
def cli(converter_factory):
    return partial(cli_module.main, converter_factory=converter_factory)


@pytest.fixture
def convert(converter):
    return converter.convert


@pytest.fixture
def check_requirements(converter):
    return converter.check_requirements


@pytest.mark.parametrize("mode", [[], ["--reuse"], ["--resume"]])
def test_missing_ocrmypdf_stops_before_conversion(cli, convert, check_requirements, capsys, mode):
    check_requirements.side_effect = ConversionError("O comando 'ocrmypdf' não foi encontrado.")

    with pytest.raises(SystemExit) as error:
        cli([URL, *mode, "--ocr"])

    assert error.value.code == 1
    check_requirements.assert_called_once()
    convert.assert_not_called()
    assert "ocrmypdf" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments, mode",
    [([], CaptureMode.NEW), (["--resume"], CaptureMode.RESUME), (["--reuse"], CaptureMode.REUSE)],
)
def test_flags_select_capture_mode(cli, convert, check_requirements, arguments, mode):
    cli([URL, *arguments])

    assert convert.call_args.args[0].mode is mode


@pytest.mark.parametrize("ocr, export_text", [(False, False), (True, False), (True, True)])
def test_builds_request_from_arguments(cli, convert, check_requirements, capsys, tmp_path, ocr, export_text):
    output = tmp_path / "livro.pdf"
    text_path = output.with_suffix(".txt") if export_text else None
    convert.return_value = ConversionResult(output, text_path)
    arguments = [URL, "-o", str(output), "--ocr-language", "por+eng"]
    arguments += ["--ocr"] if ocr else []
    arguments += ["--export-text"] if export_text else []

    cli(arguments)

    request = convert.call_args.args[0]
    assert request.output_path == output
    assert request.ocr_language == ("por+eng" if ocr else None)
    assert request.export_text is export_text

    messages = capsys.readouterr().out
    assert f"PDF salvo em: {output}" in messages
    assert ("Texto salvo em:" in messages) is export_text


@pytest.mark.parametrize("arguments, compact", [([], False), (["--compact"], True)])
def test_compact_flag_reaches_request(cli, convert, check_requirements, arguments, compact):
    cli([URL, *arguments])

    assert convert.call_args.args[0].compact is compact


def test_default_output_uses_default_folder(cli, convert, check_requirements, tmp_path):
    cli([URL])

    assert convert.call_args.args[0].output_path == tmp_path / "pdfs" / "123.pdf"


@pytest.mark.parametrize("arguments, captures_dir", [([], None), (["--captures-dir", "capturas"], Path("capturas"))])
def test_captures_dir_is_passed_to_converter(cli, converter_factory, convert, check_requirements, arguments, captures_dir):
    cli([URL, *arguments])

    converter_factory.assert_called_once_with(captures_dir)


def test_export_requires_ocr_before_anything_runs(cli, convert, check_requirements, capsys):
    with pytest.raises(SystemExit) as error:
        cli([URL, "--export-text"])

    assert error.value.code == 2
    assert "--export-text exige --ocr" in capsys.readouterr().err
    check_requirements.assert_not_called()
    convert.assert_not_called()


@pytest.mark.parametrize("arguments", [["https://example.com/document/1"], [URL, "-o", "livro.txt"]])
def test_invalid_input_exits_with_error(cli, convert, check_requirements, capsys, arguments):
    with pytest.raises(SystemExit) as error:
        cli(arguments)

    assert error.value.code == 1
    assert capsys.readouterr().err.startswith("Erro:")
    convert.assert_not_called()


def test_conversion_error_exits_with_message(cli, convert, check_requirements, capsys):
    convert.side_effect = ConversionError("Falha no navegador: tempo esgotado.")

    with pytest.raises(SystemExit) as error:
        cli([URL])

    assert error.value.code == 1
    assert capsys.readouterr().err == "Erro: Falha no navegador: tempo esgotado.\n"


def test_keyboard_interrupt_exits_with_130_and_suggests_resume(cli, convert, check_requirements, capsys):
    convert.side_effect = KeyboardInterrupt

    with pytest.raises(SystemExit) as error:
        cli([URL])

    assert error.value.code == 130
    message = capsys.readouterr().err
    assert "interrompida" in message
    assert "--resume" in message
