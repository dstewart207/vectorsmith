from pathlib import Path

import numpy as np
import skrf as rf

from vectorsmith.exports import export_touchstone, prepare_export_network, touchstone_extension
from vectorsmith.loader import load_touchstone
from vectorsmith.mixed_mode import ParamDomain
from vectorsmith.session import LoadedFile, PortPairingConfig

FIXTURES = Path(__file__).parent / "fixtures"


def _four_port() -> rf.Network:
    f = np.linspace(1e9, 3e9, 11)
    s = np.zeros((len(f), 4, 4), dtype=complex)
    for i in range(4):
        s[:, i, i] = 0.1
    s[:, 0, 1] = s[:, 1, 0] = 0.5
    s[:, 2, 3] = s[:, 3, 2] = 0.5
    return rf.Network(frequency=rf.Frequency.from_f(f, unit="Hz"), s=s, z0=50.0)


def test_touchstone_extension():
    assert touchstone_extension(2) == ".s2p"
    assert touchstone_extension(4) == ".s4p"


def test_export_renormalized_two_port(tmp_path):
    result = load_touchstone(FIXTURES / "twoport.s2p")
    lf = LoadedFile(
        path=result.path,
        network=result.network,
        display_name=result.display_name,
        pairing=PortPairingConfig(num_diff_ports=1, renumber_map=[0, 1]),
    )
    out = tmp_path / "renorm.s2p"
    written = export_touchstone(out, lf, domain=ParamDomain.SINGLE_ENDED, z0_ohms=75.0)
    assert written.exists()
    loaded = rf.Network(str(written))
    assert loaded.nports == 2
    assert np.allclose(loaded.z0.real, 75.0)


def test_export_mixed_mode_four_port(tmp_path):
    net = _four_port()
    path = tmp_path / "se.s4p"
    net.write_touchstone(filename=str(path), form="ri")
    result = load_touchstone(path)
    lf = LoadedFile(
        path=result.path,
        network=result.network,
        display_name=result.display_name,
        pairing=PortPairingConfig(num_diff_ports=2, renumber_map=[0, 2, 1, 3]),
    )
    mm = prepare_export_network(lf, domain=ParamDomain.MIXED_MODE)
    assert mm.nports == 4
    out = tmp_path / "mm_export"
    written = export_touchstone(out, lf, domain=ParamDomain.MIXED_MODE)
    assert written.suffix.lower() == ".s4p"
    assert written.exists()
