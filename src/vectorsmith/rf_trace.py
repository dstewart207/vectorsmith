"""Shared RF trace Y-value computation (avoids plots <-> marker import cycle)."""

from __future__ import annotations

import numpy as np
import skrf as rf

from vectorsmith.plot_kinds import PlotKind

HZ_PER_GHZ = 1e9
SEC_PER_NS = 1e-9
EPSILON_GAMMA_DENOM = 1e-9


def _gamma_from_s(s: np.ndarray) -> np.ndarray:
    return s


def _vswr_from_gamma(gamma: np.ndarray) -> np.ndarray:
    mag = np.abs(gamma)
    mag = np.clip(mag, 0, 0.9999)
    return (1 + mag) / (1 - mag)


def is_reflection_trace(m: int, n: int) -> bool:
    return m == n


def is_tdr_kind(kind: PlotKind) -> bool:
    return kind == PlotKind.TDR_IMPEDANCE


def is_frequency_domain_kind(kind: PlotKind) -> bool:
    return kind != PlotKind.SMITH and not is_tdr_kind(kind)


def plot_kind_unit(kind: PlotKind) -> str:
    return {
        PlotKind.MAG_DB: "dB",
        PlotKind.PHASE_DEG: "deg",
        PlotKind.VSWR: "",
        PlotKind.INPUT_Z: "ohm",
        PlotKind.RETURN_LOSS_DB: "dB",
        PlotKind.INSERTION_LOSS_DB: "dB",
        PlotKind.GROUP_DELAY_NS: "ns",
        PlotKind.REAL_Z: "ohm",
        PlotKind.IMAG_Z: "ohm",
        PlotKind.TDR_IMPEDANCE: "ohm",
    }.get(kind, "")


def plot_kind_ylabel(kind: PlotKind) -> str:
    return {
        PlotKind.MAG_DB: "|S| (dB)",
        PlotKind.PHASE_DEG: "Phase (deg)",
        PlotKind.VSWR: "VSWR",
        PlotKind.INPUT_Z: "|Z| (ohm)",
        PlotKind.RETURN_LOSS_DB: "Return loss (dB)",
        PlotKind.INSERTION_LOSS_DB: "Insertion loss (dB)",
        PlotKind.GROUP_DELAY_NS: "Group delay (ns)",
        PlotKind.REAL_Z: "Re(Z) (ohm)",
        PlotKind.IMAG_Z: "Im(Z) (ohm)",
        PlotKind.TDR_IMPEDANCE: "Impedance (ohm)",
    }.get(kind, "")


def _input_impedance(network: rf.Network, m: int, n: int) -> np.ndarray:
    s_mn = network.s[:, m, n]
    z = network.z0[:, m] if network.z0.ndim > 1 else network.z0
    return z * (1 + s_mn) / (1 - s_mn + 1e-30)


def gamma_to_impedance(gamma: np.ndarray, z_ref_ohms: float) -> np.ndarray:
    denom = 1 - gamma
    denom = np.where(np.abs(denom) < EPSILON_GAMMA_DENOM, EPSILON_GAMMA_DENOM, denom)
    return z_ref_ohms * (1 + gamma) / denom


def default_tdr_z_ref_ohms(domain_value: str | None, trace_name: str = "") -> float:
    upper = trace_name.upper()
    if domain_value == "mixed_mode" or upper.startswith(("SDD", "TDD")):
        return 100.0
    return 50.0


def extract_reflection_oneport(network: rf.Network, m: int, n: int) -> rf.Network:
    if not is_reflection_trace(m, n):
        raise ValueError("TDR requires a reflection trace.")
    one = rf.Network(
        frequency=network.frequency.copy(),
        s=network.s[:, m : m + 1, n : n + 1].copy(),
        z0=np.full((network.frequency.npoints, 1), 50.0),
    )
    return one


