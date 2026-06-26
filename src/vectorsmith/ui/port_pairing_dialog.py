"""Dialog to configure port renumbering and se2gmm diff-port count."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from vectorsmith.session import LoadedFile, PortPairingConfig


class PortPairingDialog(QDialog):
    def __init__(self, loaded: LoadedFile, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Port pairing — {loaded.display_name}")
        self._loaded = loaded
        n = loaded.network.nports

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Renumber maps physical port order before se2gmm. "
                "Example for 4-port: 0,2,1,3 pairs (1,3) and (2,4)."
            )
        )

        form = QFormLayout()
        self._diff_ports = QSpinBox()
        self._diff_ports.setRange(0, max(0, n // 2))
        self._diff_ports.setValue(loaded.pairing.num_diff_ports)
        form.addRow("Differential port groups (p):", self._diff_ports)

        default_map = loaded.pairing.renumber_map or list(range(n))
        self._renumber = QLineEdit(",".join(str(x) for x in default_map))
        form.addRow(f"Renumber map ({n} ints):", self._renumber)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_pairing(self) -> PortPairingConfig | None:
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        n = self._loaded.network.nports
        try:
            ren = [int(x.strip()) for x in self._renumber.text().split(",") if x.strip()]
        except ValueError:
            ren = list(range(n))
        if len(ren) != n:
            ren = list(range(n))
        return PortPairingConfig(
            num_diff_ports=self._diff_ports.value(),
            renumber_map=ren,
        )
