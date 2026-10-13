import re
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import sync_playwright

from scribd_to_pdf.cache import load_progress, save_capture, save_progress
from scribd_to_pdf.capture import capture_page, prepare_page
from scribd_to_pdf.models import Document
from scribd_to_pdf.navigation import get_total_pages


def inspect_document(
        document: Document,
        resume: bool = False,
        *,
        on_status: Callable[[str], None] = print,
        wait_for_ready: Callable[[], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
) -> list[Path]:
    def check_cancelled() -> None:
        if should_cancel is not None and should_cancel():
            raise InterruptedError("Captura interrompida.")

    check_cancelled()
    output_dir = Path("output") / document.document_id
    progress = load_progress(document, output_dir) if resume else None

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)

        try:
            page = browser.new_page(
                viewport={"width": 1280, "height": 900},
                device_scale_factor=2,
            )
            check_cancelled()

            response = page.goto(
                document.url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            if response is not None and response.status >= 400:
                raise ValueError(
                    f"Não foi possível abrir o documento: HTTP {response.status}."
                )

            on_status(f"Documento aberto: {page.title()}")
            check_cancelled()

            if wait_for_ready is None:
                input(
                    "\nAguarde a capa carregar e feche o aviso de privacidade."
                    "\nPressione Enter para ativar Fullscreen e capturar..."
                )
            else:
                wait_for_ready()

            check_cancelled()

            fullscreen_button = page.get_by_role(
                "button",
                name=re.compile(r"full\s*screen", re.IGNORECASE),
            )
            fullscreen_button.click(timeout=30_000)

            page.set_viewport_size(
                {"width": 1280, "height": 1800},
            )

            total_pages = get_total_pages(page)
            on_status(f"Total de páginas: {total_pages}")
            check_cancelled()
            captured_numbers: set[int] = set()

            if progress is not None:
                saved_total, saved_numbers = progress

                if saved_total != total_pages:
                    raise ValueError(
                        "O total de páginas difere da captura registrada. "
                        "Execute novamente sem --resume."
                    )

                for number in saved_numbers:
                    path = output_dir / f"page_{number:04d}.png"

                    if path.is_file() and path.stat().st_size > 0:
                        captured_numbers.add(number)

            save_progress(
                document,
                output_dir,
                total_pages,
                captured_numbers,
            )
            captured_paths: list[Path] = []

            for page_number in range(1, total_pages + 1):
                check_cancelled()

                if page_number in captured_numbers:
                    on_status(
                        f"Reutilizando página {page_number} de {total_pages}..."
                    )
                    prepare_page(page, page_number)
                    output_path = output_dir / f"page_{page_number:04d}.png"
                else:
                    on_status(
                        f"Capturando página {page_number} de {total_pages}..."
                    )
                    output_path = capture_page(
                        page,
                        page_number=page_number,
                        output_dir=output_dir,
                    )
                    captured_numbers.add(page_number)
                    save_progress(
                        document,
                        output_dir,
                        total_pages,
                        captured_numbers,
                    )

                captured_paths.append(output_path)

            check_cancelled()
            save_capture(document, output_dir, total_pages)

            on_status(
                f"Captura concluída: {len(captured_paths)} páginas."
                f"\nPasta: {output_dir.resolve()}"
            )

            return captured_paths
        finally:
            browser.close()