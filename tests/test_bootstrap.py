from pathlib import Path

from scribd_to_pdf.bootstrap import build_converter
from scribd_to_pdf.domain.document import Document

DOCUMENT = Document("123", "https://www.scribd.com/document/123/livro")


def test_default_pdf_goes_to_the_current_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert build_converter().output_path(DOCUMENT) == tmp_path / "123.pdf"


def test_captures_dir_expands_user_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    captures = build_converter(Path("~") / "capturas").captures

    assert captures.store(DOCUMENT).directory == tmp_path / "capturas" / "123"
