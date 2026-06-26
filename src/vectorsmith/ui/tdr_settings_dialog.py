"""Dialog for time-domain reflectometry settings."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
)

from vectorsmith.plots import TdrSettings


class TdrSettingsDialog(QDialog):
    def __init__(self, settings: TdrSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("TDR Settings")
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._z_default = QCheckBox("Use domain default")
        self._z_default.setChecked(settings.z_ref_ohms is None)
        self._z_ref = QDoubleSpinBox()
        self._z_ref.setRange(1.0, 10000.0)
        self._z_ref.setDecimals(3)
        self._z_ref.setSuffix(" ohm")
        self._z_ref.setValue(settings.z_ref_ohms or 50.0)
        self._z_ref.setEnabled(settings.z_ref_ohms is not None)
        self._z_default.toggled.connect(lambda checked: self._z_ref.setEnabled(not checked))
        form.addRow("Normalization:", self._z_default)
        form.addRow("Zref:", self._z_ref)

        self._window = QComboBox()
        for value in ("hamming", "hann", "blackman", "boxcar"):
            self._window.addItem(value, value)
        idx = self._window.findData(settings.window)
        if idx >= 0:
            self._window.setCurrentIndex(idx)
        form.addRow("Window:", self._window)

        self._pad = QSpinBox()
        self._pad.setRange(0, 1_000_000)
        self._pad.setValue(settings.pad)
        form.addRow("Zero padding:", self._pad)

        self._sample_default = QCheckBox("Auto")
        self._sample_default.setChecked(settings.sample_count is None)
        self._sample_count = QSpinBox()
        self._sample_count.setRange(2, 1_000_000)
        self._sample_count.setValue(settings.sample_count or 256)
        self._sample_count.setEnabled(settings.sample_count is not None)
        self._sample_default.toggled.connect(
            lambda checked: self._sample_count.setEnabled(not checked)
        )
        form.addRow("Samples:", self._sample_default)
        form.addRow("Sample count:", self._sample_count)

        self._extrapolate_dc = QCheckBox("Extrapolate to DC")
        self._extrapolate_dc.setChecked(settings.extrapolate_dc)
        form.addRow("Preprocess:", self._extrapolate_dc)

        self._time_min_default = QCheckBox("Auto")
        self._time_min_default.setChecked(settings.time_min_ns is None)
        self._time_min = QDoubleSpinBox()
        self._time_min.setRange(-1_000_000.0, 1_000_000.0)
        self._time_min.setDecimals(6)
        self._time_min.setSuffix(" ns")
        self._time_min.setValue(settings.time_min_ns or 0.0)
        self._time_min.setEnabled(settings.time_min_ns is not None)
        self._time_min_default.toggled.connect(lambda checked: self._time_min.setEnabled(not checked))
        form.addRow("Time min:", self._time_min_default)
        form.addRow("Min value:", self._time_min)

        self._time_max_default = QCheckBox("Auto")
        self._time_max_default.setChecked(settings.time_max_ns is None)
        self._time_max = QDoubleSpinBox()
        self._time_max.setRange(-1_000_000.0, 1_000_000.0)
        self._time_max.setDecimals(6)
        self._time_max.setSuffix(" ns")
        self._time_max.setValue(settings.time_max_ns or 10.0)
        self._time_max.setEnabled(settings.time_max_ns is not None)
        self._time_max_default.toggled.connect(lambda checked: self._time_max.setEnabled(not checked))
        form.addRow("Time max:", self._time_max_default)
        form.addRow("Max value:", self._time_max)

        self._velocity = QDoubleSpinBox()
        self._velocity.setRange(0.01, 1.0)
        self._velocity.setDecimals(3)
        self._velocity.setSingleStep(0.01)
        self._velocity.setValue(settings.velocity_factor)
        form.addRow("Velocity factor:", self._velocity)

        self._distance = QCheckBox("Show distance axis")
        self._distance.setChecked(settings.show_distance)
        form.addRow("Distance:", self._distance)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_settings(self) -> TdrSettings | None:
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return TdrSettings(
            z_ref_ohms=None if self._z_default.isChecked() else self._z_ref.value(),
            window=self._window.currentData(),
            pad=self._pad.value(),
            sample_count=None if self._sample_default.isChecked() else self._sample_count.value(),
            extrapolate_dc=self._extrapolate_dc.isChecked(),
            time_min_ns=None if self._time_min_default.isChecked() else self._time_min.value(),
            time_max_ns=None if self._time_max_default.isChecked() else self._time_max.value(),
            velocity_factor=self._velocity.value(),
            show_distance=self._distance.isChecked(),
        )
