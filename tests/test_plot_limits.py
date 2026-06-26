from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from vectorsmith.loader import load_touchstone
from vectorsmith.mixed_mode import ParamDomain, convert_to_gmm
from vectorsmith.plot_kinds import PlotKind
from vectorsmith.plots import (
    DEFAULT_MAG_Y_MAX_DB,
    DEFAULT_MAG_Y_MIN_DB,
    GraphSettings,
    MAX_FREQ_WINDOW_GHZ,
    PlotState,
    compute_axis_limits,
    freq_window_ghz,
    ghz_tick_steps,
    render_plot,
    resolve_line_color,
)
from vectorsmith.session import LoadedFile, Session
from vectorsmith.session import PortPairingConfig

FIXTURES = Path(__file__).parent / "fixtures"


def test_mag_limits_zero_hz_and_zero_db_top():
    net = load_touchstone(FIXTURES / "twoport.s2p").network
    limits = compute_axis_limits([net], PlotKind.MAG_DB)
    assert limits is not None
    assert limits.xmin == 0.0
    assert limits.ymin == DEFAULT_MAG_Y_MIN_DB
    assert limits.ymax == DEFAULT_MAG_Y_MAX_DB
    assert limits.xmax == float(net.frequency.f.max())
    assert limits.ymax > limits.ymin


def test_mag_limits_stable_across_trace_selection():
    net = load_touchstone(FIXTURES / "twoport.s2p").network
    lim_11 = compute_axis_limits([net], PlotKind.MAG_DB)
    lim_22 = compute_axis_limits([net], PlotKind.MAG_DB)
    assert lim_11 == lim_22


def test_ghz_tick_steps_adaptive():
    assert ghz_tick_steps(6.0) == (1.0, 0.2)
    assert ghz_tick_steps(40.0) == (5.0, 1.0)


def test_ghz_tick_steps_autoscale_for_wide_spans():
    assert ghz_tick_steps(250.0) == (25.0, 5.0)


def test_frequency_window_caps_to_250_ghz():
    assert freq_window_ghz(100.0, 0.0) == (0.0, 100.0)
    assert freq_window_ghz(400.0, 50.0) == (50.0, 50.0 + MAX_FREQ_WINDOW_GHZ)
    assert freq_window_ghz(400.0, 300.0) == (150.0, 400.0)


def test_line_color_modes():
    assert resolve_line_color("blue", dark_theme=False) == "#1f77b4"
    assert resolve_line_color("red", dark_theme=False) == "#d62728"
    assert resolve_line_color("automatic", dark_theme=False) == "black"
    assert resolve_line_color("automatic", dark_theme=True) == "white"


def test_log_freq_uses_min_positive_f():
    net = load_touchstone(FIXTURES / "twoport.s2p").network
    limits = compute_axis_limits([net], PlotKind.MAG_DB, freq_log=True)
    assert limits is not None
    assert limits.xmin == float(net.frequency.f.min())
    assert limits.xmin > 0.0


def test_manual_frequency_overrides_are_applied():
    net = load_touchstone(FIXTURES / "twoport.s2p").network
    limits = compute_axis_limits(
        [net],
        PlotKind.MAG_DB,
        graph_settings=GraphSettings(x_min_ghz=1.25, x_max_ghz=1.75),
    )
    assert limits is not None
    assert limits.xmin == 1.25e9
    assert limits.xmax == 1.75e9


def test_manual_mag_db_overrides_are_applied():
    net = load_touchstone(FIXTURES / "twoport.s2p").network
    limits = compute_axis_limits(
        [net],
        PlotKind.MAG_DB,
        graph_settings=GraphSettings(mag_y_min_db=-80.0, mag_y_max_db=5.0),
    )
    assert limits is not None
    assert limits.ymin == -80.0
    assert limits.ymax == 5.0


def test_log_freq_manual_zero_min_uses_min_positive_f():
    net = load_touchstone(FIXTURES / "twoport.s2p").network
    limits = compute_axis_limits(
        [net],
        PlotKind.MAG_DB,
        freq_log=True,
        graph_settings=GraphSettings(x_min_ghz=0.0),
    )
    assert limits is not None
    assert limits.xmin == float(net.frequency.f.min())
    assert limits.xmin > 0.0


def test_render_plot_xlabel_ghz():
    from matplotlib.figure import Figure

    result = load_touchstone(FIXTURES / "twoport.s2p")
    session = Session()
    session.files.append(
        LoadedFile(path=result.path, network=result.network, display_name=result.display_name)
    )
    fig = Figure()
    render_plot(session, PlotState(), fig)
    ax = fig.axes[0]
    assert "GHz" in ax.get_xlabel()


