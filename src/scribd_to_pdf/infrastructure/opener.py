import os
import shutil
import subprocess
import sys
from pathlib import Path


def open_path(path: Path) -> None:
    path = path.expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"O caminho não existe: {path}")

    if sys.platform == "win32":
        os.startfile(str(path))
        return

    command = "open" if sys.platform == "darwin" else "xdg-open"
    executable = shutil.which(command)

    if executable is None:
        raise OSError(
            f"O comando '{command}' não foi encontrado. "
            "No Linux, instale o pacote xdg-utils."
        )

    result = subprocess.run(
        [executable, str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=True,
        check=False,
    )

    if result.returncode != 0:
        detail = result.stderr.strip() or f"código {result.returncode}"
        raise OSError(f"Não foi possível abrir {path}: {detail}")