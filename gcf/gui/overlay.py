from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WDA_EXCLUDEFROMCAPTURE = 0x00000011
user32 = ctypes.windll.user32
user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.SetWindowDisplayAffinity.restype = wintypes.BOOL


def exclude_from_capture(widget) -> bool:
    try:
        return bool(user32.SetWindowDisplayAffinity(int(widget.winId()), WDA_EXCLUDEFROMCAPTURE))
    except Exception:
        return False


ACCENT = "#00B7FF"
DARK = "#15171d"
PANEL = "#20232b"
MUTED = "#9aa3b2"


class CropOverlay(QWidget):
    frameChanged = Signal(QRect)

    def __init__(self):
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.bounds = QRect(0, 0, 1920, 1080)
        self.frame = QRect()
        self.dragging: str | None = None
        self.start_pos = QPoint()
        self.start_frame = QRect()
        self.locked = False
        self.handle = 18
        self.capture_excluded = False
        self._reset_frame()

    def show_for(self, bounds: QRect) -> None:
        self.setGeometry(bounds)
        self.bounds = QRect(0, 0, bounds.width(), bounds.height())
        if self.frame.isNull() or not self.bounds.contains(self.frame):
            self._reset_frame()
        self._clamp()
        self.show()
        self.raise_()
        self.capture_excluded = exclude_from_capture(self)
        self.update()

    def _reset_frame(self) -> None:
        h = int(self.bounds.height() * 0.78)
        w = int(h * 9 / 16)
        if w > self.bounds.width() * 0.86:
            w = int(self.bounds.width() * 0.86)
            h = int(w * 16 / 9)
        w = max(120, w)
        h = max(214, h)
        self.frame = QRect(
            (self.bounds.width() - w) // 2,
            (self.bounds.height() - h) // 2,
            w, h,
        )
        self._clamp()

    def _clamp(self) -> None:
        if self.bounds.isNull():
            return
        w = max(120, min(self.frame.width(), self.bounds.width()))
        h = int(round(w * 16 / 9))
        if h > self.bounds.height():
            h = self.bounds.height()
            w = int(round(h * 9 / 16))
        x = max(0, min(self.frame.x(), self.bounds.width() - w))
        y = max(0, min(self.frame.y(), self.bounds.height() - h))
        self.frame = QRect(x, y, w, h)

    def set_frame(self, rect: QRect) -> None:
        self.frame = QRect(rect)
        self._clamp()
        self.update()

    def frame_global(self) -> QRect:
        return QRect(self.geometry().topLeft() + self.frame.topLeft(), self.frame.size())

    def handle_at(self, pos: QPoint) -> str | None:
        f = self.frame
        if not f.adjusted(-self.handle, -self.handle, self.handle, self.handle).contains(pos):
            return None
        corners = {
            "tl": f.topLeft(),
            "tr": f.topRight(),
            "bl": f.bottomLeft(),
            "br": f.bottomRight(),
        }
        for name, p in corners.items():
            if abs(pos.x() - p.x()) <= self.handle and abs(pos.y() - p.y()) <= self.handle:
                return name
        if f.contains(pos):
            return "move"
        return None

    def mousePressEvent(self, event):
        if self.locked or event.button() != Qt.LeftButton:
            return
        handle = self.handle_at(event.position().toPoint())
        if not handle:
            return
        self.dragging = handle
        self.start_pos = event.position().toPoint()
        self.start_frame = QRect(self.frame)
        self._set_cursor(handle)
        event.accept()

    def mouseMoveEvent(self, event):
        if self.locked:
            return
        pos = event.position().toPoint()
        if not self.dragging:
            self._set_cursor(self.handle_at(pos))
            return
        dx = pos.x() - self.start_pos.x()
        dy = pos.y() - self.start_pos.y()
        if self.dragging == "move":
            self.frame = QRect(
                self.start_frame.x() + dx,
                self.start_frame.y() + dy,
                self.start_frame.width(),
                self.start_frame.height(),
            )
        else:
            right = self.dragging in ("tr", "br")
            bottom = self.dragging in ("bl", "br")
            if right:
                w = self.start_frame.width() + dx
            else:
                w = self.start_frame.width() - dx
            max_w = min(self.bounds.width(), int(self.bounds.height() * 9 / 16))
            w = max(120, min(w, max_w))
            h = int(round(w * 16 / 9))
            x = self.start_frame.x() if right else self.start_frame.right() - w + 1
            y = self.start_frame.y() if not bottom else self.start_frame.bottom() - h + 1
            self.frame = QRect(x, y, w, h)
        self._clamp()
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = None
            self.frameChanged.emit(self.frame_global())
            event.accept()

    def _set_cursor(self, handle: str | None):
        if handle == "move":
            self.setCursor(Qt.SizeAllCursor)
        elif handle in ("tl", "br"):
            self.setCursor(Qt.SizeFDiagCursor)
        elif handle in ("tr", "bl"):
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def set_locked(self, locked: bool) -> None:
        self.locked = locked
        hwnd = int(self.winId())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if locked:
            style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
        else:
            style &= ~WS_EX_TRANSPARENT
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, locked)
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = self.frame
        if not self.locked:
            mask = QColor(0, 0, 0, 150)
            p.fillRect(QRect(0, 0, self.width(), f.top()), mask)
            p.fillRect(QRect(0, f.bottom() + 1, self.width(), self.height() - f.bottom() - 1), mask)
            p.fillRect(QRect(0, f.top(), f.left(), f.height()), mask)
            p.fillRect(QRect(f.right() + 1, f.top(), self.width() - f.right() - 1, f.height()), mask)
            p.setPen(QPen(QColor(0, 0, 0), 7))
            p.drawRect(f)
            p.setPen(QPen(QColor(ACCENT), 3))
            p.drawRect(f)
            p.setBrush(QColor(ACCENT))
            p.setPen(QPen(QColor(0, 0, 0), 2))
            for pt in (f.topLeft(), f.topRight(), f.bottomLeft(), f.bottomRight()):
                p.drawRect(QRect(pt.x() - 6, pt.y() - 6, 12, 12))
            p.setBrush(Qt.NoBrush)
            label = f"9:16   {f.width()} x {f.height()}"
            p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
            metrics = p.fontMetrics()
            tw = metrics.horizontalAdvance(label) + 24
            lr = QRect(f.center().x() - tw // 2, f.top() + 10, tw, 28)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 190))
            p.drawRoundedRect(lr, 7, 7)
            p.setPen(QColor("white"))
            p.drawText(lr, Qt.AlignCenter, label)
            hint = "Trascina la cornice · angoli per ridimensionare"
            p.setFont(QFont("Segoe UI", 9))
            p.setPen(QColor("white"))
            p.drawText(QRect(f.left(), f.bottom() - 34, f.width(), 24), Qt.AlignCenter, hint)
        else:
            p.setPen(QPen(QColor(0, 0, 0), 5))
            p.drawRect(f)
            p.setPen(QPen(QColor(ACCENT), 2))
            p.drawRect(f)
        p.end()


class CaptureControlPanel(QWidget):
    record = Signal()
    stop_requested = Signal()
    retry_requested = Signal()
    next_game = Signal()
    previous_game = Signal()
    toggle_lock = Signal()
    close_requested = Signal()
    open_clip = Signal()

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.card = QFrame()
        self.card.setObjectName("card")
        self.card.setStyleSheet(
            f"#card {{ background: {DARK}; border: 1px solid #343948; border-radius: 14px; }}"
            "QLabel { color: #e8edf6; }"
            "QPushButton { background: #2a2e39; color: #e8edf6; border: 0; border-radius: 7px;"
            " padding: 7px 10px; font-weight: 600; }"
            "QPushButton:hover { background: #384052; }"
            "QPushButton:disabled { color: #5c6474; background: #232630; }"
            "QPushButton#rec { background: #1f9d55; color: white; }"
            "QPushButton#rec:hover { background: #27b865; }"
            "QPushButton#stop { background: #c0392b; color: white; }"
            "QPushButton#stop:hover { background: #e04b3a; }"
            "QPushButton#next { background: #006f9e; color: white; }"
            "QPushButton#next:hover { background: #008cc7; }"
        )
        outer.addWidget(self.card)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        self.title = QLabel("GCF Capture")
        self.title.setStyleSheet(f"color: {ACCENT}; font-size: 15px; font-weight: 800;")
        self.game = QLabel("Gioco 1 di 6")
        self.game.setStyleSheet("font-size: 13px; font-weight: 700;")
        self.status = QLabel("Posiziona la cornice")
        self.status.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        self.warning = QLabel("")
        self.warning.setStyleSheet("color: #ffb74d; font-size: 11px; font-weight: 700;")
        self.warning.setWordWrap(True)
        self.warning.hide()
        lay.addWidget(self.title)
        lay.addWidget(self.game)
        lay.addWidget(self.status)
        lay.addWidget(self.warning)

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        self.rec = QPushButton("REC")
        self.rec.setObjectName("rec")
        self.stop = QPushButton("Stop")
        self.stop.setObjectName("stop")
        self.lock = QPushButton("Blocca")
        row1.addWidget(self.rec)
        row1.addWidget(self.stop)
        row1.addWidget(self.lock)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self.retry = QPushButton("Riprova")
        self.clip = QPushButton("Apri clip")
        self.next = QPushButton("Clip successiva")
        self.next.setObjectName("next")
        row2.addWidget(self.retry)
        row2.addWidget(self.clip)
        row2.addWidget(self.next)
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(6)
        self.previous = QPushButton("Precedente")
        self.close_btn = QPushButton("Chiudi")
        row3.addWidget(self.previous)
        row3.addStretch(1)
        row3.addWidget(self.close_btn)
        lay.addLayout(row3)

        self.rec.clicked.connect(self.record)
        self.stop.clicked.connect(self.stop_requested)
        self.retry.clicked.connect(self.retry_requested)
        self.next.clicked.connect(self.next_game)
        self.previous.clicked.connect(self.previous_game)
        self.lock.clicked.connect(self.toggle_lock)
        self.close_btn.clicked.connect(self.close_requested)
        self.clip.clicked.connect(self.open_clip)

        self.set_recording(False)
        self.set_has_take(False)
        self.capture_excluded = False

    def set_game(self, text: str) -> None:
        self.game.setText(text)

    def set_status(self, text: str) -> None:
        self.status.setText(text)

    def set_next_label(self, text: str) -> None:
        self.next.setText(text)

    def set_warning(self, text: str) -> None:
        self.warning.setText(text)
        self.warning.setVisible(bool(text))
        self.adjustSize()

    def set_recording(self, recording: bool) -> None:
        self.rec.setEnabled(not recording)
        self.stop.setEnabled(recording)
        self.retry.setEnabled(not recording)
        self.next.setEnabled(not recording)

    def set_has_take(self, has_take: bool) -> None:
        self.clip.setEnabled(has_take)
        self.next.setEnabled(has_take)

    def set_locked(self, locked: bool) -> None:
        self.lock.setText("Sblocca" if locked else "Blocca")
        self.status.setText("Cornice bloccata · mouse nel gioco" if locked else "Posiziona la cornice")

    def show_for(self, bounds: QRect) -> None:
        self.adjustSize()
        x = bounds.right() - self.width() - 24
        y = bounds.bottom() - self.height() - 24
        self.move(max(bounds.left(), x), max(bounds.top(), y))
        self.show()
        self.raise_()
        self.capture_excluded = exclude_from_capture(self)

