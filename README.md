# Scribd to PDF

Aplicativo em Python para reunir páginas de documentos em um único PDF,
preservando a aparência e a numeração original.

A primeira integração prevista é com o Scribd, para materiais com
permissão de cópia.

## Estado atual

O programa recebe um link de documento do Scribd, valida seu formato,
identifica o ID e normaliza o endereço.

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
```

Execute:

```bash
scribd-to-pdf "link"
```