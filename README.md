# scribd-to-pdf

Ferramenta de linha de comando em Python que captura as páginas de um documento aberto no leitor do Scribd e as reúne, na ordem, em um único PDF. Opcionalmente, aplica OCR para deixar o texto pesquisável e selecionável.

Use a ferramenta apenas com documentos que você tem direito de guardar.

## Requisitos

- Python 3.12 ou superior.
- Ambiente gráfico, porque a captura abre uma janela do navegador.
- Para o OCR (opcional): OCRmyPDF, Tesseract e os modelos dos idiomas desejados.

## Instalação

```bash
git clone https://github.com/joaom-abreu/scribd-to-pdf.git
cd scribd-to-pdf
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m playwright install chromium
```

No Windows, crie o ambiente com `py -m venv .venv` e use `.venv\Scripts\python` no lugar de `python`.

## Uso

```bash
scribd-to-pdf "https://www.scribd.com/document/ID/titulo"
```

Quando o navegador abrir, espere a capa carregar, feche os avisos que cobrirem o documento e pressione **Enter** no terminal. O aviso de cookies é fechado automaticamente quando reconhecido. Cada página é tentada até três vezes antes de a captura parar.

Exemplos:

```bash
scribd-to-pdf "LINK" -o livro.pdf
scribd-to-pdf "LINK" --resume
scribd-to-pdf "LINK" --reuse --compact -o livro-compacto.pdf
scribd-to-pdf "LINK" --ocr --ocr-language por+eng --export-text
```

| Opção | Efeito |
| --- | --- |
| `-o`, `--output ARQUIVO` | Destino do PDF. Padrão: `ID.pdf` na pasta atual. |
| `--resume` | Continua uma captura interrompida, pulando as páginas já salvas. |
| `--reuse` | Gera o PDF a partir de uma captura completa, sem abrir o navegador. |
| `--compact` | Usa JPEG nas páginas em que ele fica menor que o PNG. |
| `--ocr` | Adiciona texto pesquisável e selecionável ao PDF. |
| `--ocr-language IDIOMA` | Idioma do OCR. Padrão: `por`. |
| `--export-text` | Salva o texto reconhecido em um `.txt` ao lado do PDF. Exige `--ocr`. |
| `--captures-dir PASTA` | Usa outra pasta para salvar e procurar capturas. |

`--resume` e `--reuse` não podem ser usados juntos. Se a captura for interrompida com `Ctrl+C`, as páginas já salvas são mantidas; rode o mesmo comando com `--resume` para continuar.

## OCR (opcional)

| Sistema | Instalação |
| --- | --- |
| Fedora | `sudo dnf install ocrmypdf tesseract-langpack-por tesseract-langpack-eng` |
| Debian e Ubuntu | `sudo apt install ocrmypdf tesseract-ocr-por tesseract-ocr-eng` |
| macOS | `brew install ocrmypdf tesseract-lang` |
| Windows | Siga a [documentação do OCRmyPDF](https://ocrmypdf.readthedocs.io/en/latest/installation.html). |

Códigos comuns de idioma: `por` (português), `eng` (inglês), `spa` (espanhol), `fra` (francês) e `deu` (alemão). Combine idiomas com `+`, como em `por+eng`. Se faltar o modelo de algum idioma, o próprio OCRmyPDF avisa no erro; confira os instalados com `tesseract --list-langs`.

Se o OCR falhar ou for interrompido, o PDF só com as imagens continua salvo. Para tentar de novo sem recapturar, use `--reuse --ocr`.

## Onde ficam as capturas

As capturas ficam em `~/.scribd-to-pdf/captures/`, ou na pasta indicada em `--captures-dir`. Cada documento tem uma pasta com o seu ID, com as imagens (`page_0001.png`, `page_0002.png`, ...) e um `capture.json` que guarda o total de páginas.

## Testes

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

Os testes não acessam o Scribd. Os do leitor abrem páginas HTML locais no Chromium do Playwright e são ignorados quando ele não está instalado.

## Arquitetura

O código segue uma Clean Architecture leve, com as dependências apontando para dentro:

| Em `src/scribd_to_pdf/` | Responsabilidade |
| --- | --- |
| `domain/` | `Document`: valida o link e extrai o ID do documento. |
| `application/` | Caso de uso `DocumentConverter`, portas (`ports.py`) e `ConversionError`. |
| `infrastructure/` | Adaptadores: leitor com Playwright, capturas em disco, PDF com img2pdf e OCR com ocrmypdf. |
| `ui/` | Linha de comando. |
| `bootstrap.py` | Monta os adaptadores e os injeta no caso de uso. |

## Licença

[MIT](LICENSE) © 2026 João Mário Abreu
