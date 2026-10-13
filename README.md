# Scribd to PDF

Aplicativo em Python para reunir páginas de documentos em um único PDF,
preservando a aparência e a numeração original.

A primeira integração prevista é com o Scribd, para materiais com
permissão de cópia.

## Estado atual

O programa recebe um link de documento do Scribd, identifica
o total de páginas e captura as páginas em Fullscreen.

Depois, reúne as imagens em um PDF único e verifica sua
quantidade de páginas.

As imagens e o PDF são salvos em output/ID_DO_DOCUMENTO/.

## Desenvolvimento

Requer Python 3.12 ou superior.

Crie e ative o ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale o projeto para desenvolvimento:

```bash
python -m pip install -e .
python -m playwright install chromium
```

Execute:

```bash
scribd-to-pdf "link"
```