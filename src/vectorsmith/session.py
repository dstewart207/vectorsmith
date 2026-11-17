"""Session state for loaded Touchstone files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt
import skrf as rf

from vectorsmith.loader import load_touchstone
from vectorsmith.mixed_mode import (
    ParamDomain,
    default_pairing_for_nports,
    is_native_mixed_mode,
)


@dataclass
class PortPairingConfig:
    num_diff_ports: int = 0
    renumber_map: list[int] = field(default_factory=list)

    def cache_key(self) -> str:
        raw = f"{self.num_diff_ports}:{','.join(map(str, self.renumber_map))}"
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:12]


@dataclass
class PlotMarker:
    """A vertical marker on frequency or TDR plots."""

    marker_id: int
    x: float
    enabled: bool = True

    @property
    def label(self) -> str:
        return f"M{self.marker_id}"


@dataclass
class LoadedFile:
    path: Path
    network: rf.Network
    display_name: str
    visible: bool = True
    color: str | None = None
    domain: ParamDomain | None = None
    pairing: PortPairingConfig = field(default_factory=PortPairingConfig)
    keysight_reorder: bool = False
    gmm_cache: dict[str, rf.Network] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.domain is None:
            self.domain = (
                ParamDomain.MIXED_MODE
                if is_native_mixed_mode(self.network)
                else ParamDomain.SINGLE_ENDED
            )
        if not self.pairing.renumber_map:
            self.pairing = default_pairing_for_nports(self.network.nports)

    @property
    def gmm_cache_key(self) -> str:
        return f"{self.path}:{self.pairing.cache_key()}:ks={self.keysight_reorder}"


class Session:
    def __init__(self) -> None:
        self.files: list[LoadedFile] = []
        self.markers_enabled: bool = False
        self.markers: list[PlotMarker] = []
        self.active_marker_id: int | None = None
        self._next_marker_id = 1
        self._color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        self._color_index = 0

    # --- Backward-compatible single-marker accessors ---
    @property
    def marker_enabled(self) -> bool:
        return self.markers_enabled

    @marker_enabled.setter
    def marker_enabled(self, value: bool) -> None:
        self.markers_enabled = bool(value)
        if self.markers_enabled and not self.markers:
            self.add_marker(0.0)
        if self.markers_enabled and self.active_marker_id is None and self.markers:
            self.active_marker_id = self.markers[0].marker_id

    @property
    def marker_freq_ghz(self) -> float | None:
        active = self.active_marker()
        return None if active is None else active.x

    @marker_freq_ghz.setter
    def marker_freq_ghz(self, value: float | None) -> None:
        if value is None:
            return
        active = self.active_marker()
        if active is None:
            self.add_marker(float(value))
        else:
            active.x = float(value)

    def _next_color(self) -> str:
        c = self._color_cycle[self._color_index % len(self._color_cycle)]
        self._color_index += 1
        return c

    def add_paths(self, paths: list[str | Path]) -> list[tuple[Path, str]]:
        errors: list[tuple[Path, str]] = []
        for raw in paths:
            p = Path(raw)
            try:
                result = load_touchstone(p)
            except Exception as exc:  # noqa: BLE001
                errors.append((p, str(exc)))
                continue
            if any(f.path == result.path for f in self.files):
                continue
            lf = LoadedFile(
                path=result.path,
                network=result.network,
                display_name=result.display_name,
                color=self._next_color(),
            )
            self.files.append(lf)
        return errors

    def remove_selected(self, indices: list[int]) -> None:
        for i in sorted(indices, reverse=True):
            if 0 <= i < len(self.files):
                del self.files[i]

    def visible_files(self) -> list[LoadedFile]:
        return [f for f in self.files if f.visible]

    def active_marker(self) -> PlotMarker | None:
        if self.active_marker_id is None:
            return self.markers[0] if self.markers else None
        for marker in self.markers:
            if marker.marker_id == self.active_marker_id:
                return marker
        return self.markers[0] if self.markers else None

    def enabled_markers(self) -> list[PlotMarker]:
        if not self.markers_enabled:
            return []
        return [m for m in self.markers if m.enabled]

    def add_marker(self, x: float, *, make_active: bool = True) -> PlotMarker:
        marker = PlotMarker(marker_id=self._next_marker_id, x=float(x), enabled=True)
        self._next_marker_id += 1
        self.markers.append(marker)
        if make_active:
            self.active_marker_id = marker.marker_id
        return marker

    def remove_marker(self, marker_id: int) -> None:
        self.markers = [m for m in self.markers if m.marker_id != marker_id]
        if self.active_marker_id == marker_id:
            self.active_marker_id = self.markers[0].marker_id if self.markers else None

    def clear_markers(self) -> None:
        self.markers.clear()
        self.active_marker_id = None
        self._next_marker_id = 1

    def set_markers_from_workspace(
        self,
        *,
        markers_enabled: bool,
        markers: list[dict] | None,
        legacy_x: float | None = None,
    ) -> None:
        self.clear_markers()
        self.markers_enabled = bool(markers_enabled)
        if markers:
            max_id = 0
            for item in markers:
                marker_id = int(item.get("marker_id", item.get("id", max_id + 1)))
                max_id = max(max_id, marker_id)
                self.markers.append(
                    PlotMarker(
                        marker_id=marker_id,
                        x=float(item.get("x", 0.0)),
                        enabled=bool(item.get("enabled", True)),
                    )
                )
            self._next_marker_id = max_id + 1
            active = markers[0].get("marker_id", markers[0].get("id"))
            self.active_marker_id = int(active) if active is not None else (
                self.markers[0].marker_id if self.markers else None
            )
        elif legacy_x is not None and self.markers_enabled:
            self.add_marker(float(legacy_x))
        elif self.markers_enabled and not self.markers:
            self.add_marker(0.0)

    def subscribe(self, callback: Callable[[], None]) -> None:
        self._notify = callback

    def notify(self) -> None:
        if hasattr(self, "_notify"):
            self._notify()
