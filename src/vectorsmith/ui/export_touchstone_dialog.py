"""Dialog for exporting converted / renormalized Touchstone files."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QVBoxLayout,
)

from vectorsmith.mixed_mode import ParamDomain
from vectorsmith.session import LoadedFile


@dataclass(frozen=True)
class TouchstoneExportOptions:
    domain: ParamDomain
    renormalize: bool
    z0_ohms: float
    keysight_reorder: bool


class ExportTouchstoneDialog(QDialog):
    def __init__(self, loaded: LoadedFile, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Export Touchstone — {loaded.display_name}")
        self._result: TouchstoneExportOptions | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._domain = QComboBox()
        self._domain.addItem("Single-ended", ParamDomain.SINGLE_ENDED)
        self._domain.addItem("Mixed-mode", ParamDomain.MIXED_MODE)
        default_domain = loaded.domain or ParamDomain.SINGLE_ENDED
        idx = self._domain.findData(default_domain)
        if idx >= 0:
            self._domain.setCurrentIndex(idx)
        form.addRow("Domain:", self._domain)

        self._renorm = QCheckBox("Renormalize Z0")
        form.addRow(self._renorm)

        self._z0 = QDoubleSpinBox()
        self._z0.setRange(1.0, 1000.0)
        self._z0.setDecimals(3)
        self._z0.setSuffix(" Ω")
        z0 = float(loaded.network.z0.real.flat[0]) if loaded.network.z0.size else 50.0
        self._z0.setValue(z0)
        self._z0.setEnabled(False)
        self._renorm.toggled.connect(self._z0.setEnabled)
        form.addRow("Z0:", self._z0)

        self._keysight = QCheckBox("Keysight GMM reorder")
        self._keysight.setChecked(loaded.keysight_reorder)
        form.addRow(self._keysight)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        self._result = TouchstoneExportOptions(
            domain=self._domain.currentData(),
            renormalize=self._renorm.isChecked(),
            z0_ohms=float(self._z0.value()),
            keysight_reorder=self._keysight.isChecked(),
        )
        self.accept()

    def result_options(self) -> TouchstoneExportOptions | None:
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return self._result
