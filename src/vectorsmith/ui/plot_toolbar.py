"""Plot controls: kind, domain, trace, comparison, and frequency scale."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
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

        row.addWidget(QLabel("Trace:"))
        self._trace = QComboBox()
        self._trace.currentIndexChanged.connect(self._emit)
        row.addWidget(self._trace)

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

    def refresh_traces(self, session: Session) -> None:
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

        prev_mn = self._trace.currentData()
        self._trace.blockSignals(True)
        self._trace.clear()
        for m, n, label in unique:
            self._trace.addItem(label, (m, n))
        if prev_mn is not None:
            for i in range(self._trace.count()):
                if self._trace.itemData(i) == prev_mn:
                    self._trace.setCurrentIndex(i)
                    break
        self._trace.blockSignals(False)

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

        data = self._trace.currentData()
        m, n = (0, 0) if data is None else data
        return PlotState(
            kind=self._plot_kind.currentData(),
            m=m,
            n=n,
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

    def snapshot(self) -> dict:
        return {
            "plot_kind": self._plot_kind.currentData().value,
            "domain": self._domain.currentData().value,
            "trace": self._trace.currentData(),
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
        trace_data = data.get("trace")
        if isinstance(trace_data, list):
            trace_data = tuple(trace_data)
        trace_idx = self._trace.findData(trace_data)
        if trace_idx >= 0:
            self._trace.setCurrentIndex(trace_idx)
