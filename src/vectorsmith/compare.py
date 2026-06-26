"""Align multiple networks onto a common frequency grid."""

from __future__ import annotations

from dataclasses import dataclass

import skrf as rf

try:
    from skrf.network import overlap_multi
except ImportError:
    from skrf.util import overlap_multi  # type: ignore[attr-defined]


@dataclass
class OverlapResult:
    networks: list[rf.Network]
    npoints: int
    f_min_hz: float
    f_max_hz: float
    warning: str | None = None


def align_networks(networks: list[rf.Network]) -> OverlapResult:
    if not networks:
        return OverlapResult([], 0, 0.0, 0.0)
    if len(networks) == 1:
        n = networks[0]
        f = n.frequency.f
        return OverlapResult(
            [n],
            len(f),
            float(f.min()),
            float(f.max()),
        )
    try:
        overlapped = overlap_multi(networks)
    except Exception as exc:  # noqa: BLE001
        target = networks[0].frequency
        fallback = [n.interpolate(target) for n in networks[1:]]
        overlapped = [networks[0], *fallback]
        f = overlapped[0].frequency.f
        return OverlapResult(
            overlapped,
            len(f),
            float(f.min()),
            float(f.max()),
            warning=str(exc),
        )
    f = overlapped[0].frequency.f
    return OverlapResult(
        overlapped,
        len(f),
        float(f.min()),
        float(f.max()),
    )


def format_freq_span(hz_min: float, hz_max: float) -> str:
    def _fmt(v: float) -> str:
        if v >= 1e9:
            return f"{v / 1e9:.3g} GHz"
        if v >= 1e6:
            return f"{v / 1e6:.3g} MHz"
        if v >= 1e3:
            return f"{v / 1e3:.3g} kHz"
        return f"{v:.3g} Hz"

    return f"{_fmt(hz_min)} - {_fmt(hz_max)}"
