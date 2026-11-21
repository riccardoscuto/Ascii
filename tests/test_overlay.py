import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from gcf.gui.overlay import CropOverlay


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _mouse(self, overlay, etype, pos, button=Qt.LeftButton, buttons=Qt.NoButton):
        ev = QMouseEvent(etype, QPointF(pos), button, buttons, Qt.NoModifier)
        if etype == QEvent.MouseButtonPress:
            overlay.mousePressEvent(ev)
        elif etype == QEvent.MouseMove:
            overlay.mouseMoveEvent(ev)
        elif etype == QEvent.MouseButtonRelease:
            overlay.mouseReleaseEvent(ev)

    def test_drag_and_resize_keep_ratio(self):
        overlay = CropOverlay()
        overlay.show_for(QRect(0, 0, 1920, 1080))
        overlay.set_frame(QRect(500, 0, 608, 1080))
        start = QRect(overlay.frame)
        center = start.center()
        self._mouse(overlay, QEvent.MouseButtonPress, center)
        self._mouse(overlay, QEvent.MouseMove, center + QPoint(100, 40), buttons=Qt.LeftButton)
        self._mouse(overlay, QEvent.MouseButtonRelease, center + QPoint(100, 40), buttons=Qt.LeftButton)
        moved = QRect(overlay.frame)
        self.assertNotEqual(start.topLeft(), moved.topLeft())
        self.assertAlmostEqual(moved.width() / moved.height(), 9 / 16, places=2)

        br = moved.bottomRight()
        self._mouse(overlay, QEvent.MouseButtonPress, br)
        self._mouse(overlay, QEvent.MouseMove, br + QPoint(-100, -50), buttons=Qt.LeftButton)
        self._mouse(overlay, QEvent.MouseButtonRelease, br + QPoint(-100, -50), buttons=Qt.LeftButton)
        resized = QRect(overlay.frame)
        self.assertLess(resized.width(), moved.width())
        self.assertAlmostEqual(resized.width() / resized.height(), 9 / 16, places=2)
        self.assertTrue(overlay.bounds.contains(resized))
        overlay.close()


if __name__ == "__main__":
    unittest.main()
