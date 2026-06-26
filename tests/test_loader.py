from pathlib import Path

import pytest

from vectorsmith.loader import load_touchstone
from vectorsmith.mixed_mode import (
    ParamDomain,
    convert_to_gmm,
    is_native_mixed_mode,
    list_mixed_mode_traces,
)
from vectorsmith.session import PortPairingConfig

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_s1p():
    r = load_touchstone(FIXTURES / "oneport.s1p")
    assert r.network.nports == 1
    assert len(r.network.frequency) == 2


def test_load_s2p():
    r = load_touchstone(FIXTURES / "twoport.s2p")
    assert r.network.nports == 2
    assert len(r.network.frequency) == 2


def test_se2gmm_four_port_synthetic():
    skrf = pytest.importorskip("skrf")
    import numpy as np

    f = skrf.Frequency(1e9, 2e9, 2, unit="Hz")
    s = np.full((2, 4, 4), 0.01 * (1 + 1j), dtype=complex)
    n = skrf.Network(frequency=f, s=s)
    pairing = PortPairingConfig(num_diff_ports=2, renumber_map=[0, 2, 1, 3])
    gmm = convert_to_gmm(n, pairing)
    traces = list_mixed_mode_traces(gmm)
    assert [t.label for t in traces] == [
        "SDD11",
        "SDD12",
        "SDD21",
        "SDD22",
        "SCD11",
        "SCD12",
        "SCD21",
        "SCD22",
        "SDC11",
        "SDC12",
        "SDC21",
        "SDC22",
        "SCC11",
        "SCC12",
        "SCC21",
        "SCC22",
    ]


def test_native_mm_detection_false_on_se():
    r = load_touchstone(FIXTURES / "twoport.s2p")
    assert not is_native_mixed_mode(r.network)
