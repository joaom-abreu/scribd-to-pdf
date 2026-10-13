import argparse

from playwright.sync_api import Error as PlaywrightError

from scribd_to_pdf.browser import inspect_document
from scribd_to_pdf.scribd import parse_document_url


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scribd-to-pdf",
        description="Abre um documento do Scribd para inspeção.",
    )
    parser.add_argument(
        "url",
        metavar="URL",
        help="Link do documento no Scribd.",
    )
    args = parser.parse_args()

    try:
        document = parse_document_url(args.url)
    except ValueError as error:
        parser.error(str(error))

    print(f"ID do documento: {document.document_id}")
    print(f"URL: {document.url}")

    try:
        inspect_document(document)
    except (PlaywrightError, ValueError, OSError) as error:
        parser.exit(
            status=1,
            message=f"\nFalha na captura: {error}\n",
        )
    except (KeyboardInterrupt, EOFError):
        parser.exit(
            status=1,
            message="\nInspeção interrompida.\n",
        )


if __name__ == "__main__":
    main()