"""Network quality checks: passivity, reciprocity, and causality."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import skrf as rf


@dataclass(frozen=True)
class QaCheckResult:
    name: str
    passed: bool
    metric: float
    detail: str
    frequency_hz: float | None = None


@dataclass(frozen=True)
class QaReport:
    filename: str
    domain: str
    checks: list[QaCheckResult]

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)


def check_passivity(network: rf.Network, tol: float = 1e-3) -> QaCheckResult:
    """Passivity: singular values of S should be <= 1 (+tol)."""
    singular_max = 0.0
    worst_freq: float | None = None
    for i in range(network.frequency.npoints):
        s_block = network.s[i, :, :]
        singular_values = np.linalg.svd(s_block, compute_uv=False)
        peak = float(np.max(np.abs(singular_values)))
        if peak > singular_max:
            singular_max = peak
            worst_freq = float(network.frequency.f[i])
    passed = singular_max <= 1.0 + tol
    skrf_passive = bool(network.is_passive(tol=tol))
    passed = passed and skrf_passive
    return QaCheckResult(
        name="Passivity",
        passed=passed,
        metric=singular_max,
        detail=(
            f"max |σ(S)| = {singular_max:.6g} "
            f"(limit 1+{tol:g}; skrf.is_passive={skrf_passive})"
        ),
        frequency_hz=worst_freq,
    )


def check_reciprocity(network: rf.Network, tol: float = 1e-3) -> QaCheckResult:
    """Reciprocity: S should equal S transpose within tolerance."""
    residual = network.s - np.transpose(network.s, axes=(0, 2, 1))
    abs_res = np.abs(residual)
    metric = float(np.max(abs_res)) if abs_res.size else 0.0
    worst_idx = int(np.argmax(abs_res)) if abs_res.size else 0
    worst_freq = None
    if abs_res.size:
        f_idx = np.unravel_index(worst_idx, abs_res.shape)[0]
        worst_freq = float(network.frequency.f[f_idx])
    passed = bool(network.is_reciprocal(tol=tol))
    return QaCheckResult(
        name="Reciprocity",
        passed=passed,
        metric=metric,
        detail=f"max |S - Sᵀ| = {metric:.6g} (tol={tol:g})",
        frequency_hz=worst_freq,
    )


def check_causality(network: rf.Network, energy_tol: float = 1e-2) -> QaCheckResult:
    """
    Causality heuristic from S11 impulse response.

    Band-limited S-parameters are never perfectly causal; report the fraction of
    impulse energy that lands at t < 0 and flag when it exceeds energy_tol.
    """
    port = min(network.nports - 1, 0)
    one_port = network.copy()
    one_port.s = network.s[:, port : port + 1, port : port + 1]
    one_port.z0 = (
        network.z0[:, port : port + 1]
        if getattr(network.z0, "ndim", 1) > 1
        else network.z0
    )
    t, y = one_port.s11.impulse_response(pad=0, window="hamming")
    energy = np.abs(y) ** 2
    total = float(np.sum(energy))
    if total <= 0.0:
        return QaCheckResult(
            name="Causality",
            passed=True,
            metric=0.0,
            detail="No impulse energy (empty response)",
        )
    neg = float(np.sum(energy[t < 0.0]))
    fraction = neg / total
    passed = fraction <= energy_tol
    return QaCheckResult(
        name="Causality",
        passed=passed,
        metric=fraction,
        detail=(
            f"S{port + 1}{port + 1} impulse energy at t<0 = {fraction:.4%} "
            f"(limit {energy_tol:.2%}; band-limited metric)"
        ),
    )


def analyze_network(
    network: rf.Network,
    *,
    filename: str = "",
    domain: str = "single_ended",
    passivity_tol: float = 1e-3,
    reciprocity_tol: float = 1e-3,
    causality_tol: float = 1e-2,
) -> QaReport:
    checks = [
        check_passivity(network, tol=passivity_tol),
        check_reciprocity(network, tol=reciprocity_tol),
        check_causality(network, energy_tol=causality_tol),
    ]
    return QaReport(filename=filename, domain=domain, checks=checks)
