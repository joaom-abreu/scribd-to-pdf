import argparse
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from pypdf.errors import PdfReadError

from scribd_to_pdf.browser import inspect_document
from scribd_to_pdf.cache import load_capture
from scribd_to_pdf.ocr import OcrError, add_ocr, check_ocr_available
from scribd_to_pdf.pdf import create_pdf
from scribd_to_pdf.scribd import parse_document_url


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scribd-to-pdf",
        description="Reúne páginas de um documento do Scribd em um PDF.",
    )

    parser.add_argument(
        "url",
        help="URL do documento no Scribd.",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="ARQUIVO",
        help="Destino do PDF. Padrão: output/ID/ID.pdf.",
    )

    modes = parser.add_mutually_exclusive_group()

    modes.add_argument(
        "--reuse",
        action="store_true",
        help=(
            "Gera o PDF usando uma captura completa já salva, "
            "sem abrir o navegador."
        ),
    )

    modes.add_argument(
        "--resume",
        action="store_true",
        help="Retoma uma captura incompleta, aproveitando as páginas já salvas.",
    )

    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Adiciona texto pesquisável e selecionável ao PDF.",
    )

    parser.add_argument(
        "--ocr-language",
        default="por",
        metavar="IDIOMA",
        help=(
            "Idioma do OCR: por (português), eng (inglês), "
            "spa (espanhol), fra (francês) ou deu (alemão). "
            "Combine idiomas com +, como por+eng. Padrão: por."
        ),
    )

    args = parser.parse_args()

    try:
        document = parse_document_url(args.url)
        capture_dir = Path("output") / document.document_id

        output_path = (
            args.output.expanduser()
            if args.output is not None
            else capture_dir / f"{document.document_id}.pdf"
        )

        if output_path.suffix.lower() != ".pdf":
            raise ValueError("O arquivo de saída deve ter a extensão .pdf.")

        if args.ocr:
            check_ocr_available(args.ocr_language)

        if args.reuse:
            print("Reutilizando as páginas já capturadas...")
            image_paths = load_capture(document, capture_dir)
        else:
            image_paths = inspect_document(
                document,
                resume=args.resume,
            )

        print(f"Gerando PDF com {len(image_paths)} páginas...")
        create_pdf(image_paths, output_path)

        if args.ocr:
            print(f"Aplicando OCR ({args.ocr_language})...")
            add_ocr(
                output_path,
                language=args.ocr_language,
            )

        print(f"PDF salvo em: {output_path.resolve()}")

    except KeyboardInterrupt:
        parser.exit(130, "\nOperação interrompida.\n")

    except EOFError:
        parser.exit(
            1,
            "\nEntrada encerrada antes de confirmar a captura.\n",
        )

    except (
            PlaywrightError,
            PdfReadError,
            ValueError,
            OSError,
            OcrError,
    ) as error:
        parser.exit(1, f"Erro: {error}\n")


if __name__ == "__main__":
    main()
