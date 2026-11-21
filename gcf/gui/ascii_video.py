from __future__ import annotations

import os
import threading
from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
)

import gcf.ascii.render as ascii_render
from gcf.ascii import media, preset
from gcf.ascii.project import AsciiProject, recent_ascii_projects
from gcf.ascii.render import AsciiCanceled


class AsciiWorker(QThread):
    progress = Signal(int, int, float, float, str)
    done = Signal(str, object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, project: AsciiProject, kind: str, at: float = 0.0):
        super().__init__()
        self.project = project
        self.kind = kind
        self.at = at
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def _on_progress(self, done, total, elapsed, eta, stage):
        self.progress.emit(int(done), int(total), float(elapsed),
                           float(eta) if eta else -1.0, stage)

    def run(self):
        try:
            if self.kind == "preview":
                path = ascii_render.preview(self.project, self._on_progress, self._cancel)
                self.done.emit("preview", str(path))
            elif self.kind == "still":
                path = ascii_render.still(self.project, self.at, self._on_progress, self._cancel)
                self.done.emit("still", str(path))
            else:
                out = ascii_render.render(self.project, self._on_progress, self._cancel)
                self.done.emit("full", out)
        except AsciiCanceled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class AsciiVideoPage(QWidget):
    def __init__(self, on_home):
        super().__init__()
        self.on_home = on_home
        self.project: AsciiProject | None = None
        self.worker: AsciiWorker | None = None
        self.source_info: dict = {}
        self.last_output = ""
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(36, 24, 36, 24)
        root.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(9)
        top = QHBoxLayout()
        home = QPushButton("Home")
        home.setObjectName("ghost")
        home.clicked.connect(self.on_home)
        top.addWidget(home)
        top.addSpacing(10)
        kicker = QLabel("NUOVO VIDEO ASCII")
        kicker.setObjectName("kicker")
        top.addWidget(kicker)
        top.addStretch(1)
        left.addLayout(top)
        title = QLabel("Gameplay -> ASCII cinematico")
        title.setObjectName("h1")
        left.addWidget(title)

        src_row = QHBoxLayout()
        self.source_edit = QLineEdit()
        self.source_edit.setReadOnly(True)
        self.source_edit.setPlaceholderText("Scegli un file MP4...")
        browse = QPushButton("Sfoglia MP4")
        browse.setObjectName("ghost")
        browse.clicked.connect(self.browse_source)
        src_row.addWidget(self.source_edit, 1)
        src_row.addWidget(browse)
        left.addLayout(src_row)
        self.source_label = QLabel("Nessuna sorgente.")
        self.source_label.setObjectName("muted")
        left.addWidget(self.source_label)

        reopen_row = QHBoxLayout()
        self.reopen_combo = QComboBox()
        self.reopen_combo.setMinimumWidth(360)
        reopen = QPushButton("Riapri progetto")
        reopen.setObjectName("ghost")
        reopen.clicked.connect(self.reopen_project)
        self.reopen_btn = reopen
        reopen_row.addWidget(self.reopen_combo, 1)
        reopen_row.addWidget(reopen)
        left.addLayout(reopen_row)
        self.refresh_projects()

        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)
        self.format_combo = QComboBox()
        self.format_combo.addItem("Orizzontale 16:9", "horizontal")
        self.format_combo.addItem("Verticale 9:16", "vertical")
        self.format_combo.currentIndexChanged.connect(self._format_changed)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Cinematic Balanced v2", preset.PRESET_NAME)
        self.color_combo = QComboBox()
        self.color_combo.addItem("Cinematic Amber", 1.0)
        self.color_combo.addItem("Original RGB", 0.0)
        self.interval_combo = QComboBox()
        self.interval_combo.addItem("Tutto il video", "full")
        self.interval_combo.addItem("Solo intervallo", "range")
        self.interval_combo.currentIndexChanged.connect(self._interval_changed)
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0.0, 36000.0)
        self.start_spin.setDecimals(2)
        self.start_spin.setSuffix(" s")
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.5, 36000.0)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setSuffix(" s")
        self.gamma_spin = QDoubleSpinBox()
        self.gamma_spin.setRange(0.50, 1.50)
        self.gamma_spin.setSingleStep(0.01)
        self.gamma_spin.setValue(0.82)
        self.shadow_spin = QDoubleSpinBox()
        self.shadow_spin.setRange(0.10, 0.60)
        self.shadow_spin.setSingleStep(0.01)
        self.shadow_spin.setValue(0.31)
        self.contrast_spin = QDoubleSpinBox()
        self.contrast_spin.setRange(0.50, 1.00)
        self.contrast_spin.setSingleStep(0.01)
        self.contrast_spin.setValue(0.85)
        self.density_spin = QSpinBox()
        self.density_spin.setRange(42, 70)
        self.density_spin.setValue(54)
        self.density_spin.valueChanged.connect(self._refresh_density)
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(6, 20)
        self.bitrate_spin.setValue(8)
        self.bitrate_spin.setSuffix(" Mbps")
        self.density_label = QLabel("96x54 - glyph 0.0166")
        self.density_label.setObjectName("muted")

        fields = [
            ("Formato", self.format_combo, "Preset", self.preset_combo),
            ("Intervallo", self.interval_combo, "Colore", self.color_combo),
            ("Inizio", self.start_spin, "Durata", self.duration_spin),
            ("Gamma", self.gamma_spin, "Ombre", self.shadow_spin),
            ("Contrasto alto", self.contrast_spin, "Densita", self.density_spin),
            ("YouTube", self.bitrate_spin, "", None),
        ]
        for r, (l1, w1, l2, w2) in enumerate(fields):
            a = QLabel(l1); a.setObjectName("muted"); grid.addWidget(a, r, 0)
            grid.addWidget(w1, r, 1)
            if w2 is not None:
                b = QLabel(l2); b.setObjectName("muted"); grid.addWidget(b, r, 2)
                grid.addWidget(w2, r, 3)
        grid.addWidget(self.density_label, len(fields), 0, 1, 4)
        left.addWidget(card)
        self.start_spin.setEnabled(False)
        self.duration_spin.setEnabled(False)

        actions = QHBoxLayout()
        self.preview_btn = QPushButton("Anteprima 4 s")
        self.preview_btn.setObjectName("primary")
        self.preview_btn.clicked.connect(self.make_preview)
        self.still_btn = QPushButton("Frame singolo")
        self.still_btn.setObjectName("ghost")
        self.still_btn.clicked.connect(self.make_still)
        self.still_at = QDoubleSpinBox()
        self.still_at.setRange(0.0, 36000.0)
        self.still_at.setDecimals(2)
        self.still_at.setSuffix(" s")
        actions.addWidget(self.preview_btn)
        actions.addWidget(self.still_btn)
        actions.addWidget(self.still_at)
        actions.addStretch(1)
        left.addLayout(actions)

        render_row = QHBoxLayout()
        self.render_btn = QPushButton("Rendering completo")
        self.render_btn.setObjectName("primary")
        self.render_btn.clicked.connect(self.make_full)
        self.stop_btn = QPushButton("Interrompi")
        self.stop_btn.setObjectName("ghost")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_worker)
        self.open_btn = QPushButton("Apri video")
        self.open_btn.setObjectName("ghost")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_output)
        render_row.addWidget(self.render_btn)
        render_row.addWidget(self.stop_btn)
        render_row.addWidget(self.open_btn)
        render_row.addStretch(1)
        left.addLayout(render_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        left.addWidget(self.progress)
        self.status = QLabel("Scegli un MP4 e genera un'anteprima.")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        left.addStretch(1)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        self.preview_title = QLabel("Anteprima")
        self.preview_title.setObjectName("h2")
        right.addWidget(self.preview_title)
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedSize(500, 560)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(8, 8, 8, 8)
        self.stack = QStackedWidget()
        self.video = QVideoWidget()
        self.video.setStyleSheet("background:#000;")
        self.still_label = QLabel("Anteprima ASCII")
        self.still_label.setAlignment(Qt.AlignCenter)
        self.still_label.setStyleSheet("background:#080a0e; color:#596273; border-radius:8px;")
        self.placeholder = QLabel("Genera un'anteprima per vedere il risultato.")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet("color:#596273;")
        self.stack.addWidget(self.placeholder)
        self.stack.addWidget(self.video)
        self.stack.addWidget(self.still_label)
        fl.addWidget(self.stack)
        right.addWidget(frame)
        self.output_label = QLabel("")
        self.output_label.setObjectName("muted")
        self.output_label.setWordWrap(True)
        right.addWidget(self.output_label)
        right.addStretch(1)
        root.addLayout(right, 0)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.8)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.setLoops(QMediaPlayer.Loops.Infinite)

    def browse_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Scegli un MP4", "", "Video (*.mp4 *.mov *.mkv)")
        if not path:
            return
        try:
            info = media.probe(path)
        except Exception as exc:
            QMessageBox.critical(self, "Sorgente non valida", str(exc))
            return
        self.source_edit.setText(path)
        self.source_info = info
        self.source_label.setText(
            f"{info['width']}x{info['height']} - {info['fps']:.3f} fps - "
            f"{info['duration']:.2f} s - audio {'si' if info['has_audio'] else 'no'}"
        )
        self.start_spin.setRange(0.0, max(0.0, info["duration"] - 0.5))
        self.duration_spin.setRange(0.5, max(0.5, info["duration"]))
        self.duration_spin.setValue(min(5.0, info["duration"]))
        self.still_at.setRange(0.0, max(0.0, info["duration"] - 0.03))
        self.project = None
        self._clear_preview()
        self.status.setText("Sorgente pronta. Genera l'anteprima.")

    def refresh_projects(self):
        current = self.reopen_combo.currentData()
        self.reopen_combo.clear()
        for path in recent_ascii_projects(20):
            try:
                project = AsciiProject.load(path)
            except Exception:
                continue
            label = f"{project.id} - {Path(project.source).name} - {project.format}"
            self.reopen_combo.addItem(label, str(path))
        index = self.reopen_combo.findData(current)
        if index >= 0:
            self.reopen_combo.setCurrentIndex(index)

    def reopen_project(self):
        path = self.reopen_combo.currentData()
        if not path:
            return
        try:
            project = AsciiProject.load(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Progetto non valido", str(exc))
            return
        self.format_combo.blockSignals(True)
        self.interval_combo.blockSignals(True)
        self.format_combo.setCurrentIndex(0 if project.format == "horizontal" else 1)
        ranged = project.interval_duration is not None
        self.interval_combo.setCurrentIndex(1 if ranged else 0)
        self.start_spin.setValue(float(project.interval_start or 0.0))
        if ranged:
            self.duration_spin.setValue(float(project.interval_duration))
        self.start_spin.setEnabled(ranged)
        self.duration_spin.setEnabled(ranged)
        self.format_combo.blockSignals(False)
        self.interval_combo.blockSignals(False)
        params = project.params or {}
        self.gamma_spin.setValue(float(params.get("gamma", 0.82)))
        self.shadow_spin.setValue(float(params.get("shadow", 0.31)))
        self.contrast_spin.setValue(float(params.get("contrast_high", 0.85)))
        self.density_spin.setValue(int(params.get("density", 54)))
        color = int(round(float(params.get("color_mode", 1.0))))
        self.color_combo.setCurrentIndex(0 if color == 1 else 1)
        self.bitrate_spin.setValue(int(params.get("youtube_mbps", 8)))
        self._refresh_density()
        self.source_edit.setText(project.source)
        self.source_info = project.source_info or {}
        info = self.source_info
        if info:
            self.source_label.setText(
                f"{info.get('width', 0)}x{info.get('height', 0)} - "
                f"{info.get('fps', 0):.3f} fps - {info.get('duration', 0):.2f} s - "
                f"audio {'si' if info.get('has_audio') else 'no'}"
            )
        self._clear_preview()
        self.project = project
        done = len(list(project.frames_dir.glob("f_*.png")))
        total = int(round(project.working_info.get("duration", 0.0) * 30)) if project.working_info else 0
        self.status.setText(
            f"Progetto {project.id} riaperto: {done}/{total} frame presenti. "
            "Rendering completo riprende dal primo frame mancante."
        )
        if project.preview and Path(project.preview).exists():
            if project.preview.lower().endswith(".mp4"):
                self._show_video(project.preview)
            else:
                self._show_still(project.preview)
            self.last_output = project.preview
            self.open_btn.setEnabled(True)

    def _format_changed(self, *_):
        self.project = None
        self._clear_preview()
        self._refresh_density()

    def _interval_changed(self, *_):
        ranged = self.interval_combo.currentData() == "range"
        self.start_spin.setEnabled(ranged)
        self.duration_spin.setEnabled(ranged)
        self._clear_preview()
        self.project = None

    def _refresh_density(self, *_):
        fmt = self.format_combo.currentData() or "horizontal"
        grid = preset.grid_for(fmt, self.density_spin.value())
        self.density_label.setText(
            f"{grid['cols']}x{grid['rows']} - glyph {grid['glyph']:.4f} - "
            f"{'9:16' if fmt == 'vertical' else '16:9'}"
        )

    def _clear_preview(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.stack.setCurrentWidget(self.placeholder)
        self.output_label.setText("")
        self.open_btn.setEnabled(False)
        self.last_output = ""

    def _params(self) -> dict:
        return {
            "gamma": float(self.gamma_spin.value()),
            "shadow": float(self.shadow_spin.value()),
            "contrast_high": float(self.contrast_spin.value()),
            "density": int(self.density_spin.value()),
            "color_mode": float(self.color_combo.currentData()),
            "youtube_mbps": int(self.bitrate_spin.value()),
        }

    def _ensure_project(self) -> AsciiProject:
        source = self.source_edit.text().strip()
        if not source:
            raise ValueError("Scegli prima un file MP4.")
        fmt = self.format_combo.currentData() or "horizontal"
        ranged = self.interval_combo.currentData() == "range"
        start = float(self.start_spin.value()) if ranged else 0.0
        duration = float(self.duration_spin.value()) if ranged else None
        params = self._params()
        if self.project is None or self.project.source != source or self.project.format != fmt:
            self.project = AsciiProject.create(source, fmt, start, duration, params)
        else:
            self.project.interval_start = start
            self.project.interval_duration = duration
            self.project.params = params
            self.project.save()
        return self.project

    def _set_busy(self, busy: bool):
        for w in (self.preview_btn, self.still_btn, self.render_btn):
            w.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)

    def _start(self, kind: str, at: float = 0.0):
        if self.worker is not None:
            return
        try:
            project = self._ensure_project()
        except Exception as exc:
            QMessageBox.critical(self, "Impossibile avviare", str(exc))
            return
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.status.setText("Preparazione sorgente...")
        self.worker = AsciiWorker(project, kind, at)
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.cancelled.connect(self.on_cancelled)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def make_preview(self):
        self._start("preview")

    def make_still(self):
        self._start("still", float(self.still_at.value()))

    def make_full(self):
        self._start("full")

    def stop_worker(self):
        if self.worker:
            self.status.setText("Interruzione richiesta...")
            self.stop_btn.setEnabled(False)
            self.worker.cancel()

    def _worker_finished(self):
        self.worker = None
        self._set_busy(False)

    def on_progress(self, done, total, elapsed, eta, stage):
        if total <= 0:
            self.progress.setRange(0, 0)
            self.status.setText(f"{stage}...")
            return
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        eta_text = ""
        if eta and eta > 0:
            eta_text = f" - ETA {int(eta // 60)}:{int(eta % 60):02d}"
        self.status.setText(f"{stage} - {done}/{total} frame - {elapsed:.0f}s{eta_text}")

    def on_done(self, kind, payload):
        if kind == "preview":
            self._show_video(str(payload))
            self.last_output = str(payload)
            self.open_btn.setEnabled(True)
            self.status.setText("Anteprima pronta. Controlla forme e movimento, poi avvia il rendering completo.")
            self.output_label.setText(f"Anteprima: {payload}")
        elif kind == "still":
            self._show_still(str(payload))
            self.last_output = str(payload)
            self.open_btn.setEnabled(True)
            self.status.setText("Frame pronto.")
            self.output_label.setText(f"Frame: {payload}")
        else:
            outputs = payload or {}
            target = outputs.get("youtube") or outputs.get("master") or ""
            self.last_output = target
            self.open_btn.setEnabled(bool(target))
            if target:
                self._show_video(target)
            master = outputs.get("master", "")
            youtube = outputs.get("youtube", "")
            self.status.setText("Rendering completato. Master e YouTube pronti.")
            self.output_label.setText(f"Master: {master}\nYouTube: {youtube}")
            self.refresh_projects()

    def on_failed(self, message):
        self.status.setText("Errore. Vedi il log del progetto.")
        self._set_busy(False)
        if self.project:
            self.project.error = message
            self.project.status = "error"
            self.project.save()
        QMessageBox.critical(self, "Errore ASCII", message[-3000:])

    def on_cancelled(self):
        self.status.setText("Rendering interrotto. I frame restano: puoi riprendere con Rendering completo.")
        self._set_busy(False)

    def _show_video(self, path: str):
        self.player.setSource(QUrl())
        self.player.setSource(QUrl.fromLocalFile(path))
        self.stack.setCurrentWidget(self.video)
        self.player.play()

    def _show_still(self, path: str):
        self.player.stop()
        pix = QPixmap(path)
        if not pix.isNull():
            self.still_label.setPixmap(
                pix.scaled(self.still_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        self.stack.setCurrentWidget(self.still_label)

    def open_output(self):
        if self.last_output and Path(self.last_output).exists():
            os.startfile(self.last_output)
