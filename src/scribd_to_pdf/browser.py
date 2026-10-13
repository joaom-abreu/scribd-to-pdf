import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from scribd_to_pdf.cache import MANIFEST_NAME, save_capture
from scribd_to_pdf.capture import capture_page
from scribd_to_pdf.models import Document
from scribd_to_pdf.navigation import get_total_pages


def inspect_document(document: Document) -> list[Path]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)

        try:
            page = browser.new_page(
                viewport={"width": 1280, "height": 900},
                device_scale_factor=2,
            )

            response = page.goto(
                document.url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            if response is not None:
                print(f"Status HTTP: {response.status}")

            print(f"Título da página: {page.title()}")

            input(
                "\nAguarde a capa carregar e feche o aviso de privacidade."
                "\nPressione Enter para ativar Fullscreen e capturar..."
            )

            fullscreen_button = page.get_by_role(
                "button",
                name=re.compile(r"full\s*screen", re.IGNORECASE),
            )
            fullscreen_button.click(timeout=30_000)

            page.set_viewport_size(
                {"width": 1280, "height": 1800},
            )

            total_pages = get_total_pages(page)
            print(f"Total de páginas: {total_pages}")

            output_dir = Path("output") / document.document_id
            (output_dir / MANIFEST_NAME).unlink(missing_ok=True)
            captured_paths: list[Path] = []

            for page_number in range(1, total_pages + 1):
                print(f"Capturando página {page_number} de {total_pages}...")

                output_path = capture_page(
                    page,
                    page_number=page_number,
                    output_dir=output_dir,
                )

                captured_paths.append(output_path)

            save_capture(document, output_dir, total_pages)

            print(
                f"Captura concluída: {len(captured_paths)} páginas."
                f"\nPasta: {output_dir.resolve()}"
            )

            return captured_paths
        finally:
            browser.close()