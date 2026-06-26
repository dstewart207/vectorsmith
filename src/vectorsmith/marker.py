"""Marker interpolation and readout helpers."""

from __future__ import annotations

import numpy as np
import skrf as rf

from vectorsmith.compare import format_freq_span
from vectorsmith.plot_kinds import PlotKind
from vectorsmith.rf_trace import HZ_PER_GHZ, plot_kind_unit, trace_x_values, trace_y_values


def format_frequency_hz(hz: float) -> str:
    """Format a single frequency or step size in Hz."""
    return format_freq_span(0.0, hz).split(" - ", 1)[1]


def describe_frequency_step(f_hz: np.ndarray) -> str:
    """Describe uniform or variable frequency stepping."""
    f = np.sort(np.unique(np.asarray(f_hz, dtype=float)))
    if len(f) < 2:
        return "-"
    diffs = np.diff(f)
    if np.allclose(diffs, diffs[0], rtol=1e-5, atol=0.0):
        return f"{format_frequency_hz(float(diffs[0]))} (uniform)"
    median = float(np.median(diffs))
    return f"variable (median: {format_frequency_hz(median)})"


def value_at_frequency(
    network: rf.Network,
    m: int,
    n: int,
    freq_ghz: float,
    kind: PlotKind,
    unwrap: bool = False,
) -> float:
    """Interpolate plotted Y value at frequency (GHz)."""
    f_ghz = network.frequency.f / HZ_PER_GHZ
    y = trace_y_values(network, m, n, kind, unwrap)
    f_min, f_max = float(f_ghz.min()), float(f_ghz.max())
    f_clamped = float(np.clip(freq_ghz, f_min, f_max))
    return float(np.interp(f_clamped, f_ghz, y))


def value_at_x(
    network: rf.Network,
    m: int,
    n: int,
    x_value: float,
    kind: PlotKind,
    unwrap: bool = False,
    **trace_kwargs,
) -> float:
    """Interpolate plotted Y value at the active plot X coordinate."""
    x = trace_x_values(network, m, n, kind, **trace_kwargs)
    y = trace_y_values(network, m, n, kind, unwrap, **trace_kwargs)
    x_min, x_max = float(x.min()), float(x.max())
    x_clamped = float(np.clip(x_value, x_min, x_max))
    return float(np.interp(x_clamped, x, y))


def format_marker_readout(
    filename: str,
    trace_name: str,
    freq_ghz: float,
    value: float,
    kind: PlotKind,
) -> str:
    unit = plot_kind_unit(kind)
    suffix = f" {unit}" if unit else ""
    return f"{filename}  {trace_name} @ {freq_ghz:.4g} GHz: {value:.4g}{suffix}"


def format_tdr_marker_readout(
    filename: str,
    trace_name: str,
    time_ns: float,
    value: float,
) -> str:
    return f"{filename}  {trace_name} @ {time_ns:.4g} ns: {value:.4g} ohm"


def freq_range_ghz(network: rf.Network) -> tuple[float, float]:
    f_ghz = network.frequency.f / HZ_PER_GHZ
    return float(f_ghz.min()), float(f_ghz.max())
