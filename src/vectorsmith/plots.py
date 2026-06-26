"""Build matplotlib plots from session plot state."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import skrf as rf
from matplotlib.figure import Figure
from matplotlib.ticker import AutoLocator, AutoMinorLocator, LogLocator, MultipleLocator
from matplotlib.transforms import blended_transform_factory

from vectorsmith.compare import align_networks
from vectorsmith.marker import value_at_frequency
from vectorsmith.mixed_mode import (
    ParamDomain,
    network_for_plot,
    tdr_trace_label,
    trace_label,
)
from vectorsmith.plot_kinds import PlotKind
from vectorsmith.rf_trace import (
    HZ_PER_GHZ,
    default_tdr_z_ref_ohms,
    is_reflection_trace,
    is_tdr_kind,
    plot_kind_unit,
    plot_kind_ylabel,
    trace_x_values,
    trace_y_values,
)
from vectorsmith.session import LoadedFile, Session
MAX_FREQ_WINDOW_GHZ = 250.0
TARGET_FREQ_MAJOR_INTERVALS = 8
MAJOR_DB = 10.0
MINOR_DB = 2.0
DEFAULT_MAG_Y_MIN_DB = -40.0
DEFAULT_MAG_Y_MAX_DB = 0.0

Y_MARGIN_DB = 1.0
Y_MARGIN_FRAC = 0.05
LEGEND_POS_ATTR = "_vectorsmith_legend_loc"
MARKER_LABEL_POS_ATTR = "_vectorsmith_marker_label_pos"
MARKER_LABEL_GID = "vectorsmith_marker_label"


@dataclass
class GraphSettings:
    x_min_ghz: float | None = None
    x_max_ghz: float | None = None
    mag_y_min_db: float | None = None
    mag_y_max_db: float | None = None


@dataclass
class TdrSettings:
    z_ref_ohms: float | None = None
    window: str = "hamming"
    pad: int = 0
    sample_count: int | None = None
    extrapolate_dc: bool = True
    time_min_ns: float | None = None
    time_max_ns: float | None = None
    velocity_factor: float = 0.66
    show_distance: bool = False


@dataclass
class PlotState:
    kind: PlotKind = PlotKind.MAG_DB
    m: int = 0
    n: int = 0
    unwrap_phase: bool = False
    freq_log: bool = False
    domain: ParamDomain = ParamDomain.SINGLE_ENDED
    freq_window_start_ghz: float = 0.0
    line_color: str = "blue"
    graph_settings: GraphSettings | None = None
    tdr_settings: TdrSettings | None = None
    comparison_enabled: bool = False
    reference_index: int = 0


@dataclass(frozen=True)
class AxisLimits:
    xmin: float
    xmax: float
    ymin: float
    ymax: float


def hz_to_ghz(hz: float) -> float:
    return hz / HZ_PER_GHZ


def _nice_step_near(raw_step: float) -> float:
    """Round a raw step to a readable interval while preserving tick density."""
    if raw_step <= 0:
        return 1.0
    exponent = np.floor(np.log10(raw_step))
    base = 10.0**exponent
    candidates = np.array([1.0, 2.0, 2.5, 5.0, 10.0]) * base
    distances = np.abs(candidates - raw_step)
    best = np.flatnonzero(distances == np.min(distances))
    return float(candidates[int(best[-1])])


def ghz_tick_steps(xmax_ghz: float) -> tuple[float, float]:
    """Return GHz tick spacing with consistent label density across ranges."""
    major = _nice_step_near(xmax_ghz / TARGET_FREQ_MAJOR_INTERVALS)
    return major, major / 5.0


def freq_window_ghz(f_max_ghz: float, start_ghz: float) -> tuple[float, float]:
    """Return a frequency window capped to MAX_FREQ_WINDOW_GHZ."""
    if f_max_ghz <= MAX_FREQ_WINDOW_GHZ:
        return 0.0, max(0.0, f_max_ghz)
    max_start = max(0.0, f_max_ghz - MAX_FREQ_WINDOW_GHZ)
    start = float(np.clip(start_ghz, 0.0, max_start))
    return start, start + MAX_FREQ_WINDOW_GHZ


def _valid_span(min_value: float, max_value: float, fallback_span: float) -> tuple[float, float]:
    if max_value > min_value:
        return min_value, max_value
    span = max(fallback_span, 1.0)
    return min_value, min_value + span


def compute_axis_limits(
    networks: list[rf.Network],
    kind: PlotKind,
    unwrap_phase: bool = False,
    freq_log: bool = False,
    freq_window_start_ghz: float = 0.0,
    graph_settings: GraphSettings | None = None,
) -> AxisLimits | None:
    """Compute stable axis limits from all ports; independent of selected trace."""
    if not networks or kind == PlotKind.SMITH:
        return None

    f_all = np.concatenate([n.frequency.f for n in networks])
    f_max = float(np.max(f_all))
    f_max_ghz = hz_to_ghz(f_max)
    x_min_ghz, x_max_ghz = freq_window_ghz(f_max_ghz, freq_window_start_ghz)
    f_positive = f_all[f_all > 0]
    if freq_log and len(f_positive) > 0:
        xmin = max(float(np.min(f_positive)), x_min_ghz * HZ_PER_GHZ)
    else:
        xmin = x_min_ghz * HZ_PER_GHZ
    xmax = x_max_ghz * HZ_PER_GHZ

    y_parts: list[np.ndarray] = []
    for net in networks:
        for m in range(net.nports):
            for n in range(net.nports):
                y_parts.append(trace_y_values(net, m, n, kind, unwrap_phase))

    y_all = np.concatenate(y_parts)
    if kind == PlotKind.MAG_DB:
        ymin = DEFAULT_MAG_Y_MIN_DB
        ymax = DEFAULT_MAG_Y_MAX_DB
    elif kind in (PlotKind.VSWR, PlotKind.INPUT_Z):
        ymin = 0.0
        ymax = float(np.max(y_all))
        if ymax <= ymin:
            ymax = ymin + 1.0
        else:
            ymax *= 1.0 + Y_MARGIN_FRAC
    else:
        ymin = float(np.min(y_all))
        ymax = float(np.max(y_all))
        if ymin == ymax:
            ymin -= 1.0
            ymax += 1.0
        else:
            margin = (ymax - ymin) * Y_MARGIN_FRAC
            ymin -= margin
            ymax += margin

    if graph_settings is not None:
        if graph_settings.x_min_ghz is not None:
            requested_xmin = graph_settings.x_min_ghz * HZ_PER_GHZ
            if freq_log and len(f_positive) > 0:
                xmin = max(float(np.min(f_positive)), requested_xmin)
            else:
                xmin = requested_xmin
        if graph_settings.x_max_ghz is not None:
            xmax = graph_settings.x_max_ghz * HZ_PER_GHZ
        if kind == PlotKind.MAG_DB:
            if graph_settings.mag_y_min_db is not None:
                ymin = graph_settings.mag_y_min_db
            if graph_settings.mag_y_max_db is not None:
                ymax = graph_settings.mag_y_max_db

    xmin, xmax = _valid_span(xmin, xmax, HZ_PER_GHZ)
    ymin, ymax = _valid_span(ymin, ymax, 1.0)
    return AxisLimits(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)


def compute_smith_limits(networks: list[rf.Network]) -> AxisLimits | None:
    """Smith chart bounds from all S-parameters across visible networks."""
    if not networks:
        return None
    re_parts: list[np.ndarray] = []
    im_parts: list[np.ndarray] = []
    for net in networks:
        for m in range(net.nports):
            for n in range(net.nports):
                gamma = net.s[:, m, n]
                re_parts.append(np.real(gamma))
                im_parts.append(np.imag(gamma))
    re_all = np.concatenate(re_parts)
    im_all = np.concatenate(im_parts)
    re_span = float(np.max(re_all) - np.min(re_all))
    im_span = float(np.max(im_all) - np.min(im_all))
    re_margin = max(re_span * Y_MARGIN_FRAC, 0.05)
    im_margin = max(im_span * Y_MARGIN_FRAC, 0.05)
    return AxisLimits(
        xmin=float(np.min(re_all)) - re_margin,
        xmax=float(np.max(re_all)) + re_margin,
        ymin=float(np.min(im_all)) - im_margin,
        ymax=float(np.max(im_all)) + im_margin,
    )


def _style_grid(ax) -> None:
    ax.grid(True, which="major", alpha=0.35)
    ax.grid(True, which="minor", alpha=0.15)
    ax.minorticks_on()


def _apply_plot_theme(ax, figure: Figure, dark_theme: bool) -> None:
    figure.patch.set_facecolor("#1f2329" if dark_theme else "white")
    ax.set_facecolor("#181b20" if dark_theme else "white")


def resolve_line_color(mode: str, dark_theme: bool) -> str:
    if mode == "red":
        return "#d62728"
    if mode == "automatic":
        return "white" if dark_theme else "black"
    return "#1f77b4"


def resolve_trace_color(lf: LoadedFile, mode: str, dark_theme: bool, multi_file: bool) -> str:
    if multi_file and lf.color:
        return lf.color
    return resolve_line_color(mode, dark_theme)


def _make_draggable(artist) -> None:
    if hasattr(artist, "set_draggable"):
        artist.set_draggable(True)
    elif hasattr(artist, "draggable"):
        artist.draggable()


def _capture_draggable_positions(figure: Figure) -> None:
    for ax in figure.axes:
        legend = ax.get_legend()
        if legend is not None:
            loc = getattr(legend, "_loc", None)
            if isinstance(loc, tuple):
                setattr(figure, LEGEND_POS_ATTR, loc)
        for text in ax.texts:
            if text.get_gid() == MARKER_LABEL_GID:
                if text.get_transform() == ax.transAxes:
                    setattr(figure, MARKER_LABEL_POS_ATTR, text.get_position())
                else:
                    axes_pos = ax.transAxes.inverted().transform(text.get_window_extent().p0)
                    setattr(figure, MARKER_LABEL_POS_ATTR, tuple(axes_pos))


def _legend_location(figure: Figure):
    return getattr(figure, LEGEND_POS_ATTR, "best")


def _marker_label_position(figure: Figure) -> tuple[float, float] | None:
    return getattr(figure, MARKER_LABEL_POS_ATTR, None)


def _default_marker_label_offset(marker_freq_ghz: float, x_min: float, x_max: float) -> tuple[str, int]:
    if marker_freq_ghz > (x_min + x_max) / 2.0:
        return "right", -6
    return "left", 6


def _configure_freq_axis(ax, limits: AxisLimits, freq_log: bool) -> None:
    span_ghz = hz_to_ghz(limits.xmax - limits.xmin)
    major_ghz, minor_ghz = ghz_tick_steps(span_ghz)
    ax.set_xlabel("Frequency (GHz)")
    if freq_log:
        ax.xaxis.set_major_locator(LogLocator(base=10))
        ax.xaxis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10) * 0.1))
    else:
        ax.xaxis.set_major_locator(MultipleLocator(major_ghz))
        ax.xaxis.set_minor_locator(MultipleLocator(minor_ghz))


def _configure_y_grid(ax, kind: PlotKind) -> None:
    if kind == PlotKind.MAG_DB:
        ax.yaxis.set_major_locator(MultipleLocator(MAJOR_DB))
        ax.yaxis.set_minor_locator(MultipleLocator(MINOR_DB))
    else:
        ax.yaxis.set_major_locator(AutoLocator())
        ax.yaxis.set_minor_locator(AutoMinorLocator())


def _apply_axis_limits(
    ax,
    limits: AxisLimits,
    kind: PlotKind,
    freq_log: bool,
) -> None:
    ax.set_xlim(hz_to_ghz(limits.xmin), hz_to_ghz(limits.xmax))
    ax.set_ylim(limits.ymin, limits.ymax)
    if freq_log:
        ax.set_xscale("log")
    _configure_freq_axis(ax, limits, freq_log)
    _configure_y_grid(ax, kind)
    _style_grid(ax)


def _plot_trace(
    ax,
    network: rf.Network,
    m: int,
    n: int,
    kind: PlotKind,
    color: str,
    label: str,
    unwrap: bool,
) -> None:
    f_ghz = network.frequency.f / HZ_PER_GHZ
    y = trace_y_values(network, m, n, kind, unwrap)
    ax.plot(f_ghz, y, color=color, label=label)
    ax.set_ylabel(plot_kind_ylabel(kind))


def _marker_value_unit(kind: PlotKind) -> str:
    return plot_kind_unit(kind)


def _format_marker_value(value: float, kind: PlotKind) -> str:
    unit = _marker_value_unit(kind)
    suffix = f" {unit}" if unit else ""
    return f"{value:.4g}{suffix}"


def draw_frequency_markers(
    ax,
    figure: Figure,
    plot_nets: list[tuple[LoadedFile, rf.Network]],
    state: PlotState,
    marker_freq_ghz: float,
    *,
    dark_theme: bool = False,
) -> None:
    marker_line_color = "#f0f3f6" if dark_theme else "#666666"
    ax.axvline(
        marker_freq_ghz,
        color=marker_line_color,
        linestyle="--",
        linewidth=1.0,
        alpha=0.85,
        zorder=5,
    )
    label_lines = [f"{marker_freq_ghz:.4g} GHz"]
    for lf, net in plot_nets:
        y = value_at_frequency(
            net,
            state.m,
            state.n,
            marker_freq_ghz,
            state.kind,
            state.unwrap_phase,
        )
        ax.plot(
            [marker_freq_ghz],
            [y],
            "o",
            color=lf.color or "C3",
            markersize=8,
            zorder=6,
        )
        label = _format_marker_value(y, state.kind)
        if len(plot_nets) > 1:
            label = f"{lf.display_name}: {label}"
        label_lines.append(label)

    text_color = "#f0f3f6" if dark_theme else "#111111"
    box_face = "#1f2329" if dark_theme else "white"
    box_edge = "#8b949e" if dark_theme else "#666666"
    x_min, x_max = ax.get_xlim()
    saved_position = _marker_label_position(figure)
    if saved_position is None:
        ha, x_offset = _default_marker_label_offset(marker_freq_ghz, x_min, x_max)
        marker_label = ax.annotate(
            "\n".join(label_lines),
            xy=(marker_freq_ghz, 0.98),
            xycoords=blended_transform_factory(ax.transData, ax.transAxes),
            xytext=(x_offset, -6),
            textcoords="offset points",
            ha=ha,
            va="top",
            fontsize=8,
            color=text_color,
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": box_face,
                "edgecolor": box_edge,
                "alpha": 0.9,
            },
            zorder=7,
        )
    else:
        marker_label = ax.text(
            saved_position[0],
            saved_position[1],
            "\n".join(label_lines),
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=8,
            color=text_color,
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": box_face,
                "edgecolor": box_edge,
                "alpha": 0.9,
            },
            zorder=7,
        )
    marker_label.set_gid(MARKER_LABEL_GID)
    _make_draggable(marker_label)


def render_plot(
    session: Session,
    state: PlotState,
    figure: Figure,
    *,
    draw_marker: bool = False,
    marker_freq_ghz: float | None = None,
    dark_theme: bool = False,
) -> str | None:
    _capture_draggable_positions(figure)
    figure.clear()
    visible = session.visible_files()
    if not visible:
        ax = figure.add_subplot(111)
        _apply_plot_theme(ax, figure, dark_theme)
        ax.text(0.5, 0.5, "Open a Touchstone file", ha="center", va="center")
        ax.set_axis_off()
        return None

    warning_parts: list[str] = []
    domains = {f.domain or ParamDomain.SINGLE_ENDED for f in visible}
    if len(domains) > 1:
        warning_parts.append("Files use different parameter domains")

    plot_nets: list[tuple[LoadedFile, rf.Network]] = []
    for lf in visible:
        domain = state.domain if state.domain else (lf.domain or ParamDomain.SINGLE_ENDED)
        net = network_for_plot(
            lf.network,
            domain,
            lf.pairing,
            lf.keysight_reorder,
            lf.gmm_cache,
            lf.gmm_cache_key,
        )
        plot_nets.append((lf, net))

    aligned = align_networks([n for _, n in plot_nets])
    if aligned.warning:
        warning_parts.append(aligned.warning)

    if is_tdr_kind(state.kind):
        ax = figure.add_subplot(111)
        _apply_plot_theme(ax, figure, dark_theme)
        if not is_reflection_trace(state.m, state.n):
            ax.text(0.5, 0.5, "TDR requires a reflection trace", ha="center", va="center")
            ax.set_axis_off()
            return "TDR requires a reflection trace"
        tdr = state.tdr_settings or TdrSettings()
        multi_file = len(plot_nets) > 1
        for (lf, _), net in zip(plot_nets, aligned.networks, strict=True):
            trace = tdr_trace_label(net, state.m, state.n, state.domain)
            z_ref = tdr.z_ref_ohms or default_tdr_z_ref_ohms(state.domain.value, trace)
            x = trace_x_values(
                net,
                state.m,
                state.n,
                state.kind,
                tdr_z_ref_ohms=z_ref,
                tdr_window=tdr.window,
                tdr_pad=tdr.pad,
                tdr_sample_count=tdr.sample_count,
                tdr_extrapolate_dc=tdr.extrapolate_dc,
            )
            y = trace_y_values(
                net,
                state.m,
                state.n,
                state.kind,
                state.unwrap_phase,
                tdr_z_ref_ohms=z_ref,
                tdr_window=tdr.window,
                tdr_pad=tdr.pad,
                tdr_sample_count=tdr.sample_count,
                tdr_extrapolate_dc=tdr.extrapolate_dc,
            )
            line_color = resolve_trace_color(lf, state.line_color, dark_theme, multi_file)
            ax.plot(x, y, color=line_color, label=f"{lf.display_name} ({trace})")
        ax.set_xlabel("Time (ns)")
        ax.set_ylabel(plot_kind_ylabel(state.kind))
        if tdr.show_distance:
            meters_per_ns = 0.299792458 * tdr.velocity_factor / 2.0
            secax = ax.secondary_xaxis(
                "top",
                functions=(lambda t: t * meters_per_ns, lambda d: d / meters_per_ns),
            )
            secax.set_xlabel("Distance (m)")
        if tdr.time_min_ns is not None or tdr.time_max_ns is not None:
            left, right = ax.get_xlim()
            ax.set_xlim(
                tdr.time_min_ns if tdr.time_min_ns is not None else left,
                tdr.time_max_ns if tdr.time_max_ns is not None else right,
            )
        _style_grid(ax)
        legend = ax.legend(loc=_legend_location(figure), fontsize=8)
        _make_draggable(legend)
    elif state.kind == PlotKind.SMITH:
        ax = figure.add_subplot(111)
        _apply_plot_theme(ax, figure, dark_theme)
        title_net = aligned.networks[0]
        multi_file = len(plot_nets) > 1
        for (lf, _), net in zip(plot_nets, aligned.networks, strict=True):
            line_color = resolve_trace_color(lf, state.line_color, dark_theme, multi_file)
            net.plot_s_smith(m=state.m, n=state.n, ax=ax, color=line_color, label=lf.display_name)
        smith_limits = compute_smith_limits(aligned.networks)
        if smith_limits is not None:
            ax.set_xlim(smith_limits.xmin, smith_limits.xmax)
            ax.set_ylim(smith_limits.ymin, smith_limits.ymax)
        legend = ax.legend(loc=_legend_location(figure), fontsize=8)
        _make_draggable(legend)
        ax.set_title(trace_label(title_net, state.m, state.n, state.domain))
        _style_grid(ax)
    else:
        ax = figure.add_subplot(111)
        _apply_plot_theme(ax, figure, dark_theme)
        limits = compute_axis_limits(
            aligned.networks,
            state.kind,
            unwrap_phase=state.unwrap_phase,
            freq_log=state.freq_log,
            freq_window_start_ghz=state.freq_window_start_ghz,
            graph_settings=state.graph_settings,
        )
        multi_file = len(plot_nets) > 1
        for (lf, _), net in zip(plot_nets, aligned.networks, strict=True):
            trace = trace_label(net, state.m, state.n, state.domain)
            line_color = resolve_trace_color(lf, state.line_color, dark_theme, multi_file)
            _plot_trace(
                ax,
                net,
                state.m,
                state.n,
                state.kind,
                line_color,
                f"{lf.display_name} ({trace})",
                state.unwrap_phase,
            )
        if state.comparison_enabled and len(aligned.networks) > 1:
            ref_idx = min(max(state.reference_index, 0), len(aligned.networks) - 1)
            ref = aligned.networks[ref_idx]
            ref_file = plot_nets[ref_idx][0]
            ref_y = trace_y_values(ref, state.m, state.n, state.kind, state.unwrap_phase)
            for idx, ((lf, _), net) in enumerate(zip(plot_nets, aligned.networks, strict=True)):
                if idx == ref_idx:
                    continue
                trace = trace_label(net, state.m, state.n, state.domain)
                y = trace_y_values(net, state.m, state.n, state.kind, state.unwrap_phase)
                ax.plot(
                    net.frequency.f / HZ_PER_GHZ,
                    y - ref_y,
                    linestyle="--",
                    label=f"{lf.display_name} - {ref_file.display_name} ({trace})",
                )
        if limits is not None:
            _apply_axis_limits(ax, limits, state.kind, state.freq_log)
        if draw_marker and marker_freq_ghz is not None:
            aligned_nets = [
                (lf, net) for (lf, _), net in zip(plot_nets, aligned.networks, strict=True)
            ]
            draw_frequency_markers(
                ax,
                figure,
                aligned_nets,
                state,
                marker_freq_ghz,
                dark_theme=dark_theme,
            )
        legend = ax.legend(loc=_legend_location(figure), fontsize=8)
        _make_draggable(legend)

    figure.tight_layout()
    return "; ".join(warning_parts) if warning_parts else None


def status_text(session: Session, aligned_npoints: int, domain: ParamDomain) -> str:
    n = len(session.files)
    vis = len(session.visible_files())
    dom = "MM" if domain == ParamDomain.MIXED_MODE else "SE"
    if aligned_npoints:
        return f"{vis}/{n} files visible | {dom} | {aligned_npoints} pts"
    return f"{vis}/{n} files visible | {dom}"
