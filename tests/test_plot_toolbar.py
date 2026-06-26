from PyQt6.QtWidgets import QApplication

from vectorsmith.plot_kinds import PlotKind
from vectorsmith.ui.plot_toolbar import PlotToolbar


def test_plot_dropdown_omits_redundant_loss_aliases():
    app = QApplication.instance() or QApplication([])
    toolbar = PlotToolbar()

    visible = {
        toolbar._plot_kind.itemData(i)  # noqa: SLF001
        for i in range(toolbar._plot_kind.count())  # noqa: SLF001
    }

    assert PlotKind.INSERTION_LOSS_DB not in visible
    assert PlotKind.RETURN_LOSS_DB not in visible
    assert PlotKind.MAG_DB in visible
    assert PlotKind.TDR_IMPEDANCE in visible
    app.processEvents()
