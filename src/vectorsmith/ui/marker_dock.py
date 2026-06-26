"""Marker tool dock: frequency entry and readout."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class MarkerDock(QDockWidget):
    marker_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__("Marker", parent)
        self.setObjectName("MarkerDock")
        container = QWidget()
        layout = QVBoxLayout(container)

        self._enabled = QCheckBox("Enable marker")
        self._enabled.stateChanged.connect(self._emit)
        layout.addWidget(self._enabled)

        form = QFormLayout()
        self._freq = QDoubleSpinBox()
        self._freq.setDecimals(6)
        self._freq.setSuffix(" GHz")
        self._freq.setEnabled(False)
        self._freq.valueChanged.connect(self._emit)
        self._axis_label = "Frequency:"
        form.addRow(self._axis_label, self._freq)
        self._form = form
        layout.addLayout(form)

        layout.addWidget(QLabel("Values at marker:"))
        self._readout = QTextEdit()
        self._readout.setReadOnly(True)
        self._readout.setMaximumHeight(120)
        layout.addWidget(self._readout)

        self.setWidget(container)

    def _emit(self, *_args) -> None:
        self.marker_changed.emit()

    def is_enabled(self) -> bool:
        return self._enabled.isChecked()

    def set_enabled(self, on: bool) -> None:
        self._enabled.blockSignals(True)
        self._enabled.setChecked(on)
        self._enabled.blockSignals(False)
        self._freq.setEnabled(on)

    def set_freq_range(self, f_min_ghz: float, f_max_ghz: float) -> None:
        self._freq.blockSignals(True)
        self._freq.setRange(f_min_ghz, f_max_ghz)
        if self._freq.value() < f_min_ghz or self._freq.value() > f_max_ghz:
            self._freq.setValue(f_min_ghz)
        self._freq.blockSignals(False)

    def freq_ghz(self) -> float:
        return self._freq.value()

    def set_freq_ghz(self, value: float) -> None:
        self._freq.blockSignals(True)
        self._freq.setValue(value)
        self._freq.blockSignals(False)

    def set_readout(self, text: str) -> None:
        self._readout.setPlainText(text)

    def set_axis(self, label: str, suffix: str, decimals: int = 6) -> None:
        self._freq.setSuffix(suffix)
        self._freq.setDecimals(decimals)
        self._form.labelForField(self._freq).setText(label)
