"""Application entrypoint for py-md-converter PySide6 GUI."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from mdconv.ui.main_window import MainWindow


def main() -> None:
    """Initializes and runs the PySide6 application."""
    # Ensure high DPI scaling is handled gracefully
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("py-md-converter")
    app.setOrganizationName("Data-AL")

    window = MainWindow()

    # If file paths were passed as CLI arguments, add them directly
    if len(sys.argv) > 1:
        initial_paths = [
            Path(arg)
            for arg in sys.argv[1:]
            if not arg.startswith("-") and Path(arg).exists()
        ]
        if initial_paths:
            window._add_paths(initial_paths)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
