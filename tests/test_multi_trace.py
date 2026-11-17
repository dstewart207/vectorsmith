from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib.figure import Figure
from PyQt6.QtWidgets import QApplication

from vectorsmith.loader import load_touchstone
from vectorsmith.mixed_mode import ParamDomain
from vectorsmith.plot_kinds import PlotKind
from vectorsmith.plots import PlotState, render_plot
from vectorsmith.session import LoadedFile, PortPairingConfig, Session
from vectorsmith.ui.plot_toolbar import PlotToolbar

FIXTURES = Path(__file__).parent / "fixtures"


def _session() -> Session:
    result = load_touchstone(FIXTURES / "twoport.s2p")
    session = Session()
    session.files.append(
        LoadedFile(
            path=result.path,
            network=result.network,
            display_name=result.display_name,
            pairing=PortPairingConfig(num_diff_ports=1, renumber_map=[0, 1]),
        )
    )
    return session


def test_plot_state_selected_traces_defaults_to_mn():
    state = PlotState(m=1, n=0)
    assert state.selected_traces() == [(1, 0)]


def test_plot_state_selected_traces_uses_list():
    state = PlotState(m=0, n=0, traces=[(0, 0), (1, 0), (0, 0)])
    assert state.selected_traces() == [(0, 0), (1, 0)]


def test_render_plot_multi_trace_creates_multiple_lines():
    session = _session()
    fig = Figure()
    state = PlotState(
        kind=PlotKind.MAG_DB,
        domain=ParamDomain.SINGLE_ENDED,
        traces=[(0, 0), (1, 0)],
    )
    warn = render_plot(session, state, fig)
    assert warn is None
    ax = fig.axes[0]
    assert len(ax.lines) >= 2


def test_toolbar_multi_trace_snapshot_round_trip():
    app = QApplication.instance() or QApplication([])
    toolbar = PlotToolbar()
    session = _session()
    toolbar.refresh_traces(session)
    # Select S11 and S21 if available.
    for action in toolbar._trace_actions:  # noqa: SLF001
        data = action.data()
        action.setChecked(data in {(0, 0), (1, 0)})
    snap = toolbar.snapshot()
    assert "traces" in snap
    assert [tuple(t) for t in snap["traces"]] == toolbar.selected_traces()

    toolbar2 = PlotToolbar()
    toolbar2.refresh_traces(session)
    toolbar2.restore_snapshot(snap)
    assert set(toolbar2.selected_traces()) == set(toolbar.selected_traces())
    app.processEvents()
