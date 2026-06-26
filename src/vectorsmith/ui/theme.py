"""Application theme helpers."""

from __future__ import annotations

import matplotlib as mpl
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication


LIGHT_MPL = {
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "black",
    "axes.labelcolor": "black",
    "axes.titlecolor": "black",
    "xtick.color": "black",
    "ytick.color": "black",
    "grid.color": "#b0b0b0",
    "text.color": "black",
    "legend.facecolor": "white",
    "legend.edgecolor": "#b0b0b0",
    "legend.labelcolor": "black",
    "savefig.facecolor": "white",
}

DARK_MPL = {
    "figure.facecolor": "#1f2329",
    "axes.facecolor": "#181b20",
    "axes.edgecolor": "#8b949e",
    "axes.labelcolor": "#e8ecf3",
    "axes.titlecolor": "#e8ecf3",
    "xtick.color": "#c9d1d9",
    "ytick.color": "#c9d1d9",
    "grid.color": "#6e7681",
    "text.color": "#e8ecf3",
    "legend.facecolor": "#1f2329",
    "legend.edgecolor": "#6e7681",
    "legend.labelcolor": "#e8ecf3",
    "savefig.facecolor": "#1f2329",
}


LIGHT_STYLESHEET = """
QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #4f5661;
    border-radius: 2px;
    background: #ffffff;
}
QCheckBox::indicator:hover {
    border-color: #0078d7;
}
QCheckBox::indicator:checked {
    background: #0078d7;
    border-color: #005a9e;
}
QCheckBox::indicator:checked:hover {
    background: #1683da;
}
QCheckBox::indicator:disabled {
    background: #eeeeee;
    border-color: #a8a8a8;
}
"""

DARK_STYLESHEET = """
QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #8b949e;
    border-radius: 2px;
    background: #181b20;
}
QCheckBox::indicator:hover {
    border-color: #79c0ff;
}
QCheckBox::indicator:checked {
    background: #4584d6;
    border-color: #79c0ff;
}
QCheckBox::indicator:disabled {
    background: #2a2f37;
    border-color: #6e7681;
}
"""


def _light_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(250, 250, 250))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(20, 20, 20))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(20, 20, 20))
    palette.setColor(QPalette.ColorRole.Text, QColor(20, 20, 20))
    palette.setColor(QPalette.ColorRole.Button, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(20, 20, 20))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 102, 204))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(120, 120, 120))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(120, 120, 120),
    )
    return palette


def _dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(31, 35, 41))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(232, 236, 243))
    palette.setColor(QPalette.ColorRole.Base, QColor(24, 27, 32))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(38, 43, 50))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(232, 236, 243))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(24, 27, 32))
    palette.setColor(QPalette.ColorRole.Text, QColor(232, 236, 243))
    palette.setColor(QPalette.ColorRole.Button, QColor(42, 47, 55))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(232, 236, 243))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 96, 96))
    palette.setColor(QPalette.ColorRole.Link, QColor(110, 168, 254))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(69, 132, 214))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(130, 138, 150))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(130, 138, 150),
    )
    return palette


def apply_theme(app: QApplication, dark: bool) -> None:
    app.setStyle("Fusion")
    app.setPalette(_dark_palette() if dark else _light_palette())
    app.setStyleSheet(DARK_STYLESHEET if dark else LIGHT_STYLESHEET)
    mpl.rcParams.update(DARK_MPL if dark else LIGHT_MPL)
