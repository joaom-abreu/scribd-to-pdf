import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from scribd_to_pdf import cli as cli_module
from scribd_to_pdf.ocr import OcrError


URL = "https://www.scribd.com/document/123/livro"


@pytest.mark.parametrize("mode", [[], ["--reuse"], ["--resume"]])
def test_missing_language_stops_before_capture(monkeypatch, capsys, mode):
    check = Mock(side_effect=OcrError("Falta o modelo Francês (fra)."))
    capture = Mock()
    reuse = Mock()
    create_pdf = Mock()
    add_ocr = Mock()
    monkeypatch.setattr(cli_module, "check_ocr_available", check)
    monkeypatch.setattr(cli_module, "inspect_document", capture)
    monkeypatch.setattr(cli_module, "load_capture", reuse)
    monkeypatch.setattr(cli_module, "create_pdf", create_pdf)
    monkeypatch.setattr(cli_module, "add_ocr", add_ocr)
    monkeypatch.setattr(
        sys,
        "argv",
        ["scribd-to-pdf", URL, *mode, "--ocr", "--ocr-language", "por+fra"],
    )

    with pytest.raises(SystemExit) as error:
        cli_module.main()

    assert error.value.code == 1
    check.assert_called_once_with("por+fra")
    capture.assert_not_called()
    reuse.assert_not_called()
    create_pdf.assert_not_called()
    add_ocr.assert_not_called()
    assert "fra" in capsys.readouterr().err


@pytest.mark.parametrize("ocr_enabled, export_text", [(False, False), (True, False), (True, True)])
def test_cli_checks_languages_only_with_ocr(monkeypatch, tmp_path, capsys, ocr_enabled, export_text):
    output = tmp_path / "livro.pdf"
    check = Mock(return_value="ocrmypdf")
    capture = Mock(return_value=[Path("page_0001.png")])
    create_pdf = Mock(return_value=output)
    add_ocr = Mock(return_value=output)
    monkeypatch.setattr(cli_module, "check_ocr_available", check)
    monkeypatch.setattr(cli_module, "inspect_document", capture)
    monkeypatch.setattr(cli_module, "create_pdf", create_pdf)
    monkeypatch.setattr(cli_module, "add_ocr", add_ocr)
    arguments = ["scribd-to-pdf", URL, "-o", str(output), "--ocr-language", "por+eng"]

    if ocr_enabled:
        arguments.append("--ocr")

    if export_text:
        arguments.append("--export-text")

    monkeypatch.setattr(sys, "argv", arguments)

    cli_module.main()

    capture.assert_called_once()
    create_pdf.assert_called_once()

    if ocr_enabled:
        check.assert_called_once_with("por+eng")
        add_ocr.assert_called_once_with(output, language="por+eng", export_text=export_text)
    else:
        check.assert_not_called()
        add_ocr.assert_not_called()

    messages = capsys.readouterr().out
    assert ("Texto salvo em:" in messages) == export_text

    if export_text:
        assert str(output.with_suffix(".txt")) in messages


def test_export_requires_ocr_before_capture(monkeypatch, capsys):
    capture = Mock()
    check = Mock()
    monkeypatch.setattr(cli_module, "inspect_document", capture)
    monkeypatch.setattr(cli_module, "check_ocr_available", check)
    monkeypatch.setattr(sys, "argv", ["scribd-to-pdf", URL, "--export-text"])

    with pytest.raises(SystemExit) as error:
        cli_module.main()

    assert error.value.code == 2
    assert "--export-text exige --ocr" in capsys.readouterr().err
    capture.assert_not_called()
    check.assert_not_called()
