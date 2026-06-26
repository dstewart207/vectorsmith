from pathlib import Path

import numpy as np

from vectorsmith.loader import load_touchstone
from vectorsmith.marker import (
    describe_frequency_step,
    value_at_frequency,
)
from vectorsmith.plot_kinds import PlotKind

FIXTURES = Path(__file__).parent / "fixtures"


def test_frequency_step_uniform_fixture():
    net = load_touchstone(FIXTURES / "twoport.s2p").network
    desc = describe_frequency_step(net.frequency.f)
    assert "uniform" in desc
    assert "GHz" in desc


def test_value_at_frequency_matches_s_param():
    net = load_touchstone(FIXTURES / "twoport.s2p").network
    f_ghz = float(net.frequency.f[0] / 1e9)
    expected = 20 * np.log10(np.abs(net.s[0, 0, 0]) + 1e-30)
    got = value_at_frequency(net, 0, 0, f_ghz, PlotKind.MAG_DB)
    assert abs(got - expected) < 1e-6


def test_variable_step_detection():
    f_hz = np.array([1e9, 2.5e9, 6e9])
    desc = describe_frequency_step(f_hz)
    assert "variable" in desc
    assert "median" in desc
