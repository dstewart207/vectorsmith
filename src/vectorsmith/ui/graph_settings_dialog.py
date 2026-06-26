"""Dialog to configure graph axis defaults for the current session."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vectorsmith.plots import (
    DEFAULT_MAG_Y_MAX_DB,
    DEFAULT_MAG_Y_MIN_DB,
    GraphSettings,
)


class GraphSettingsDialog(QDialog):
    def __init__(
        self,
        settings: GraphSettings,
        *,
        default_x_max_ghz: float,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Graph Settings")
        self._default_x_max_ghz = max(0.0, default_x_max_ghz)

        layout = QVBoxLayout(self)
        layout.addWidget(self._axis_group(settings))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        reset = QPushButton("Reset Defaults")
        buttons.addButton(reset, QDialogButtonBox.ButtonRole.ResetRole)
        reset.clicked.connect(self._reset_defaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _axis_group(self, settings: GraphSettings) -> QGroupBox:
        group = QGroupBox("Axis defaults")
        form = QFormLayout(group)

        self._x_min_default, self._x_min = self._bound_row(
            settings.x_min_ghz,
            default_value=0.0,
            minimum=0.0,
            maximum=1_000_000.0,
            suffix=" GHz",
        )
        form.addRow("Frequency min:", self._x_min_row)

        self._x_max_default, self._x_max = self._bound_row(
            settings.x_max_ghz,
            default_value=self._default_x_max_ghz,
            minimum=0.0,
            maximum=1_000_000.0,
            suffix=" GHz",
        )
        form.addRow("Frequency max:", self._x_max_row)

        self._mag_y_min_default, self._mag_y_min = self._bound_row(
            settings.mag_y_min_db,
            default_value=DEFAULT_MAG_Y_MIN_DB,
            minimum=-500.0,
            maximum=500.0,
            suffix=" dB",
        )
        form.addRow("Magnitude min:", self._mag_y_min_row)

        self._mag_y_max_default, self._mag_y_max = self._bound_row(
            settings.mag_y_max_db,
            default_value=DEFAULT_MAG_Y_MAX_DB,
            minimum=-500.0,
            maximum=500.0,
            suffix=" dB",
        )
        form.addRow("Magnitude max:", self._mag_y_max_row)
        return group

    def _bound_row(
        self,
        value: float | None,
        *,
        default_value: float,
        minimum: float,
        maximum: float,
        suffix: str,
    ) -> tuple[QCheckBox, QDoubleSpinBox]:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        default = QCheckBox("Default")
        default.setChecked(value is None)
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(6 if suffix == " GHz" else 2)
        spin.setSingleStep(0.1 if suffix == " GHz" else 1.0)
        spin.setSuffix(suffix)
        spin.setValue(default_value if value is None else value)
        spin.setEnabled(value is not None)
        default.toggled.connect(lambda checked: spin.setEnabled(not checked))

        layout.addWidget(default)
        layout.addWidget(spin, 1)

        if suffix == " GHz":
            if not hasattr(self, "_x_min_row"):
                self._x_min_row = row
            else:
                self._x_max_row = row
        elif not hasattr(self, "_mag_y_min_row"):
            self._mag_y_min_row = row
        else:
            self._mag_y_max_row = row
        return default, spin

    def _reset_defaults(self) -> None:
        defaults = [
            (self._x_min_default, self._x_min, 0.0),
            (self._x_max_default, self._x_max, self._default_x_max_ghz),
            (self._mag_y_min_default, self._mag_y_min, DEFAULT_MAG_Y_MIN_DB),
            (self._mag_y_max_default, self._mag_y_max, DEFAULT_MAG_Y_MAX_DB),
        ]
        for checkbox, spin, value in defaults:
            checkbox.setChecked(True)
            spin.setValue(value)

    def result_settings(self) -> GraphSettings | None:
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return GraphSettings(
            x_min_ghz=None if self._x_min_default.isChecked() else self._x_min.value(),
            x_max_ghz=None if self._x_max_default.isChecked() else self._x_max.value(),
            mag_y_min_db=None
            if self._mag_y_min_default.isChecked()
            else self._mag_y_min.value(),
            mag_y_max_db=None
            if self._mag_y_max_default.isChecked()
            else self._mag_y_max.value(),
        )
