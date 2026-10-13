import os
import sys
from pathlib import Path


def main() -> None:
    if getattr(sys, "frozen", False):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

        workspace = Path.home() / "scribd-to-pdf"
        workspace.mkdir(parents=True, exist_ok=True)
        os.chdir(workspace)

    from scribd_to_pdf.gui import main as start_gui

    start_gui()


if __name__ == "__main__":
    main()