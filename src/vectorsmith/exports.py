"""CSV export helpers for traces and markers."""

from __future__ import annotations

import csv
from pathlib import Path

from vectorsmith.compare import align_networks
from vectorsmith.marker import value_at_frequency, value_at_x
from vectorsmith.mixed_mode import network_for_plot, tdr_trace_label, trace_label
from vectorsmith.plot_kinds import PlotKind
from vectorsmith.plots import PlotState, TdrSettings
from vectorsmith.rf_trace import (
    HZ_PER_GHZ,
    default_tdr_z_ref_ohms,
    is_tdr_kind,
    plot_kind_unit,
    trace_x_values,
    trace_y_values,
)
from vectorsmith.session import Session


def _plot_networks(session: Session, state: PlotState):
    pairs = []
    for lf in session.visible_files():
        net = network_for_plot(
            lf.network,
            state.domain,
            lf.pairing,
            lf.keysight_reorder,
            lf.gmm_cache,
            lf.gmm_cache_key,
        )
        pairs.append((lf, net))
    return pairs


def export_trace_csv(path: str | Path, session: Session, state: PlotState) -> None:
    pairs = _plot_networks(session, state)
    unit = plot_kind_unit(state.kind)
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "trace", "domain", "x", "x_unit", "value", "unit", "plot_kind"])
        if not pairs:
            return
        if is_tdr_kind(state.kind):
            tdr = state.tdr_settings or TdrSettings()
            for lf, net in pairs:
                trace = tdr_trace_label(net, state.m, state.n, state.domain)
                z_ref = tdr.z_ref_ohms or default_tdr_z_ref_ohms(state.domain.value, trace)
                kwargs = {
                    "tdr_z_ref_ohms": z_ref,
                    "tdr_window": tdr.window,
                    "tdr_pad": tdr.pad,
                    "tdr_sample_count": tdr.sample_count,
                    "tdr_extrapolate_dc": tdr.extrapolate_dc,
                }
                x = trace_x_values(net, state.m, state.n, state.kind, **kwargs)
                y = trace_y_values(net, state.m, state.n, state.kind, state.unwrap_phase, **kwargs)
                for xv, yv in zip(x, y, strict=True):
                    writer.writerow([lf.display_name, trace, state.domain.value, xv, "ns", yv, unit, state.kind.value])
            return
        aligned = align_networks([net for _, net in pairs])
        for (lf, _), net in zip(pairs, aligned.networks, strict=True):
            trace = trace_label(net, state.m, state.n, state.domain)
            x = net.frequency.f / HZ_PER_GHZ
            y = trace_y_values(net, state.m, state.n, state.kind, state.unwrap_phase)
            for xv, yv in zip(x, y, strict=True):
                writer.writerow([lf.display_name, trace, state.domain.value, xv, "GHz", yv, unit, state.kind.value])


def export_marker_csv(
    path: str | Path,
    session: Session,
    state: PlotState,
    marker_x: float,
) -> None:
    pairs = _plot_networks(session, state)
    unit = plot_kind_unit(state.kind)
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "trace", "domain", "x", "x_unit", "value", "unit", "plot_kind"])
        for lf, net in pairs:
            if is_tdr_kind(state.kind):
                tdr = state.tdr_settings or TdrSettings()
                trace = tdr_trace_label(net, state.m, state.n, state.domain)
                z_ref = tdr.z_ref_ohms or default_tdr_z_ref_ohms(state.domain.value, trace)
                value = value_at_x(
                    net,
                    state.m,
                    state.n,
                    marker_x,
                    state.kind,
                    state.unwrap_phase,
                    tdr_z_ref_ohms=z_ref,
                    tdr_window=tdr.window,
                    tdr_pad=tdr.pad,
                    tdr_sample_count=tdr.sample_count,
                    tdr_extrapolate_dc=tdr.extrapolate_dc,
                )
                writer.writerow([lf.display_name, trace, state.domain.value, marker_x, "ns", value, unit, state.kind.value])
            else:
                trace = trace_label(net, state.m, state.n, state.domain)
                value = value_at_frequency(net, state.m, state.n, marker_x, state.kind, state.unwrap_phase)
                writer.writerow([lf.display_name, trace, state.domain.value, marker_x, "GHz", value, unit, state.kind.value])
