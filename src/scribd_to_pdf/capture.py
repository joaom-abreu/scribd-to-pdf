import re
from pathlib import Path

from playwright.sync_api import Locator, Page


def get_page_numbers(page: Page) -> list[int]:
    element_ids = page.locator('[id^="page"]').evaluate_all(
        "elements => elements.map(element => element.id)"
    )

    numbers: set[int] = set()

    for element_id in element_ids:
        match = re.fullmatch(r"page([1-9][0-9]*)", element_id)

        if match is not None:
            numbers.add(int(match.group(1)))

    return sorted(numbers)


def prepare_page(page: Page, page_number: int) -> Locator:
    document_page = page.locator(f"#page{page_number}")
    document_page.wait_for(state="attached", timeout=30_000)
    document_page.scroll_into_view_if_needed(timeout=30_000)
    return document_page


def capture_page(page: Page, page_number: int, output_dir: Path) -> Path:
    document_page = prepare_page(page, page_number)

    document_page.wait_for_function(
        """
        element => Array.from(element.querySelectorAll("img")).every(
            image => image.complete && image.naturalWidth > 0
        )
        """,
        timeout=30_000,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"page_{page_number:04d}.png"

    document_page.screenshot(
        path=str(output_path),
        type="png",
        animations="disabled",
        timeout=30_000,
    )

    return output_path