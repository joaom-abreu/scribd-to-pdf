import argparse
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from pypdf.errors import PdfReadError

from scribd_to_pdf.browser import inspect_document
from scribd_to_pdf.pdf import create_pdf
from scribd_to_pdf.scribd import parse_document_url


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scribd-to-pdf",
        description="Converte documentos do Scribd em PDF.",
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
        image_paths = inspect_document(document)

        output_path = (
                Path("output")
                / document.document_id
                / f"{document.document_id}.pdf"
        )

        print("Gerando PDF...")
        pdf_path = create_pdf(image_paths, output_path)
        print(f"PDF salvo em: {pdf_path.resolve()}")
    except (PlaywrightError, PdfReadError, ValueError, OSError) as error:
        parser.exit(
            status=1,
            message=f"\nFalha na conversão: {error}\n",
        )
    except (KeyboardInterrupt, EOFError):
        parser.exit(
            status=1,
            message="\nConversão interrompida.\n",
        )


if __name__ == "__main__":
    main()