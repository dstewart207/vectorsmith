"""File list dock with visibility toggles."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDockWidget,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class FileDock(QDockWidget):
    selection_changed = pyqtSignal()
    visibility_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__("Files", parent)
        self.setObjectName("FileDock")
        container = QWidget()
        layout = QVBoxLayout(container)
        self.list = QListWidget()
        self.list.itemChanged.connect(self._on_item_changed)
        self.list.currentRowChanged.connect(lambda _: self.selection_changed.emit())
        layout.addWidget(self.list)
        self.setWidget(container)

    def sync_files(self, files) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for i, lf in enumerate(files):
            item = QListWidgetItem(lf.display_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if lf.visible else Qt.CheckState.Unchecked
            )
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(item)
        self.list.blockSignals(False)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None:
            return
        self.visibility_changed.emit()

    def selected_indices(self) -> list[int]:
        return [self.list.currentRow()] if self.list.currentRow() >= 0 else []

    def apply_visibility_to_session(self, session) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx is not None and 0 <= idx < len(session.files):
                session.files[idx].visible = item.checkState() == Qt.CheckState.Checked
