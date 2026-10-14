import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile


def _read_umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


DEFAULT_FILE_MODE = 0o666 & ~_read_umask()


@contextmanager
def atomic_target(
    target: Path,
    *,
    directory_mode: int = 0o777,
    file_mode: int = DEFAULT_FILE_MODE,
) -> Iterator[Path]:
    target.parent.mkdir(parents=True, exist_ok=True, mode=directory_mode)

    with NamedTemporaryFile(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    ) as file:
        temporary = Path(file.name)

    try:
        temporary.chmod(file_mode)
        yield temporary
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def write_text_atomically(
    target: Path,
    text: str,
    *,
    directory_mode: int = 0o777,
    file_mode: int = DEFAULT_FILE_MODE,
) -> None:
    with atomic_target(target, directory_mode=directory_mode, file_mode=file_mode) as temporary:
        temporary.write_text(text, encoding="utf-8")