def test_render_plot_marker_line_and_label():
    from matplotlib.figure import Figure

    result = load_touchstone(FIXTURES / "twoport.s2p")
    session = Session()
    session.files.append(
        LoadedFile(path=result.path, network=result.network, display_name=result.display_name)
    )
    marker_freq_ghz = float(result.network.frequency.f[0] / 1e9)
    fig = Figure()

    render_plot(
        session,
        PlotState(kind=PlotKind.MAG_DB),
        fig,
        draw_marker=True,
        marker_freq_ghz=marker_freq_ghz,
    )

    ax = fig.axes[0]
    assert any(line.get_linestyle() == "--" for line in ax.lines)
    marker_labels = [text.get_text() for text in ax.texts]
    assert any("GHz" in text and "dB" in text for text in marker_labels)


def test_render_plot_dark_marker_label_uses_light_text():
    from matplotlib.figure import Figure

    result = load_touchstone(FIXTURES / "twoport.s2p")
    session = Session()
    session.files.append(
        LoadedFile(path=result.path, network=result.network, display_name=result.display_name)
    )
    marker_freq_ghz = float(result.network.frequency.f[0] / 1e9)
    fig = Figure()

    render_plot(
        session,
        PlotState(kind=PlotKind.MAG_DB),
        fig,
        draw_marker=True,
        marker_freq_ghz=marker_freq_ghz,
        dark_theme=True,
    )

    marker_label = next(text for text in fig.axes[0].texts if "GHz" in text.get_text())
    assert marker_label.get_color() == "#f0f3f6"


def test_render_plot_uses_file_colors_for_multiple_visible_files():
    from matplotlib.figure import Figure

    result = load_touchstone(FIXTURES / "twoport.s2p")
    session = Session()
    session.files.extend(
        [
            LoadedFile(
                path=result.path.with_name("a.s2p"),
                network=result.network,
                display_name="a.s2p",
                color="#123456",
            ),
            LoadedFile(
                path=result.path.with_name("b.s2p"),
                network=result.network,
                display_name="b.s2p",
                color="#abcdef",
            ),
        ]
    )
    fig = Figure()

    render_plot(session, PlotState(kind=PlotKind.MAG_DB, line_color="blue"), fig)

    plotted_colors = [line.get_color() for line in fig.axes[0].lines[:2]]
    assert plotted_colors == ["#123456", "#abcdef"]


def test_render_plot_mixed_mode_legend_uses_dropdown_label():
    from matplotlib.figure import Figure
    import numpy as np
    import skrf

    f = skrf.Frequency(1e9, 2e9, 2, unit="Hz")
    s = np.full((2, 4, 4), 0.01 * (1 + 1j), dtype=complex)
    network = skrf.Network(frequency=f, s=s)
    gmm = convert_to_gmm(
        network,
        PortPairingConfig(num_diff_ports=2, renumber_map=[0, 2, 1, 3]),
    )
    session = Session()
    session.files.append(
        LoadedFile(
            path=FIXTURES / "synthetic.s4p",
            network=gmm,
            display_name="synthetic.s4p",
            domain=ParamDomain.MIXED_MODE,
        )
    )
    fig = Figure()

    render_plot(session, PlotState(kind=PlotKind.MAG_DB, domain=ParamDomain.MIXED_MODE), fig)

    legend = fig.axes[0].get_legend()
    legend_text = legend.get_texts()[0].get_text()
    assert legend_text == "synthetic.s4p (SDD11)"
    assert getattr(legend, "_draggable", None) is not None


def test_marker_label_dragged_position_survives_marker_move():
    from matplotlib.figure import Figure

    result = load_touchstone(FIXTURES / "twoport.s2p")
    session = Session()
    session.files.append(
        LoadedFile(path=result.path, network=result.network, display_name=result.display_name)
    )
    fig = Figure()

    render_plot(
        session,
        PlotState(kind=PlotKind.MAG_DB),
        fig,
        draw_marker=True,
        marker_freq_ghz=1.0,
    )
    marker_label = next(text for text in fig.axes[0].texts if "GHz" in text.get_text())
    marker_label.set_transform(fig.axes[0].transAxes)
    marker_label.set_position((0.25, 0.35))

    render_plot(
        session,
        PlotState(kind=PlotKind.MAG_DB),
        fig,
        draw_marker=True,
        marker_freq_ghz=2.0,
    )

    moved_marker_label = next(text for text in fig.axes[0].texts if "GHz" in text.get_text())
    assert moved_marker_label.get_transform() == fig.axes[0].transAxes
    assert moved_marker_label.get_position() == (0.25, 0.35)
