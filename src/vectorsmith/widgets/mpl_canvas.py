"""Matplotlib canvas embedded in Qt."""

from __future__ import annotations

from collections.abc import Callable

from matplotlib.backend_bases import MouseButton
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QVBoxLayout, QWidget


MARKER_PICK_TOLERANCE_PX = 8


class MplCanvasWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.figure = Figure(figsize=(8, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setObjectName("MatplotlibNavigationToolbar")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        self._marker_cids: list[int] = []
        self._marker_callback: Callable[[float], None] | None = None
        self._marker_freq_ghz: float | None = None
        self._marker_dragging = False
        self._toolbar_icons = {
            action: action.icon()
            for action in self.toolbar.actions()
            if not action.icon().isNull()
        }

    def clear_and_draw(self) -> None:
        self.canvas.draw_idle()

    def set_dark_theme(self, dark: bool) -> None:
        if not dark:
            for action, icon in self._toolbar_icons.items():
                action.setIcon(icon)
            return
        color = QColor("#f0f3f6" if dark else "#111111")
        for action, icon in self._toolbar_icons.items():
            action.setIcon(self._tinted_icon(icon, color))

    def connect_marker_interaction(
        self,
        callback: Callable[[float], None],
        marker_freq_ghz: float | None,
    ) -> None:
        if self._marker_cids and self._marker_callback == callback:
            self._marker_freq_ghz = marker_freq_ghz
            return
        self.disconnect_marker_interaction()
        self._marker_callback = callback
        self._marker_freq_ghz = marker_freq_ghz
        self._marker_cids = [
            self.canvas.mpl_connect("button_press_event", self._on_marker_press),
            self.canvas.mpl_connect("motion_notify_event", self._on_marker_motion),
            self.canvas.mpl_connect("button_release_event", self._on_marker_release),
        ]

    def disconnect_marker_interaction(self) -> None:
        for cid in self._marker_cids:
            self.canvas.mpl_disconnect(cid)
        self._marker_cids = []
        self._marker_callback = None
        self._marker_freq_ghz = None
        self._marker_dragging = False

    def connect_marker_click(self, callback: Callable[[float], None]) -> None:
        self.connect_marker_interaction(callback, None)

    def disconnect_marker_click(self) -> None:
        self.disconnect_marker_interaction()

    def _on_marker_press(self, event) -> None:
        if not self._marker_event_is_active(event):
            return
        if not self._is_near_marker_line(event):
            self._marker_dragging = False
            return
        self._marker_dragging = True
        self._emit_marker_frequency(event)

    def _on_marker_motion(self, event) -> None:
        if not self._marker_dragging or not self._marker_event_is_active(event):
            return
        self._emit_marker_frequency(event)

    def _on_marker_release(self, _event) -> None:
        self._marker_dragging = False

    def _marker_event_is_active(self, event) -> bool:
        if self._marker_callback is None:
            return False
        if event.button not in (None, 1, MouseButton.LEFT):
            return False
        if event.inaxes is None or event.xdata is None:
            return False
        mode = getattr(self.toolbar, "mode", "") or ""
        return not bool(mode)

    def _is_near_marker_line(self, event) -> bool:
        if self._marker_freq_ghz is None or event.inaxes is None:
            return False
        marker_x, _ = event.inaxes.transData.transform((self._marker_freq_ghz, 0.0))
        return abs(event.x - marker_x) <= MARKER_PICK_TOLERANCE_PX

    def _emit_marker_frequency(self, event) -> None:
        if self._marker_callback is None or event.inaxes is None or event.xdata is None:
            return
        xmin, xmax = event.inaxes.get_xlim()
        lo, hi = sorted((float(xmin), float(xmax)))
        freq_ghz = min(max(float(event.xdata), lo), hi)
        self._marker_freq_ghz = freq_ghz
        self._marker_callback(freq_ghz)

    @staticmethod
    def _tinted_icon(icon: QIcon, color: QColor) -> QIcon:
        tinted = QIcon()
        for size in (16, 24, 32):
            pixmap = icon.pixmap(QSize(size, size))
            if pixmap.isNull():
                continue
            image = pixmap.toImage()
            painter = QPainter(image)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(image.rect(), color)
            painter.end()
            tinted.addPixmap(QPixmap.fromImage(image), QIcon.Mode.Normal, QIcon.State.Off)
        return tinted if not tinted.isNull() else icon
