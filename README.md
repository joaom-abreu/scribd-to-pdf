# scribd-to-pdf

Aplicativo em Python para capturar as páginas exibidas no leitor do Scribd e reuni-las, na ordem, em um PDF. Pode ser usado pela interface gráfica ou pelo terminal.

O OCR opcional reconhece o texto das imagens para permitir buscas, seleção e cópia no PDF. Também é possível salvar esse texto em um arquivo `.txt` para consultar e editar.

## Recursos

- Captura das páginas com Chromium, controlado pelo Playwright, com a interface do leitor em inglês.
- Fechamento automático do aviso de privacidade, quando ele é reconhecido.
- Até três tentativas para cada página que demora a carregar.
- Geração de PDF a partir das imagens salvas.
- Retomada de capturas interrompidas e reutilização de capturas completas.
- OCR com um ou mais idiomas e verificação dos modelos instalados antes da captura.
- Interrupção do OCR preservando o PDF com as imagens.
- Exportação do texto reconhecido para `.txt`.
- Botões **Abrir PDF** e **Abrir pasta** na interface gráfica.
- Preferências da interface salvas entre execuções: pasta de destino, OCR, idiomas e exportação de texto.

## Requisitos

- Python **3.12 ou superior**, com `pip` e `venv`.
- Git para obter o código.
- Tkinter para usar a interface gráfica.
- Chromium instalado pelo Playwright.
- Ambiente gráfico e conexão com a internet para capturar ou retomar páginas.
- Para OCR: OCRmyPDF, Tesseract e os modelos dos idiomas escolhidos, disponíveis no `PATH`.

O PDF é montado a partir das páginas capturadas no navegador. A captura depende do carregamento das páginas e da estrutura do leitor do Scribd. O reconhecimento de texto depende da qualidade dessas imagens e dos idiomas selecionados.

## Instalação

### Preparar o sistema

Instale Python 3.12 ou superior, Git e o suporte a Tkinter correspondente à sua instalação do Python. Os pacotes e comandos de instalação variam conforme o sistema operacional.

