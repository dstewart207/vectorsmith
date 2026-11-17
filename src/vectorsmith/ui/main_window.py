"""Main application window."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QScrollBar,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from vectorsmith.compare import align_networks, format_freq_span
from vectorsmith.exports import export_marker_csv, export_touchstone, export_trace_csv
from vectorsmith.loader import is_touchstone_path
from vectorsmith.marker import (
    bandwidth_at_level,
    find_extrema,
    find_tdr_features,
    format_marker_delta,
    format_marker_readout,
    format_tdr_marker_readout,
    freq_range_ghz,
    marker_delta,
    value_at_frequency,
    value_at_x,
)
from vectorsmith.mixed_mode import ParamDomain, network_for_plot, tdr_trace_label, trace_label
from vectorsmith.plot_kinds import PlotKind
from vectorsmith.plots import (
    GraphSettings,
    HZ_PER_GHZ,
    MAX_FREQ_WINDOW_GHZ,
    TdrSettings,
    render_plot,
    status_text,
)
from vectorsmith.qa import analyze_network
from vectorsmith.resources import app_icon
from vectorsmith.rf_trace import (
    default_tdr_z_ref_ohms,
    is_tdr_kind,
    plot_kind_unit,
    trace_x_values,
    trace_y_values,
)
from vectorsmith.session import Session
from vectorsmith.ui.export_touchstone_dialog import ExportTouchstoneDialog
from vectorsmith.ui.file_dock import FileDock
from vectorsmith.ui.graph_settings_dialog import GraphSettingsDialog
from vectorsmith.ui.marker_dock import MarkerDock
from vectorsmith.ui.metadata_dock import MetadataDock
from vectorsmith.ui.plot_toolbar import PlotToolbar
from vectorsmith.ui.port_pairing_dialog import PortPairingDialog
from vectorsmith.ui.qa_dialog import QaDialog
from vectorsmith.ui.tdr_settings_dialog import TdrSettingsDialog
from vectorsmith.ui.theme import apply_theme
from vectorsmith.workspace import (
    graph_settings_from_dict,
    load_workspace,
    save_workspace,
    session_from_workspace,
    session_to_dict,
    tdr_settings_from_dict,
)
from vectorsmith.widgets.mpl_canvas import MplCanvasWidget


SCROLL_UNITS_PER_GHZ = 1000


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VectorSmith")
        self.setWindowIcon(app_icon())
        self.resize(1200, 800)
        self._session = Session()
        self._dark_theme = False
        self._graph_settings = GraphSettings()
        self._tdr_settings = TdrSettings()
        self._settings = QSettings("VectorSmith", "VectorSmith")
        self._last_dir = ""

        self._canvas = MplCanvasWidget()
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(self._canvas)
        self._freq_scroll = QScrollBar(Qt.Orientation.Horizontal)
        self._freq_scroll.setVisible(False)
        self._freq_scroll.valueChanged.connect(self._on_freq_scroll)
        central_layout.addWidget(self._freq_scroll)
        self.setCentralWidget(central)

        self._file_dock = FileDock(self)
        self._meta_dock = MetadataDock(self)
        self._marker_dock = MarkerDock(self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._file_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._meta_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._marker_dock)
        self.setCorner(Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.TopDockWidgetArea)
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.TopDockWidgetArea)

        self._plot_bar = PlotToolbar()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._wrap_toolbar(self._plot_bar))

        self._keysight_cb = QCheckBox("Keysight GMM reorder")
        self._keysight_cb.stateChanged.connect(self._on_keysight_toggle)
        ks_toolbar = self.addToolBar("Keysight")
        ks_toolbar.setObjectName("KeysightToolbar")
        ks_toolbar.setMovable(False)
        ks_toolbar.addWidget(self._keysight_cb)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        apply_theme(QApplication.instance(), self._dark_theme)
        self._canvas.set_dark_theme(self._dark_theme)
        self._build_menus()
        self.setAcceptDrops(True)

        self._file_dock.visibility_changed.connect(self._refresh_all)
        self._file_dock.selection_changed.connect(self._on_selection)
        self._plot_bar.changed.connect(self._on_plot_changed)
        self._plot_bar.domain_changed.connect(self._on_plot_domain_changed)
        self._plot_bar.port_pairing_requested.connect(self._open_port_pairing)
        self._plot_bar.tdr_settings_requested.connect(self._open_tdr_settings)
        self._marker_dock.marker_changed.connect(self._on_marker_changed)
        self._marker_dock.search_requested.connect(self._on_marker_search)

        self._restore_app_settings()
        self._redraw()

    def _wrap_toolbar(self, widget):
        from PyQt6.QtWidgets import QToolBar

        bar = QToolBar("Plot controls")
        bar.setObjectName("PlotControlsToolbar")
        bar.setMovable(False)
        bar.addWidget(widget)
        return bar

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_act = QAction("&Open…", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._open_files)
        file_menu.addAction(open_act)
        save_workspace_act = QAction("Save Workspace...", self)
        save_workspace_act.triggered.connect(self._save_workspace)
        file_menu.addAction(save_workspace_act)
        load_workspace_act = QAction("Load Workspace...", self)
        load_workspace_act.triggered.connect(self._load_workspace)
        file_menu.addAction(load_workspace_act)
        file_menu.addSeparator()
        export_plot_act = QAction("Export Plot...", self)
        export_plot_act.triggered.connect(self._export_plot)
        file_menu.addAction(export_plot_act)
        export_trace_act = QAction("Export Trace CSV...", self)
        export_trace_act.triggered.connect(self._export_trace_csv)
        file_menu.addAction(export_trace_act)
        export_marker_act = QAction("Export Marker CSV...", self)
        export_marker_act.triggered.connect(self._export_marker_csv)
        file_menu.addAction(export_marker_act)
        export_touchstone_act = QAction("Export Touchstone...", self)
        export_touchstone_act.triggered.connect(self._export_touchstone)
        file_menu.addAction(export_touchstone_act)
        file_menu.addSeparator()
        close_act = QAction("Close selected", self)
        close_act.triggered.connect(self._close_selected)
        file_menu.addAction(close_act)
        close_all = QAction("Close all", self)
        close_all.triggered.connect(self._close_all)
        file_menu.addAction(close_all)
        file_menu.addSeparator()
        quit_act = QAction("E&xit", self)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self._file_dock.toggleViewAction())
        view_menu.addAction(self._meta_dock.toggleViewAction())
        view_menu.addAction(self._marker_dock.toggleViewAction())
        view_menu.addSeparator()
        dark_act = QAction("Dark mode", self)
        dark_act.setCheckable(True)
        dark_act.triggered.connect(self._on_dark_theme_toggle)
        view_menu.addAction(dark_act)

        options_menu = self.menuBar().addMenu("&Options")
        graph_settings_act = QAction("Graph Settings...", self)
        graph_settings_act.triggered.connect(self._open_graph_settings)
        options_menu.addAction(graph_settings_act)
        tdr_settings_act = QAction("TDR Settings...", self)
        tdr_settings_act.triggered.connect(self._open_tdr_settings)
        options_menu.addAction(tdr_settings_act)

        tools_menu = self.menuBar().addMenu("&Tools")
        qa_act = QAction("Network QA...", self)
        qa_act.triggered.connect(self._run_network_qa)
        tools_menu.addAction(qa_act)

    def _on_dark_theme_toggle(self, checked: bool) -> None:
        self._dark_theme = checked
        apply_theme(QApplication.instance(), checked)
        self._canvas.set_dark_theme(checked)
        self._update_marker_readout()
        self._redraw()

    def _open_graph_settings(self) -> None:
        dlg = GraphSettingsDialog(
            self._graph_settings,
            default_x_max_ghz=self._visible_fmax_ghz(),
            parent=self,
        )
        settings = dlg.result_settings()
        if settings is None:
            return
        self._graph_settings = settings
        self._update_marker_readout()
        self._redraw()

    def _open_tdr_settings(self) -> None:
        dlg = TdrSettingsDialog(self._tdr_settings, self)
        settings = dlg.result_settings()
        if settings is None:
            return
        self._tdr_settings = settings
        self._update_marker_readout()
        self._redraw()

    def _open_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Touchstone",
            self._last_dir,
            "Touchstone (*.s*p *.S*p);;All (*.*)",
        )
        if paths:
            self._last_dir = str(Path(paths[0]).parent)
            self._add_paths([Path(p) for p in paths])

    def _save_workspace(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Workspace",
            self._last_dir,
            "VectorSmith Workspace (*.vsmith.json);;JSON (*.json)",
        )
        if not path:
            return
        data = session_to_dict(
            self._session,
            graph_settings=self._graph_settings,
            tdr_settings=self._tdr_settings,
            toolbar=self._plot_bar.snapshot(),
            dark_theme=self._dark_theme,
        )
        save_workspace(path, data)
        self._last_dir = str(Path(path).parent)

    def _load_workspace(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Workspace",
            self._last_dir,
            "VectorSmith Workspace (*.vsmith.json *.json);;JSON (*.json)",
        )
        if not path:
            return
        data = load_workspace(path)
        session, errors = session_from_workspace(data)
        self._session = session
        self._graph_settings = graph_settings_from_dict(data.get("graph_settings"))
        self._tdr_settings = tdr_settings_from_dict(data.get("tdr_settings"))
        self._dark_theme = bool(data.get("dark_theme", self._dark_theme))
        apply_theme(QApplication.instance(), self._dark_theme)
        self._canvas.set_dark_theme(self._dark_theme)
        self._plot_bar.refresh_traces(self._session)
        self._plot_bar.restore_snapshot(data.get("toolbar", {}))
        self._marker_dock.sync_from_session(self._session)
        self._last_dir = str(Path(path).parent)
        self._refresh_all()
        if errors:
            skipped = "\n".join(f"{p}: {msg}" for p, msg in errors[:8])
            QMessageBox.warning(self, "Workspace loaded with missing files", skipped)

    def _export_plot(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Plot",
            self._last_dir,
            "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)",
        )
        if not path:
            return
        self._canvas.figure.savefig(path)
        self._last_dir = str(Path(path).parent)

    def _export_trace_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Trace CSV",
            self._last_dir,
            "CSV (*.csv)",
        )
        if not path:
            return
        state = self._plot_bar.plot_state(self._session)
        state.tdr_settings = self._tdr_settings
        export_trace_csv(path, self._session, state)
        self._last_dir = str(Path(path).parent)

    def _export_marker_csv(self) -> None:
        if not self._session.markers_enabled or not self._session.enabled_markers():
            QMessageBox.information(self, "Export Marker CSV", "Enable markers first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Marker CSV",
            self._last_dir,
            "CSV (*.csv)",
        )
        if not path:
            return
        state = self._plot_bar.plot_state(self._session)
        state.tdr_settings = self._tdr_settings
        export_marker_csv(
            path,
            self._session,
            state,
            markers=self._session.enabled_markers(),
        )
        self._last_dir = str(Path(path).parent)

    def _export_touchstone(self) -> None:
        idx = self._file_dock.list.currentRow()
        if idx < 0 or idx >= len(self._session.files):
            QMessageBox.information(self, "Export Touchstone", "Select a file in the list first.")
            return
        lf = self._session.files[idx]
        dlg = ExportTouchstoneDialog(lf, self)
        options = dlg.result_options()
        if options is None:
            return
        suggested = str(Path(self._last_dir or str(lf.path.parent)) / f"{lf.path.stem}_export")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Touchstone",
            suggested,
            "Touchstone (*.s*p);;All (*.*)",
        )
        if not path:
            return
        written = export_touchstone(
            path,
            lf,
            domain=options.domain,
            z0_ohms=options.z0_ohms if options.renormalize else None,
            keysight_reorder=options.keysight_reorder,
        )
        self._last_dir = str(written.parent)
        self._status.showMessage(f"Wrote {written.name}", 5000)

    def _run_network_qa(self) -> None:
        idx = self._file_dock.list.currentRow()
        if idx < 0 or idx >= len(self._session.files):
            QMessageBox.information(self, "Network QA", "Select a file in the list first.")
            return
        lf = self._session.files[idx]
        state = self._plot_bar.plot_state(self._session)
        domain = state.domain if state.domain else (lf.domain or ParamDomain.SINGLE_ENDED)
        net = network_for_plot(
            lf.network,
            domain,
            lf.pairing,
            lf.keysight_reorder,
            lf.gmm_cache,
            lf.gmm_cache_key,
        )
        report = analyze_network(net, filename=lf.display_name, domain=domain.value)
        QaDialog(report, self).exec()

    def _add_paths(self, paths: list[Path]) -> None:
        touchstone = [p for p in paths if is_touchstone_path(p)]
        if not touchstone:
            return
        errors = self._session.add_paths(touchstone)
        for p, msg in errors:
            QMessageBox.warning(self, "Load failed", f"{p.name}:\n{msg}")
        self._refresh_all()

    def _close_selected(self) -> None:
        indices = self._file_dock.selected_indices()
        if indices:
            self._session.remove_selected(indices)
            self._refresh_all()

    def _close_all(self) -> None:
        self._session.files.clear()
        self._session.clear_markers()
        self._marker_dock.sync_from_session(self._session)
        self._refresh_all()

    def _on_selection(self) -> None:
        idx = self._file_dock.list.currentRow()
        lf = self._session.files[idx] if 0 <= idx < len(self._session.files) else None
        self._meta_dock.show_file(lf)
        if lf and lf.domain:
            self._plot_bar.set_domain(lf.domain)

    def _on_plot_domain_changed(self) -> None:
        self._plot_bar.refresh_traces(self._session)
        self._update_marker_readout()
        self._redraw()

    def _on_plot_changed(self) -> None:
        self._update_marker_freq_range()
        self._update_marker_readout()
        self._redraw()

    def _on_freq_scroll(self) -> None:
        self._update_marker_readout()
        self._redraw()

    def _on_marker_changed(self) -> None:
        self._marker_dock.apply_to_session(self._session)
        self._marker_dock.sync_from_session(self._session)
        self._update_marker_readout()
        self._redraw()

    def _on_marker_click(self, x_value: float, marker_id: int | None = None) -> None:
        state = self._plot_bar.plot_state(self._session)
        if state.kind == PlotKind.SMITH:
            return
        if marker_id is not None:
            self._session.active_marker_id = marker_id
            for marker in self._session.markers:
                if marker.marker_id == marker_id:
                    marker.x = x_value
                    break
        else:
            self._session.marker_freq_ghz = x_value
        self._marker_dock.sync_from_session(self._session)
        self._update_marker_readout()
        self._redraw()

    def _primary_plot_network(self):
        vis = self._session.visible_files()
        if not vis:
            return None, None, None
        state = self._plot_bar.plot_state(self._session)
        state.tdr_settings = self._tdr_settings
        lf = vis[0]
        net = network_for_plot(
            lf.network,
            state.domain,
            lf.pairing,
            lf.keysight_reorder,
            lf.gmm_cache,
            lf.gmm_cache_key,
        )
        return state, lf, net

    def _on_marker_search(self, mode: str) -> None:
        state, lf, net = self._primary_plot_network()
        if state is None or net is None or lf is None:
            QMessageBox.information(self, "Marker search", "Open a visible file first.")
            return
        if state.kind == PlotKind.SMITH:
            QMessageBox.information(self, "Marker search", "Search is not available on Smith chart.")
            return

        traces = state.selected_traces()
        m, n = traces[0]
        self._session.markers_enabled = True

        if mode in {"tdr_peak", "tdr_step"} or is_tdr_kind(state.kind) and mode in {"min", "max"}:
            if not is_tdr_kind(state.kind):
                QMessageBox.information(self, "Marker search", "Switch to TDR Z(t) for TDR find.")
                return
            trace = tdr_trace_label(net, m, n, state.domain)
            z_ref = self._tdr_settings.z_ref_ohms or default_tdr_z_ref_ohms(state.domain.value, trace)
            kwargs = {
                "tdr_z_ref_ohms": z_ref,
                "tdr_window": self._tdr_settings.window,
                "tdr_pad": self._tdr_settings.pad,
                "tdr_sample_count": self._tdr_settings.sample_count,
                "tdr_extrapolate_dc": self._tdr_settings.extrapolate_dc,
            }
            x = trace_x_values(net, m, n, state.kind, **kwargs)
            y = trace_y_values(net, m, n, state.kind, state.unwrap_phase, **kwargs)
            if mode == "min":
                mn, _ = find_extrema(x, y)
                self._session.add_marker(mn.x)
            elif mode == "max":
                _, mx = find_extrema(x, y)
                self._session.add_marker(mx.x)
            else:
                features = find_tdr_features(x, y, z_ref_ohms=z_ref)
                wanted = "peak" if mode == "tdr_peak" else "step"
                match = next((f for f in features if f.kind == wanted or (wanted == "peak" and f.kind == "valley")), None)
                if match is None:
                    QMessageBox.information(self, "Marker search", f"No TDR {wanted} found.")
                    return
                self._session.add_marker(match.time_ns)
        elif mode in {"min", "max"}:
            x = net.frequency.f / HZ_PER_GHZ
            y = trace_y_values(net, m, n, state.kind, state.unwrap_phase)
            mn, mx = find_extrema(x, y)
            self._session.add_marker(mn.x if mode == "min" else mx.x)
        elif mode == "bw3db":
            if state.kind not in {PlotKind.MAG_DB, PlotKind.RETURN_LOSS_DB, PlotKind.INSERTION_LOSS_DB}:
                QMessageBox.information(
                    self,
                    "Marker search",
                    "−3 dB bandwidth search requires Mag (dB) plot.",
                )
                return
            x = net.frequency.f / HZ_PER_GHZ
            y = trace_y_values(net, m, n, state.kind, state.unwrap_phase)
            # Transmission-like: peak max; reflection dips: use min for S11-style.
            relative = "min" if m == n else "max"
            bw = bandwidth_at_level(x, y, -3.0, relative_to=relative)
            if bw is None:
                QMessageBox.information(self, "Marker search", "Could not find −3 dB crossings.")
                return
            self._session.clear_markers()
            self._session.markers_enabled = True
            self._session.add_marker(bw.low_x)
            self._session.add_marker(bw.high_x)
            self._session.add_marker(bw.peak_x)
            self._status.showMessage(
                f"−3 dB BW = {bw.bandwidth:.4g} GHz  (low={bw.low_x:.4g}, high={bw.high_x:.4g})",
                8000,
            )
        else:
            return

        self._marker_dock.sync_from_session(self._session)
        self._update_marker_readout()
        self._redraw()

    def _update_marker_freq_range(self) -> None:
        vis = self._session.visible_files()
        if not vis:
            self._marker_dock.set_freq_range(0.0, 1.0)
            return
        state = self._plot_bar.plot_state(self._session)
        state.tdr_settings = self._tdr_settings
        traces = state.selected_traces()
        m, n = traces[0]
        if is_tdr_kind(state.kind):
            self._marker_dock.set_axis("Time:", " ns")
            mins: list[float] = []
            maxs: list[float] = []
            for lf in vis:
                net = network_for_plot(
                    lf.network,
                    state.domain,
                    lf.pairing,
                    lf.keysight_reorder,
                    lf.gmm_cache,
                    lf.gmm_cache_key,
                )
                trace = tdr_trace_label(net, m, n, state.domain)
                z_ref = self._tdr_settings.z_ref_ohms or default_tdr_z_ref_ohms(
                    state.domain.value, trace
                )
                try:
                    x = trace_x_values(
                        net,
                        m,
                        n,
                        state.kind,
                        tdr_z_ref_ohms=z_ref,
                        tdr_window=self._tdr_settings.window,
                        tdr_pad=self._tdr_settings.pad,
                        tdr_sample_count=self._tdr_settings.sample_count,
                        tdr_extrapolate_dc=self._tdr_settings.extrapolate_dc,
                    )
                except Exception:
                    continue
                mins.append(float(x.min()))
                maxs.append(float(x.max()))
            if not mins:
                self._marker_dock.set_freq_range(0.0, 1.0)
                return
            self._marker_dock.set_freq_range(min(mins), max(maxs))
            if self._session.marker_freq_ghz is None and self._session.markers_enabled:
                self._session.marker_freq_ghz = min(mins)
                self._marker_dock.sync_from_session(self._session)
            return
        self._marker_dock.set_axis("Frequency:", " GHz")
        f_min = float("inf")
        f_max = 0.0
        for lf in vis:
            lo, hi = freq_range_ghz(lf.network)
            f_min = min(f_min, lo)
            f_max = max(f_max, hi)
        self._marker_dock.set_freq_range(f_min, f_max)
        if self._session.marker_freq_ghz is None and self._session.markers_enabled:
            self._session.marker_freq_ghz = f_min
            self._marker_dock.sync_from_session(self._session)

    def _update_marker_readout(self) -> None:
        if not self._session.markers_enabled:
            self._marker_dock.set_readout("")
            return
        state = self._plot_bar.plot_state(self._session)
        if state.kind == PlotKind.SMITH:
            self._marker_dock.set_readout("Marker not available on Smith chart.")
            return
        markers = self._session.enabled_markers()
        if not markers:
            self._marker_dock.set_readout("")
            return
        vis = self._session.visible_files()
        if not vis:
            self._marker_dock.set_readout("No visible files.")
            return
        traces = state.selected_traces()
        m, n = traces[0]
        lines: list[str] = []
        x_unit = "ns" if is_tdr_kind(state.kind) else "GHz"
        y_unit = plot_kind_unit(state.kind)
        values_by_marker: dict[int, list[float]] = {}
        for marker in markers:
            values_by_marker[marker.marker_id] = []
            for lf in vis:
                domain = state.domain if state.domain else (lf.domain or ParamDomain.SINGLE_ENDED)
                net = network_for_plot(
                    lf.network,
                    domain,
                    lf.pairing,
                    lf.keysight_reorder,
                    lf.gmm_cache,
                    lf.gmm_cache_key,
                )
                if is_tdr_kind(state.kind):
                    trace = tdr_trace_label(net, m, n, state.domain)
                    z_ref = self._tdr_settings.z_ref_ohms or default_tdr_z_ref_ohms(
                        state.domain.value, trace
                    )
                    try:
                        val = value_at_x(
                            net,
                            m,
                            n,
                            marker.x,
                            state.kind,
                            state.unwrap_phase,
                            tdr_z_ref_ohms=z_ref,
                            tdr_window=self._tdr_settings.window,
                            tdr_pad=self._tdr_settings.pad,
                            tdr_sample_count=self._tdr_settings.sample_count,
                            tdr_extrapolate_dc=self._tdr_settings.extrapolate_dc,
                        )
                    except Exception as exc:  # noqa: BLE001
                        lines.append(f"{marker.label}  {lf.display_name}  {trace}: {exc}")
                        continue
                    values_by_marker[marker.marker_id].append(val)
                    lines.append(
                        format_tdr_marker_readout(
                            lf.display_name, trace, marker.x, val, marker_label=marker.label
                        )
                    )
                else:
                    for tm, tn in traces:
                        trace = trace_label(net, tm, tn, state.domain)
                        val = value_at_frequency(
                            net,
                            tm,
                            tn,
                            marker.x,
                            state.kind,
                            state.unwrap_phase,
                        )
                        if tm == m and tn == n:
                            values_by_marker[marker.marker_id].append(val)
                        lines.append(
                            format_marker_readout(
                                lf.display_name,
                                trace,
                                marker.x,
                                val,
                                state.kind,
                                marker_label=marker.label,
                            )
                        )

        if len(markers) >= 2:
            a, b = markers[0], markers[1]
            ya = values_by_marker.get(a.marker_id, [np.nan])[0]
            yb = values_by_marker.get(b.marker_id, [np.nan])[0]
            if np.isfinite(ya) and np.isfinite(yb):
                delta = marker_delta(a.x, ya, b.x, yb, x_unit=x_unit, y_unit=y_unit)
                lines.append(format_marker_delta(delta, a.label, b.label))
        self._marker_dock.set_readout("\n".join(lines))

    def _open_port_pairing(self) -> None:
        idx = self._file_dock.list.currentRow()
        if idx < 0 or idx >= len(self._session.files):
            QMessageBox.information(self, "Port pairing", "Select a file in the list first.")
            return
        lf = self._session.files[idx]
        dlg = PortPairingDialog(lf, self)
        pairing = dlg.result_pairing()
        if pairing is None:
            return
        lf.pairing = pairing
        lf.gmm_cache.clear()
        self._plot_bar.refresh_traces(self._session)
        self._update_marker_readout()
        self._redraw()

    def _on_keysight_toggle(self) -> None:
        idx = self._file_dock.list.currentRow()
        if 0 <= idx < len(self._session.files):
            self._session.files[idx].keysight_reorder = self._keysight_cb.isChecked()
            self._session.files[idx].gmm_cache.clear()
        self._update_marker_readout()
        self._redraw()

    def _refresh_all(self) -> None:
        self._file_dock.apply_visibility_to_session(self._session)
        self._file_dock.sync_files(self._session.files)
        self._plot_bar.refresh_traces(self._session)
        self._update_marker_freq_range()
        self._sync_freq_scrollbar()
        self._on_selection()
        self._marker_dock.sync_from_session(self._session)
        self._update_marker_readout()
        self._redraw()

    def _visible_fmax_ghz(self) -> float:
        vis = self._session.visible_files()
        if not vis:
            return 0.0
        return max(float(f.network.frequency.f.max() / HZ_PER_GHZ) for f in vis)

    def _sync_freq_scrollbar(self) -> None:
        f_max_ghz = self._visible_fmax_ghz()
        max_start_ghz = max(0.0, f_max_ghz - MAX_FREQ_WINDOW_GHZ)
        self._freq_scroll.blockSignals(True)
        self._freq_scroll.setVisible(max_start_ghz > 0.0)
        self._freq_scroll.setRange(0, int(round(max_start_ghz * SCROLL_UNITS_PER_GHZ)))
        self._freq_scroll.setSingleStep(SCROLL_UNITS_PER_GHZ)
        self._freq_scroll.setPageStep(int(MAX_FREQ_WINDOW_GHZ * SCROLL_UNITS_PER_GHZ))
        if self._freq_scroll.value() > self._freq_scroll.maximum():
            self._freq_scroll.setValue(self._freq_scroll.maximum())
        self._freq_scroll.blockSignals(False)

    def _redraw(self) -> None:
        self._sync_freq_scrollbar()
        state = self._plot_bar.plot_state(self._session)
        state.freq_window_start_ghz = self._freq_scroll.value() / SCROLL_UNITS_PER_GHZ
        state.graph_settings = self._graph_settings
        state.tdr_settings = self._tdr_settings
        markers = self._session.enabled_markers()
        draw_marker = bool(markers) and state.kind != PlotKind.SMITH
        warn = render_plot(
            self._session,
            state,
            self._canvas.figure,
            draw_marker=draw_marker,
            marker_freq_ghz=self._session.marker_freq_ghz,
            markers=markers if draw_marker else None,
            active_marker_id=self._session.active_marker_id,
            dark_theme=self._dark_theme,
        )
        self._canvas.clear_and_draw()
        if self._session.markers_enabled and state.kind != PlotKind.SMITH:
            self._canvas.connect_marker_interaction(
                self._on_marker_click,
                markers=[(m.marker_id, m.x) for m in markers],
                active_marker_id=self._session.active_marker_id,
            )
        else:
            self._canvas.disconnect_marker_interaction()

        vis = self._session.visible_files()
        npts = 0
        span = ""
        if vis:
            nets = []
            for lf in vis:
                nets.append(
                    network_for_plot(
                        lf.network,
                        state.domain,
                        lf.pairing,
                        lf.keysight_reorder,
                        lf.gmm_cache,
                        lf.gmm_cache_key,
                    )
                )
            aligned = align_networks(nets)
            npts = aligned.npoints
            if aligned.npoints:
                span = format_freq_span(aligned.f_min_hz, aligned.f_max_hz)

        base = status_text(self._session, npts, state.domain)
        traces = state.selected_traces()
        if len(traces) > 1:
            base += f" | {len(traces)} traces"
        if span:
            base += f" | {span}"
        if warn:
            base += f" | Warning: {warn}"
        self._status.showMessage(base)

    def _restore_app_settings(self) -> None:
        geometry = self._settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = self._settings.value("window_state")
        if state is not None:
            self.restoreState(state)
        self._last_dir = str(self._settings.value("last_dir", ""))
        self._dark_theme = self._settings.value("dark_theme", False, type=bool)
        apply_theme(QApplication.instance(), self._dark_theme)
        self._canvas.set_dark_theme(self._dark_theme)
        try:
            self._graph_settings = graph_settings_from_dict(
                json.loads(str(self._settings.value("graph_settings", "{}")))
            )
            self._tdr_settings = tdr_settings_from_dict(
                json.loads(str(self._settings.value("tdr_settings", "{}")))
            )
            self._plot_bar.restore_snapshot(
                json.loads(str(self._settings.value("toolbar", "{}")))
            )
        except json.JSONDecodeError:
            pass

    def _save_app_settings(self) -> None:
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("window_state", self.saveState())
        self._settings.setValue("last_dir", self._last_dir)
        self._settings.setValue("dark_theme", self._dark_theme)
        self._settings.setValue("graph_settings", json.dumps(self._graph_settings.__dict__))
        self._settings.setValue("tdr_settings", json.dumps(self._tdr_settings.__dict__))
        self._settings.setValue("toolbar", json.dumps(self._plot_bar.snapshot()))

    def closeEvent(self, event) -> None:
        self._save_app_settings()
        super().closeEvent(event)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls()]
        self._add_paths(paths)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self._close_selected()
        else:
            super().keyPressEvent(event)
