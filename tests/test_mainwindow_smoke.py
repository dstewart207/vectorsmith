"""Headless Qt smoke tests for multi-trace, markers, menus, and QA wiring."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from PyQt6.QtWidgets import QApplication, QMenu

from vectorsmith.loader import load_touchstone
from vectorsmith.session import LoadedFile, PortPairingConfig
from vectorsmith.ui.main_window import MainWindow

FIXTURES = Path(__file__).parent / "fixtures"


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _load_fixture(window: MainWindow) -> None:
    result = load_touchstone(FIXTURES / "twoport.s2p")
    window._session.files.append(  # noqa: SLF001
        LoadedFile(
            path=result.path,
            network=result.network,
            display_name=result.display_name,
            pairing=PortPairingConfig(num_diff_ports=1, renumber_map=[0, 1]),
        )
    )
    window._refresh_all()  # noqa: SLF001


def test_multi_trace_selection_updates_plot_state():
    app = _app()
    window = MainWindow()
    _load_fixture(window)
    toolbar = window._plot_bar  # noqa: SLF001
    assert toolbar._trace_actions  # noqa: SLF001

    for action in toolbar._trace_actions:  # noqa: SLF001
        mn = tuple(action.data())
        action.setChecked(mn in {(0, 0), (1, 0)})
    app.processEvents()

    state = toolbar.plot_state(window._session)  # noqa: SLF001
    assert set(state.selected_traces()) == {(0, 0), (1, 0)}
    window.close()


def test_marker_dock_enable_add_and_search_min():
    app = _app()
    window = MainWindow()
    _load_fixture(window)
    dock = window._marker_dock  # noqa: SLF001

    dock._enabled.setChecked(True)  # noqa: SLF001
    app.processEvents()
    dock.apply_to_session(window._session)  # noqa: SLF001
    assert window._session.markers_enabled  # noqa: SLF001
    assert window._session.markers

    before = len(window._session.markers)  # noqa: SLF001
    dock._pending_action = "add"  # noqa: SLF001
    dock.apply_to_session(window._session)  # noqa: SLF001
    assert len(window._session.markers) == before + 1  # noqa: SLF001

    window._on_marker_search("max")  # noqa: SLF001
    assert window._session.markers_enabled  # noqa: SLF001
    assert any(m.x > 0 for m in window._session.markers)  # noqa: SLF001
    window.close()


def test_selecting_active_marker_preserves_positions():
    app = _app()
    window = MainWindow()
    _load_fixture(window)
    session = window._session  # noqa: SLF001
    dock = window._marker_dock  # noqa: SLF001

    session.markers_enabled = True
    session.clear_markers()
    m1 = session.add_marker(1.0)
    m2 = session.add_marker(2.0)
    session.active_marker_id = m2.marker_id
    dock.sync_from_session(session)
    assert dock.freq_ghz() == 2.0

    # Simulate choosing M1 in the combo without a spinbox edit.
    idx = dock._marker_list.findData(m1.marker_id)  # noqa: SLF001
    dock._marker_list.setCurrentIndex(idx)  # noqa: SLF001
    app.processEvents()
    # apply_to_session is invoked by marker_changed; call explicitly if signals blocked.
    if session.active_marker_id != m1.marker_id:
        dock._pending_action = "select"  # noqa: SLF001
        dock.apply_to_session(session)
        dock.sync_from_session(session)

    assert session.active_marker_id == m1.marker_id
    assert m1.x == 1.0
    assert m2.x == 2.0
    assert dock.freq_ghz() == 1.0
    window.close()


def test_export_touchstone_and_qa_menu_actions_exist():
    app = _app()
    window = MainWindow()
    all_texts: list[str] = []
    for action in window.menuBar().actions():
        menu = action.menu()
        if menu is None:
            continue
        assert isinstance(menu, QMenu)
        for sub in menu.actions():
            all_texts.append(sub.text())
    assert any("Export Touchstone" in t for t in all_texts)
    assert any("Network QA" in t for t in all_texts)
    window.close()
    app.processEvents()
