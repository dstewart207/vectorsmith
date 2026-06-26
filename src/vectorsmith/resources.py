"""Packaged application resources."""

from __future__ import annotations

from importlib.resources import files

from PyQt6.QtGui import QIcon


def app_icon() -> QIcon:
    logo_path = files("vectorsmith").joinpath("assets/vectorsmith-logo.png")
    return QIcon(str(logo_path))
