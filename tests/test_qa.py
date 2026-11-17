import numpy as np
import skrf as rf

from vectorsmith.qa import analyze_network, check_causality, check_passivity, check_reciprocity


def _thru_network() -> rf.Network:
    f = np.linspace(1e9, 5e9, 51)
    s = np.zeros((len(f), 2, 2), dtype=complex)
    s[:, 0, 1] = 1.0
    s[:, 1, 0] = 1.0
    return rf.Network(frequency=rf.Frequency.from_f(f, unit="Hz"), s=s, z0=50.0)


def _nonreciprocal_network() -> rf.Network:
    net = _thru_network()
    net.s[:, 0, 1] = 0.9
    net.s[:, 1, 0] = 0.2
    return net


def test_thru_is_passive_and_reciprocal():
    net = _thru_network()
    assert check_passivity(net).passed
    assert check_reciprocity(net).passed


def test_nonreciprocal_fails_reciprocity():
    net = _nonreciprocal_network()
    result = check_reciprocity(net, tol=1e-3)
    assert not result.passed
    assert result.metric > 0.5


def test_analyze_network_report():
    report = analyze_network(_thru_network(), filename="thru.s2p", domain="single_ended")
    assert report.filename == "thru.s2p"
    assert len(report.checks) == 3
    assert {c.name for c in report.checks} == {"Passivity", "Reciprocity", "Causality"}


def test_causality_returns_metric():
    result = check_causality(_thru_network())
    assert result.name == "Causality"
    assert 0.0 <= result.metric <= 1.0
