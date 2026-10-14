# scribd-to-pdf

Aplicativo em Python que captura as páginas de um documento aberto no leitor do Scribd e as reúne, na ordem, em um único PDF. Funciona pela interface gráfica ou pelo terminal e pode aplicar OCR para deixar o texto pesquisável e selecionável.

## Recursos

- Captura das páginas com o Chromium, controlado pelo Playwright.
- Retomada de capturas interrompidas e reaproveitamento de capturas completas, sem abrir o navegador.
- PDF compacto opcional: usa JPEG só nas páginas em que ele fica menor que o PNG, como digitalizações e ilustrações.
- OCR opcional em um ou mais idiomas, com exportação do texto reconhecido para `.txt`.
- Interface gráfica que lembra as últimas escolhas e se ajusta à densidade da tela.

## Requisitos

- Python 3.12 ou superior, com `venv`.
- Tkinter, para a interface gráfica.
- Ambiente gráfico, porque a captura abre uma janela do navegador.
- Para o OCR: OCRmyPDF, Tesseract e os modelos dos idiomas desejados.

No Linux, prefira o Python da distribuição. Versões baixadas prontas pelo uv, pelo pyenv ou pelo conda costumam trazer um Tk sem suporte a Xft, o que deixa as fontes da interface minúsculas.

## Instalação

### Linux e macOS

```bash
git clone https://github.com/joaom-abreu/scribd-to-pdf.git
cd scribd-to-pdf
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m playwright install chromium
```

Para instalar o Tkinter no Linux, use `sudo dnf install python3-tkinter` no Fedora ou `sudo apt install python3-tk` no Debian e no Ubuntu. Se o Chromium indicar bibliotecas ausentes, instale-as pelo gerenciador de pacotes do sistema.

Em um terminal novo, entre na pasta do projeto e rode `source .venv/bin/activate` antes de usar o aplicativo.

### Windows (PowerShell)

```powershell
git clone https://github.com/joaom-abreu/scribd-to-pdf.git
cd scribd-to-pdf
py -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m playwright install chromium
```

Nos exemplos deste README, use `.venv\Scripts\scribd-to-pdf` e `.venv\Scripts\scribd-to-pdf-gui` no lugar dos comandos curtos.

### OCR (opcional)

