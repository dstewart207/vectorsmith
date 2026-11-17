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
        self._marker_callback: Callable[[float, int | None], None] | None = None
        self._marker_xs: list[tuple[int, float]] = []  # (marker_id, x)
        self._active_marker_id: int | None = None
        self._marker_dragging = False
        self._drag_marker_id: int | None = None
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
        callback: Callable[..., None],
        marker_freq_ghz: float | None = None,
        *,
        markers: list[tuple[int, float]] | None = None,
        active_marker_id: int | None = None,
    ) -> None:
        """
        Connect click/drag marker interaction.

        callback(x, marker_id=None) — marker_id is set when dragging an existing marker.
        """
        marker_list = markers
        if marker_list is None and marker_freq_ghz is not None:
            marker_list = [(active_marker_id or 1, marker_freq_ghz)]
        marker_list = marker_list or []

        if self._marker_cids and self._marker_callback == callback:
            self._marker_xs = list(marker_list)
            self._active_marker_id = active_marker_id
            return
        self.disconnect_marker_interaction()
        self._marker_callback = callback
        self._marker_xs = list(marker_list)
        self._active_marker_id = active_marker_id
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
        self._marker_xs = []
        self._active_marker_id = None
        self._marker_dragging = False
        self._drag_marker_id = None

    def connect_marker_click(self, callback: Callable[[float], None]) -> None:
        self.connect_marker_interaction(callback, None)

    def disconnect_marker_click(self) -> None:
        self.disconnect_marker_interaction()

    def _on_marker_press(self, event) -> None:
        if not self._marker_event_is_active(event):
            return
        near_id = self._nearest_marker_id(event)
        if near_id is None:
            # Click elsewhere moves the active marker.
            self._marker_dragging = True
            self._drag_marker_id = self._active_marker_id
            self._emit_marker_frequency(event, self._drag_marker_id)
            return
        self._marker_dragging = True
        self._drag_marker_id = near_id
        self._emit_marker_frequency(event, near_id)

    def _on_marker_motion(self, event) -> None:
        if not self._marker_dragging or not self._marker_event_is_active(event):
            return
        self._emit_marker_frequency(event, self._drag_marker_id)

    def _on_marker_release(self, _event) -> None:
        self._marker_dragging = False
        self._drag_marker_id = None

    def _marker_event_is_active(self, event) -> bool:
        if self._marker_callback is None:
            return False
        if event.button not in (None, 1, MouseButton.LEFT):
            return False
        if event.inaxes is None or event.xdata is None:
            return False
        mode = getattr(self.toolbar, "mode", "") or ""
        return not bool(mode)

    def _nearest_marker_id(self, event) -> int | None:
        if event.inaxes is None or not self._marker_xs:
            return None
        best_id = None
        best_dist = None
        for marker_id, x in self._marker_xs:
            marker_px, _ = event.inaxes.transData.transform((x, 0.0))
            dist = abs(event.x - marker_px)
            if dist <= MARKER_PICK_TOLERANCE_PX and (best_dist is None or dist < best_dist):
                best_dist = dist
                best_id = marker_id
        return best_id

    def _emit_marker_frequency(self, event, marker_id: int | None) -> None:
        if self._marker_callback is None or event.inaxes is None or event.xdata is None:
            return
        xmin, xmax = event.inaxes.get_xlim()
        lo, hi = sorted((float(xmin), float(xmax)))
        x_value = min(max(float(event.xdata), lo), hi)
        if marker_id is not None:
            self._marker_xs = [
                (mid, x_value if mid == marker_id else x) for mid, x in self._marker_xs
            ]
            self._active_marker_id = marker_id
        try:
            self._marker_callback(x_value, marker_id)
        except TypeError:
            # Backward-compatible single-arg callbacks.
            self._marker_callback(x_value)

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
