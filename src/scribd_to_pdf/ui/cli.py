import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from scribd_to_pdf.application.conversion import (
    CaptureMode,
    ConversionRequest,
    ConversionResult,
    DocumentConverter,
    Stage,
)
from scribd_to_pdf.application.errors import ConversionError
from scribd_to_pdf.bootstrap import build_converter
from scribd_to_pdf.domain.document import Document
from scribd_to_pdf.domain.languages import DEFAULT_LANGUAGE, LANGUAGES

READY_PROMPT = (
    "\nAguarde a capa carregar e feche avisos que ainda cubram o documento."
    "\nPressione Enter para ativar Fullscreen e capturar..."
)


def main(
    argv: Sequence[str] | None = None,
    *,
    converter_factory: Callable[[Path | None], DocumentConverter] = build_converter,
) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.export_text and not args.ocr:
        parser.error("A opção --export-text exige --ocr.")

    try:
        result = _run(args, converter_factory(args.captures_dir))
    except KeyboardInterrupt:
        parser.exit(130, "\nOperação interrompida.\n")
    except EOFError:
        parser.exit(1, "\nEntrada encerrada antes de confirmar a captura.\n")
    except (ValueError, OSError, ConversionError) as error:
        parser.exit(1, f"Erro: {error}\n")

    print(f"PDF salvo em: {result.pdf_path}")

    if result.text_path is not None:
        print(f"Texto salvo em: {result.text_path}")


def _run(args: argparse.Namespace, converter: DocumentConverter) -> ConversionResult:
    document = Document.from_url(args.url)
    request = ConversionRequest(
        document=document,
        output_path=converter.output_path(document, args.output),
        mode=_capture_mode(args),
        ocr_language=args.ocr_language if args.ocr else None,
        export_text=args.export_text,
    )

    converter.check_requirements(request)
    return converter.convert(request, on_progress=_print_progress, wait_for_ready=_wait_for_enter)


def _capture_mode(args: argparse.Namespace) -> CaptureMode:
    if args.reuse:
        return CaptureMode.REUSE

    return CaptureMode.RESUME if args.resume else CaptureMode.NEW


def _print_progress(_: Stage, message: str) -> None:
    print(message)


def _wait_for_enter() -> None:
    input(READY_PROMPT)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scribd-to-pdf",
        description="Reúne páginas de um documento do Scribd em um PDF.",
    )
    parser.add_argument("url", help="URL do documento no Scribd.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="ARQUIVO",
        help="Destino do PDF. Padrão: ID.pdf na pasta atual.",
    )
    parser.add_argument(
        "--captures-dir",
        type=Path,
        metavar="PASTA",
        help=(
            "Pasta onde as capturas são salvas e procuradas para --resume e --reuse. "
            "Padrão: pasta de dados do usuário (veja o README)."
        ),
    )

    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--reuse",
        action="store_true",
        help="Gera o PDF usando uma captura completa já salva, sem abrir o navegador.",
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
        default=DEFAULT_LANGUAGE,
        metavar="IDIOMA",
        help=(
            "Idioma do OCR: "
            + ", ".join(f"{code} ({name.lower()})" for code, name in LANGUAGES.items())
            + f". Combine idiomas com +, como por+eng. Padrão: {DEFAULT_LANGUAGE}."
        ),
    )
    parser.add_argument(
        "--export-text",
        action="store_true",
        help="Salva o texto reconhecido em um .txt ao lado do PDF. Exige --ocr.",
    )
    return parser


if __name__ == "__main__":
    main()
