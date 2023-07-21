import pytest
from silx.gui import qt
from silx.gui.widgets.WaiterOverlay import WaiterOverlay
from silx.gui.plot import Plot2D
from silx.gui.plot.PlotWidget import PlotWidget


@pytest.mark.parametrize("widget_parent", (Plot2D, qt.QFrame))
def test_show(qapp, qapp_utils, widget_parent):
    """Simple test of the WaiterOverlay component"""
    widget = widget_parent()
    widget.setAttribute(qt.Qt.WA_DeleteOnClose)

    waitingOverlay = WaiterOverlay(widget)
    waitingOverlay.setAttribute(qt.Qt.WA_DeleteOnClose)

    widget.show()
    qapp_utils.qWaitForWindowExposed(widget)
    assert waitingOverlay._waitingButton.isWaiting()

    waitingOverlay.hide()
    qapp.processEvents()
    assert not waitingOverlay._waitingButton.isWaiting()

    widget.close()
    waitingOverlay.close()
    qapp.processEvents()
