import numpy as np

from vectorsmith.marker import (
    bandwidth_at_level,
    find_extrema,
    find_tdr_features,
    format_marker_delta,
    marker_delta,
)


def test_find_extrema():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    y = np.array([0.0, -5.0, 2.0, 1.0])
    mn, mx = find_extrema(x, y)
    assert mn.x == 2.0 and mn.y == -5.0
    assert mx.x == 3.0 and mx.y == 2.0


def test_bandwidth_at_level_peak():
    x = np.linspace(1.0, 5.0, 401)
    y = -((x - 3.0) ** 2)  # peak 0 dB at 3 GHz
    bw = bandwidth_at_level(x, y, -1.0, relative_to="max")
    assert bw is not None
    assert abs(bw.peak_x - 3.0) < 1e-6
    assert bw.low_x < 3.0 < bw.high_x
    assert abs(bw.bandwidth - 2.0) < 0.05


def test_bandwidth_at_level_notch():
    x = np.linspace(1.0, 5.0, 401)
    y = (x - 3.0) ** 2 - 10.0  # min -10 at 3 GHz
    bw = bandwidth_at_level(x, y, -3.0, relative_to="min")
    assert bw is not None
    assert abs(bw.peak_x - 3.0) < 1e-6
    assert bw.bandwidth > 0


def test_marker_delta_format():
    delta = marker_delta(1.0, -10.0, 2.5, -13.0, x_unit="GHz", y_unit="dB")
    text = format_marker_delta(delta)
    assert "Δx=1.5 GHz" in text
    assert "Δy=-3 dB" in text


def test_find_tdr_features_detects_peak_and_step():
    t = np.linspace(0.0, 10.0, 201)
    z = np.full_like(t, 50.0)
    z[(t > 2.0) & (t < 3.0)] = 80.0  # peak
    z[t >= 6.0] = 65.0  # step
    features = find_tdr_features(t, z, z_ref_ohms=50.0, min_step_ohm=2.0)
    kinds = {f.kind for f in features}
    assert "peak" in kinds or "valley" in kinds
    assert any(abs(f.time_ns - 2.5) < 0.3 for f in features if f.kind in {"peak", "valley"})
    assert any(f.kind == "step" and 5.5 <= f.time_ns <= 7.0 for f in features)
