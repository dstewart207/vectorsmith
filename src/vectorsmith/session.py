"""Session state for loaded Touchstone files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt
import skrf as rf

from vectorsmith.loader import LoadResult, load_touchstone
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
        self.marker_enabled: bool = False
        self.marker_freq_ghz: float | None = None
        self._color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        self._color_index = 0

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

    def subscribe(self, callback: Callable[[], None]) -> None:
        self._notify = callback

    def notify(self) -> None:
        if hasattr(self, "_notify"):
            self._notify()
