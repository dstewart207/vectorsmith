"""Plot controls: kind, domain, traces, comparison, and frequency scale."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)

from vectorsmith.mixed_mode import (
    ParamDomain,
    list_mixed_mode_traces,
    list_mixed_mode_tdr_traces,
    list_single_ended_traces,
    list_single_ended_tdr_traces,
    network_for_plot,
)
from vectorsmith.plot_kinds import PlotKind
from vectorsmith.session import Session


class PlotToolbar(QWidget):
    changed = pyqtSignal()
    domain_changed = pyqtSignal()
    port_pairing_requested = pyqtSignal()
    tdr_settings_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 4, 4)

        row.addWidget(QLabel("Plot:"))
        self._plot_kind = QComboBox()
        labels = {
            PlotKind.MAG_DB: "Mag (dB)",
            PlotKind.PHASE_DEG: "Phase (deg)",
            PlotKind.SMITH: "Smith",
            PlotKind.VSWR: "VSWR",
            PlotKind.INPUT_Z: "|Z|",
            PlotKind.RETURN_LOSS_DB: "Return loss",
            PlotKind.INSERTION_LOSS_DB: "Insertion loss",
            PlotKind.GROUP_DELAY_NS: "Group delay",
            PlotKind.REAL_Z: "Re(Z)",
            PlotKind.IMAG_Z: "Im(Z)",
            PlotKind.TDR_IMPEDANCE: "TDR Z(t)",
        }
        visible_plot_kinds = [
            PlotKind.MAG_DB,
            PlotKind.PHASE_DEG,
            PlotKind.SMITH,
            PlotKind.VSWR,
            PlotKind.INPUT_Z,
            PlotKind.REAL_Z,
            PlotKind.IMAG_Z,
            PlotKind.GROUP_DELAY_NS,
            PlotKind.TDR_IMPEDANCE,
        ]
        for k in visible_plot_kinds:
            self._plot_kind.addItem(labels[k], k)
        self._plot_kind.currentIndexChanged.connect(self._on_plot_kind_changed)
        row.addWidget(self._plot_kind)

        row.addWidget(QLabel("Domain:"))
        self._domain = QComboBox()
        self._domain.addItem("Single-ended", ParamDomain.SINGLE_ENDED)
        self._domain.addItem("Mixed-mode", ParamDomain.MIXED_MODE)
        self._domain.currentIndexChanged.connect(self._on_domain_changed)
        row.addWidget(self._domain)

        row.addWidget(QLabel("Traces:"))
        self._trace_btn = QToolButton()
        self._trace_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._trace_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._trace_menu = QMenu(self)
        self._trace_btn.setMenu(self._trace_menu)
        self._trace_btn.setText("S11")
        self._trace_btn.setMinimumWidth(90)
        self._trace_btn.clicked.connect(self._trace_btn.showMenu)
        self._trace_actions: list[QAction] = []
        self._available_traces: list[tuple[int, int, str]] = []
        self._selected_traces: list[tuple[int, int]] = [(0, 0)]
        row.addWidget(self._trace_btn)

        self._unwrap = QCheckBox("Unwrap phase")
        self._unwrap.stateChanged.connect(self._emit)
        row.addWidget(self._unwrap)

        self._log_freq = QCheckBox("Log freq")
        self._log_freq.stateChanged.connect(self._emit)
        row.addWidget(self._log_freq)

        row.addWidget(QLabel("Line:"))
        self._line_color = QComboBox()
        self._line_color.addItem("Blue", "blue")
        self._line_color.addItem("Red", "red")
        self._line_color.addItem("Automatic", "automatic")
        self._line_color.currentIndexChanged.connect(self._emit)
        row.addWidget(self._line_color)

        self._pairing_btn = QPushButton("Port pairing...")
        self._pairing_btn.clicked.connect(self.port_pairing_requested.emit)
        row.addWidget(self._pairing_btn)

        self._tdr_btn = QPushButton("TDR settings...")
        self._tdr_btn.clicked.connect(self.tdr_settings_requested.emit)
        row.addWidget(self._tdr_btn)

        self._compare = QCheckBox("Delta")
        self._compare.stateChanged.connect(self._emit)
        row.addWidget(self._compare)

        row.addWidget(QLabel("Ref:"))
        self._reference = QComboBox()
        self._reference.currentIndexChanged.connect(self._emit)
        row.addWidget(self._reference)

        row.addStretch()

    def _emit(self, *_args) -> None:
        self.changed.emit()

    def _on_domain_changed(self) -> None:
        self.domain_changed.emit()
        self._emit()

    def _on_plot_kind_changed(self) -> None:
        self.domain_changed.emit()
        self._emit()

    def _on_trace_toggled(self) -> None:
        selected: list[tuple[int, int]] = []
        for action in self._trace_actions:
            if action.isChecked():
                data = action.data()
                if data is not None:
                    selected.append(tuple(data))
        if not selected and self._trace_actions:
            # Keep at least one trace selected.
            self._trace_actions[0].blockSignals(True)
            self._trace_actions[0].setChecked(True)
            self._trace_actions[0].blockSignals(False)
            data = self._trace_actions[0].data()
            selected = [tuple(data)] if data is not None else [(0, 0)]
        self._selected_traces = selected
        self._update_trace_button_text()
        self._emit()

    def _update_trace_button_text(self) -> None:
        labels = []
        selected = set(self._selected_traces)
        for m, n, label in self._available_traces:
            if (m, n) in selected:
                labels.append(label)
        if not labels:
            self._trace_btn.setText("(none)")
        elif len(labels) == 1:
            self._trace_btn.setText(labels[0])
        elif len(labels) <= 3:
            self._trace_btn.setText(", ".join(labels))
        else:
            self._trace_btn.setText(f"{labels[0]} +{len(labels) - 1}")

    def _collect_unique_traces(self, session: Session) -> list[tuple[int, int, str]]:
        domain = self._domain.currentData()
        is_tdr = self._plot_kind.currentData() == PlotKind.TDR_IMPEDANCE
        traces: list[tuple[int, int, str]] = []
        for lf in session.visible_files() or session.files:
            net = network_for_plot(
                lf.network,
                domain,
                lf.pairing,
                lf.keysight_reorder,
                lf.gmm_cache,
                lf.gmm_cache_key,
            )
            if is_tdr and domain == ParamDomain.MIXED_MODE:
                traces.extend(list_mixed_mode_tdr_traces(net))
            elif is_tdr:
                traces.extend(list_single_ended_tdr_traces(net.nports))
            elif domain == ParamDomain.MIXED_MODE:
                for t in list_mixed_mode_traces(net):
                    traces.append((t.m, t.n, t.label))
            else:
                traces.extend(list_single_ended_traces(net.nports))

        if not traces and session.files:
            lf = session.files[0]
            if domain == ParamDomain.MIXED_MODE:
                net = network_for_plot(
                    lf.network,
                    domain,
                    lf.pairing,
                    lf.keysight_reorder,
                    lf.gmm_cache,
                    lf.gmm_cache_key,
                )
                if is_tdr:
                    traces.extend(list_mixed_mode_tdr_traces(net))
                else:
                    for t in list_mixed_mode_traces(net):
                        traces.append((t.m, t.n, t.label))
            elif is_tdr:
                traces = list_single_ended_tdr_traces(lf.network.nports)
            else:
                traces = list_single_ended_traces(lf.network.nports)

        seen: set[str] = set()
        unique: list[tuple[int, int, str]] = []
        for m, n, label in traces:
            if label not in seen:
                seen.add(label)
                unique.append((m, n, label))
        return unique

    def refresh_traces(self, session: Session) -> None:
        unique = self._collect_unique_traces(session)
        self._available_traces = unique
        available_mn = {(m, n) for m, n, _ in unique}
        prev = [mn for mn in self._selected_traces if mn in available_mn]
        if not prev and unique:
            prev = [(unique[0][0], unique[0][1])]
        self._selected_traces = prev

        self._trace_menu.clear()
        self._trace_actions = []
        for m, n, label in unique:
            action = QAction(label, self._trace_menu)
            action.setCheckable(True)
            action.setChecked((m, n) in self._selected_traces)
            action.setData((m, n))
            action.toggled.connect(self._on_trace_toggled)
            self._trace_menu.addAction(action)
            self._trace_actions.append(action)
        self._update_trace_button_text()

        prev_ref = self._reference.currentData()
        self._reference.blockSignals(True)
        self._reference.clear()
        for i, lf in enumerate(session.visible_files() or session.files):
            self._reference.addItem(lf.display_name, i)
        if prev_ref is not None:
            idx = self._reference.findData(prev_ref)
            if idx >= 0:
                self._reference.setCurrentIndex(idx)
        self._reference.blockSignals(False)

    def plot_state(self, session: Session):
        from vectorsmith.plots import PlotState

        traces = list(self._selected_traces) or [(0, 0)]
        m, n = traces[0]
        return PlotState(
            kind=self._plot_kind.currentData(),
            m=m,
            n=n,
            traces=traces,
            unwrap_phase=self._unwrap.isChecked(),
            freq_log=self._log_freq.isChecked(),
            domain=self._domain.currentData(),
            line_color=self._line_color.currentData(),
            comparison_enabled=self._compare.isChecked(),
            reference_index=self._reference.currentData() or 0,
        )

    def set_domain(self, domain: ParamDomain) -> None:
        idx = self._domain.findData(domain)
        if idx >= 0:
            self._domain.setCurrentIndex(idx)

    def selected_traces(self) -> list[tuple[int, int]]:
        return list(self._selected_traces)

    def snapshot(self) -> dict:
        primary = self._selected_traces[0] if self._selected_traces else (0, 0)
        return {
            "plot_kind": self._plot_kind.currentData().value,
            "domain": self._domain.currentData().value,
            "trace": list(primary),
            "traces": [list(mn) for mn in self._selected_traces],
            "unwrap_phase": self._unwrap.isChecked(),
            "freq_log": self._log_freq.isChecked(),
            "line_color": self._line_color.currentData(),
            "comparison_enabled": self._compare.isChecked(),
            "reference_index": self._reference.currentData() or 0,
        }

    def restore_snapshot(self, data: dict) -> None:
        kind = data.get("plot_kind")
        for item in PlotKind:
            if item.value == kind:
                idx = self._plot_kind.findData(item)
                if idx >= 0:
                    self._plot_kind.setCurrentIndex(idx)
                break
        domain = data.get("domain")
        for item in ParamDomain:
            if item.value == domain:
                idx = self._domain.findData(item)
                if idx >= 0:
                    self._domain.setCurrentIndex(idx)
                break
        self._unwrap.setChecked(bool(data.get("unwrap_phase", False)))
        self._log_freq.setChecked(bool(data.get("freq_log", False)))
        color_idx = self._line_color.findData(data.get("line_color"))
        if color_idx >= 0:
            self._line_color.setCurrentIndex(color_idx)
        self._compare.setChecked(bool(data.get("comparison_enabled", False)))
        ref_idx = self._reference.findData(int(data.get("reference_index", 0)))
        if ref_idx >= 0:
            self._reference.setCurrentIndex(ref_idx)

        traces_raw = data.get("traces")
        selected: list[tuple[int, int]] = []
        if isinstance(traces_raw, list) and traces_raw:
            for item in traces_raw:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    selected.append((int(item[0]), int(item[1])))
        else:
            trace_data = data.get("trace")
            if isinstance(trace_data, list) and len(trace_data) >= 2:
                selected = [(int(trace_data[0]), int(trace_data[1]))]
            elif isinstance(trace_data, tuple) and len(trace_data) >= 2:
                selected = [(int(trace_data[0]), int(trace_data[1]))]
        if selected:
            self._selected_traces = selected
            available = {(m, n) for m, n, _ in self._available_traces}
            if available:
                self._selected_traces = [mn for mn in selected if mn in available] or [
                    (self._available_traces[0][0], self._available_traces[0][1])
                ]
            for action in self._trace_actions:
                data_mn = action.data()
                action.blockSignals(True)
                action.setChecked(tuple(data_mn) in self._selected_traces)
                action.blockSignals(False)
            self._update_trace_button_text()
