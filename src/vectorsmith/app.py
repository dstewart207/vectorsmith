"""Application entry point."""

from __future__ import annotations

import ctypes
import sys

from PyQt6.QtWidgets import QApplication

from vectorsmith.resources import app_icon
from vectorsmith.ui.main_window import MainWindow


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    app_id = "VectorSmith.VectorSmith.0.1"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)


def main() -> int:
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("VectorSmith")
    app.setWindowIcon(app_icon())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
