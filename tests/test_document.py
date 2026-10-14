import pytest

from scribd_to_pdf.domain.document import Document


@pytest.mark.parametrize(
    "url",
    [
        "https://www.scribd.com/document/123/livro",
        "https://scribd.com/document/123/livro/",
        "  https://WWW.SCRIBD.COM/document/123  ",
    ],
)
def test_parses_document_id_and_normalizes_url(url):
    document = Document.from_url(url)

    assert document.document_id == "123"
    assert document.url.startswith("https://www.scribd.com/document/123")
    assert not document.url.endswith("/")


@pytest.mark.parametrize(
    "url",
    [
        "http://www.scribd.com/document/123/livro",
        "https://example.com/document/123/livro",
        "https://www.scribd.com/book/123/livro",
        "https://www.scribd.com/document/abc/livro",
        "https://www.scribd.com/document/123/livro/extra",
        "https://www.scribd.com/document/123/li vro",
        "",
    ],
    ids=["http", "other-host", "not-a-document", "non-numeric-id", "extra-segment", "space", "empty"],
)
def test_rejects_invalid_urls(url):
    with pytest.raises(ValueError):
        Document.from_url(url)