Consulte os [requisitos de sistema do Playwright](https://playwright.dev/python/docs/intro#system-requirements) para o navegador e a [documentação do Tkinter](https://docs.python.org/3/library/tkinter.html) para a interface.

### Obter o projeto

```bash
git clone https://github.com/joaom-abreu/scribd-to-pdf.git
cd scribd-to-pdf
```

Execute a instalação dentro dessa pasta, onde está o arquivo `pyproject.toml`.

### Linux e macOS

Confira a versão do Python e crie um ambiente virtual:

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
```

Ao abrir um novo terminal, entre novamente na pasta do projeto e ative o ambiente com `source .venv/bin/activate` antes de usar os comandos deste README.

Em distribuições Linux atendidas pelo instalador de dependências do Playwright, o comando abaixo instala também as bibliotecas de sistema exigidas pelo Chromium:

```bash
python -m playwright install --with-deps chromium
```

Se o navegador indicar bibliotecas ausentes, instale-as pelo gerenciador de pacotes do sistema, seguindo as mensagens do Playwright.

### Windows — PowerShell

Use o Python do ambiente virtual diretamente:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m playwright install chromium
```

Para abrir a interface:

```powershell
.\.venv\Scripts\python.exe -m scribd_to_pdf.ui.gui
```

Nos exemplos de terminal abaixo, substitua `scribd-to-pdf` por `.\.venv\Scripts\python.exe -m scribd_to_pdf.ui.cli`.

## Preparar o OCR

Instale o OCRmyPDF e os modelos do Tesseract antes de habilitar o OCR. Essa instalação é separada da instalação Python do projeto.

Siga as [instruções oficiais de instalação do OCRmyPDF](https://ocrmypdf.readthedocs.io/en/latest/installation.html) para seu sistema operacional, incluindo suas dependências e os modelos dos idiomas que deseja usar.

Confira a instalação no mesmo terminal usado para executar o aplicativo:

```bash
ocrmypdf --version
tesseract --list-langs
```

| Idioma | Código do Tesseract |
| --- | --- |
| Português | `por` |
| Inglês | `eng` |
| Espanhol | `spa` |
| Francês | `fra` |
| Alemão | `deu` |

Na interface, marque os idiomas presentes no documento. No terminal, combine os códigos com `+`, como `por+eng`. Português é o idioma padrão.

Ao iniciar uma conversão com OCR, o aplicativo verifica se os comandos necessários e todos os modelos escolhidos estão disponíveis. Se faltar algum modelo, a interface mostra um aviso e o terminal informa o erro antes de abrir o navegador.

## Usar a interface gráfica

Com o ambiente virtual ativo no Linux ou macOS:

```bash
scribd-to-pdf-gui
```

1. Cole o link HTTPS do documento no campo **Link do documento**.
2. Se quiser escolher o nome e o destino do PDF, clique em **Escolher...**. O arquivo deve ter a extensão `.pdf`.
3. Selecione o modo de captura na tabela abaixo.
4. Para reconhecer o texto, marque **Adicionar texto pesquisável e selecionável (OCR)** e escolha os idiomas. Para gerar o TXT, marque também **Salvar também o texto reconhecido em .txt**.
5. Clique em **Iniciar**.
6. Quando o navegador abrir, aguarde a capa carregar. O aplicativo tenta fechar sozinho o aviso de privacidade; se ele ou outra janela continuar cobrindo o documento, feche-os.
7. Volte à interface e clique em **Capturar páginas**. O aplicativo ativa o modo Fullscreen e começa a captura.
8. Ao concluir, use **Abrir PDF** para ler o resultado ou **Abrir pasta** para acessar os arquivos, incluindo o TXT quando solicitado.

| Modo | Quando usar |
| --- | --- |
| **Nova captura** | Capturar novamente todas as páginas do documento. |
| **Retomar captura** | Continuar uma captura incompleta, aproveitando as páginas já salvas. |
| **Usar captura completa** | Gerar o PDF a partir de todas as páginas já salvas, sem abrir o navegador. Também permite aplicar OCR novamente. |

Em **Usar captura completa**, não há a etapa de confirmação no navegador. É preciso que a captura esteja completa e que suas imagens continuem na [pasta de capturas](#arquivos-gerados).

### Destino e preferências

Se o campo de destino estiver vazio, o aplicativo salva o PDF na pasta lembrada da execução anterior, usando o ID do documento como nome. Se nenhuma pasta tiver sido escolhida, salva `ID.pdf` na pasta de onde o aplicativo foi iniciado.

A interface lembra a **pasta**, sem preencher novamente o nome do arquivo anterior. Também lembra se o OCR está ativado, os idiomas marcados e a opção de exportar texto. As escolhas são salvas ao selecionar um destino, iniciar uma conversão válida ou fechar a janela.

## Usar pelo terminal

Nos comandos abaixo, substitua `LINK_DO_DOCUMENTO` pela URL HTTPS do documento, no formato `https://www.scribd.com/document/ID/TITULO`, com um ID numérico. O título no final da URL é opcional.

Capture as páginas e gere o PDF no destino padrão:

```bash
scribd-to-pdf "LINK_DO_DOCUMENTO"
```

Quando o navegador abrir, aguarde a capa carregar, feche os avisos que ainda cobrirem o documento e pressione **Enter no terminal**. O aplicativo ativa o Fullscreen e inicia a captura.

Escolha o destino e reconheça texto em português e inglês, salvando também o TXT:

```bash
scribd-to-pdf "LINK_DO_DOCUMENTO" -o "livro.pdf" --ocr --ocr-language por+eng --export-text
```

Retome uma captura interrompida:

```bash
scribd-to-pdf "LINK_DO_DOCUMENTO" --resume
```

Gere novamente o PDF e aplique OCR a uma captura completa, sem abrir o navegador:

```bash
scribd-to-pdf "LINK_DO_DOCUMENTO" --reuse -o "livro.pdf" --ocr --ocr-language por+eng --export-text
```

| Opção | Comportamento |
| --- | --- |
| `-o ARQUIVO`, `--output ARQUIVO` | Define o destino do PDF. Padrão: `ID.pdf` na pasta atual. Exige extensão `.pdf`. |
| `--captures-dir PASTA` | Define onde as capturas são salvas e procuradas por `--resume` e `--reuse`. Padrão: a pasta de capturas do sistema, descrita em [Arquivos gerados](#arquivos-gerados). |
| `--resume` | Retoma uma captura incompleta. Abre o navegador e aguarda a confirmação. |
| `--reuse` | Usa uma captura completa salva. Dispensa o navegador e o acesso ao Scribd. |
| `--ocr` | Adiciona texto pesquisável e selecionável ao PDF. |
| `--ocr-language IDIOMA` | Escolhe o idioma do OCR. Padrão: `por`. Aceita combinações, como `por+eng`. |
| `--export-text` | Salva o texto reconhecido em um `.txt` ao lado do PDF. Exige `--ocr`. |
| `-h`, `--help` | Mostra a ajuda. |

`--resume` e `--reuse` são mutuamente exclusivos. No terminal, os parâmetros são definidos em cada comando; as preferências salvas pela interface gráfica não são aplicadas.

## Arquivos gerados

`ID` é o número que aparece na URL do documento. As capturas ficam na pasta de dados do usuário, independentemente da pasta de onde o aplicativo é iniciado:

| Sistema | Pasta de capturas |
| --- | --- |
| Linux | `~/.local/share/scribd-to-pdf/captures/`, ou `$XDG_DATA_HOME/scribd-to-pdf/captures/` quando essa variável aponta para um caminho absoluto. |
| macOS | `~/Library/Application Support/scribd-to-pdf/captures/` |
| Windows | `%LOCALAPPDATA%\scribd-to-pdf\captures\`, com fallback para `AppData\Local` na pasta do usuário. |

No terminal, `--captures-dir PASTA` usa outra pasta no lugar dessa.

| Arquivo | Conteúdo |
| --- | --- |
| `CAPTURAS/ID/page_0001.png`, `page_0002.png`, ... | Imagens das páginas, numeradas na ordem do documento. |
| `CAPTURAS/ID/capture.json` | Registro do documento, do total de páginas e do progresso da captura. |
| `ID.pdf` na pasta atual ou o destino escolhido | PDF montado a partir das imagens, com texto pesquisável quando o OCR é concluído. |
| Mesmo destino e nome do PDF, com extensão `.txt` | Texto reconhecido pelo OCR, quando a exportação está ativada. Por exemplo: `livro.pdf` e `livro.txt`. |

Mantenha as imagens e o `capture.json` para retomar ou reutilizar a captura.

Versões anteriores salvavam as capturas em `output/`, dentro da pasta de execução. Para aproveitá-las, mova as pastas `output/ID/` para a pasta de capturas ou, no terminal, use `--captures-dir output` a partir da mesma pasta de antes.

O TXT é salvo em UTF-8 usando a saída `--sidecar` do OCRmyPDF. Ele contém o texto reconhecido; revise possíveis erros de OCR antes de usar ou editar o conteúdo.

### Interromper e continuar

- **Durante a captura:** clique em **Interromper** na interface ou pressione **Ctrl+C** no terminal. As páginas concluídas ficam salvas. Para continuar, use **Retomar captura** ou `--resume`.
- **Durante o OCR:** use **Interromper** ou **Ctrl+C**. O processo de OCR é encerrado e o PDF já montado com as imagens é preservado. Um TXT parcial dessa execução não é publicado; um TXT anterior é mantido.
- **Para tentar o OCR novamente:** use **Usar captura completa** ou `--reuse --ocr`, acrescentando `--export-text` se quiser o TXT.

Na interface, **Interromper** fica temporariamente desativado durante a montagem do PDF e volta a ficar disponível na etapa de OCR. Aguarde a confirmação da interrupção antes de iniciar outra operação. Se o OCR for interrompido, os botões de abrir o PDF e sua pasta permitem acessar o arquivo preservado.

### Onde ficam as preferências

| Sistema | Arquivo |
| --- | --- |
| Linux | `~/.config/scribd-to-pdf/preferences.json`, ou `$XDG_CONFIG_HOME/scribd-to-pdf/preferences.json` quando essa variável aponta para um caminho absoluto. |
| macOS | `~/Library/Application Support/scribd-to-pdf/preferences.json` |
| Windows | `%APPDATA%\scribd-to-pdf\preferences.json`, com fallback para `AppData\Roaming` na pasta do usuário. |

Na primeira execução, o OCR e a exportação de texto estão desativados, com português selecionado. Se as preferências estiverem ausentes ou não puderem ser lidas, a interface usa os valores padrão.

## Problemas comuns

| Problema | O que verificar |
| --- | --- |
| Comando `scribd-to-pdf` ou `scribd-to-pdf-gui` não encontrado | Entre na pasta do projeto, ative o ambiente virtual e confira a instalação com `python -m pip install -e .`. No Windows, use os caminhos completos indicados na instalação. |
| Chromium não encontrado | Execute `python -m playwright install chromium` com o Python do ambiente virtual. No Windows, use `.\.venv\Scripts\python.exe -m playwright install chromium`. |
| Erro ao importar `tkinter` | Instale o suporte a Tkinter para a versão de Python usada pelo ambiente virtual, conforme as instruções do seu sistema operacional. |
| OCRmyPDF, Tesseract ou idioma não encontrado | Confira `ocrmypdf --version` e `tesseract --list-langs` no terminal usado para iniciar o aplicativo. Instale os comandos ou modelos indicados pelo erro. |
| Captura salva não encontrada ou incompleta | Confira a pasta de capturas (ou a indicada em `--captures-dir`), as imagens e o `capture.json`. Use `--resume` para uma captura incompleta e `--reuse` somente depois de concluí-la. |
| Captura não avança no leitor | Confira se a capa carregou e se há avisos sobre o documento. O navegador é aberto em inglês para que o código encontre o botão **Fullscreen** e o contador de páginas; mudanças no leitor podem exigir ajuste nos seletores. |
| Página demora a carregar | Cada página é tentada até três vezes, com pausas crescentes. Se ainda assim falhar, as páginas anteriores ficam salvas; use **Retomar captura** ou `--resume`. |
| **Abrir PDF** ou **Abrir pasta** falha no Linux | Confira se `xdg-open` está disponível e se há um aplicativo associado a PDFs. |

## Desenvolvimento

Na pasta do projeto, com o ambiente virtual ativo, instale as dependências de desenvolvimento e rode os testes:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

No Windows, use `.\.venv\Scripts\python.exe` no lugar de `python`. A suíte usa arquivos locais e simulações de navegador e OCR, sem acessar o Scribd. Os testes do leitor abrem páginas HTML locais no Chromium do Playwright e são ignorados quando ele não está instalado.

O código segue a Clean Architecture: as dependências apontam para dentro, e a aplicação conhece apenas as interfaces que ela mesma define.

| Pasta em `src/scribd_to_pdf/` | Responsabilidade |
| --- | --- |
| `domain/` | Regras sem dependências externas: documento e validação da URL, progresso da captura, idiomas e cancelamento. |
| `application/` | Caso de uso `DocumentConverter`, que coordena captura, montagem do PDF e OCR, e as portas em `ports.py` (`CaptureRepository`, `PageCapturer`, `PdfBuilder`, `TextRecognizer`). Não importa nada da infraestrutura. |
| `infrastructure/` | Adaptadores que implementam as portas: leitor do Scribd com Playwright (`reader.py`), capturas salvas (`storage.py`), PDF (`pdf.py`) e OCR (`ocr.py`), além de preferências, gravação atômica de arquivos e abertura pelo sistema. |
| `ui/` | Interfaces de terminal (`cli.py`) e gráfica (`gui.py`), que montam o pedido e exibem o progresso. |
| `bootstrap.py` | Raiz de composição: cria os adaptadores e os injeta no `DocumentConverter` usado pelas interfaces. |

Os adaptadores convertem as falhas do Playwright, do pypdf, do img2pdf e do OCRmyPDF em `ConversionError` (`application/errors.py`), então as interfaces tratam um único tipo de erro e não importam essas bibliotecas. Nos testes, o caso de uso recebe dublês das portas, sem substituir funções dos módulos.

Documentação das ferramentas: [Playwright](https://playwright.dev/python/), [OCRmyPDF](https://ocrmypdf.readthedocs.io/en/latest/), [Tesseract](https://tesseract-ocr.github.io/tessdoc/).

## Licença

[MIT](LICENSE) — Copyright (c) 2026 João Mário Abreu.
