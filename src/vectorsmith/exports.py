"""CSV and Touchstone export helpers."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import skrf as rf

from vectorsmith.compare import align_networks
from vectorsmith.marker import value_at_frequency, value_at_x
from vectorsmith.mixed_mode import (
    ParamDomain,
    convert_to_gmm,
    is_native_mixed_mode,
    network_for_plot,
    tdr_trace_label,
    trace_label,
)
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
from vectorsmith.session import LoadedFile, PlotMarker, Session


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
    traces = state.selected_traces()
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "trace", "domain", "x", "x_unit", "value", "unit", "plot_kind"])
        if not pairs:
            return
        if is_tdr_kind(state.kind):
            tdr = state.tdr_settings or TdrSettings()
            for lf, net in pairs:
                for m, n in traces:
                    if m != n:
                        continue
                    trace = tdr_trace_label(net, m, n, state.domain)
                    z_ref = tdr.z_ref_ohms or default_tdr_z_ref_ohms(state.domain.value, trace)
                    kwargs = {
                        "tdr_z_ref_ohms": z_ref,
                        "tdr_window": tdr.window,
                        "tdr_pad": tdr.pad,
                        "tdr_sample_count": tdr.sample_count,
                        "tdr_extrapolate_dc": tdr.extrapolate_dc,
                    }
                    x = trace_x_values(net, m, n, state.kind, **kwargs)
                    y = trace_y_values(net, m, n, state.kind, state.unwrap_phase, **kwargs)
                    for xv, yv in zip(x, y, strict=True):
                        writer.writerow(
                            [lf.display_name, trace, state.domain.value, xv, "ns", yv, unit, state.kind.value]
                        )
            return
        aligned = align_networks([net for _, net in pairs])
        for (lf, _), net in zip(pairs, aligned.networks, strict=True):
            for m, n in traces:
                trace = trace_label(net, m, n, state.domain)
                x = net.frequency.f / HZ_PER_GHZ
                y = trace_y_values(net, m, n, state.kind, state.unwrap_phase)
                for xv, yv in zip(x, y, strict=True):
                    writer.writerow(
                        [lf.display_name, trace, state.domain.value, xv, "GHz", yv, unit, state.kind.value]
                    )


def export_marker_csv(
    path: str | Path,
    session: Session,
    state: PlotState,
    marker_x: float | None = None,
    markers: list[PlotMarker] | None = None,
) -> None:
    pairs = _plot_networks(session, state)
    unit = plot_kind_unit(state.kind)
    traces = state.selected_traces()
    m0, n0 = traces[0]
    marker_list = markers
    if marker_list is None:
        if marker_x is None:
            return
        marker_list = [PlotMarker(marker_id=1, x=marker_x)]
    x_unit = "ns" if is_tdr_kind(state.kind) else "GHz"
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["marker", "filename", "trace", "domain", "x", "x_unit", "value", "unit", "plot_kind"]
        )
        for marker in marker_list:
            for lf, net in pairs:
                if is_tdr_kind(state.kind):
                    tdr = state.tdr_settings or TdrSettings()
                    trace = tdr_trace_label(net, m0, n0, state.domain)
                    z_ref = tdr.z_ref_ohms or default_tdr_z_ref_ohms(state.domain.value, trace)
                    value = value_at_x(
                        net,
                        m0,
                        n0,
                        marker.x,
                        state.kind,
                        state.unwrap_phase,
                        tdr_z_ref_ohms=z_ref,
                        tdr_window=tdr.window,
                        tdr_pad=tdr.pad,
                        tdr_sample_count=tdr.sample_count,
                        tdr_extrapolate_dc=tdr.extrapolate_dc,
                    )
                else:
                    trace = trace_label(net, m0, n0, state.domain)
                    value = value_at_frequency(
                        net, m0, n0, marker.x, state.kind, state.unwrap_phase
                    )
                writer.writerow(
                    [
                        marker.label,
                        lf.display_name,
                        trace,
                        state.domain.value,
                        marker.x,
                        x_unit,
                        value,
                        unit,
                        state.kind.value,
                    ]
                )


def prepare_export_network(
    loaded: LoadedFile,
    *,
    domain: ParamDomain,
    z0_ohms: float | None = None,
    keysight_reorder: bool | None = None,
) -> rf.Network:
    """Build a network for Touchstone export (optional MM conversion / Z0 renormalize)."""
    reorder = loaded.keysight_reorder if keysight_reorder is None else keysight_reorder
    if domain == ParamDomain.MIXED_MODE:
        if is_native_mixed_mode(loaded.network):
            net = loaded.network.copy()
            if reorder:
                from vectorsmith.mixed_mode import apply_keysight_reorder

                net = apply_keysight_reorder(net)
        else:
            net = convert_to_gmm(loaded.network, loaded.pairing, reorder)
    else:
        net = loaded.network.copy()
    if z0_ohms is not None:
        net = net.copy()
        net.renormalize(z0_ohms)
    return net


def touchstone_extension(nports: int) -> str:
    return f".s{nports}p"


def export_touchstone(
    path: str | Path,
    loaded: LoadedFile,
    *,
    domain: ParamDomain,
    z0_ohms: float | None = None,
    keysight_reorder: bool | None = None,
) -> Path:
    """Write a converted/renormalized Touchstone file and return the written path."""
    net = prepare_export_network(
        loaded,
        domain=domain,
        z0_ohms=z0_ohms,
        keysight_reorder=keysight_reorder,
    )
    out = Path(path)
    if out.suffix.lower() not in {".s1p", ".s2p", ".s3p", ".s4p", ".s5p", ".s6p", ".s7p", ".s8p", ".snp"}:
        out = out.with_suffix(touchstone_extension(net.nports))
    # Mixed-mode GMM networks often have unequal port Z0 (e.g. 100 Ω DD / 25 Ω CC).
    # Write Z0 comments so skrf can emit the file without forcing a single r_ref.
    unequal_z0 = bool(np.any(net.z0 != net.z0.flat[0]))
    net.write_touchstone(filename=str(out), form="ri", write_z0=unequal_z0)
    return out
