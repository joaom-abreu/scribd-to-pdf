import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from scribd_to_pdf.capture import capture_first_page
from scribd_to_pdf.models import Document


def inspect_document(document: Document) -> None:
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

            output_path = capture_first_page(
                page,
                output_dir=Path("output"),
            )

            print(f"Captura salva em: {output_path.resolve()}")
        finally:
            browser.close()