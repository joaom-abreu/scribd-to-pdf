import argparse
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from pypdf.errors import PdfReadError

from scribd_to_pdf.browser import inspect_document
from scribd_to_pdf.cache import load_capture
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
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="ARQUIVO",
        help="Caminho do PDF. Padrão: output/ID/ID.pdf.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--reuse",
        action="store_true",
        help="Reutiliza uma captura completa salva, sem abrir o navegador.",
    )
    mode.add_argument(
        "--resume",
        action="store_true",
        help="Retoma uma captura, abrindo o navegador para capturar o que falta.",
    )
    args = parser.parse_args()

    try:
        document = parse_document_url(args.url)
        output_dir = Path("output") / document.document_id
        output_path = (
            args.output.expanduser()
            if args.output is not None
            else output_dir / f"{document.document_id}.pdf"
        )

        if output_path.suffix.lower() != ".pdf":
            raise ValueError(
                "O destino deve ser um arquivo com extensão .pdf."
            )
    except ValueError as error:
        parser.error(str(error))

    print(f"ID do documento: {document.document_id}")
    print(f"URL: {document.url}")

    try:
        if args.reuse:
            image_paths = load_capture(document, output_dir)
            print(f"Reutilizando {len(image_paths)} páginas salvas.")
        else:
            image_paths = inspect_document(document, resume=args.resume)

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