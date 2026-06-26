"""Load Touchstone files into scikit-rf Network objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import skrf as rf


@dataclass(frozen=True)
class LoadResult:
    path: Path
    network: rf.Network
    display_name: str


def load_touchstone(path: str | Path) -> LoadResult:
    """Load a Touchstone file; raises on parse failure."""
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(p)
    network = rf.Network(str(p))
    return LoadResult(path=p, network=network, display_name=p.name)


def is_touchstone_path(path: str | Path) -> bool:
    p = Path(path)
    if not p.is_file():
        return False
    suffix = p.suffix.lower()
    if suffix == ".snp":
        return True
    if len(suffix) == 4 and suffix[1] == "s" and suffix[2].isdigit() and suffix[3] == "p":
        return True
    return False