def prepare_tdr_oneport(
    network: rf.Network,
    m: int,
    n: int,
    *,
    extrapolate_dc: bool = True,
) -> rf.Network:
    one = extract_reflection_oneport(network, m, n)
    if extrapolate_dc and float(one.frequency.f.min()) > 0.0:
        try:
            one = one.extrapolate_to_dc(kind="linear")
        except Exception:
            f = np.insert(one.frequency.f, 0, 0.0)
            s = np.insert(one.s[:, 0, 0], 0, one.s[0, 0, 0])
            one = rf.Network(
                frequency=rf.Frequency.from_f(f, unit="Hz"),
                s=s.reshape(-1, 1, 1),
                z0=np.full((len(f), 1), 50.0),
            )
    f = one.frequency.f
    if len(f) > 2 and not np.allclose(np.diff(f), np.diff(f)[0], rtol=1e-5, atol=0.0):
        uniform = rf.Frequency.from_f(np.linspace(float(f.min()), float(f.max()), len(f)), unit="Hz")
        one = one.interpolate(uniform, kind="linear")
    return one


def tdr_impedance_response(
    network: rf.Network,
    m: int,
    n: int,
    *,
    z_ref_ohms: float,
    window: str = "hamming",
    pad: int = 0,
    sample_count: int | None = None,
    extrapolate_dc: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    one = prepare_tdr_oneport(network, m, n, extrapolate_dc=extrapolate_dc)
    t_s, gamma = one.step_response(
        window=window,
        n=sample_count,
        pad=pad,
        squeeze=True,
    )
    gamma = np.asarray(gamma, dtype=complex)
    impedance = np.real(gamma_to_impedance(gamma, z_ref_ohms))
    return np.asarray(t_s, dtype=float), impedance


def trace_x_values(
    network: rf.Network,
    m: int,
    n: int,
    kind: PlotKind,
    *,
    tdr_z_ref_ohms: float = 50.0,
    tdr_window: str = "hamming",
    tdr_pad: int = 0,
    tdr_sample_count: int | None = None,
    tdr_extrapolate_dc: bool = True,
) -> np.ndarray:
    if is_tdr_kind(kind):
        t_s, _ = tdr_impedance_response(
            network,
            m,
            n,
            z_ref_ohms=tdr_z_ref_ohms,
            window=tdr_window,
            pad=tdr_pad,
            sample_count=tdr_sample_count,
            extrapolate_dc=tdr_extrapolate_dc,
        )
        return t_s / SEC_PER_NS
    return network.frequency.f / HZ_PER_GHZ


def trace_y_values(
    network: rf.Network,
    m: int,
    n: int,
    kind: PlotKind,
    unwrap: bool,
    *,
    tdr_z_ref_ohms: float = 50.0,
    tdr_window: str = "hamming",
    tdr_pad: int = 0,
    tdr_sample_count: int | None = None,
    tdr_extrapolate_dc: bool = True,
) -> np.ndarray:
    s_mn = network.s[:, m, n]
    if kind == PlotKind.MAG_DB:
        return 20 * np.log10(np.abs(s_mn) + 1e-30)
    if kind == PlotKind.PHASE_DEG:
        phase = np.angle(s_mn, deg=True)
        if unwrap:
            phase = np.unwrap(np.deg2rad(phase), axis=0)
            phase = np.rad2deg(phase)
        return phase
    if kind == PlotKind.VSWR:
        return _vswr_from_gamma(_gamma_from_s(s_mn))
    if kind == PlotKind.INPUT_Z:
        return np.abs(_input_impedance(network, m, n))
    if kind == PlotKind.RETURN_LOSS_DB:
        return -20 * np.log10(np.abs(s_mn) + 1e-30)
    if kind == PlotKind.INSERTION_LOSS_DB:
        return -20 * np.log10(np.abs(s_mn) + 1e-30)
    if kind == PlotKind.GROUP_DELAY_NS:
        phase = np.unwrap(np.angle(s_mn), axis=0)
        omega = 2 * np.pi * network.frequency.f
        return -np.gradient(phase, omega) / SEC_PER_NS
    if kind == PlotKind.REAL_Z:
        return np.real(_input_impedance(network, m, n))
    if kind == PlotKind.IMAG_Z:
        return np.imag(_input_impedance(network, m, n))
    if kind == PlotKind.TDR_IMPEDANCE:
        _, impedance = tdr_impedance_response(
            network,
            m,
            n,
            z_ref_ohms=tdr_z_ref_ohms,
            window=tdr_window,
            pad=tdr_pad,
            sample_count=tdr_sample_count,
            extrapolate_dc=tdr_extrapolate_dc,
        )
        return impedance
    return np.abs(s_mn)
