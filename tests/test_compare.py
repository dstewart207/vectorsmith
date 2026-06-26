from pathlib import Path

from vectorsmith.compare import align_networks
from vectorsmith.loader import load_touchstone

FIXTURES = Path(__file__).parent / "fixtures"


def test_align_two_files():
    a = load_touchstone(FIXTURES / "oneport.s1p").network
    b = load_touchstone(FIXTURES / "oneport.s1p").network
    result = align_networks([a, b])
    assert result.npoints == 2
    assert len(result.networks) == 2
