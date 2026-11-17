"""Marker tool dock: multi-marker entry, search, and readout."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vectorsmith.session import Session


class MarkerDock(QDockWidget):
    marker_changed = pyqtSignal()
    search_requested = pyqtSignal(str)  # min | max | bw3db | tdr_peak | tdr_step

    def __init__(self, parent=None) -> None:
        super().__init__("Marker", parent)
        self.setObjectName("MarkerDock")
        container = QWidget()
        layout = QVBoxLayout(container)

        self._enabled = QCheckBox("Enable markers")
        self._enabled.stateChanged.connect(self._emit)
        layout.addWidget(self._enabled)

        row = QHBoxLayout()
        self._marker_list = QComboBox()
        self._marker_list.currentIndexChanged.connect(self._on_active_changed)
        row.addWidget(self._marker_list, stretch=1)
        self._add_btn = QPushButton("Add")
        self._add_btn.clicked.connect(self._on_add)
        row.addWidget(self._add_btn)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.clicked.connect(self._on_remove)
        row.addWidget(self._remove_btn)
        layout.addLayout(row)

        form = QFormLayout()
        self._freq = QDoubleSpinBox()
        self._freq.setDecimals(6)
        self._freq.setSuffix(" GHz")
        self._freq.setEnabled(False)
        self._freq.valueChanged.connect(self._on_x_changed)
        self._axis_label = "Frequency:"
        form.addRow(self._axis_label, self._freq)
        self._form = form
        layout.addLayout(form)

        search_row = QHBoxLayout()
        self._min_btn = QPushButton("Min")
        self._min_btn.clicked.connect(lambda: self.search_requested.emit("min"))
        search_row.addWidget(self._min_btn)
        self._max_btn = QPushButton("Max")
        self._max_btn.clicked.connect(lambda: self.search_requested.emit("max"))
        search_row.addWidget(self._max_btn)
        self._bw_btn = QPushButton("−3 dB BW")
        self._bw_btn.clicked.connect(lambda: self.search_requested.emit("bw3db"))
        search_row.addWidget(self._bw_btn)
        layout.addLayout(search_row)

        tdr_row = QHBoxLayout()
        self._tdr_peak_btn = QPushButton("TDR peak")
        self._tdr_peak_btn.clicked.connect(lambda: self.search_requested.emit("tdr_peak"))
        tdr_row.addWidget(self._tdr_peak_btn)
        self._tdr_step_btn = QPushButton("TDR step")
        self._tdr_step_btn.clicked.connect(lambda: self.search_requested.emit("tdr_step"))
        tdr_row.addWidget(self._tdr_step_btn)
        layout.addLayout(tdr_row)

        layout.addWidget(QLabel("Values at markers:"))
        self._readout = QTextEdit()
        self._readout.setReadOnly(True)
        self._readout.setMaximumHeight(180)
        layout.addWidget(self._readout)

        self.setWidget(container)
        self._syncing = False
        self._x_min = 0.0
        self._x_max = 1.0

    def _emit(self, *_args) -> None:
        if not self._syncing:
            self.marker_changed.emit()

    def _on_active_changed(self, *_args) -> None:
        if self._syncing:
            return
        # Selection must not write the previous spinbox value onto the new marker.
        self._pending_action = "select"
        self._emit()

    def _on_x_changed(self, *_args) -> None:
        if self._syncing:
            return
        self._pending_action = "move"
        self._emit()

    def _on_add(self) -> None:
        if self._syncing:
            return
        self._pending_action = "add"
        self._emit()

    def _on_remove(self) -> None:
        if self._syncing:
            return
        self._pending_action = "remove"
        self._emit()

    def consume_pending_action(self) -> str | None:
        action = getattr(self, "_pending_action", None)
        self._pending_action = None
        return action

    def is_enabled(self) -> bool:
        return self._enabled.isChecked()

    def set_enabled(self, on: bool) -> None:
        self._syncing = True
        self._enabled.setChecked(on)
        self._freq.setEnabled(on)
        self._marker_list.setEnabled(on)
        self._add_btn.setEnabled(on)
        self._remove_btn.setEnabled(on)
        self._min_btn.setEnabled(on)
        self._max_btn.setEnabled(on)
        self._bw_btn.setEnabled(on)
        self._tdr_peak_btn.setEnabled(on)
        self._tdr_step_btn.setEnabled(on)
        self._syncing = False

    def set_freq_range(self, f_min_ghz: float, f_max_ghz: float) -> None:
        self._x_min = f_min_ghz
        self._x_max = f_max_ghz
        self._syncing = True
        self._freq.setRange(f_min_ghz, f_max_ghz)
        if self._freq.value() < f_min_ghz or self._freq.value() > f_max_ghz:
            self._freq.setValue(f_min_ghz)
        self._syncing = False

    def freq_ghz(self) -> float:
        return self._freq.value()

    def set_freq_ghz(self, value: float) -> None:
        self._syncing = True
        self._freq.setValue(value)
        self._syncing = False

    def active_marker_id(self) -> int | None:
        return self._marker_list.currentData()

    def set_readout(self, text: str) -> None:
        self._readout.setPlainText(text)

    def set_axis(self, label: str, suffix: str, decimals: int = 6) -> None:
        self._freq.setSuffix(suffix)
        self._freq.setDecimals(decimals)
        self._form.labelForField(self._freq).setText(label)

    def sync_from_session(self, session: Session) -> None:
        """Refresh marker list and active X from session state."""
        self._syncing = True
        self._enabled.setChecked(session.markers_enabled)
        enabled = session.markers_enabled
        self._freq.setEnabled(enabled)
        self._marker_list.setEnabled(enabled)
        self._add_btn.setEnabled(enabled)
        self._remove_btn.setEnabled(enabled)
        self._min_btn.setEnabled(enabled)
        self._max_btn.setEnabled(enabled)
        self._bw_btn.setEnabled(enabled)
        self._tdr_peak_btn.setEnabled(enabled)
        self._tdr_step_btn.setEnabled(enabled)

        self._marker_list.clear()
        for marker in session.markers:
            self._marker_list.addItem(marker.label, marker.marker_id)
        if session.active_marker_id is not None:
            idx = self._marker_list.findData(session.active_marker_id)
            if idx >= 0:
                self._marker_list.setCurrentIndex(idx)
        active = session.active_marker()
        if active is not None:
            self._freq.setValue(active.x)
        self._syncing = False

    def apply_to_session(self, session: Session) -> None:
        """Push dock edits into session (enable/active/x/add/remove)."""
        action = self.consume_pending_action()
        session.markers_enabled = self.is_enabled()
        if action == "add":
            x = self._freq.value() if session.markers else self._x_min
            if session.markers:
                # Place new marker near mid-span.
                x = 0.5 * (self._x_min + self._x_max)
            session.add_marker(x)
        elif action == "remove":
            marker_id = self._marker_list.currentData()
            if marker_id is not None:
                session.remove_marker(int(marker_id))
        elif action == "select":
            marker_id = self._marker_list.currentData()
            if marker_id is not None:
                session.active_marker_id = int(marker_id)
            # Intentionally do not write spinbox X onto the newly selected marker.
        elif action == "move":
            marker_id = self._marker_list.currentData()
            if marker_id is not None:
                session.active_marker_id = int(marker_id)
            active = session.active_marker()
            if active is not None and session.markers_enabled:
                active.x = self._freq.value()
        if session.markers_enabled and not session.markers:
            session.add_marker(self._x_min)
