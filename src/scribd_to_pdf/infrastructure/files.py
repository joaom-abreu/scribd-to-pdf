from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile


@contextmanager
def atomic_target(target: Path, *, directory_mode: int = 0o777) -> Iterator[Path]:
    target.parent.mkdir(parents=True, exist_ok=True, mode=directory_mode)

    with NamedTemporaryFile(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    ) as file:
        temporary = Path(file.name)

    try:
        yield temporary
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def write_text_atomically(target: Path, text: str, *, directory_mode: int = 0o777) -> None:
    with atomic_target(target, directory_mode=directory_mode) as temporary:
        temporary.write_text(text, encoding="utf-8")
