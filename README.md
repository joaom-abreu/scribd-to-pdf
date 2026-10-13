# scribd-to-pdf

Aplicativo em Python que captura as páginas exibidas no leitor do
Scribd e reúne as imagens em um único PDF, preservando a ordem.

Oferece interface gráfica e execução pelo terminal.

## Recursos

- Captura de documentos com páginas de texto ou imagens.
- Geração de um único PDF.
- Escolha do destino do PDF.
- Retomada de capturas interrompidas.
- Geração de PDF usando uma captura completa já salva.
- Acompanhamento do progresso pela interface ou pelo terminal.

## Requisitos

- Python 3.12 ou superior.
- Tkinter disponível para utilizar a interface gráfica.
- Ambiente gráfico para abrir o navegador.
- Internet para instalar as dependências e capturar documentos.

A compatibilidade do navegador depende dos
[requisitos do Playwright](https://playwright.dev/python/docs/intro#system-requirements).

## Instalação

Baixe ou clone este repositório. Abra um terminal na raiz do
projeto, na pasta que contém `pyproject.toml`.

Escolha as instruções do seu sistema. Os comandos utilizam o
Python da `.venv` diretamente, sem precisar ativá-la.

### Linux

Instale Python, o suporte a ambientes virtuais e Tkinter pelo
gerenciador de pacotes da sua distribuição.

Verifique se o Python é 3.12 ou superior:

```bash
python3 --version
```

Confira o Tkinter; uma janela de demonstração deve abrir:

```bash
python3 -m tkinter
```

Feche essa janela e instale o projeto:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m playwright install chromium
```

#### Dependências do Chromium no Linux

Se o navegador informar que faltam bibliotecas, nas distribuições
oficialmente suportadas pelo Playwright é possível executar:

```bash
.venv/bin/python -m playwright install-deps chromium
```

Em outras distribuições, instale as bibliotecas indicadas pelo erro
usando o gerenciador de pacotes do sistema.

### macOS

Instale Python 3.12 ou superior pelo
[site oficial do Python](https://www.python.org/downloads/macos/).

Verifique a versão e o Tkinter:

```bash
python3 --version
python3 -m tkinter
```

Feche a janela de demonstração e instale o projeto:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m playwright install chromium
```

### Windows — PowerShell

Instale Python 3.12 ou superior pelo
[site oficial do Python](https://www.python.org/downloads/windows/).

Verifique a versão e o Tkinter:

```powershell
py -3 --version
py -3 -m tkinter
```

Feche a janela de demonstração e instale o projeto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Interface gráfica

Execute na raiz do projeto.

Linux e macOS:

```bash
.venv/bin/python -m scribd_to_pdf.gui
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m scribd_to_pdf.gui
```

1. Cole o link do documento.
2. Escolha o destino do PDF, se desejar.
3. Selecione o modo de captura.
4. Inicie a conversão.
5. Aguarde o documento aparecer no navegador e feche os avisos
   que estiverem sobre as páginas.
6. Volte à interface e clique em **Capturar páginas**.
7. Aguarde a mensagem com o caminho do PDF.

### Modos disponíveis

| Modo | Comportamento |
| --- | --- |
| Nova captura | Captura todas as páginas novamente. |
| Retomar captura | Aproveita o progresso salvo e captura as páginas restantes. |
| Usar captura completa | Gera o PDF a partir das imagens salvas, sem abrir o navegador. |

## Terminal

Substitua `LINK_DO_DOCUMENTO` pelo endereço do documento.

Linux e macOS:

```bash
.venv/bin/python -m scribd_to_pdf.cli "LINK_DO_DOCUMENTO"
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m scribd_to_pdf.cli "LINK_DO_DOCUMENTO"
```

Quando solicitado, prepare o documento no navegador e pressione
Enter no terminal para iniciar a captura.

### Opções

Acrescente as opções ao comando:

| Opção | Uso |
| --- | --- |
| `--output "livro.pdf"` | Define o destino do PDF. |
| `--resume` | Retoma uma captura interrompida. |
| `--reuse` | Usa uma captura completa já salva. |
| `--help` | Exibe a ajuda. |

Use `--resume` e `--reuse` separadamente.

## Arquivos gerados

Por padrão, os arquivos ficam em `output/<ID_DO_DOCUMENTO>/`:

- `page_0001.png`, `page_0002.png` etc.: imagens das páginas.
- `capture.json`: registro do progresso.
- `<ID_DO_DOCUMENTO>.pdf`: PDF final.

O caminho é relativo à pasta de onde o aplicativo foi executado.

Para retomar uma captura, mantenha as imagens e `capture.json`.

## Desenvolvimento

Instale as dependências de desenvolvimento e execute os testes
na raiz do projeto.

### Linux e macOS

```bash
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

### Windows — PowerShell

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes utilizam imagens geradas localmente e arquivos temporários.
Verificam a geração do PDF, a ordem das páginas, a preservação de
arquivos após falhas e a validação do progresso salvo para retomar
ou reutilizar capturas.