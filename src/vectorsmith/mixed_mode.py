"""Mixed-mode (differential/common) S-parameter handling."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np
import skrf as rf

if TYPE_CHECKING:
    from vectorsmith.session import PortPairingConfig


class ParamDomain(Enum):
    SINGLE_ENDED = "single_ended"
    MIXED_MODE = "mixed_mode"


def is_native_mixed_mode(network: rf.Network) -> bool:
    modes = getattr(network, "port_modes", None)
    if modes is None:
        return False
    arr = np.asarray(modes)
    return np.any(arr == "D") or np.any(arr == "C")


def gmm_reorder_matrix(s_block: np.ndarray) -> np.ndarray:
    """Reorder 2x2 submatrix from Keysight-style to skrf GMM layout."""
    b = np.array(
        [
            [1, 0, 0, 0],
            [0, 0, 1, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
        ],
        dtype=float,
    ).reshape(4, 4)
    flat = s_block.reshape(4, 4)
    return b.dot(flat.dot(b))


def apply_keysight_reorder(network: rf.Network) -> rf.Network:
    out = network.copy()
    for i in range(out.frequency.npoints):
        out.s[i, :, :] = gmm_reorder_matrix(out.s[i, :, :])
    return out


@dataclass
class MixedModeTrace:
    """UI-facing mixed-mode trace id, e.g. SDD11."""

    label: str
    m: int
    n: int
    kind: str  # dd, dc, cd, cc


def _trace_kind(network: rf.Network, m: int, n: int) -> str:
    modes = np.asarray(getattr(network, "port_modes", ["S"] * network.nports))
    if len(modes) <= max(m, n):
        return "se"
    pm, pn = str(modes[m]), str(modes[n])
    return {"D": "d", "C": "c"}.get(pm, "s") + {"D": "d", "C": "c"}.get(pn, "s")


def _mode_pair_indices(network: rf.Network) -> dict[str, dict[int, int]]:
    modes = np.asarray(getattr(network, "port_modes", ["S"] * network.nports))
    indices: dict[str, dict[int, int]] = {"D": {}, "C": {}}
    for mode in ("D", "C"):
        pair_num = 1
        for port_idx, port_mode in enumerate(modes):
            if str(port_mode) == mode:
                indices[mode][port_idx] = pair_num
                pair_num += 1
    return indices


def mixed_mode_trace_label(network: rf.Network, m: int, n: int) -> str:
    modes = np.asarray(getattr(network, "port_modes", ["S"] * network.nports))
    if len(modes) <= max(m, n):
        return network._fmt_trace_name(m, n)  # noqa: SLF001
    out_mode = str(modes[m])
    in_mode = str(modes[n])
    pair_indices = _mode_pair_indices(network)
    if out_mode not in pair_indices or in_mode not in pair_indices:
        return network._fmt_trace_name(m, n)  # noqa: SLF001
    out_pair = pair_indices[out_mode].get(m)
    in_pair = pair_indices[in_mode].get(n)
    if out_pair is None or in_pair is None:
        return network._fmt_trace_name(m, n)  # noqa: SLF001
    return f"S{out_mode}{in_mode}{out_pair}{in_pair}"


def trace_label(network: rf.Network, m: int, n: int, domain: ParamDomain) -> str:
    if domain == ParamDomain.MIXED_MODE:
        return mixed_mode_trace_label(network, m, n)
    return network._fmt_trace_name(m, n)  # noqa: SLF001


def tdr_trace_label(network: rf.Network, m: int, n: int, domain: ParamDomain) -> str:
    if domain == ParamDomain.MIXED_MODE:
        label = mixed_mode_trace_label(network, m, n)
        if label.startswith("S"):
            return f"T{label[1:]}"
        return f"T{m + 1}{n + 1}"
    return f"T{m + 1}{n + 1}"


def list_mixed_mode_traces(network: rf.Network) -> list[MixedModeTrace]:
    traces: list[MixedModeTrace] = []
    n = network.nports
    kind_order = {"dd": 0, "cd": 1, "dc": 2, "cc": 3}
    raw: list[tuple[int, int, int, MixedModeTrace]] = []
    for m in range(n):
        for nn in range(n):
            kind = _trace_kind(network, m, nn)
            if kind == "ss":
                continue
            label = mixed_mode_trace_label(network, m, nn)
            raw.append((kind_order.get(kind, 99), m, nn, MixedModeTrace(label=label, m=m, n=nn, kind=kind)))
    for _, _, _, trace in sorted(raw, key=lambda item: (item[0], item[1], item[2])):
        traces.append(trace)
    return traces


def list_mixed_mode_tdr_traces(network: rf.Network) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    for trace in list_mixed_mode_traces(network):
        if trace.m != trace.n:
            continue
        if trace.kind not in {"dd", "cc"}:
            continue
        out.append((trace.m, trace.n, tdr_trace_label(network, trace.m, trace.n, ParamDomain.MIXED_MODE)))
    return out


def list_single_ended_traces(nports: int) -> list[tuple[int, int, str]]:
    out: list[tuple[int, int, str]] = []
    for m in range(nports):
        for n in range(nports):
            out.append((m, n, f"S{m + 1}{n + 1}"))
    return out


def list_single_ended_tdr_traces(nports: int) -> list[tuple[int, int, str]]:
    return [(i, i, f"T{i + 1}{i + 1}") for i in range(nports)]


def convert_to_gmm(
    network: rf.Network,
    pairing: PortPairingConfig,
    keysight_reorder: bool = False,
) -> rf.Network:
    """Convert single-ended network to generalized mixed-mode."""
    out = network.copy()
    if pairing.renumber_map:
        old = list(range(out.nports))
        new = pairing.renumber_map
        out.renumber(old, new)
    if pairing.num_diff_ports > 0:
        out.se2gmm(p=pairing.num_diff_ports)
    if keysight_reorder:
        out = apply_keysight_reorder(out)
    return out


def network_for_plot(
    network: rf.Network,
    domain: ParamDomain,
    pairing: PortPairingConfig,
    keysight_reorder: bool,
    gmm_cache: dict[str, rf.Network],
    cache_key: str,
) -> rf.Network:
    if domain == ParamDomain.SINGLE_ENDED:
        return network
    if is_native_mixed_mode(network):
        if keysight_reorder:
            ck = f"{cache_key}:ks"
            if ck not in gmm_cache:
                gmm_cache[ck] = apply_keysight_reorder(network)
            return gmm_cache[ck]
        return network
    if cache_key in gmm_cache:
        return gmm_cache[cache_key]
    converted = convert_to_gmm(network, pairing, keysight_reorder)
    gmm_cache[cache_key] = converted
    return converted


def default_pairing_for_nports(nports: int) -> PortPairingConfig:
    from vectorsmith.session import PortPairingConfig

    if nports >= 4:
        return PortPairingConfig(
            num_diff_ports=2,
            renumber_map=[0, 2, 1, 3] + list(range(4, nports)),
        )
    if nports == 2:
        return PortPairingConfig(num_diff_ports=1, renumber_map=[0, 1])
    return PortPairingConfig(num_diff_ports=0, renumber_map=list(range(nports)))
