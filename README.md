# Scribd to PDF

Aplicativo em Python para reunir páginas de documentos em um único PDF,
preservando a aparência e a numeração original.

A primeira integração prevista é com o Scribd, para materiais com
permissão de cópia.

## Estado atual

O programa recebe e valida links de documentos do Scribd.
Abre o visualizador em Fullscreen e captura as três primeiras
páginas em sequência, salvando as imagens na pasta output.

Esta etapa testa a navegação e a captura de várias páginas.

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