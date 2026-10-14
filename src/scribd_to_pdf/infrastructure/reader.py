import re
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, sync_playwright

from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.domain.cancellation import ShouldCancel, raise_if_cancelled
from scribd_to_pdf.domain.capture import CaptureProgress
from scribd_to_pdf.domain.document import Document
from scribd_to_pdf.infrastructure.storage import CaptureStore, FileCaptureRepository

TIMEOUT_MS = 30_000
NAVIGATION_TIMEOUT_MS = 60_000
DEVICE_SCALE_FACTOR = 2
READER_VIEWPORT = {"width": 1280, "height": 900}
CAPTURE_VIEWPORT = {"width": 1280, "height": 1800}
FULLSCREEN_BUTTON = re.compile(r"full\s*screen", re.IGNORECASE)
PAGE_COUNTER = re.compile(r"^You are on page\s*\d[\d\s]*$")
CAPTURE_INTERRUPTED = "Captura interrompida."

IMAGES_LOADED = """
element => Array.from(element.querySelectorAll("img")).every(
    image => image.complete && image.naturalWidth > 0
)
"""

TEXT_NODE_NUMBERS = r"""
element => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    const numbers = [];

    while (walker.nextNode() !== null) {
        numbers.push(...(walker.currentNode.textContent.match(/\d+/g) ?? []));
    }

    return numbers;
}
"""


class ScribdReader:
    def __init__(self, page: Page) -> None:
        self._page = page

    def open(self, url: str) -> str:
        response = self._page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)

        if response is not None and response.status >= 400:
            raise ValueError(f"Não foi possível abrir o documento: HTTP {response.status}.")

        return self._page.title()

    def enter_fullscreen(self) -> None:
        self._page.get_by_role("button", name=FULLSCREEN_BUTTON).click(timeout=TIMEOUT_MS)
        self._page.set_viewport_size(CAPTURE_VIEWPORT)

    def count_pages(self) -> int:
        counter = self._page.locator("div").filter(has_text=PAGE_COUNTER).nth(1)
        counter.wait_for(state="visible", timeout=TIMEOUT_MS)
        numbers = counter.evaluate(TEXT_NODE_NUMBERS)

        if len(numbers) != 2:
            raise ValueError(f"Não foi possível ler o contador de páginas: {numbers}.")

        current_page, total_pages = map(int, numbers)

        if not 1 <= current_page <= total_pages:
            raise ValueError("O contador de páginas apresentou valores inválidos.")

        return total_pages

    def scroll_to(self, number: int) -> Locator:
        document_page = self._page.locator(f"#page{number}")
        document_page.wait_for(state="attached", timeout=TIMEOUT_MS)
        document_page.scroll_into_view_if_needed(timeout=TIMEOUT_MS)
        return document_page

    def capture(self, number: int, path: Path) -> None:
        document_page = self.scroll_to(number)
        document_page.wait_for_function(IMAGES_LOADED, timeout=TIMEOUT_MS)
        document_page.screenshot(path=path, type="png", animations="disabled", timeout=TIMEOUT_MS)


class PlaywrightPageCapturer:
    def __init__(self, repository: FileCaptureRepository) -> None:
        self._repository = repository

    def capture(
        self,
        document: Document,
        *,
        resume: bool,
        wait_for_ready: Callable[[], None],
        on_status: Callable[[str], None],
        should_cancel: ShouldCancel,
    ) -> list[Path]:
        try:
            return capture_document(
                self._repository.store(document),
                resume=resume,
                wait_for_ready=wait_for_ready,
                on_status=on_status,
                should_cancel=should_cancel,
            )
        except InterruptedError:
            raise
        except PlaywrightError as error:
            raise ConversionError(f"Falha no navegador: {error.message}") from error
        except (OSError, ValueError) as error:
            raise ConversionError(str(error)) from error


def capture_document(
    store: CaptureStore,
    *,
    resume: bool,
    wait_for_ready: Callable[[], None],
    on_status: Callable[[str], None],
    should_cancel: ShouldCancel,
) -> list[Path]:
    previous = store.load_progress() if resume else None
    raise_if_cancelled(should_cancel, CAPTURE_INTERRUPTED)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)

        try:
            page = browser.new_page(viewport=READER_VIEWPORT, device_scale_factor=DEVICE_SCALE_FACTOR)
            reader = ScribdReader(page)
            on_status(f"Documento aberto: {reader.open(store.document.url)}")

            raise_if_cancelled(should_cancel, CAPTURE_INTERRUPTED)
            wait_for_ready()
            raise_if_cancelled(should_cancel, CAPTURE_INTERRUPTED)

            reader.enter_fullscreen()
            total_pages = reader.count_pages()
            on_status(f"Total de páginas: {total_pages}")

            progress = _starting_progress(store, previous, total_pages)
            store.save_progress(progress)
            _capture_pages(reader, store, progress, on_status, should_cancel)
        finally:
            browser.close()

    on_status(f"Captura concluída: {total_pages} páginas.\nPasta: {store.directory.resolve()}")
    return store.page_paths(total_pages)


def _starting_progress(
    store: CaptureStore,
    previous: CaptureProgress | None,
    total_pages: int,
) -> CaptureProgress:
    if previous is None:
        return CaptureProgress(total_pages)

    if previous.total_pages != total_pages:
        raise ValueError(
            "O total de páginas difere da captura registrada. Faça uma nova captura."
        )

    return CaptureProgress(
        total_pages,
        frozenset(number for number in previous.captured_pages if store.has_page(number)),
    )


def _capture_pages(
    reader: ScribdReader,
    store: CaptureStore,
    progress: CaptureProgress,
    on_status: Callable[[str], None],
    should_cancel: ShouldCancel,
) -> None:
    total_pages = progress.total_pages

    for number in range(1, total_pages + 1):
        raise_if_cancelled(should_cancel, CAPTURE_INTERRUPTED)

        if number in progress.captured_pages:
            on_status(f"Reutilizando página {number} de {total_pages}...")
            reader.scroll_to(number)
            continue

        on_status(f"Capturando página {number} de {total_pages}...")
        reader.capture(number, store.page_path(number))
        progress = progress.with_page(number)
        store.save_progress(progress)
