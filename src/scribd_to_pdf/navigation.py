import re

from playwright.sync_api import Page


def get_total_pages(page: Page) -> int:
    counter = page.locator("div").filter(
        has_text=re.compile(r"^You are on page\s*\d[\d\s]*$")
    ).nth(1)

    counter.wait_for(state="visible", timeout=30_000)

    values = counter.evaluate(
        r"""
        element => {
            const walker = document.createTreeWalker(
                element,
                NodeFilter.SHOW_TEXT
            );

            const numbers = [];
            let node;

            while ((node = walker.nextNode()) !== null) {
                const matches = node.textContent.match(/\d+/g);

                if (matches !== null) {
                    numbers.push(...matches);
                }
            }

            return numbers;
        }
        """
    )

    if len(values) != 2:
        raise ValueError(
            f"Não consegui separar página atual e total: {values}.\n"
            f"HTML do contador:\n{counter.inner_html()}"
        )

    current_page, total_pages = map(int, values)

    if not 1 <= current_page <= total_pages:
        raise ValueError("O contador de páginas apresentou valores inválidos.")

    return total_pages