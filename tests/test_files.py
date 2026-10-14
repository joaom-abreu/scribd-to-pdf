import os
import stat
import sys
from pathlib import Path

import pytest

from scribd_to_pdf.infrastructure.files import DEFAULT_FILE_MODE, atomic_target, write_text_atomically

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Permissões POSIX.")


def current_umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


def file_mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_default_mode_follows_the_umask():
    assert DEFAULT_FILE_MODE == 0o666 & ~current_umask()


def test_written_file_uses_the_default_mode(tmp_path):
    target = tmp_path / "capture.json"

    write_text_atomically(target, "{}")

    assert file_mode(target) == DEFAULT_FILE_MODE


@pytest.mark.parametrize("mode", [0o600, 0o640, 0o644])
def test_written_file_uses_the_requested_mode(tmp_path, mode):
    target = tmp_path / "arquivo.txt"

    with atomic_target(target, file_mode=mode) as temporary:
        temporary.write_bytes(b"conteudo")

    assert file_mode(target) == mode
    assert list(tmp_path.iterdir()) == [target]
