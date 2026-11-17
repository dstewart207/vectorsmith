from pathlib import Path

import matplotlib
import numpy as np
import skrf as rf

matplotlib.use("Agg")

from matplotlib.figure import Figure

from vectorsmith.marker import find_tdr_features
from vectorsmith.plot_kinds import PlotKind
from vectorsmith.plots import PlotState, TdrSettings, render_plot
from vectorsmith.rf_trace import tdr_impedance_response
from vectorsmith.session import LoadedFile, PlotMarker, Session

FIXTURES = Path(__file__).parent / "fixtures"


def test_tdr_render_draws_marker_line():
    from vectorsmith.loader import load_touchstone

    result = load_touchstone(FIXTURES / "oneport.s1p")
    session = Session()
    session.files.append(
        LoadedFile(
            path=result.path,
            network=result.network,
            display_name=result.display_name,
        )
    )
    fig = Figure()
    state = PlotState(kind=PlotKind.TDR_IMPEDANCE, m=0, n=0, tdr_settings=TdrSettings())
    markers = [PlotMarker(marker_id=1, x=0.1)]
    render_plot(
        session,
        state,
        fig,
        draw_marker=True,
        markers=markers,
        active_marker_id=1,
    )
    ax = fig.axes[0]
    # axvline creates a Line2D in ax.lines
    assert any(abs(line.get_xdata()[0] - 0.1) < 1e-9 for line in ax.lines if len(line.get_xdata()) >= 1)


def test_tdr_feature_find_on_delayed_reflection():
    one_way_delay_s = 5e-9
    expected_peak_s = 2.0 * one_way_delay_s
    f = np.linspace(0.0, 10e9, 401)
    s11 = 0.2 * np.exp(-1j * 2 * np.pi * f * expected_peak_s)
    net = rf.Network(
        frequency=rf.Frequency.from_f(f, unit="Hz"),
        s=s11.reshape(-1, 1, 1),
        z0=50.0,
    )
    t, z = tdr_impedance_response(net, 0, 0, z_ref_ohms=50.0, window="hamming")
    t_ns = t / 1e-9
    features = find_tdr_features(t_ns, z, z_ref_ohms=50.0)
    assert features
    best = features[0]
    assert abs(best.time_ns - expected_peak_s * 1e9) < 1.0
