from pathlib import Path

from playwright.sync_api import Page


def capture_first_page(page: Page, output_dir: Path) -> Path:
    document_page = page.locator("#page1")
    document_page.wait_for(state="visible", timeout=30_000)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "page_0001.png"

    document_page.screenshot(
        path=str(output_path),
        type="png",
        animations="disabled",
        timeout=30_000,
    )

    return output_path