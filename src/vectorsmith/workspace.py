"""Workspace serialization for VectorSmith sessions."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vectorsmith.loader import load_touchstone
from vectorsmith.mixed_mode import ParamDomain
from vectorsmith.plots import GraphSettings, TdrSettings
from vectorsmith.session import LoadedFile, PortPairingConfig, Session

WORKSPACE_VERSION = 1


def graph_settings_to_dict(settings: GraphSettings) -> dict[str, float | None]:
    return asdict(settings)


def graph_settings_from_dict(data: dict[str, Any] | None) -> GraphSettings:
    data = data or {}
    return GraphSettings(
        x_min_ghz=data.get("x_min_ghz"),
        x_max_ghz=data.get("x_max_ghz"),
        mag_y_min_db=data.get("mag_y_min_db"),
        mag_y_max_db=data.get("mag_y_max_db"),
    )


def tdr_settings_to_dict(settings: TdrSettings) -> dict[str, Any]:
    return asdict(settings)


def tdr_settings_from_dict(data: dict[str, Any] | None) -> TdrSettings:
    data = data or {}
    return TdrSettings(
        z_ref_ohms=data.get("z_ref_ohms"),
        window=data.get("window", "hamming"),
        pad=int(data.get("pad", 0)),
        sample_count=data.get("sample_count"),
        extrapolate_dc=bool(data.get("extrapolate_dc", True)),
        time_min_ns=data.get("time_min_ns"),
        time_max_ns=data.get("time_max_ns"),
        velocity_factor=float(data.get("velocity_factor", 0.66)),
        show_distance=bool(data.get("show_distance", False)),
    )


def session_to_dict(
    session: Session,
    *,
    graph_settings: GraphSettings,
    tdr_settings: TdrSettings,
    toolbar: dict,
    dark_theme: bool,
) -> dict[str, Any]:
    return {
        "version": WORKSPACE_VERSION,
        "dark_theme": dark_theme,
        "marker_enabled": session.marker_enabled,
        "marker_freq_ghz": session.marker_freq_ghz,
        "graph_settings": graph_settings_to_dict(graph_settings),
        "tdr_settings": tdr_settings_to_dict(tdr_settings),
        "toolbar": toolbar,
        "files": [
            {
                "path": str(lf.path),
                "visible": lf.visible,
                "color": lf.color,
                "domain": lf.domain.value if lf.domain else None,
                "pairing": {
                    "num_diff_ports": lf.pairing.num_diff_ports,
                    "renumber_map": lf.pairing.renumber_map,
                },
                "keysight_reorder": lf.keysight_reorder,
            }
            for lf in session.files
        ],
    }


def save_workspace(path: str | Path, data: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_workspace(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def session_from_workspace(data: dict[str, Any]) -> tuple[Session, list[tuple[Path, str]]]:
    session = Session()
    errors: list[tuple[Path, str]] = []
    for item in data.get("files", []):
        path = Path(item.get("path", ""))
        try:
            result = load_touchstone(path)
        except Exception as exc:  # noqa: BLE001
            errors.append((path, str(exc)))
            continue
        domain_value = item.get("domain")
        domain = None
        if domain_value:
            try:
                domain = ParamDomain(domain_value)
            except ValueError:
                domain = None
        pairing_data = item.get("pairing", {})
        lf = LoadedFile(
            path=result.path,
            network=result.network,
            display_name=result.display_name,
            visible=bool(item.get("visible", True)),
            color=item.get("color"),
            domain=domain,
            pairing=PortPairingConfig(
                num_diff_ports=int(pairing_data.get("num_diff_ports", 0)),
                renumber_map=list(pairing_data.get("renumber_map", [])),
            ),
            keysight_reorder=bool(item.get("keysight_reorder", False)),
        )
        session.files.append(lf)
    session.marker_enabled = bool(data.get("marker_enabled", False))
    session.marker_freq_ghz = data.get("marker_freq_ghz")
    return session, errors
