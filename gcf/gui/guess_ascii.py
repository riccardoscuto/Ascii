from __future__ import annotations

import os
import threading
from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
)

from gcf.ascii import media
from gcf.ascii.render import AsciiCanceled
from gcf.guess import ascii_clip


class _ClueWorker(QThread):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int, str)

    def __init__(self, project, game, slot: int, settings: dict, kind: str):
        super().__init__()
        self.project = project
        self.game = game
        self.slot = slot
        self.settings = settings
        self.kind = kind
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def _progress(self, done, total, elapsed, eta, stage):
        self.progress.emit(int(done), int(total), str(stage))

    def run(self):
        try:
            if self.kind == "preview":
                result = ascii_clip.preview(
                    self.project, self.game, self.slot, self.settings,
                    self._progress, self.cancel_event,
                )
            elif self.kind == "compare":
                result = ascii_clip.compare(
                    self.project, self.game, self.slot, self.settings,
                )
            else:
                result = ascii_clip.convert(
                    self.project, self.game, self.slot, self.settings,
                    self._progress, self.cancel_event,
                )
            self.done.emit(result)
        except AsciiCanceled:
            self.failed.emit("Operazione interrotta.")
        except Exception as exc:
            self.failed.emit(str(exc))


class AsciiClueDialog(QDialog):
    def __init__(self, project, game, slot: int, parent=None):
        super().__init__(parent)
        self.project = project
        self.game = game
        self.slot = slot
        self.worker: _ClueWorker | None = None
        self.source_info: dict = {}
        self._build()
        self._load()

    def _build(self):
        self.setWindowTitle("Indizio ASCII")
        self.resize(1120, 780)
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(8)

        self.title = QLabel("")
        self.title.setObjectName("h1")
        left.addWidget(self.title)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        left.addWidget(self.status)

        source_row = QHBoxLayout()
        self.source_label = QLabel("")
        self.source_label.setObjectName("muted")
        self.source_label.setWordWrap(True)
        source_row.addWidget(self.source_label, 1)
        self.open_btn = QPushButton("Apri originale")
        self.open_btn.setObjectName("ghost")
        self.open_btn.clicked.connect(self.open_original)
        source_row.addWidget(self.open_btn)
        self.original_btn = QPushButton("Mostra originale")
        self.original_btn.setObjectName("ghost")
        self.original_btn.clicked.connect(self.show_original)
        source_row.addWidget(self.original_btn)
        self.import_btn = QPushButton("Importa video")
        self.import_btn.setObjectName("ghost")
        self.import_btn.clicked.connect(self.import_source)
        source_row.addWidget(self.import_btn)
        left.addLayout(source_row)

        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)
        self.mode_combo = QComboBox()
        for key, label in ascii_clip.MODE_LABELS.items():
            self.mode_combo.addItem(label, key)
        self.color_combo = QComboBox()
        for key, label in ascii_clip.COLOR_LABELS.items():
            self.color_combo.addItem(label, key)
        self.density_spin = QSpinBox()
        self.density_spin.setRange(42, 120)
        self.gamma_spin = QDoubleSpinBox()
        self.gamma_spin.setRange(0.50, 1.50)
        self.gamma_spin.setSingleStep(0.01)
        self.shadow_spin = QDoubleSpinBox()
        self.shadow_spin.setRange(0.10, 0.60)
        self.shadow_spin.setSingleStep(0.01)
        self.contrast_spin = QDoubleSpinBox()
        self.contrast_spin.setRange(0.50, 1.00)
        self.contrast_spin.setSingleStep(0.01)
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0.0, 36000.0)
        self.start_spin.setDecimals(2)
        self.start_spin.setSuffix(" s")
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.5, 12.0)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setSuffix(" s")
        fields = [
            ("Modalità", self.mode_combo, "Colore", self.color_combo),
            ("Densità", self.density_spin, "Luminosità", self.gamma_spin),
            ("Ombre", self.shadow_spin, "Contrasto", self.contrast_spin),
            ("Inizio", self.start_spin, "Durata", self.duration_spin),
        ]
        for row, (label_a, widget_a, label_b, widget_b) in enumerate(fields):
            a = QLabel(label_a); a.setObjectName("muted")
            b = QLabel(label_b); b.setObjectName("muted")
            grid.addWidget(a, row, 0); grid.addWidget(widget_a, row, 1)
            grid.addWidget(b, row, 2); grid.addWidget(widget_b, row, 3)
        left.addWidget(card)

        for widget in (self.mode_combo, self.color_combo, self.density_spin,
                       self.gamma_spin, self.shadow_spin, self.contrast_spin,
                       self.start_spin, self.duration_spin):
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._save_settings)
            else:
                widget.valueChanged.connect(self._save_settings)

        actions = QHBoxLayout()
        self.preview_btn = QPushButton("Anteprima")
        self.preview_btn.setObjectName("primary")
        self.preview_btn.clicked.connect(lambda: self._start("preview"))
        self.compare_btn = QPushButton("Confronta 3 modalità")
        self.compare_btn.setObjectName("ghost")
        self.compare_btn.clicked.connect(lambda: self._start("compare"))
        actions.addWidget(self.preview_btn)
        actions.addWidget(self.compare_btn)
        actions.addStretch(1)
        left.addLayout(actions)

        actions2 = QHBoxLayout()
        self.convert_btn = QPushButton("Genera clip ASCII")
        self.convert_btn.setObjectName("primary")
        self.convert_btn.clicked.connect(lambda: self._start("convert"))
        self.stop_btn = QPushButton("Interrompi")
        self.stop_btn.setObjectName("ghost")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        self.approve_btn = QPushButton("Approva")
        self.approve_btn.setObjectName("ghost")
        self.approve_btn.clicked.connect(self.approve)
        actions2.addWidget(self.convert_btn)
        actions2.addWidget(self.stop_btn)
        actions2.addWidget(self.approve_btn)
        actions2.addStretch(1)
        left.addLayout(actions2)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        left.addWidget(self.progress)
        self.run_status = QLabel("")
        self.run_status.setObjectName("muted")
        self.run_status.setWordWrap(True)
        left.addWidget(self.run_status)
        left.addStretch(1)

        close = QPushButton("Chiudi")
        close.setObjectName("ghost")
        close.clicked.connect(self.accept)
        foot = QHBoxLayout()
        foot.addStretch(1)
        foot.addWidget(close)
        left.addLayout(foot)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        preview_title = QLabel("Confronto")
        preview_title.setObjectName("h2")
        right.addWidget(preview_title)
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedSize(360, 620)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(6, 6, 6, 6)
        self.stack = QStackedWidget()
        self.video = QVideoWidget()
        self.video.setStyleSheet("background:#000;")
        self.still = QLabel("Anteprima ASCII")
        self.still.setAlignment(Qt.AlignCenter)
        self.still.setStyleSheet("background:#080a0e; color:#596273;")
        self.placeholder = QLabel("Genera un'anteprima o confronta le modalità.")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet("color:#596273;")
        self.stack.addWidget(self.placeholder)
        self.stack.addWidget(self.video)
        self.stack.addWidget(self.still)
        fl.addWidget(self.stack)
        right.addWidget(frame)
        self.output_label = QLabel("")
        self.output_label.setObjectName("muted")
        self.output_label.setWordWrap(True)
        right.addWidget(self.output_label)
        root.addLayout(right, 0)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.8)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)

    def _load(self):
        self.title.setText(f"{self.game.title} — Indizio {self.slot + 1}")
        source = self.project.clip_mp4(self.game, self.slot)
        self.source_info = media.probe(source) if source else {}
        if source:
            info = self.source_info
            self.source_label.setText(
                f"Originale: {source.name} — {info['width']}x{info['height']}, "
                f"{info['fps']:.2f} fps, {info['duration']:.2f} s"
            )
            self.start_spin.setRange(0.0, max(0.0, info["duration"] - 0.5))
            self.duration_spin.setRange(0.5, max(0.5, min(12.0, info["duration"])))
        else:
            self.source_label.setText("Nessuna clip registrata: registra o importa un video.")
            self.start_spin.setEnabled(False)
            self.duration_spin.setEnabled(False)
        self.open_btn.setEnabled(bool(source))
        self.original_btn.setEnabled(bool(source))
        data = self.game.clips[self.slot].ascii or {}
        mode = data.get("mode", ascii_clip.DEFAULT_SETTINGS["mode"])
        index = self.mode_combo.findData(mode)
        self.mode_combo.setCurrentIndex(max(0, index))
        color = data.get("color", ascii_clip.DEFAULT_SETTINGS["color"])
        index = self.color_combo.findData(color)
        self.color_combo.setCurrentIndex(max(0, index))
        self.density_spin.setValue(int(data.get("density", 81)))
        self.gamma_spin.setValue(float(data.get("gamma", 0.82)))
        self.shadow_spin.setValue(float(data.get("shadow", 0.31)))
        self.contrast_spin.setValue(float(data.get("contrast_high", 0.85)))
        duration = float(data.get("duration", 2.0))
        self.duration_spin.setValue(duration)
        start = data.get("start")
        if start is None and self.source_info:
            start = max(0.0, (self.source_info["duration"] - duration) / 2.0)
        self.start_spin.setValue(float(start or 0.0))
        self._refresh_state()
        preview = data.get("preview") or data.get("compare")
        if preview and Path(preview).exists():
            if str(preview).lower().endswith((".mp4", ".mkv", ".mov")):
                self._show_video(str(preview))
            else:
                self._show_still(str(preview))
        elif source:
            verify = source.parent / "verify_vertical.png"
            if verify.exists():
                self._show_still(str(verify))
        if data.get("output") and Path(data["output"]).exists():
            self.output_label.setText(f"Clip ASCII: {data['output']}")

    def _settings(self) -> dict:
        return ascii_clip.normalize_settings({
            "mode": self.mode_combo.currentData(),
            "density": int(self.density_spin.value()),
            "color": self.color_combo.currentData(),
            "gamma": float(self.gamma_spin.value()),
            "shadow": float(self.shadow_spin.value()),
            "contrast_high": float(self.contrast_spin.value()),
            "start": float(self.start_spin.value()),
            "duration": float(self.duration_spin.value()),
        })

    def _save_settings(self, *_):
        if not self.project.clip_mp4(self.game, self.slot):
            return
        settings = self._settings()
        current = self.game.clips[self.slot].ascii or {}
        update = dict(settings)
        if current.get("output") and Path(current["output"]).exists():
            try:
                new_fp = ascii_clip.fingerprint(self.project, self.game, self.slot, settings)
                update["dirty"] = current.get("fingerprint") != new_fp
            except Exception:
                pass
        self.project.set_ascii(self.game, self.slot, update)
        self._refresh_state()

    def _refresh_state(self):
        state = self.project.ascii_state(self.game, self.slot)
        labels = {
            "missing": "Mancante: registra o importa l'originale.",
            "recorded": "Originale registrato; conversione ASCII mancante.",
            "dirty": "Parametri cambiati: rigenera la conversione ASCII.",
            "converted": "Conversione ASCII pronta: da approvare.",
            "approved": "Indizio ASCII approvato.",
        }
        data = self.game.clips[self.slot].ascii or {}
        extra = ""
        if data.get("output") and Path(data["output"]).exists():
            extra = f"\nFile: {data['output']}"
        self.status.setText(labels.get(state, state) + extra)
        self.approve_btn.setEnabled(state == "converted")

    def _set_busy(self, busy: bool):
        for widget in (self.preview_btn, self.compare_btn, self.convert_btn,
                       self.import_btn, self.approve_btn, self.mode_combo,
                       self.color_combo, self.density_spin, self.gamma_spin,
                       self.shadow_spin, self.contrast_spin, self.start_spin,
                       self.duration_spin):
            widget.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)

    def _start(self, kind: str):
        if self.worker is not None:
            return
        if not self.project.clip_mp4(self.game, self.slot):
            QMessageBox.warning(self, "Indizio ASCII", "Registra o importa prima l'originale.")
            return
        self._save_settings()
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.run_status.setText("Confronto modalità in corso..." if kind == "compare" else "Preparazione...")
        self.worker = _ClueWorker(self.project, self.game, self.slot, self._settings(), kind)
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def stop(self):
        if self.worker:
            self.run_status.setText("Interruzione richiesta...")
            self.worker.cancel()

    def _worker_finished(self):
        self.worker = None
        self._set_busy(False)

    def on_progress(self, done, total, stage):
        if total <= 0:
            self.progress.setRange(0, 0)
            self.run_status.setText(f"{stage}...")
            return
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.run_status.setText(f"{stage} — {done}/{total} frame")

    def on_done(self, payload):
        if isinstance(payload, dict):
            self.project = self.project
            self.output_label.setText(f"Clip ASCII: {payload.get('output', '')}")
            self.run_status.setText("Clip ASCII generata. Controllala e approvala.")
            if payload.get("output") and Path(payload["output"]).exists():
                self._show_video(payload["output"])
        else:
            path = str(payload)
            self.run_status.setText("Operazione completata.")
            self._show_video(path) if path.lower().endswith((".mp4", ".mkv", ".mov")) else self._show_still(path)
        self._refresh_state()

    def on_failed(self, message):
        self.run_status.setText("Operazione non riuscita.")
        self._refresh_state()
        QMessageBox.critical(self, "Indizio ASCII", message[-3000:])

    def approve(self):
        try:
            ascii_clip.approve(self.project, self.game, self.slot)
        except Exception as exc:
            QMessageBox.critical(self, "Indizio ASCII", str(exc))
            return
        self.run_status.setText("Indizio approvato.")
        self._refresh_state()

    def import_source(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importa video", "", "Video (*.mp4 *.mov *.mkv *.webm)"
        )
        if not path:
            return
        try:
            ascii_clip.import_video(self.project, self.game, self.slot, path)
        except Exception as exc:
            QMessageBox.critical(self, "Importa video", str(exc))
            return
        self.source_info = media.probe(self.project.clip_mp4(self.game, self.slot))
        self._load()
        self.run_status.setText("Video importato. Scegli l'intervallo e converti.")

    def open_original(self):
        source = self.project.clip_mp4(self.game, self.slot)
        if source:
            os.startfile(source)

    def show_original(self):
        source = self.project.clip_mp4(self.game, self.slot)
        if not source:
            return
        verify = source.parent / "verify_vertical.png"
        if verify.exists():
            self._show_still(str(verify))
        else:
            self.open_original()

    def _show_video(self, path: str):
        self.player.setSource(QUrl())
        self.player.setSource(QUrl.fromLocalFile(path))
        self.stack.setCurrentWidget(self.video)
        self.player.play()

    def _show_still(self, path: str):
        self.player.stop()
        pix = QPixmap(path)
        if not pix.isNull():
            self.still.setPixmap(pix.scaled(self.still.size(), Qt.KeepAspectRatio,
                                            Qt.SmoothTransformation))
        self.stack.setCurrentWidget(self.still)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(8000)
        self.player.stop()
        super().closeEvent(event)
