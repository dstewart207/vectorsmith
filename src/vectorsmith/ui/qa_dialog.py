"""Dialog showing passivity / reciprocity / causality QA results."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from vectorsmith.qa import QaReport


class QaDialog(QDialog):
    def __init__(self, report: QaReport, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Network QA — {report.filename or 'network'}")
        self.resize(640, 280)

        layout = QVBoxLayout(self)
        status = "PASS" if report.all_passed else "FAIL"
        layout.addWidget(
            QLabel(f"{report.filename}  [{report.domain}]  overall: {status}")
        )

        table = QTableWidget(len(report.checks), 4)
        table.setHorizontalHeaderLabels(["Check", "Result", "Metric", "Detail"])
        table.horizontalHeader().setStretchLastSection(True)
        for row, check in enumerate(report.checks):
            table.setItem(row, 0, QTableWidgetItem(check.name))
            table.setItem(row, 1, QTableWidgetItem("PASS" if check.passed else "FAIL"))
            table.setItem(row, 2, QTableWidgetItem(f"{check.metric:.6g}"))
            detail = check.detail
            if check.frequency_hz is not None:
                detail += f" @ {check.frequency_hz / 1e9:.4g} GHz"
            table.setItem(row, 3, QTableWidgetItem(detail))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(buttons)
