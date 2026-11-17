"""Marker interpolation, readout, and search helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import skrf as rf

from vectorsmith.compare import format_freq_span
from vectorsmith.plot_kinds import PlotKind
from vectorsmith.rf_trace import HZ_PER_GHZ, plot_kind_unit, trace_x_values, trace_y_values


@dataclass(frozen=True)
class ExtremumResult:
    x: float
    y: float
    kind: str  # "min" or "max"


@dataclass(frozen=True)
class BandwidthResult:
    center_x: float
    low_x: float
    high_x: float
    bandwidth: float
    level_y: float
    peak_x: float
    peak_y: float


@dataclass(frozen=True)
class MarkerDelta:
    dx: float
    dy: float
    x_unit: str
    y_unit: str


@dataclass(frozen=True)
class TdrFeature:
    time_ns: float
    impedance_ohm: float
    kind: str  # "peak", "valley", or "step"
    score: float


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
    marker_label: str | None = None,
) -> str:
    unit = plot_kind_unit(kind)
    suffix = f" {unit}" if unit else ""
    prefix = f"{marker_label}  " if marker_label else ""
    return f"{prefix}{filename}  {trace_name} @ {freq_ghz:.4g} GHz: {value:.4g}{suffix}"


def format_tdr_marker_readout(
    filename: str,
    trace_name: str,
    time_ns: float,
    value: float,
    marker_label: str | None = None,
) -> str:
    prefix = f"{marker_label}  " if marker_label else ""
    return f"{prefix}{filename}  {trace_name} @ {time_ns:.4g} ns: {value:.4g} ohm"


def freq_range_ghz(network: rf.Network) -> tuple[float, float]:
    f_ghz = network.frequency.f / HZ_PER_GHZ
    return float(f_ghz.min()), float(f_ghz.max())


def find_extrema(x: np.ndarray, y: np.ndarray) -> tuple[ExtremumResult, ExtremumResult]:
    """Return global min and max of y versus x."""
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    if x_arr.size == 0 or y_arr.size == 0:
        raise ValueError("Cannot find extrema of empty arrays")
    imin = int(np.argmin(y_arr))
    imax = int(np.argmax(y_arr))
    return (
        ExtremumResult(x=float(x_arr[imin]), y=float(y_arr[imin]), kind="min"),
        ExtremumResult(x=float(x_arr[imax]), y=float(y_arr[imax]), kind="max"),
    )


def _crossing(x0: float, y0: float, x1: float, y1: float, level: float) -> float:
    if y1 == y0:
        return float(x0)
    frac = (level - y0) / (y1 - y0)
    return float(x0 + frac * (x1 - x0))


def bandwidth_at_level(
    x: np.ndarray,
    y_db: np.ndarray,
    level_db: float = -3.0,
    *,
    relative_to: str = "max",
) -> BandwidthResult | None:
    """
    Find bandwidth where y stays above peak+level_db (for positive peaks like |S21|).

    For return-loss style curves that peak near 0 dB and dip at resonance, use
    relative_to='min' to measure width around the minimum (notch).
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y_db, dtype=float)
    if x_arr.size < 2:
        return None

    if relative_to == "min":
        peak_idx = int(np.argmin(y_arr))
        peak_y = float(y_arr[peak_idx])
        threshold = peak_y - level_db  # level_db negative => threshold above min
        inside = y_arr <= threshold
    else:
        peak_idx = int(np.argmax(y_arr))
        peak_y = float(y_arr[peak_idx])
        threshold = peak_y + level_db
        inside = y_arr >= threshold

    if not np.any(inside):
        return None

    # Expand contiguous region containing the peak.
    left = peak_idx
    while left > 0 and inside[left - 1]:
        left -= 1
    right = peak_idx
    while right < len(inside) - 1 and inside[right + 1]:
        right += 1

    low_x = float(x_arr[left])
    high_x = float(x_arr[right])
    if left > 0:
        low_x = _crossing(float(x_arr[left - 1]), float(y_arr[left - 1]), float(x_arr[left]), float(y_arr[left]), threshold)
    if right < len(x_arr) - 1:
        high_x = _crossing(float(x_arr[right]), float(y_arr[right]), float(x_arr[right + 1]), float(y_arr[right + 1]), threshold)

    return BandwidthResult(
        center_x=0.5 * (low_x + high_x),
        low_x=low_x,
        high_x=high_x,
        bandwidth=high_x - low_x,
        level_y=threshold,
        peak_x=float(x_arr[peak_idx]),
        peak_y=peak_y,
    )


def marker_delta(
    x_a: float,
    y_a: float,
    x_b: float,
    y_b: float,
    *,
    x_unit: str,
    y_unit: str,
) -> MarkerDelta:
    return MarkerDelta(dx=x_b - x_a, dy=y_b - y_a, x_unit=x_unit, y_unit=y_unit)


def format_marker_delta(delta: MarkerDelta, label_a: str = "M1", label_b: str = "M2") -> str:
    x_suffix = f" {delta.x_unit}" if delta.x_unit else ""
    y_suffix = f" {delta.y_unit}" if delta.y_unit else ""
    return (
        f"Δ({label_b}-{label_a}): "
        f"Δx={delta.dx:.4g}{x_suffix}, Δy={delta.dy:.4g}{y_suffix}"
    )


def find_tdr_features(
    time_ns: np.ndarray,
    impedance_ohm: np.ndarray,
    *,
    z_ref_ohms: float = 50.0,
    max_features: int = 5,
    min_step_ohm: float = 1.0,
) -> list[TdrFeature]:
    """
    Find impedance peaks/valleys and large steps in a TDR waveform.

    Peaks/valleys are ranked by |Z - Zref|. Steps are ranked by |ΔZ|.
    """
    from scipy.signal import find_peaks

    t = np.asarray(time_ns, dtype=float)
    z = np.asarray(impedance_ohm, dtype=float)
    if t.size < 3:
        return []

    # Minimum spacing ~2% of span (at least 2 samples).
    min_distance = max(2, int(0.02 * len(z)))

    deviation = z - z_ref_ohms
    abs_dev = np.abs(deviation)
    peak_idx, _ = find_peaks(abs_dev, height=min_step_ohm, distance=min_distance)
    peaks: list[TdrFeature] = []
    for i in peak_idx:
        peaks.append(
            TdrFeature(
                time_ns=float(t[i]),
                impedance_ohm=float(z[i]),
                kind="peak" if deviation[i] >= 0 else "valley",
                score=float(abs_dev[i]),
            )
        )

    # Steps from raw differences; ignore convolution edge artifacts.
    dz = np.diff(z)
    abs_dz = np.abs(dz)
    if abs_dz.size >= 4:
        abs_dz = abs_dz.copy()
        abs_dz[:2] = 0.0
        abs_dz[-2:] = 0.0
    step_idx, _ = find_peaks(abs_dz, height=min_step_ohm, distance=min_distance)
    steps: list[TdrFeature] = []
    for i in step_idx:
        steps.append(
            TdrFeature(
                time_ns=float(t[i + 1]),
                impedance_ohm=float(z[i + 1]),
                kind="step",
                score=float(abs_dz[i]),
            )
        )

    peaks.sort(key=lambda item: item.score, reverse=True)
    steps.sort(key=lambda item: item.score, reverse=True)

    peak_budget = max(1, max_features // 2)
    step_budget = max(1, max_features - peak_budget)
    selected = peaks[:peak_budget] + steps[:step_budget]
    selected.sort(key=lambda item: item.score, reverse=True)
    return selected[:max_features]
