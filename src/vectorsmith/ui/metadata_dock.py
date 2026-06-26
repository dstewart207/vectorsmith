"""Metadata panel for the selected Touchstone file."""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import QDockWidget, QLabel, QTextEdit, QVBoxLayout, QWidget

from vectorsmith.compare import format_freq_span
from vectorsmith.marker import describe_frequency_step
from vectorsmith.mixed_mode import is_native_mixed_mode
from vectorsmith.session import LoadedFile


class MetadataDock(QDockWidget):
    def __init__(self, parent=None) -> None:
        super().__init__("Metadata", parent)
        self.setObjectName("MetadataDock")
        container = QWidget()
        layout = QVBoxLayout(container)
        self._title = QLabel("No file selected")
        self._title.setWordWrap(True)
        self._body = QTextEdit()
        self._body.setReadOnly(True)
        layout.addWidget(self._title)
        layout.addWidget(self._body)
        self.setWidget(container)

    def show_file(self, lf: LoadedFile | None) -> None:
        if lf is None:
            self._title.setText("No file selected")
            self._body.clear()
            return

        n = lf.network
        f_hz = n.frequency.f
        span = format_freq_span(float(f_hz.min()), float(f_hz.max())) if len(f_hz) else "-"
        z0 = n.z0
        z0_real = np.real(z0)
        if hasattr(z0_real, "shape") and z0_real.size > 1:
            z0_str = f"{float(np.mean(z0_real)):.4g} ohm (mean)"
        else:
            z0_str = f"{float(np.atleast_1d(z0_real).flat[0]):.4g} ohm"

        modes = getattr(n, "port_modes", None)
        mode_str = ", ".join(str(m) for m in modes) if modes is not None else "S (single-ended)"
        mm_native = is_native_mixed_mode(n)

        lines = [
            f"Ports: {n.nports}",
            f"Frequency: {span} ({len(f_hz)} points)",
            f"Frequency step: {describe_frequency_step(f_hz)}",
            f"Z0: {z0_str}",
            f"Port modes: {mode_str}",
            f"Native mixed-mode file: {'yes' if mm_native else 'no'}",
            f"Plot domain: {lf.domain.value if lf.domain else '-'}",
            f"Diff port groups (p): {lf.pairing.num_diff_ports}",
            f"Renumber: {lf.pairing.renumber_map}",
        ]
        comments = getattr(n, "comments", None) or ""
        if comments:
            lines.append("\n--- Comments ---\n" + str(comments).strip())

        self._title.setText(lf.display_name)
        self._body.setPlainText("\n".join(lines))