| Sistema | Instalação |
| --- | --- |
| Fedora | `sudo dnf install ocrmypdf tesseract-langpack-por tesseract-langpack-eng` |
| Debian e Ubuntu | `sudo apt install ocrmypdf tesseract-ocr-por tesseract-ocr-eng` |
| macOS | `brew install ocrmypdf tesseract-lang` |
| Windows | Siga a [documentação do OCRmyPDF](https://ocrmypdf.readthedocs.io/en/latest/installation.html). |

Confira a instalação com `ocrmypdf --version` e `tesseract --list-langs`. O aplicativo aceita estes idiomas, que podem ser combinados com `+`, como em `por+eng`:

| Idioma | Código |
| --- | --- |
| Português | `por` |
| Inglês | `eng` |
| Espanhol | `spa` |
| Francês | `fra` |
| Alemão | `deu` |

Antes de abrir o navegador, o aplicativo verifica se os comandos e os idiomas escolhidos estão instalados.

## Interface gráfica

```bash
scribd-to-pdf-gui
```

1. Cole o link do documento, no formato `https://www.scribd.com/document/ID/titulo`.
2. Se quiser, escolha o destino do PDF, a compactação e o OCR.
3. Escolha o modo e clique em **Iniciar**.
4. No navegador, espere a capa carregar. O aviso de privacidade é fechado automaticamente quando reconhecido; feche o que ainda cobrir o documento.
5. Clique em **Capturar páginas**. Ao terminar, use **Abrir PDF** ou **Abrir pasta**.

| Modo | Quando usar |
| --- | --- |
| **Nova captura** | Capturar o documento do zero. |
| **Retomar captura** | Continuar uma captura interrompida, aproveitando as páginas já salvas. |
| **Usar captura completa** | Gerar o PDF de novo a partir de uma captura terminada, sem abrir o navegador. Serve para compactar ou aplicar OCR depois. |

A interface lembra a pasta de destino, a compactação, o OCR, os idiomas e a exportação de texto. Com o destino vazio, o PDF é salvo como `ID.pdf` na última pasta escolhida ou, se nenhuma foi escolhida, na pasta de onde o aplicativo foi aberto.

Se a interface ficar pequena ou grande demais, ajuste a escala com a variável `SCRIBD_TO_PDF_SCALE`, que aceita valores de 0.5 a 4:

```bash
SCRIBD_TO_PDF_SCALE=1.5 scribd-to-pdf-gui
```

## Linha de comando

```bash
scribd-to-pdf "https://www.scribd.com/document/ID/titulo"
```

Quando o navegador abrir, espere a capa carregar, feche os avisos que cobrirem o documento e pressione **Enter** no terminal.

Outros exemplos:

```bash
scribd-to-pdf "LINK" -o livro.pdf --ocr --ocr-language por+eng --export-text
scribd-to-pdf "LINK" --resume
scribd-to-pdf "LINK" --reuse --compact -o livro-compacto.pdf
```

| Opção | Efeito |
| --- | --- |
| `-o`, `--output ARQUIVO` | Destino do PDF. Padrão: `ID.pdf` na pasta atual. |
| `--resume` | Continua uma captura interrompida. |
| `--reuse` | Gera o PDF a partir de uma captura completa, sem abrir o navegador. |
| `--compact` | Usa JPEG (qualidade 85) nas páginas em que ele fica menor que o PNG. |
| `--ocr` | Adiciona texto pesquisável e selecionável ao PDF. |
| `--ocr-language IDIOMA` | Idioma do OCR, ou vários combinados com `+`. Padrão: `por`. |
| `--export-text` | Salva o texto reconhecido em um `.txt` ao lado do PDF. Exige `--ocr`. |
| `--captures-dir PASTA` | Usa outra pasta para salvar e procurar capturas. |

`--resume` e `--reuse` não podem ser usados juntos. As preferências da interface gráfica não valem para o terminal.

## Onde ficam os arquivos

O PDF vai para o destino escolhido, e o `.txt`, quando pedido, fica ao lado dele com o mesmo nome. As capturas e as preferências ficam nas pastas do usuário:

| Sistema | Capturas | Preferências |
| --- | --- | --- |
| Linux | `~/.local/share/scribd-to-pdf/captures/` | `~/.config/scribd-to-pdf/preferences.json` |
| macOS | `~/Library/Application Support/scribd-to-pdf/captures/` | `~/Library/Application Support/scribd-to-pdf/preferences.json` |
| Windows | `%LOCALAPPDATA%\scribd-to-pdf\captures\` | `%APPDATA%\scribd-to-pdf\preferences.json` |

No Linux, `XDG_DATA_HOME` e `XDG_CONFIG_HOME` são respeitadas quando definidas. Cada documento tem uma pasta com o seu ID, que guarda as imagens (`page_0001.png`, `page_0002.png`, ...) e o `capture.json`, usado para retomar e reaproveitar a captura.

Versões anteriores salvavam as capturas em `output/`, dentro da pasta de execução. Para aproveitá-las, mova as pastas de `output/` para a pasta de capturas ou use `--captures-dir output` no terminal.

## Interromper e retomar

- **Captura:** use **Interromper** ou `Ctrl+C`. As páginas já capturadas ficam salvas; continue com **Retomar captura** ou `--resume`.
- **Páginas lentas:** cada página é tentada até três vezes antes de a captura parar.
- **OCR:** ao interromper, o PDF com as imagens é preservado, assim como um `.txt` anterior. Para tentar de novo, use **Usar captura completa** ou `--reuse --ocr`.

## Problemas comuns

| Problema | Solução |
| --- | --- |
| Comando `scribd-to-pdf` não encontrado | Ative o ambiente virtual na pasta do projeto e rode `python -m pip install -e .` de novo. |
| Chromium não encontrado | Rode `python -m playwright install chromium` com o ambiente ativo. |
| Erro ao importar `tkinter` ou fontes minúsculas | Instale o Tkinter da distribuição e recrie o ambiente com o Python do sistema. |
| Idioma do OCR não encontrado | Instale o modelo indicado no erro e confira com `tesseract --list-langs`. |
| Captura não avança | Confira se a capa carregou e se algum aviso cobre o documento. Mudanças no leitor do Scribd podem exigir ajuste nos seletores de `reader.py`. |
| **Abrir PDF** falha no Linux | Confira se o `xdg-open` está instalado e se há um leitor de PDF padrão. |

## Desenvolvimento

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

Os testes não acessam o Scribd. Os do leitor abrem páginas HTML locais no Chromium do Playwright e são ignorados quando ele não está instalado.

O código segue a Clean Architecture, com as dependências apontando para dentro:

| Pasta em `src/scribd_to_pdf/` | Responsabilidade |
| --- | --- |
| `domain/` | Regras sem dependências externas: documento, progresso da captura, idiomas e cancelamento. |
| `application/` | Caso de uso `DocumentConverter`, portas (`ports.py`) e `ConversionError`. |
| `infrastructure/` | Adaptadores das portas: Playwright, capturas em disco, PDF, OCR, preferências e pastas do sistema. |
| `ui/` | Linha de comando, interface gráfica em Tkinter e o presenter, que concentra a lógica da interface e é testado sem Tk. |
| `bootstrap.py` | Monta os adaptadores e os injeta no caso de uso. |

## Licença

[MIT](LICENSE) © 2026 João Mário Abreu
