import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "scribd-to-pdf-gui"

BROWSER_CHECK = """
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        channel="chromium",
        headless=True,
        timeout=30_000,
    )
    browser.close()
"""


def run_python(arguments: list[str], environment: dict[str, str]) -> None:
    subprocess.run(
        [sys.executable, *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )


def main() -> None:
    if sys.version_info < (3, 12):
        raise SystemExit("Utilize Python 3.12 ou superior.")

    for module in ("PyInstaller", "tkinter", "playwright", "img2pdf", "pypdf"):
        try:
            import_module(module)
        except (ImportError, OSError) as error:
            raise SystemExit(
                f"Falha ao carregar {module}: {error}"
            ) from error

    environment = os.environ.copy()
    environment["PLAYWRIGHT_BROWSERS_PATH"] = "0"

    build_dir = PROJECT_ROOT / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    print("Instalando o Chromium para incluir no pacote...", flush=True)
    run_python(
        ["-m", "playwright", "install", "chromium", "--no-shell"],
        environment,
    )

    print("Verificando se o Chromium inicia...", flush=True)
    run_python(["-c", BROWSER_CHECK], environment)

    print("Gerando o pacote da GUI...", flush=True)
    run_python(
        [
            "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--windowed",
            "--noupx",
            "--name", APP_NAME,
            "--paths", str(PROJECT_ROOT / "src"),
            "--collect-all", "playwright",
            "--specpath", str(build_dir),
            "--workpath", str(build_dir / "pyinstaller"),
            "--distpath", str(PROJECT_ROOT / "dist"),
            str(PROJECT_ROOT / "scripts" / "gui_entry.py"),
        ],
        environment,
    )

    bundle_name = f"{APP_NAME}.app" if sys.platform == "darwin" else APP_NAME
    print(f"Pacote criado em: {PROJECT_ROOT / 'dist' / bundle_name}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from error