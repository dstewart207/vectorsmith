import numpy as np
import skrf

from vectorsmith.mixed_mode import (
    ParamDomain,
    apply_keysight_reorder,
    convert_to_gmm,
    is_native_mixed_mode,
    list_mixed_mode_traces,
    list_mixed_mode_tdr_traces,
    list_single_ended_tdr_traces,
    network_for_plot,
    tdr_trace_label,
)
from vectorsmith.session import PortPairingConfig


def _four_port():
    f = skrf.Frequency(1e9, 2e9, 2, unit="Hz")
    s = np.arange(32, dtype=float).reshape(2, 4, 4) / 100.0
    return skrf.Network(frequency=f, s=s)


def test_keysight_reorder_changes_four_port_matrix():
    net = _four_port()
    reordered = apply_keysight_reorder(net)
    assert reordered.s.shape == net.s.shape
    assert not np.allclose(reordered.s, net.s)


def test_native_mixed_mode_detection_true():
    net = _four_port()
    net.port_modes = np.array(["D", "D", "C", "C"])
    assert is_native_mixed_mode(net)
    labels = [t.label for t in list_mixed_mode_traces(net)]
    assert "SDD11" in labels
    assert "SCC22" in labels


def test_network_for_plot_caches_gmm_conversion():
    net = _four_port()
    cache = {}
    pairing = PortPairingConfig(num_diff_ports=2, renumber_map=[0, 2, 1, 3])
    first = network_for_plot(net, ParamDomain.MIXED_MODE, pairing, False, cache, "key")
    second = network_for_plot(net, ParamDomain.MIXED_MODE, pairing, False, cache, "key")
    assert first is second
    assert first.nports == convert_to_gmm(net, pairing).nports


def test_single_ended_tdr_traces_are_reflection_only():
    assert list_single_ended_tdr_traces(4) == [
        (0, 0, "T11"),
        (1, 1, "T22"),
        (2, 2, "T33"),
        (3, 3, "T44"),
    ]


def test_mixed_mode_tdr_traces_use_tdd_and_tcc_labels():
    net = _four_port()
    net.port_modes = np.array(["D", "D", "C", "C"])
    traces = list_mixed_mode_tdr_traces(net)
    labels = [label for _, _, label in traces]
    assert labels == ["TDD11", "TDD22", "TCC11", "TCC22"]
    assert tdr_trace_label(net, 0, 0, ParamDomain.MIXED_MODE) == "TDD11"
