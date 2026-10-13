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

## Opções de execução

Por padrão, o PDF é salvo em `output/ID/ID.pdf`.

Para escolher o destino:

```bash
scribd-to-pdf "URL_DO_DOCUMENTO" --output "output/livro.pdf"
```

Para gerar novamente o PDF usando uma captura completa salva:

```bash
scribd-to-pdf "URL_DO_DOCUMENTO" --reuse
```

As opções podem ser combinadas:

```bash
scribd-to-pdf "URL_DO_DOCUMENTO" --reuse --output "output/livro.pdf"
```

As capturas ficam em `output/ID/`, junto ao arquivo `capture.json`,
que registra o total de páginas esperado. A reutilização exige
esse registro e a presença de todas as imagens correspondentes.

Execute os comandos na raiz do projeto.

### Retomar uma captura interrompida

O progresso é registrado após cada página capturada.

Para continuar uma captura:

```bash
scribd-to-pdf "URL_DO_DOCUMENTO" --resume
```

Também é possível escolher o destino do PDF:

```bash
scribd-to-pdf "URL_DO_DOCUMENTO" --resume --output "output/livro.pdf"
```

| Opção | Comportamento |
| --- | --- |
| Sem `--reuse` ou `--resume` | Inicia uma nova captura. |
| `--reuse` | Gera o PDF usando uma captura completa, sem abrir o navegador. |
| `--resume` | Abre o navegador e captura as páginas que faltam. |