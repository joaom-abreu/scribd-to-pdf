from pathlib import Path
from unittest.mock import Mock

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from scribd_to_pdf.application.conversion import ConversionError
from scribd_to_pdf.domain.document import Document
from scribd_to_pdf.infrastructure import reader as reader_module
from scribd_to_pdf.infrastructure.reader import CAPTURE_ATTEMPTS, PlaywrightPageCapturer, ScribdReader
from scribd_to_pdf.infrastructure.storage import CaptureStore, FileCaptureRepository

DOCUMENT = Document("123", "https://www.scribd.com/document/123/livro")


def capture(tmp_path: Path) -> list[Path]:
    return PlaywrightPageCapturer(FileCaptureRepository(tmp_path)).capture(
        DOCUMENT,
        resume=False,
        wait_for_ready=Mock(),
        on_status=Mock(),
    )


def test_capturer_saves_pages_in_the_document_folder(tmp_path, monkeypatch):
    capture_document = Mock(return_value=[tmp_path / "page_0001.png"])
    monkeypatch.setattr(reader_module, "capture_document", capture_document)

    assert capture(tmp_path) == [tmp_path / "page_0001.png"]
    assert capture_document.call_args.args[0].directory == tmp_path / "123"


@pytest.mark.parametrize(
    "failure, message",
    [
        (PlaywrightError("Timeout 30000ms exceeded."), "Falha no navegador: Timeout 30000ms exceeded."),
        (ValueError("O contador de páginas apresentou valores inválidos."), "contador de páginas"),
        (PermissionError("Sem permissão."), "Sem permissão."),
    ],
    ids=["playwright", "valor-invalido", "arquivo"],
)
def test_capturer_reports_failures_as_conversion_error(tmp_path, monkeypatch, failure, message):
    monkeypatch.setattr(reader_module, "capture_document", Mock(side_effect=failure))

    with pytest.raises(ConversionError, match=message) as error:
        capture(tmp_path)

    assert error.value.__cause__ is failure


class FakeReader:
    def __init__(self, timeouts: dict[int, int] | None = None) -> None:
        self.timeouts = dict(timeouts or {})
        self.captured: list[int] = []
        self.pauses: list[int] = []

    def capture(self, number: int, path: Path) -> None:
        if self.timeouts.get(number, 0) > 0:
            self.timeouts[number] -= 1
            raise PlaywrightTimeoutError(f"Página {number} sem imagem.")

        path.write_bytes(b"png")
        self.captured.append(number)

    def scroll_to(self, number: int) -> None:
        pass

    def pause(self, milliseconds: int) -> None:
        self.pauses.append(milliseconds)


@pytest.fixture
def store(tmp_path) -> CaptureStore:
    store = FileCaptureRepository(tmp_path).store(DOCUMENT)
    store.directory.mkdir()
    return store


def capture_pages(
    reader: FakeReader,
    store: CaptureStore,
    total_pages: int,
    resume: bool = False,
) -> list[str]:
    messages: list[str] = []
    reader_module._capture_pages(reader, store, total_pages, messages.append, resume)
    return messages


def test_slow_page_is_retried_with_growing_pauses(store):
    reader = FakeReader({2: CAPTURE_ATTEMPTS - 1})

    messages = capture_pages(reader, store, 3)

    assert reader.captured == [1, 2, 3]
    assert reader.pauses == [2_000, 4_000]
    assert f"Tentativa {CAPTURE_ATTEMPTS} de {CAPTURE_ATTEMPTS}" in "\n".join(messages)
    assert all(store.has_page(number) for number in (1, 2, 3))


def test_page_that_never_loads_keeps_pages_already_captured(store):
    reader = FakeReader({2: CAPTURE_ATTEMPTS})

    with pytest.raises(PlaywrightTimeoutError):
        capture_pages(reader, store, 3)

    assert reader.captured == [1]
    assert store.has_page(1)
    assert not store.has_page(2)


@pytest.mark.parametrize("resume, captured", [(True, [2, 3]), (False, [1, 2, 3])])
def test_only_resume_skips_pages_already_saved(store, resume, captured):
    store.page_path(1).write_bytes(b"png")
    reader = FakeReader()

    capture_pages(reader, store, 3, resume=resume)

    assert reader.captured == captured


@pytest.fixture(scope="module")
def browser_page():
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as error:
            pytest.skip(f"Chromium do Playwright indisponível: {error.message.splitlines()[0]}")

        page = browser.new_page(locale=reader_module.READER_LOCALE)
        yield page
        browser.close()


COUNTER = "<div><div><span>You are on page</span><span>{current}</span><span>{total}</span></div></div>"


def test_page_counter_ignores_hidden_copies_and_nesting(browser_page):
    browser_page.set_content(
        f'<div style="display: none">{COUNTER.format(current=9, total=99)}</div>'
        f"<header>{COUNTER.format(current=3, total=120)}</header>"
    )

    assert ScribdReader(browser_page).count_pages() == 120


def test_page_counter_rejects_current_page_above_total(browser_page):
    browser_page.set_content(COUNTER.format(current=7, total=5))

    with pytest.raises(ValueError, match="inválidos"):
        ScribdReader(browser_page).count_pages()


@pytest.mark.parametrize("label", ["Accept All", "I agree", "Got it"])
def test_consent_banner_is_dismissed(browser_page, label):
    browser_page.set_content(
        f'<div id="banner"><button onclick="banner.remove()">{label}</button></div>'
    )

    assert ScribdReader(browser_page).dismiss_consent(timeout_ms=1_000)
    assert browser_page.locator("#banner").count() == 0


def test_missing_consent_banner_is_not_an_error(browser_page):
    browser_page.set_content("<button>Fullscreen</button><button>Accept invitation</button>")

    assert not ScribdReader(browser_page).dismiss_consent(timeout_ms=300)
