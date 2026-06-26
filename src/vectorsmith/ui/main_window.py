"""Main application window."""

from __future__ import annotations

import json
from pathlib import Path

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
from vectorsmith.loader import is_touchstone_path
from vectorsmith.marker import (
    format_marker_readout,
    format_tdr_marker_readout,
    freq_range_ghz,
    value_at_x,
    value_at_frequency,
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
from vectorsmith.exports import export_marker_csv, export_trace_csv
from vectorsmith.resources import app_icon
from vectorsmith.rf_trace import default_tdr_z_ref_ohms, is_tdr_kind, trace_x_values
from vectorsmith.session import Session
from vectorsmith.ui.file_dock import FileDock
from vectorsmith.ui.graph_settings_dialog import GraphSettingsDialog
from vectorsmith.ui.marker_dock import MarkerDock
from vectorsmith.ui.metadata_dock import MetadataDock
from vectorsmith.ui.plot_toolbar import PlotToolbar
from vectorsmith.ui.port_pairing_dialog import PortPairingDialog
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

    def _current_marker_x(self) -> float | None:
        if not self._session.marker_enabled:
            return None
        return self._session.marker_freq_ghz

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
        marker_x = self._current_marker_x()
        if marker_x is None:
            QMessageBox.information(self, "Export Marker CSV", "Enable the marker first.")
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
        export_marker_csv(path, self._session, state, marker_x)
        self._last_dir = str(Path(path).parent)


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
        self._session.marker_freq_ghz = None
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
        self._update_marker_readout()
        self._redraw()

    def _on_freq_scroll(self) -> None:
        self._update_marker_readout()
        self._redraw()

    def _on_marker_changed(self) -> None:
        self._session.marker_enabled = self._marker_dock.is_enabled()
        self._marker_dock.set_enabled(self._session.marker_enabled)
        if self._session.marker_enabled:
            self._session.marker_freq_ghz = self._marker_dock.freq_ghz()
            self._canvas.connect_marker_interaction(
                self._on_marker_click,
                self._session.marker_freq_ghz,
            )
        else:
            self._canvas.disconnect_marker_interaction()
        self._update_marker_readout()
        self._redraw()

    def _on_marker_click(self, freq_ghz: float) -> None:
        state = self._plot_bar.plot_state(self._session)
        if state.kind == PlotKind.SMITH:
            return
        self._session.marker_freq_ghz = freq_ghz
        self._marker_dock.set_freq_ghz(freq_ghz)
        self._update_marker_readout()
        self._redraw()

    def _update_marker_freq_range(self) -> None:
        vis = self._session.visible_files()
        if not vis:
            self._marker_dock.set_freq_range(0.0, 1.0)
            return
        state = self._plot_bar.plot_state(self._session)
        state.tdr_settings = self._tdr_settings
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
                trace = tdr_trace_label(net, state.m, state.n, state.domain)
                z_ref = self._tdr_settings.z_ref_ohms or default_tdr_z_ref_ohms(
                    state.domain.value, trace
                )
                try:
                    x = trace_x_values(
                        net,
                        state.m,
                        state.n,
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
            if self._session.marker_freq_ghz is None:
                self._marker_dock.set_freq_ghz(min(mins))
                self._session.marker_freq_ghz = min(mins)
            return
        self._marker_dock.set_axis("Frequency:", " GHz")
        f_min = float("inf")
        f_max = 0.0
        for lf in vis:
            lo, hi = freq_range_ghz(lf.network)
            f_min = min(f_min, lo)
            f_max = max(f_max, hi)
        self._marker_dock.set_freq_range(f_min, f_max)
        if self._session.marker_freq_ghz is None:
            self._marker_dock.set_freq_ghz(f_min)
            self._session.marker_freq_ghz = f_min

    def _update_marker_readout(self) -> None:
        if not self._session.marker_enabled:
            self._marker_dock.set_readout("")
            return
        state = self._plot_bar.plot_state(self._session)
        if state.kind == PlotKind.SMITH:
            self._marker_dock.set_readout("Marker not available on Smith chart.")
            return
        freq = self._session.marker_freq_ghz
        if freq is None:
            self._marker_dock.set_readout("")
            return
        vis = self._session.visible_files()
        if not vis:
            self._marker_dock.set_readout("No visible files.")
            return
        lines: list[str] = []
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
                trace = tdr_trace_label(net, state.m, state.n, state.domain)
                z_ref = self._tdr_settings.z_ref_ohms or default_tdr_z_ref_ohms(
                    state.domain.value, trace
                )
                try:
                    val = value_at_x(
                        net,
                        state.m,
                        state.n,
                        freq,
                        state.kind,
                        state.unwrap_phase,
                        tdr_z_ref_ohms=z_ref,
                        tdr_window=self._tdr_settings.window,
                        tdr_pad=self._tdr_settings.pad,
                        tdr_sample_count=self._tdr_settings.sample_count,
                        tdr_extrapolate_dc=self._tdr_settings.extrapolate_dc,
                    )
                except Exception as exc:  # noqa: BLE001
                    lines.append(f"{lf.display_name}  {trace}: {exc}")
                    continue
                lines.append(format_tdr_marker_readout(lf.display_name, trace, freq, val))
            else:
                trace = trace_label(net, state.m, state.n, state.domain)
                val = value_at_frequency(
                    net,
                    state.m,
                    state.n,
                    freq,
                    state.kind,
                    state.unwrap_phase,
                )
                lines.append(
                    format_marker_readout(lf.display_name, trace, freq, val, state.kind)
                )
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
        draw_marker = (
            self._session.marker_enabled
            and self._session.marker_freq_ghz is not None
            and state.kind != PlotKind.SMITH
            and not is_tdr_kind(state.kind)
        )
        warn = render_plot(
            self._session,
            state,
            self._canvas.figure,
            draw_marker=draw_marker,
            marker_freq_ghz=self._session.marker_freq_ghz,
            dark_theme=self._dark_theme,
        )
        self._canvas.clear_and_draw()
        if self._session.marker_enabled and state.kind != PlotKind.SMITH:
            self._canvas.connect_marker_interaction(
                self._on_marker_click,
                self._session.marker_freq_ghz,
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
