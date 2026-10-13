from playwright.sync_api import sync_playwright

from scribd_to_pdf.models import Document


def inspect_document(document: Document) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)

        try:
            page = browser.new_page(
                viewport={"width": 1280, "height": 900},
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
                "\nConfira o documento no navegador."
                "\nPressione Enter neste terminal para fechar..."
            )
        finally:
            browser.close()