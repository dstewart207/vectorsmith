from pathlib import Path

import numpy as np
import pytest
import skrf as rf

from vectorsmith.loader import load_touchstone
from vectorsmith.plot_kinds import PlotKind
from vectorsmith.rf_trace import (
    default_tdr_z_ref_ohms,
    gamma_to_impedance,
    tdr_impedance_response,
    trace_y_values,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_new_frequency_plot_kinds():
    net = load_touchstone(FIXTURES / "twoport.s2p").network
    s11 = net.s[:, 0, 0]

    np.testing.assert_allclose(
        trace_y_values(net, 0, 0, PlotKind.RETURN_LOSS_DB, False),
        -20 * np.log10(np.abs(s11) + 1e-30),
    )
    assert len(trace_y_values(net, 1, 0, PlotKind.GROUP_DELAY_NS, False)) == len(net.frequency)
    assert len(trace_y_values(net, 0, 0, PlotKind.REAL_Z, False)) == len(net.frequency)
    assert len(trace_y_values(net, 0, 0, PlotKind.IMAG_Z, False)) == len(net.frequency)


def test_tdr_defaults_and_impedance_conversion():
    gamma = np.array([0.0, 0.5, -0.5])
    np.testing.assert_allclose(gamma_to_impedance(gamma, 50.0), [50.0, 150.0, 50.0 / 3.0])
    assert default_tdr_z_ref_ohms("single_ended", "S11") == 50.0
    assert default_tdr_z_ref_ohms("mixed_mode", "SDD11") == 100.0


def test_tdr_response_requires_reflection_trace():
    net = load_touchstone(FIXTURES / "twoport.s2p").network
    with pytest.raises(ValueError):
        tdr_impedance_response(net, 1, 0, z_ref_ohms=50.0)


def test_tdr_response_returns_time_and_impedance():
    net = load_touchstone(FIXTURES / "oneport.s1p").network
    t, z = tdr_impedance_response(net, 0, 0, z_ref_ohms=50.0)
    assert len(t) == len(z)
    assert t[0] == pytest.approx(0.0)
    assert t.min() == pytest.approx(0.0)
    assert np.isfinite(z).all()


def test_tdr_response_places_reflection_at_causal_time():
    """Regression: skrf step_response is fftshifted; TDR must start at t=0."""
    one_way_delay_s = 5e-9
    expected_peak_s = 2.0 * one_way_delay_s
    f = np.linspace(0.0, 10e9, 401)
    s11 = 0.2 * np.exp(-1j * 2 * np.pi * f * expected_peak_s)
    net = rf.Network(
        frequency=rf.Frequency.from_f(f, unit="Hz"),
        s=s11.reshape(-1, 1, 1),
        z0=50.0,
    )

    t, z = tdr_impedance_response(net, 0, 0, z_ref_ohms=50.0, window="hamming")
    peak_s = float(t[np.argmax(np.abs(z - 50.0))])

    assert t[0] == pytest.approx(0.0)
    assert peak_s == pytest.approx(expected_peak_s, abs=0.5e-9)
    # Guard against the old mid-window offset (~T/2 ≈ 20 ns here).
    assert peak_s < 15e-9
