from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QColorDialog, QComboBox, QDialog,
    QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QProgressBar, QSpinBox, QStackedWidget, QTabWidget,
    QToolButton, QVBoxLayout, QWidget,
)

from gcf.capture.obs import Obs
from gcf.config import ROOT, project_dir
from gcf.gui.ascii_video import AsciiVideoPage
from gcf.gui.capture import GuiCaptureSession
from gcf.gui.guess_ascii import AsciiClueDialog
from gcf.gui.overlay import ACCENT, CaptureControlPanel, CropOverlay, exclude_from_capture
from gcf.gui.project import CLIP_COUNT, CLIP_LABELS, Project, recent_projects
from gcf.gui.windows import (
    find_window,
    foreground_window,
    monitor_for_window,
    monitor_rect_from_obs_item,
    primary_screen,
    title_from_obs_item,
)
from gcf.guess.cover import build_cover, render_cover_still
from gcf.guess.round import load_preset
from gcf.guess.short import build_game_round, build_short, build_short_preview


APP_STYLE = """
QMainWindow, QDialog, QWidget#page { background: #101218; }
QLabel { color: #e8edf6; }
QLabel#kicker { color: #00B7FF; font-size: 12px; font-weight: 800; letter-spacing: 2px; }
QLabel#h1 { font-size: 30px; font-weight: 800; }
QLabel#h2 { font-size: 19px; font-weight: 700; }
QLabel#muted { color: #9aa3b2; font-size: 12px; }
QPushButton { background: #252a35; color: #e8edf6; border: 0; border-radius: 9px;
              padding: 10px 16px; font-size: 13px; font-weight: 650; }
QPushButton:hover { background: #333a49; }
QPushButton#primary { background: #00A6E6; color: #061118; font-weight: 800; padding: 13px 22px; }
QPushButton#primary:hover { background: #2fc1ff; }
QPushButton#primary:disabled { background: #1b1f28; color: #596273; }
QPushButton#ghost { background: transparent; border: 1px solid #343a49; color: #b7c0cf; }
QPushButton#ghost:hover { border-color: #00B7FF; color: white; }
QPushButton:disabled { color: #596273; background: #1b1f28; }
QLineEdit { background: #191d25; border: 1px solid #303644; border-radius: 8px;
            padding: 10px 12px; color: white; font-size: 14px; }
QLineEdit:focus { border-color: #00B7FF; }
QComboBox { background: #191d25; border: 1px solid #303644; border-radius: 8px;
            padding: 8px 10px; color: white; min-height: 18px; }
QComboBox QAbstractItemView { background: #191d25; color: white; selection-background-color: #006f9e; }
QSpinBox, QDoubleSpinBox { background: #191d25; border: 1px solid #303644; border-radius: 8px;
                           padding: 6px 8px; color: white; min-height: 18px; }
QTabWidget { background: #101218; }
QTabWidget::pane { border: 1px solid #2a303c; background: #151920; border-radius: 8px; }
QTabBar::tab { background: #1b2029; color: #9aa3b2; padding: 8px 18px;
               border: 1px solid #2a303c; border-bottom: 0; }
QTabBar::tab:selected { background: #22303e; color: white; }
QWidget#tabPage { background: #151920; }
QListWidget { background: #151920; border: 1px solid #2a303c; border-radius: 10px; padding: 6px; }
QListWidget::item { padding: 10px; border-radius: 6px; color: #cfd7e4; }
QListWidget::item:selected { background: #22303e; color: white; }
QToolButton { background: #161a22; border: 1px solid #2a303c; border-radius: 10px;
              color: #9aa3b2; padding: 6px; font-size: 11px; font-weight: 650; }
QToolButton:hover { border-color: #00B7FF; color: #e8edf6; }
QToolButton:checked { border: 2px solid #00B7FF; background: #16232e; color: white; }
QFrame#card { background: #161a22; border: 1px solid #2a303c; border-radius: 14px; }
QProgressBar { background: #1b2029; border: 0; border-radius: 5px; height: 6px; text-align: center; }
QProgressBar::chunk { background: #00B7FF; border-radius: 5px; }
"""


class ShortWorker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, project_id: str):
        super().__init__()
        self.project_id = project_id

    def run(self):
        try:
            manifest = build_short(self.project_id)
            self.done.emit(str(ROOT / manifest["output"]))
        except Exception as exc:
            self.failed.emit(str(exc))


class ShortPreviewWorker(QThread):
    done = Signal(str, int)
    failed = Signal(str)

    def __init__(self, project_id: str, games: int = 3):
        super().__init__()
        self.project_id = project_id
        self.games = games

    def run(self):
        try:
            manifest = build_short_preview(self.project_id, games=self.games)
            self.done.emit(str(ROOT / manifest["output"]), int(manifest["frames"]))
        except Exception as exc:
            self.failed.emit(str(exc))


class WarmObsWorker(QThread):
    def run(self):
        try:
            obs = Obs()
            obs.ensure_running()
            obs.close()
        except Exception:
            pass


class RoundWorker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, project_id: str, game_index: int):
        super().__init__()
        self.project_id = project_id
        self.game_index = game_index

    def run(self):
        try:
            project = Project.load(project_dir(self.project_id))
            manifest = build_game_round(project, self.game_index)
            out = Path(manifest["output"])
            self.done.emit(str(out if out.is_absolute() else ROOT / out))
        except Exception as exc:
            self.failed.emit(str(exc))


COVER_CATEGORIES = ("ASCII", "Scenery", "HUD", "Menu", "Skybox", "Title Screen", "Personalizzato")


def _pil_pixmap(image, size: QSize) -> QPixmap:
    image = image.convert("RGBA")
    data = image.tobytes()
    qimage = QImage(
        data, image.width, image.height, image.width * 4, QImage.Format_RGBA8888
    ).copy()
    return QPixmap.fromImage(qimage).scaled(
        size, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )


class CoverEditor(QWidget):
    def __init__(self, project: Project | None = None, compact: bool = True):
        super().__init__()
        self.project = project
        self._loading = False
        self.preview_size = QSize(150, 267) if compact else QSize(240, 426)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        form = QVBoxLayout()
        form.setSpacing(5)
        form.addWidget(self._muted("Titolo challenge"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("GUESS THE GAME IN ASCII")
        form.addWidget(self.title_edit)
        form.addWidget(self._muted("Categoria (opzionale)"))
        self.category = QComboBox()
        self.category.addItems(COVER_CATEGORIES)
        form.addWidget(self.category)
        form.addWidget(self._muted("Sfondo"))
        bg_row = QHBoxLayout()
        bg_row.setSpacing(6)
        self.background = QComboBox()
        bg_row.addWidget(self.background, 1)
        self.browse_btn = QPushButton("Sfoglia")
        self.browse_btn.setObjectName("ghost")
        self.browse_btn.setFixedWidth(74)
        self.browse_btn.clicked.connect(self._browse_image)
        bg_row.addWidget(self.browse_btn)
        form.addLayout(bg_row)
        form.addWidget(self._muted("Durata copertina"))
        self.duration = QDoubleSpinBox()
        self.duration.setRange(1.0, 4.0)
        self.duration.setSingleStep(0.5)
        self.duration.setDecimals(1)
        self.duration.setSuffix(" s")
        form.addWidget(self.duration)
        preset = load_preset(project.graphics_preset if project else None)
        form.addWidget(self._muted(f"Preset grafico: {preset.get('name', 'guess_default')}"))
        form.addStretch(1)
        lay.addLayout(form, 1)

        self.preview = QLabel("Anteprima")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedSize(self.preview_size)
        self.preview.setStyleSheet(
            "background:#0b0d12; border:1px solid #2a303c; border-radius:10px; color:#596273;"
        )
        lay.addWidget(self.preview, 0, Qt.AlignTop)

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(120)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.title_edit.textChanged.connect(self._on_title_edited)
        self.category.currentTextChanged.connect(self._on_category_changed)
        self.background.currentIndexChanged.connect(self.schedule_preview)
        self.duration.valueChanged.connect(self.schedule_preview)

        if project:
            self.load_project(project)
        else:
            self._loading = True
            self.title_edit.setText("GUESS THE GAME IN ASCII")
            self.category.setCurrentText("ASCII")
            self.duration.setValue(2.0)
            self._loading = False
            self.populate_backgrounds({"type": "auto"})
            self.refresh_preview()

    @staticmethod
    def _muted(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted")
        return label

    def load_project(self, project: Project) -> None:
        self.project = project
        self._loading = True
        self.populate_backgrounds(project.cover_background)
        self.title_edit.setText(project.challenge_title)
        category = project.challenge_category
        expected = ("GUESS THE GAME IN ASCII" if category == "ASCII"
                    else f"GUESS THE GAME FROM ITS {category.upper()}")
        if category != "Personalizzato" and project.challenge_title.strip().upper() != expected:
            category = "Personalizzato"
        index = self.category.findText(category)
        self.category.setCurrentIndex(index if index >= 0 else self.category.count() - 1)
        self.duration.setValue(project.cover_duration)
        self._loading = False
        self.refresh_preview()

    def populate_backgrounds(self, selected: dict | None = None) -> None:
        selected = selected or {"type": "auto"}
        self.background.blockSignals(True)
        self.background.clear()
        self.background.addItem("Automatico (sfondo, poi prima clip)", {"type": "auto"})
        if self.project:
            if self.project.cover_mp4():
                self.background.addItem(
                    "Clip di sfondo (registrata)", {"type": "cover"}
                )
            for gi, game in enumerate(self.project.games):
                for slot, _clip in enumerate(game.clips):
                    if self.project.clip_mp4(game, slot):
                        self.background.addItem(
                            f"G{gi + 1} · {game.title} — {CLIP_LABELS[slot]}",
                            {"type": "clip", "game": game.title, "slot": slot},
                        )
        if selected.get("type") == "image" and Path(selected.get("path", "")).exists():
            self.background.addItem(
                f"Immagine: {Path(selected['path']).name}", selected
            )
        chosen = 0
        for i in range(self.background.count()):
            if self.background.itemData(i) == selected:
                chosen = i
                break
        self.background.setCurrentIndex(chosen)
        self.background.blockSignals(False)

    def _on_category_changed(self, category: str) -> None:
        if self._loading:
            return
        if category != "Personalizzato":
            self._loading = True
            self.title_edit.setText(
                "GUESS THE GAME IN ASCII" if category == "ASCII"
                else f"GUESS THE GAME FROM ITS {category.upper()}"
            )
            self._loading = False
        self.schedule_preview()

    def _on_title_edited(self, _text: str) -> None:
        if self._loading:
            return
        if self.category.currentText() != "Personalizzato":
            self._loading = True
            self.category.setCurrentText("Personalizzato")
            self._loading = False
        self.schedule_preview()

    def _browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Immagine di sfondo", "",
            "Immagini (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not path:
            return
        data = {"type": "image", "path": path}
        self.background.blockSignals(True)
        self.background.addItem(f"Immagine: {Path(path).name}", data)
        self.background.setCurrentIndex(self.background.count() - 1)
        self.background.blockSignals(False)
        self.schedule_preview()

    def values(self) -> dict:
        return {
            "challenge_title": self.title_edit.text().strip() or "GUESS THE GAME",
            "challenge_category": self.category.currentText(),
            "cover_background": self.background.currentData() or {"type": "auto"},
            "cover_duration": float(self.duration.value()),
        }

    def _first_clip(self) -> Path | None:
        if not self.project:
            return None
        for game in self.project.games:
            for slot in range(len(game.clips)):
                path = self.project.clip_mp4(game, slot)
                if path:
                    return path
        return None

    def _still_background(self) -> Path | None:
        data = self.background.currentData() or {"type": "auto"}
        if data.get("type") == "image":
            path = Path(data.get("path", ""))
            return path if path.exists() else None
        clip = None
        if data.get("type") == "cover" and self.project:
            clip = self.project.cover_mp4()
        if data.get("type") == "clip" and self.project:
            game = next(
                (g for g in self.project.games if g.title == data.get("game")), None
            )
            if game:
                clip = self.project.clip_mp4(game, int(data.get("slot", 0)))
        if clip is None:
            clip = self.project.cover_mp4() if self.project else None
        if clip is None:
            clip = self._first_clip()
        if clip:
            verify = clip.parent / "verify_vertical.png"
            if verify.exists():
                return verify
        return None

    def schedule_preview(self, *_args) -> None:
        if not self._loading:
            self.preview_timer.start()

    def refresh_preview(self, *_args) -> None:
        if self._loading:
            return
        try:
            preset = load_preset(self.project.graphics_preset if self.project else None)
            image = render_cover_still(
                self.title_edit.text().strip() or "GUESS THE GAME",
                self._still_background(),
                preset,
            )
            self.preview.setPixmap(_pil_pixmap(image, self.preview_size))
        except Exception:
            self.preview.setText("Anteprima non disponibile")

    def show_preview_file(self, path: Path) -> None:
        pix = QPixmap(str(path))
        if pix.isNull():
            return
        self.preview.setPixmap(pix.scaled(
            self.preview_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))


class CoverDialog(QDialog):
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Copertina")
        self.setStyleSheet(APP_STYLE)
        self.resize(780, 560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)
        title = QLabel("Copertina introduttiva")
        title.setObjectName("h2")
        lay.addWidget(title)
        hint = QLabel(
            "Il testo e lo sfondo vengono salvati nel progetto e usati nei primi secondi dello Short."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.editor = CoverEditor(project, compact=False)
        lay.addWidget(self.editor, 1)
        row = QHBoxLayout()
        self.preview_btn = QPushButton("Anteprima animata")
        self.preview_btn.setObjectName("ghost")
        self.preview_btn.clicked.connect(self.preview_animated)
        row.addWidget(self.preview_btn)
        row.addStretch(1)
        cancel = QPushButton("Annulla")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Salva")
        save.setObjectName("primary")
        save.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)

    def preview_animated(self) -> None:
        values = self.editor.values()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            manifest = build_cover(
                self.project,
                title=values["challenge_title"],
                background=values["cover_background"],
                duration=values["cover_duration"],
            )
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Copertina", str(exc))
            return
        QApplication.restoreOverrideCursor()
        preview = Path(manifest["preview"])
        if not preview.is_absolute():
            preview = ROOT / preview
        self.editor.show_preview_file(preview)
        out = Path(manifest["output"])
        if not out.is_absolute():
            out = ROOT / out
        try:
            os.startfile(out)
        except Exception:
            pass

    def accept(self) -> None:
        values = self.editor.values()
        self.project.challenge_title = values["challenge_title"]
        self.project.challenge_category = values["challenge_category"]
        self.project.cover_background = values["cover_background"]
        self.project.cover_duration = values["cover_duration"]
        self.project.save()
        super().accept()


class ColorButton(QPushButton):
    changed = Signal()

    def __init__(self, color):
        super().__init__()
        self.setFixedSize(96, 26)
        self.color = [0, 0, 0, 255]
        self.set_color(color)

    def set_color(self, color) -> None:
        values = list(color) + [255]
        self.color = [int(c) for c in values[:4]]
        r, g, b, _a = self.color
        text = "#0b0d12" if (r * 0.299 + g * 0.587 + b * 0.114) > 150 else "#ffffff"
        self.setText(f"#{r:02X}{g:02X}{b:02X}")
        self.setStyleSheet(
            f"background: rgb({r},{g},{b}); color:{text}; border:1px solid #343a49;"
            "border-radius:6px; font-size:10px; font-weight:700;"
        )

    def pick(self) -> None:
        color = QColorDialog.getColor(QColor(*self.color[:3]), self, "Colore")
        if color.isValid():
            self.set_color(color.getRgb())
            self.changed.emit()

    def value(self) -> list[int]:
        return list(self.color)


class GraphicsDialog(QDialog):
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.preset = load_preset(project.graphics_preset or None)
        self.setWindowTitle("Grafica e caratteri")
        self.setStyleSheet(APP_STYLE)
        self.resize(980, 680)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)

        font_row = QHBoxLayout()
        font_row.addWidget(self._label("Font"))
        self.font_combo = QComboBox()
        self.font_combo.setMinimumWidth(420)
        self._populate_fonts()
        font_row.addWidget(self.font_combo, 1)
        browse = QPushButton("Sfoglia")
        browse.setObjectName("ghost")
        browse.clicked.connect(self._browse_font)
        font_row.addWidget(browse)
        lay.addLayout(font_row)

        body = QHBoxLayout()
        body.setSpacing(16)
        self.tabs = QTabWidget()
        body.addWidget(self.tabs, 1)
        self.preview = QLabel("Anteprima")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedSize(240, 426)
        self.preview.setStyleSheet(
            "background:#0b0d12; border:1px solid #2a303c; border-radius:10px; color:#596273;"
        )
        body.addWidget(self.preview, 0, Qt.AlignTop)
        lay.addLayout(body, 1)

        self._build_number_tab()
        self._build_title_tab()
        self._build_cover_tab()
        self._load_controls(self.preset)

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(150)
        self.preview_timer.timeout.connect(self.refresh_preview)
        for widget in self._preview_widgets:
            if isinstance(widget, ColorButton):
                widget.changed.connect(self.schedule_preview)
            elif isinstance(widget, QLineEdit):
                widget.textChanged.connect(self.schedule_preview)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self.schedule_preview)
        self.font_combo.currentIndexChanged.connect(self.schedule_preview)

        row = QHBoxLayout()
        reset = QPushButton("Ripristina preset")
        reset.setObjectName("ghost")
        reset.clicked.connect(self.reset_preset)
        row.addWidget(reset)
        row.addStretch(1)
        cancel = QPushButton("Annulla")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Salva")
        save.setObjectName("primary")
        save.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)
        self.refresh_preview()

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted")
        label.setStyleSheet("color:#b8c2d0; font-size:12px;")
        return label

    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    @staticmethod
    def _spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    @staticmethod
    def _dspin(minimum: float, maximum: float, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(0.05)
        spin.setValue(value)
        return spin

    def _populate_fonts(self) -> None:
        self.font_combo.clear()
        current = self.preset.get("font") or "assets/fonts/Montserrat-Variable.ttf"
        font_dir = ROOT / "assets" / "fonts"
        choices: list[tuple[str, Path]] = [
            (f"{p.stem} (assets)", p)
            for p in sorted(font_dir.glob("*"))
            if p.suffix.lower() in (".ttf", ".otf")
        ]
        windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for label, filename in (
            ("Arial Bold", "arialbd.ttf"),
            ("Impact", "impact.ttf"),
            ("Segoe UI Bold", "segoeuib.ttf"),
            ("Verdana Bold", "verdanab.ttf"),
            ("Tahoma Bold", "tahomabd.ttf"),
            ("Trebuchet MS Bold", "trebucbd.ttf"),
        ):
            path = windows_fonts / filename
            if path.exists():
                choices.append((label, path))
        current_path = Path(current)
        if not current_path.is_absolute():
            current_path = ROOT / current_path
        if current_path.exists() and all(p != current_path for _, p in choices):
            choices.append((current_path.stem, current_path))
        selected = 0
        for i, (label, path) in enumerate(choices):
            self.font_combo.addItem(label, self._rel(path))
            if path == current_path:
                selected = i
        if self.font_combo.count():
            self.font_combo.setCurrentIndex(selected)

    def _browse_font(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Font", str(ROOT / "assets" / "fonts"), "Font (*.ttf *.otf)"
        )
        if not path:
            return
        data = self._rel(Path(path))
        for i in range(self.font_combo.count()):
            if self.font_combo.itemData(i) == data:
                self.font_combo.setCurrentIndex(i)
                return
        self.font_combo.addItem(Path(path).name, data)
        self.font_combo.setCurrentIndex(self.font_combo.count() - 1)

    def _build_number_tab(self) -> None:
        tab = QWidget()
        tab.setObjectName("tabPage")
        grid = QGridLayout(tab)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(9)
        cfg = self.preset["number"]
        self.n_size = self._spin(20, 300, int(cfg["font_size"]))
        self.n_x = self._spin(0, 1080, int(cfg["x"]))
        self.n_y = self._spin(0, 1920, int(cfg["y"]))
        self.n_stroke = self._spin(0, 40, int(cfg["stroke"]))
        self.n_color = ColorButton(cfg["color"])
        self.n_outline = ColorButton(cfg["outline"])
        rows = [
            ("Dimensione", self.n_size), ("X", self.n_x), ("Y", self.n_y),
            ("Contorno", self.n_stroke), ("Colore", self.n_color),
            ("Colore contorno", self.n_outline),
        ]
        for i, (text, widget) in enumerate(rows):
            grid.addWidget(self._label(text), i, 0)
            grid.addWidget(widget, i, 1)
        grid.setRowStretch(len(rows), 1)
        self._preview_widgets = [self.n_size, self.n_x, self.n_y, self.n_stroke,
                                 self.n_color, self.n_outline]
        self.tabs.addTab(tab, "Numero")

    def _build_title_tab(self) -> None:
        tab = QWidget()
        tab.setObjectName("tabPage")
        grid = QGridLayout(tab)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(9)
        cfg = self.preset["title"]
        self.t_size = self._spin(20, 300, int(cfg["font_size"]))
        self.t_y = self._spin(0, 1920, int(cfg["y"]))
        self.t_stroke = self._spin(0, 40, int(cfg["stroke"]))
        self.t_color = ColorButton(cfg["color"])
        self.t_outline = ColorButton(cfg["outline"])
        rows = [
            ("Dimensione", self.t_size), ("Y", self.t_y),
            ("Contorno", self.t_stroke), ("Colore", self.t_color),
            ("Colore contorno", self.t_outline),
        ]
        for i, (text, widget) in enumerate(rows):
            grid.addWidget(self._label(text), i, 0)
            grid.addWidget(widget, i, 1)
        grid.setRowStretch(len(rows), 1)
        self._preview_widgets += [self.t_size, self.t_y, self.t_stroke,
                                  self.t_color, self.t_outline]
        self.tabs.addTab(tab, "Titolo")

    def _build_cover_tab(self) -> None:
        tab = QWidget()
        tab.setObjectName("tabPage")
        grid = QGridLayout(tab)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        cfg = self.preset["cover"]
        self.c_size = self._spin(20, 300, int(cfg["font_size"]))
        self.c_center = self._spin(0, 1920, int(cfg["center_y"]))
        self.c_width = self._spin(200, 1080, int(cfg["max_width"]))
        self.c_gap = self._spin(0, 80, int(cfg["line_gap"]))
        self.c_stroke = self._spin(0, 40, int(cfg["stroke"]))
        self.c_fade = self._dspin(0.0, 2.0, float(cfg.get("fade_in", 0.35)))
        self.c_slide = self._spin(0, 100, int(cfg.get("slide_px", 28)))
        self.c_color = ColorButton(cfg["color"])
        self.c_highlight = ColorButton(cfg["highlight_color"])
        self.c_outline = ColorButton(cfg["outline"])
        self.c_phrases = QLineEdit(", ".join(cfg.get("highlight_phrases", [])))
        rows = [
            ("Dimensione", self.c_size), ("Centro Y", self.c_center),
            ("Larghezza max", self.c_width), ("Spazio righe", self.c_gap),
            ("Contorno", self.c_stroke), ("Fade (s)", self.c_fade),
            ("Slide (px)", self.c_slide), ("Colore testo", self.c_color),
            ("Colore evidenza", self.c_highlight),
            ("Colore contorno", self.c_outline),
            ("Frasi evidenziate", self.c_phrases),
        ]
        for i, (text, widget) in enumerate(rows):
            grid.addWidget(self._label(text), i, 0)
            grid.addWidget(widget, i, 1)
        grid.setRowStretch(len(rows), 1)
        self._preview_widgets += [self.c_size, self.c_center, self.c_width,
                                  self.c_gap, self.c_stroke, self.c_fade,
                                  self.c_slide, self.c_color, self.c_highlight,
                                  self.c_outline, self.c_phrases]
        self.tabs.addTab(tab, "Copertina")

    def _load_controls(self, preset: dict) -> None:
        self.n_size.setValue(int(preset["number"]["font_size"]))
        self.n_x.setValue(int(preset["number"]["x"]))
        self.n_y.setValue(int(preset["number"]["y"]))
        self.n_stroke.setValue(int(preset["number"]["stroke"]))
        self.n_color.set_color(preset["number"]["color"])
        self.n_outline.set_color(preset["number"]["outline"])
        self.t_size.setValue(int(preset["title"]["font_size"]))
        self.t_y.setValue(int(preset["title"]["y"]))
        self.t_stroke.setValue(int(preset["title"]["stroke"]))
        self.t_color.set_color(preset["title"]["color"])
        self.t_outline.set_color(preset["title"]["outline"])
        cover = preset["cover"]
        self.c_size.setValue(int(cover["font_size"]))
        self.c_center.setValue(int(cover["center_y"]))
        self.c_width.setValue(int(cover["max_width"]))
        self.c_gap.setValue(int(cover["line_gap"]))
        self.c_stroke.setValue(int(cover["stroke"]))
        self.c_fade.setValue(float(cover.get("fade_in", 0.35)))
        self.c_slide.setValue(int(cover.get("slide_px", 28)))
        self.c_color.set_color(cover["color"])
        self.c_highlight.set_color(cover["highlight_color"])
        self.c_outline.set_color(cover["outline"])
        self.c_phrases.setText(", ".join(cover.get("highlight_phrases", [])))

    def _values(self) -> dict:
        preset = json.loads(json.dumps(self.preset))
        preset["name"] = "custom_project"
        preset["font"] = self.font_combo.currentData() or preset.get("font")
        preset["number"].update({
            "font_size": self.n_size.value(), "x": self.n_x.value(),
            "y": self.n_y.value(), "stroke": self.n_stroke.value(),
            "color": self.n_color.value(), "outline": self.n_outline.value(),
        })
        preset["title"].update({
            "font_size": self.t_size.value(), "y": self.t_y.value(),
            "stroke": self.t_stroke.value(), "color": self.t_color.value(),
            "outline": self.t_outline.value(),
        })
        phrases = [
            part.strip() for part in self.c_phrases.text().split(",")
            if part.strip()
        ]
        preset["cover"].update({
            "font_size": self.c_size.value(), "center_y": self.c_center.value(),
            "max_width": self.c_width.value(), "line_gap": self.c_gap.value(),
            "stroke": self.c_stroke.value(), "fade_in": self.c_fade.value(),
            "slide_px": self.c_slide.value(), "color": self.c_color.value(),
            "highlight_color": self.c_highlight.value(),
            "outline": self.c_outline.value(), "highlight_phrases": phrases,
        })
        return preset

    def _preview_background(self) -> Path | None:
        clip = self.project.cover_mp4()
        if not clip:
            for game in self.project.games:
                for slot in range(len(game.clips)):
                    clip = self.project.clip_mp4(game, slot)
                    if clip:
                        break
                if clip:
                    break
        if clip:
            verify = clip.parent / "verify_vertical.png"
            if verify.exists():
                return verify
        return None

    def refresh_preview(self, *_args) -> None:
        try:
            image = render_cover_still(
                self.project.challenge_title or "GUESS THE GAME",
                self._preview_background(),
                self._values(),
            )
            self.preview.setPixmap(_pil_pixmap(image, QSize(230, 409)))
        except Exception:
            self.preview.setText("Anteprima non disponibile")

    def schedule_preview(self, *_args) -> None:
        self.preview_timer.start()

    def reset_preset(self) -> None:
        self.preset = load_preset(None)
        self._populate_fonts()
        self._load_controls(self.preset)
        self.schedule_preview()

    def accept(self) -> None:
        preset = self._values()
        path = self.project.path / "graphics.json"
        path.write_text(json.dumps(preset, indent=2), encoding="utf-8")
        self.project.graphics_preset = self._rel(path)
        self.project.save()
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gaming Content Factory")
        self.resize(1040, 760)
        self.setMinimumSize(900, 640)
        self.setStyleSheet(APP_STYLE)

        self.project: Project | None = None
        self.session: GuiCaptureSession | None = None
        self.prepared = None
        self._preparing = False
        self.cover_recording = False
        self.short_worker: ShortWorker | None = None
        self.short_preview_worker: ShortPreviewWorker | None = None
        self.round_worker: RoundWorker | None = None
        self.warm_worker: WarmObsWorker | None = None
        self.watch_timer = QTimer(self)
        self.watch_timer.setInterval(1000)
        self.watch_timer.timeout.connect(self.check_active_window)

        self.overlay = CropOverlay()
        self.panel = CaptureControlPanel()
        self.panel.record.connect(self.start_recording)
        self.panel.stop_requested.connect(self.stop_recording)
        self.panel.retry_requested.connect(self.retry_capture)
        self.panel.next_game.connect(self.next_step)
        self.panel.previous_game.connect(self.previous_step)
        self.panel.toggle_lock.connect(self.toggle_lock)
        self.panel.close_requested.connect(self.close_capture)
        self.panel.open_clip.connect(self.open_clip)

        self.pages = QStackedWidget()
        self.pages.setObjectName("page")
        self.setCentralWidget(self.pages)

        self.home = self._build_home()
        self.new_page = self._build_new()
        self.record_page = self._build_record()
        self.ascii_page = AsciiVideoPage(self.go_home)
        self.pages.addWidget(self.home)
        self.pages.addWidget(self.new_page)
        self.pages.addWidget(self.record_page)
        self.pages.addWidget(self.ascii_page)
        self.pages.setCurrentWidget(self.home)
        self.refresh_recent()

    # ---------- pages ----------

    def _build_home(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(56, 46, 56, 40)
        lay.setSpacing(16)

        kicker = QLabel("GUESS THE GAME IN ASCII")
        kicker.setObjectName("kicker")
        title = QLabel("Sei giochi. Tre indizi ASCII. Un reveal.")
        title.setObjectName("h1")
        sub = QLabel(
            "Il percorso principale: registra le clip, converti i primi tre indizi, "
            "approva e monta lo Short verticale."
        )
        sub.setObjectName("muted")
        lay.addWidget(kicker)
        lay.addWidget(title)
        lay.addWidget(sub)

        new_btn = QPushButton("Nuovo Short ASCII")
        new_btn.setObjectName("primary")
        new_btn.setFixedWidth(220)
        new_btn.clicked.connect(lambda: self.pages.setCurrentWidget(self.new_page))
        lay.addSpacing(10)
        home_row = QHBoxLayout()
        home_row.addWidget(new_btn)
        ascii_btn = QPushButton("Strumento ASCII")
        ascii_btn.setObjectName("ghost")
        ascii_btn.setFixedWidth(220)
        ascii_btn.clicked.connect(self.open_ascii_page)
        home_row.addWidget(ascii_btn)
        self.home_generate = QPushButton("Genera Short")
        self.home_generate.setObjectName("ghost")
        self.home_generate.setFixedWidth(180)
        self.home_generate.setEnabled(False)
        self.home_generate.clicked.connect(self.generate_from_home)
        home_row.addWidget(self.home_generate)
        home_row.addStretch(1)
        lay.addLayout(home_row)

        lay.addSpacing(24)
        recent_title = QLabel("Progetti recenti")
        recent_title.setObjectName("h2")
        lay.addWidget(recent_title)
        self.recent = QListWidget()
        self.recent.itemDoubleClicked.connect(self.open_recent)
        self.recent.itemSelectionChanged.connect(self.update_home_generate)
        lay.addWidget(self.recent, 1)
        hint = QLabel("Doppio clic per riaprire un progetto.")
        hint.setObjectName("muted")
        lay.addWidget(hint)
        return page

    def _build_new(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(56, 42, 56, 40)
        lay.setSpacing(14)
        kicker = QLabel("NUOVO SHORT ASCII")
        kicker.setObjectName("kicker")
        title = QLabel("Inserisci i sei videogiochi")
        title.setObjectName("h1")
        sub = QLabel(
            "Ogni gioco avrà tre indizi ASCII e un reveal originale. "
            "Potrai registrare o importare le clip una alla volta."
        )
        sub.setObjectName("muted")
        lay.addWidget(kicker)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(4)

        content = QHBoxLayout()
        content.setSpacing(16)
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)
        self.title_inputs: list[QLineEdit] = []
        for i in range(6):
            label = QLabel(f"Gioco {i + 1}")
            label.setObjectName("muted")
            edit = QLineEdit()
            edit.setPlaceholderText("Titolo del videogioco")
            self.title_inputs.append(edit)
            grid.addWidget(label, i, 0)
            grid.addWidget(edit, i, 1)
        cl.addLayout(grid)
        content.addWidget(card, 1)

        cover_card = QFrame()
        cover_card.setObjectName("card")
        cover_lay = QVBoxLayout(cover_card)
        cover_lay.setContentsMargins(18, 16, 18, 16)
        cover_title = QLabel("Copertina")
        cover_title.setObjectName("h2")
        cover_lay.addWidget(cover_title)
        self.cover_editor = CoverEditor(project=None, compact=True)
        cover_lay.addWidget(self.cover_editor)
        cover_hint = QLabel(
            "Dopo la creazione potrai registrare la clip di sfondo dal monitor "
            "e cambiare font, colori e dimensioni con il pulsante “Grafica”."
        )
        cover_hint.setObjectName("muted")
        cover_hint.setWordWrap(True)
        cover_lay.addWidget(cover_hint)
        cover_lay.addStretch(1)
        content.addWidget(cover_card, 1)
        lay.addLayout(content, 1)

        row = QHBoxLayout()
        back = QPushButton("Annulla")
        back.setObjectName("ghost")
        back.clicked.connect(lambda: self.pages.setCurrentWidget(self.home))
        create = QPushButton("Crea progetto")
        create.setObjectName("primary")
        create.clicked.connect(self.create_project)
        row.addWidget(back)
        row.addStretch(1)
        row.addWidget(create)
        lay.addLayout(row)
        lay.addStretch(1)
        return page

    def _build_record(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(40, 28, 40, 26)
        lay.setSpacing(10)

        top = QHBoxLayout()
        home = QPushButton("Home")
        home.setObjectName("ghost")
        home.clicked.connect(self.go_home)
        self.step_label = QLabel("Gioco 1 di 6 — Clip 1 di 4")
        self.step_label.setObjectName("kicker")
        top.addWidget(home)
        top.addSpacing(14)
        top.addWidget(self.step_label)
        top.addStretch(1)
        self.graphics_btn = QPushButton("Grafica")
        self.graphics_btn.setObjectName("ghost")
        self.graphics_btn.clicked.connect(self.edit_graphics)
        top.addWidget(self.graphics_btn)
        self.ascii_btn = QPushButton("Indizio ASCII")
        self.ascii_btn.setObjectName("ghost")
        self.ascii_btn.clicked.connect(self.edit_ascii_clue)
        top.addWidget(self.ascii_btn)
        self.cover_btn = QPushButton("Copertina")
        self.cover_btn.setObjectName("ghost")
        self.cover_btn.clicked.connect(self.edit_cover)
        top.addWidget(self.cover_btn)
        self.cover_record_btn = QPushButton("Registra sfondo")
        self.cover_record_btn.setObjectName("ghost")
        self.cover_record_btn.clicked.connect(self.record_cover)
        top.addWidget(self.cover_record_btn)
        lay.addLayout(top)

        title_row = QHBoxLayout()
        self.game_title = QLabel("Titolo")
        self.game_title.setObjectName("h1")
        self.slot_title = QLabel(CLIP_LABELS[0])
        self.slot_title.setObjectName("h2")
        title_row.addWidget(self.game_title)
        title_row.addSpacing(14)
        title_row.addWidget(self.slot_title)
        title_row.addStretch(1)
        lay.addLayout(title_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 24)
        self.progress.setTextVisible(False)
        lay.addWidget(self.progress)

        content = QHBoxLayout()
        content.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(10)
        slot_row = QHBoxLayout()
        slot_row.setSpacing(8)
        self.slot_group = QButtonGroup(self)
        self.slot_group.setExclusive(True)
        self.slot_buttons: list[QToolButton] = []
        for i, label in enumerate(CLIP_LABELS):
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setIconSize(QSize(72, 128))
            btn.setFixedSize(132, 190)
            btn.setText(f"{label}\nDa registrare")
            btn.clicked.connect(lambda _checked=False, i=i: self.select_slot(i))
            self.slot_group.addButton(btn, i)
            self.slot_buttons.append(btn)
            slot_row.addWidget(btn)
        slot_row.addStretch(1)
        left.addLayout(slot_row)

        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 14, 18, 14)
        cl.setSpacing(8)
        source_title = QLabel("Sorgente della clip")
        source_title.setObjectName("h2")
        cl.addWidget(source_title)
        mode_row = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Monitor (predefinito)", "Finestra", "Game Capture"])
        self.mode_combo.setMinimumWidth(220)
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch(1)
        cl.addLayout(mode_row)
        row = QHBoxLayout()
        self.target_combo = QComboBox()
        self.target_combo.setMinimumWidth(360)
        self.refresh_btn = QPushButton("Aggiorna sorgenti")
        self.refresh_btn.setObjectName("ghost")
        self.refresh_btn.clicked.connect(self.refresh_sources)
        row.addWidget(self.target_combo, 1)
        row.addWidget(self.refresh_btn)
        cl.addLayout(row)
        self.capture_btn = QPushButton("Prendi video")
        self.capture_btn.setObjectName("primary")
        self.capture_btn.setFixedWidth(220)
        self.capture_btn.setMinimumHeight(42)
        self.capture_btn.clicked.connect(lambda: self.prepare_capture(False))
        cl.addWidget(self.capture_btn)
        self.start_hint = QLabel("Scegli un monitor, avvia il gioco, poi premi Aggiorna sorgenti.")
        self.start_hint.setObjectName("muted")
        cl.addWidget(self.start_hint)
        self.borderless_hint = QLabel(
            "La cattura è indipendente dalla finestra attiva. Ogni clip può avere cornice e sorgente proprie."
        )
        self.borderless_hint.setObjectName("muted")
        self.borderless_hint.setWordWrap(True)
        cl.addWidget(self.borderless_hint)
        left.addWidget(card)
        left.addStretch(1)

        right = QVBoxLayout()
        right.setSpacing(8)
        self.preview = QLabel("Nessuna clip registrata")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedSize(200, 356)
        self.preview.setStyleSheet("background:#0b0d12; border:1px solid #2a303c; border-radius:12px; color:#596273;")
        right.addWidget(self.preview, 0, Qt.AlignHCenter)
        self.take_info = QLabel("")
        self.take_info.setObjectName("muted")
        self.take_info.setWordWrap(True)
        right.addWidget(self.take_info)
        self.open_btn = QPushButton("Apri clip")
        self.open_btn.setObjectName("ghost")
        self.open_btn.clicked.connect(self.open_clip)
        right.addWidget(self.open_btn)
        right.addStretch(1)
        content.addLayout(left, 1)
        content.addLayout(right, 0)
        lay.addLayout(content, 1)

        nav = QHBoxLayout()
        self.prev_btn = QPushButton("Clip precedente")
        self.prev_btn.setObjectName("ghost")
        self.prev_btn.clicked.connect(self.previous_step)
        self.round_btn = QPushButton("Anteprima round")
        self.round_btn.setObjectName("ghost")
        self.round_btn.setEnabled(False)
        self.round_btn.clicked.connect(self.preview_round)
        self.rounds3_btn = QPushButton("Montaggio 3 round")
        self.rounds3_btn.setObjectName("ghost")
        self.rounds3_btn.setEnabled(False)
        self.rounds3_btn.clicked.connect(self.build_three_rounds)
        self.generate_btn = QPushButton("Genera Short")
        self.generate_btn.setObjectName("primary")
        self.generate_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self.generate_short)
        self.next_btn = QPushButton("Clip successiva")
        self.next_btn.setObjectName("primary")
        self.next_btn.clicked.connect(self.next_step)
        nav.addWidget(self.prev_btn)
        nav.addStretch(1)
        nav.addWidget(self.round_btn)
        nav.addSpacing(8)
        nav.addWidget(self.rounds3_btn)
        nav.addSpacing(8)
        nav.addWidget(self.generate_btn)
        nav.addSpacing(10)
        nav.addWidget(self.next_btn)
        lay.addLayout(nav)
        return page

    # ---------- project ----------

    def refresh_recent(self) -> None:
        self.recent.clear()
        for p in recent_projects():
            count = p.completed_clips()
            ascii_done = sum(
                1 for g in p.games for slot in range(3)
                if p.ascii_state(g, slot) == "approved"
            )
            label = p.challenge_title.strip() or p.title
            item = QListWidgetItem(
                f"{label}  ·  {count}/24 clip  ·  {ascii_done}/18 ASCII  ·  {p.id}"
            )
            item.setData(Qt.UserRole, str(p.path))
            self.recent.addItem(item)
        if self.recent.count() and not self.recent.currentItem():
            self.recent.setCurrentRow(0)
        self.update_home_generate()

    def update_home_generate(self) -> None:
        item = self.recent.currentItem()
        enabled = False
        if item:
            try:
                p = Project.load(Path(item.data(Qt.UserRole)))
                enabled = p.ascii_ready()
            except Exception:
                enabled = False
        self.home_generate.setEnabled(enabled)

    def generate_from_home(self) -> None:
        item = self.recent.currentItem()
        if not item:
            QMessageBox.information(self, "Genera Short", "Seleziona un progetto recente.")
            return
        try:
            p = Project.load(Path(item.data(Qt.UserRole)))
        except Exception as exc:
            QMessageBox.critical(self, "Errore", str(exc))
            return
        if not p.ascii_ready():
            QMessageBox.warning(
                self, "Indizi ASCII mancanti",
                "Servono tre indizi ASCII approvati e un reveal originale per ogni gioco."
            )
            return
        self.open_project(p)
        self.generate_short()

    def open_recent(self, item: QListWidgetItem) -> None:
        path = Path(item.data(Qt.UserRole))
        try:
            project = Project.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Errore", f"Impossibile aprire il progetto:\n{exc}")
            return
        self.open_project(project)

    def create_project(self) -> None:
        titles = [e.text().strip() for e in self.title_inputs]
        if any(not t for t in titles):
            QMessageBox.warning(self, "Titoli mancanti", "Inserisci tutti e sei i titoli.")
            return
        cover = self.cover_editor.values()
        try:
            project = Project.create(
                titles,
                challenge_title=cover["challenge_title"],
                challenge_category=cover["challenge_category"],
                cover_background=cover["cover_background"],
                cover_duration=cover["cover_duration"],
            )
        except Exception as exc:
            QMessageBox.critical(self, "Errore", str(exc))
            return
        for e in self.title_inputs:
            e.clear()
        self.refresh_recent()
        self.open_project(project)

    def open_project(self, project: Project) -> None:
        self.close_capture()
        self.project = project
        self.pages.setCurrentWidget(self.record_page)
        self.load_game()
        self.warm_obs()

    def warm_obs(self) -> None:
        if self.warm_worker and self.warm_worker.isRunning():
            return
        self.warm_worker = WarmObsWorker(self)
        self.warm_worker.start()

    def go_home(self) -> None:
        self.close_capture()
        self.refresh_recent()
        self.pages.setCurrentWidget(self.home)

    def open_ascii_page(self) -> None:
        self.ascii_page.refresh_projects()
        self.pages.setCurrentWidget(self.ascii_page)

    def load_game(self) -> None:
        if not self.project:
            return
        game = self.project.current_game
        idx = self.project.current_index
        slot = self.project.current_clip
        clip = game.clips[slot]
        source = self._clip_source(game, slot)
        self.step_label.setText(
            f"Gioco {idx + 1} di {len(self.project.games)} — Clip {slot + 1} di {CLIP_COUNT}"
        )
        self.game_title.setText(game.title)
        self.slot_title.setText(CLIP_LABELS[slot])
        self.progress.setValue(self.project.completed_clips())
        self.start_hint.setText(
            "Clip già registrata. Puoi riprovarla o passare alla successiva."
            if clip.take_id else
            "Scegli un monitor, avvia il gioco, poi premi Aggiorna sorgenti."
        )
        self.panel.set_game(
            f"Gioco {idx + 1} di {len(self.project.games)} · Clip {slot + 1} di {CLIP_COUNT} — {game.title}"
        )
        self.panel.set_recording(False)
        self.panel.set_warning("")
        self._apply_source(source)
        mp4 = self.project.clip_mp4(game, slot)
        self.take_info.setText(self._take_info(game, slot))
        self.preview.setText("Nessuna clip registrata")
        self.preview.setPixmap(QPixmap())
        if mp4:
            verify = mp4.parent / "verify_vertical.png"
            if verify.exists():
                self._show_preview(verify)
        self.open_btn.setEnabled(bool(mp4))
        self.ascii_btn.setEnabled(slot < 3 and bool(mp4))
        self.ascii_btn.setText(
            "Indizio ASCII" if slot < 3 else "Reveal originale"
        )
        self.generate_btn.setEnabled(self.project.ascii_ready())
        self.round_btn.setEnabled(self.project.ascii_ready_for_game(game))
        self.rounds3_btn.setEnabled(
            len(self.project.games) >= 3
            and all(self.project.ascii_ready_for_game(g) for g in self.project.games[:3])
        )
        self.prev_btn.setEnabled(idx > 0 or slot > 0)
        self._update_next_controls()
        self.update_slot_cards()

    def _apply_source(self, source) -> None:
        capture = source.capture or "screen"
        mode = {"screen": 0, "window": 1, "game": 2}.get(capture, 0)
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(mode)
        self.mode_combo.blockSignals(False)
        self.target_combo.clear()
        if capture == "screen" and source.monitor_name:
            self.target_combo.addItem(
                source.monitor_name,
                {"name": source.monitor_name, "ffmpeg": bool(source.monitor_ffmpeg)},
            )
        elif source.window:
            self.target_combo.addItem(source.window, source.window)

    def _clip_source(self, game, index: int):
        clip = game.clips[index]
        if clip.monitor_name or clip.window:
            return clip
        for previous in reversed(game.clips[:index]):
            if previous.monitor_name or previous.window:
                return previous
        return clip

    def _next_label(self) -> str:
        game = self.project.current_game
        if self.project.game_complete(game):
            if self.project.current_index + 1 >= len(self.project.games):
                return "Completa"
            return "Gioco successivo"
        return "Clip successiva"

    def _update_next_controls(self) -> None:
        if not self.project:
            return
        enabled = bool(
            self.project.clip_mp4(self.project.current_game, self.project.current_clip)
        )
        label = self._next_label()
        self.next_btn.setText(label)
        self.next_btn.setEnabled(enabled)
        self.panel.set_next_label(label)
        self.panel.set_has_take(enabled)

    def update_slot_cards(self) -> None:
        if not self.project:
            return
        game = self.project.current_game
        labels = {
            "missing": "Da registrare",
            "recorded": "Da convertire",
            "dirty": "Da rigenerare",
            "converted": "Da approvare",
            "approved": "Approvata",
            "original": "Pronta",
        }
        for i, button in enumerate(self.slot_buttons):
            clip = game.clips[i]
            mp4 = self.project.clip_mp4(game, i)
            state = self.project.ascii_state(game, i) if i < 3 else ("original" if mp4 else "missing")
            button.setText(f"{CLIP_LABELS[i]}\n{labels.get(state, state)}")
            button.setToolTip(
                f"{clip.take_id or 'Nessuna clip'}\nASCII: {state}"
            )
            icon = None
            data = clip.ascii or {}
            for candidate in (data.get("compare"), data.get("preview")):
                if candidate and Path(candidate).exists() and str(candidate).lower().endswith(".png"):
                    icon = candidate
                    break
            if mp4 and not icon:
                for name in ("verify_vertical.png", "preview_vertical.png"):
                    candidate = mp4.parent / name
                    if candidate.exists():
                        icon = candidate
                        break
            button.setIcon(QIcon(str(icon)) if icon else QIcon())
            button.setChecked(i == self.project.current_clip)

    def select_slot(self, index: int) -> None:
        if not self.project:
            return
        if index == self.project.current_clip:
            self.update_slot_cards()
            return
        self.close_capture()
        self.project.set_clip_index(index)
        self.load_game()

    def edit_ascii_clue(self) -> None:
        if not self.project:
            return
        self.close_capture()
        game = self.project.current_game
        slot = self.project.current_clip
        if slot >= 3:
            QMessageBox.information(
                self, "Reveal originale",
                "Il quarto slot resta la registrazione originale e non viene convertito.",
            )
            return
        if not self.project.clip_mp4(game, slot):
            QMessageBox.warning(
                self, "Indizio ASCII",
                f"Registra o importa prima {CLIP_LABELS[slot]} di {game.title}.",
            )
            return
        dialog = AsciiClueDialog(self.project, game, slot, self)
        dialog.exec()
        self.load_game()

    def edit_cover(self) -> None:
        if not self.project:
            return
        self.close_capture()
        dialog = CoverDialog(self.project, self)
        if dialog.exec() == QDialog.Accepted:
            self.start_hint.setText("Copertina aggiornata.")
            self.refresh_recent()

    def edit_graphics(self) -> None:
        if not self.project:
            return
        self.close_capture()
        dialog = GraphicsDialog(self.project, self)
        if dialog.exec() == QDialog.Accepted:
            self.start_hint.setText(
                "Grafica aggiornata. Rigenera copertina o round per applicarla."
            )

    def record_cover(self) -> None:
        if not self.project:
            return
        self.close_capture()
        if self.project.cover_clip.monitor_name or self.project.cover_clip.window:
            self._apply_source(self.project.cover_clip)
        self.start_hint.setText("Preparo la clip di sfondo dal monitor...")
        self.prepare_capture(cover=True)

    def _take_info(self, game, slot: int) -> str:
        clip = game.clips[slot]
        if not clip.take_id:
            return (
                f"{CLIP_LABELS[slot]}: nessuna clip.\n"
                "Registra il gameplay con la cornice 9:16.\n"
                "La registrazione full-frame resta nel progetto."
            )
        mp4 = self.project.clip_mp4(game, slot)
        if not mp4:
            return f"{CLIP_LABELS[slot]}: clip mancante."
        ascii_state = self.project.ascii_state(game, slot) if slot < 3 else "originale"
        data = clip.ascii or {}
        ascii_line = f"\nASCII: {ascii_state}"
        if data.get("output"):
            ascii_line += f"\n{data['output']}"
        return (
            f"{CLIP_LABELS[slot]}\n"
            f"Take: {clip.take_id}\n"
            f"Stato: {clip.status}\n"
            f"Crop: {clip.crop}"
            f"{ascii_line}"
        )

    def _overlay_frame(self, crop: dict, client: QRect, source_w: int, source_h: int) -> QRect:
        return GuiCaptureSession.frame_from_crop(crop, client, source_w, source_h)

    def _show_preview(self, path: Path) -> None:
        pix = QPixmap(str(path))
        if pix.isNull():
            return
        self.preview.setPixmap(pix.scaled(200, 356, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.preview.setVisible(True)

    # ---------- windows ----------

    def on_mode_changed(self, *_args) -> None:
        self.target_combo.clear()
        self.start_hint.setText("Premi Aggiorna sorgenti per elencare monitor o finestre.")
        self.panel.set_warning("")

    def refresh_sources(self) -> None:
        if not self.project:
            return
        mode = self.mode_combo.currentIndex()
        kind = "monitor_capture" if mode == 0 else "window_capture" if mode == 1 else "game_capture"
        self.refresh_btn.setEnabled(False)
        self.start_hint.setText("Avvio OBS e ricerca delle sorgenti...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            obs = Obs()
            items = obs.list_windows(kind)
            obs.close()
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self.refresh_btn.setEnabled(True)
            self.start_hint.setText("Impossibile ottenere le sorgenti.")
            QMessageBox.critical(self, "OBS", str(exc))
            return
        QApplication.restoreOverrideCursor()
        self.refresh_btn.setEnabled(True)
        self.target_combo.clear()
        game = self.project.current_game
        source = self._clip_source(game, self.project.current_clip)
        preferred = source.monitor_name if mode == 0 else source.window
        selected = -1
        seen_monitor_values: set[str] = set()
        for item in items:
            if not item.get("itemEnabled"):
                continue
            name = item["itemName"]
            if not name.strip() or "Seleziona" in name:
                continue
            if mode == 0:
                value = item.get("itemValue", "")
                fallback = value in seen_monitor_values
                seen_monitor_values.add(value)
                label = f"Schermo {self.target_combo.count() + 1} · {name}"
                if fallback:
                    label += " · fallback FFmpeg"
                data = {"name": name, "ffmpeg": fallback}
            else:
                label = name
                data = name
            self.target_combo.addItem(label, data)
            if preferred and preferred == name:
                selected = self.target_combo.count() - 1
            elif selected < 0 and mode != 0 and game.title.lower() in name.lower():
                selected = self.target_combo.count() - 1
        if mode == 0 and selected < 0 and self.target_combo.count():
            for i in range(self.target_combo.count()):
                if "principale" in self.target_combo.itemText(i).lower() or "primary" in self.target_combo.itemText(i).lower():
                    selected = i
                    break
            if selected < 0:
                selected = 0
        if selected >= 0:
            self.target_combo.setCurrentIndex(selected)
        self.start_hint.setText(
            "Seleziona il monitor: la cattura registra ciò che appare lì, indipendentemente dalla finestra attiva."
            if mode == 0 and self.target_combo.count() else
            "Seleziona la finestra di gioco." if self.target_combo.count() else
            "Nessuna sorgente trovata. Avvia il gioco/app e premi Aggiorna sorgenti."
        )

    def prepare_capture(self, cover: bool = False) -> None:
        if not self.project or self._preparing:
            return
        mode = self.mode_combo.currentIndex()
        data = self.target_combo.currentData()
        use_ffmpeg = False
        if isinstance(data, dict):
            target = data.get("name", "")
            use_ffmpeg = bool(data.get("ffmpeg"))
        elif data:
            target = str(data)
        else:
            target = self.target_combo.currentText().strip()
        if not target:
            self.refresh_sources()
            data = self.target_combo.currentData()
            if isinstance(data, dict):
                target = data.get("name", "")
                use_ffmpeg = bool(data.get("ffmpeg"))
            else:
                target = self.target_combo.currentText().strip()
        if not target:
            QMessageBox.warning(self, "Sorgente mancante", "Seleziona un monitor o una finestra.")
            return
        capture = "screen" if mode == 0 else "window" if mode == 1 else "game"
        monitor_index = self.target_combo.currentIndex() if capture == "screen" else None
        monitor_rect = None
        if capture == "screen":
            m = monitor_rect_from_obs_item(target, monitor_index or 0)
            if m:
                monitor_rect = QRect(m.left, m.top, m.width, m.height)
        self._preparing = True
        self.capture_btn.setEnabled(False)
        self.start_hint.setText("Preparo la sorgente...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            session = GuiCaptureSession(
                self.project, self.project.current_game, capture, target,
                monitor_index, monitor_rect, use_ffmpeg=use_ffmpeg,
                slot=self.project.current_clip, cover=cover,
            )
            prepared = session.prepare()
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self._preparing = False
            self.capture_btn.setEnabled(True)
            self.start_hint.setText("Preparazione non riuscita.")
            QMessageBox.critical(self, "Cattura", str(exc))
            return
        QApplication.restoreOverrideCursor()
        self._preparing = False
        self.capture_btn.setEnabled(True)
        self.session = session
        self.prepared = prepared
        self.cover_recording = cover
        game = self.project.current_game
        slot = self.project.current_clip
        clip = self.project.cover_clip if cover else game.clips[slot]

        self.overlay.show_for(prepared.client_rect)
        if clip.crop:
            self.overlay.set_frame(
                self._overlay_frame(
                    clip.crop, prepared.client_rect,
                    prepared.setup.width, prepared.setup.height,
                )
            )
        self.overlay.set_locked(False)
        self.panel.show_for(prepared.client_rect)
        if cover:
            self.panel.set_game("Copertina — clip di sfondo")
            self.panel.set_next_label("Clip successiva")
            self.panel.set_has_take(False)
        else:
            self.panel.set_game(
                f"Gioco {self.project.current_index + 1} di {len(self.project.games)} · "
                f"Clip {slot + 1} di {CLIP_COUNT} — {game.title}"
            )
            self.panel.set_next_label(self._next_label())
            self.panel.set_has_take(bool(clip.take_id))
        self.panel.set_status("Posiziona la cornice; poi REC")
        self.panel.set_recording(False)
        self.panel.set_warning("")
        if not (self.overlay.capture_excluded and self.panel.capture_excluded):
            self.panel.set_warning(
                "Esclusione overlay non supportata: la cornice potrebbe apparire nella cattura."
            )
        self.watch_timer.start()
        self.start_hint.setText("Cornice attiva sul monitor. Posizionala e premi REC nel pannello.")
        self.showMinimized()

    def check_active_window(self) -> None:
        if not self.prepared:
            return
        fg = foreground_window()
        if not fg:
            self.panel.set_warning("")
            return
        title = fg.title.lower()
        if any(x in title for x in ("gaming content factory", "gcf capture", "obs", "opencode")):
            self.panel.set_warning("")
            return
        if title in ("program manager", "workerw") or "desktop" in title:
            self.panel.set_warning("Desktop attivo: la cattura resta sul monitor selezionato.")
            return
        if self.prepared.monitor_rect:
            m = monitor_for_window(fg.hwnd)
            r = self.prepared.monitor_rect
            if m and (m.left != r.x() or m.top != r.y()):
                self.panel.set_warning(
                    "Finestra attiva su un altro monitor. La cattura resta sul monitor selezionato."
                )
            else:
                self.panel.set_warning("")
    # ---------- recording ----------

    def start_recording(self) -> None:
        if not self.session or not self.prepared:
            QMessageBox.warning(self, "Cattura", "Prepara prima la cattura con Prendi video.")
            return
        try:
            self.session.begin_take(self.overlay.frame_global())
        except Exception as exc:
            QMessageBox.critical(self, "Registrazione", str(exc))
            return
        self.overlay.set_locked(True)
        self.panel.set_locked(True)
        self.panel.set_recording(True)
        self.panel.set_has_take(False)
        self.next_btn.setEnabled(False)
        self.panel.set_status("Registrazione in corso...")

    def stop_recording(self) -> None:
        if not self.session:
            return
        self.panel.set_status("Salvataggio e crop...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            meta = self.session.stop_take()
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Registrazione", str(exc))
            self.panel.set_status("Errore")
            self.panel.set_recording(False)
            return
        QApplication.restoreOverrideCursor()
        self.overlay.set_locked(False)
        self.panel.set_locked(False)
        self.panel.set_recording(False)
        self.showNormal()
        self.activateWindow()
        if self.cover_recording:
            self.panel.set_status("Clip di sfondo salvata")
            self.panel.set_has_take(False)
            self.open_btn.setEnabled(True)
            self.start_hint.setText(
                "Clip di sfondo registrata. Apri Copertina per titolo, sfondo e anteprima."
            )
            return
        self.panel.set_status("Clip salvata")
        game = self.project.current_game
        slot = self.project.current_clip
        self.progress.setValue(self.project.completed_clips())
        self.take_info.setText(self._take_info(game, slot))
        verify = self.session.take_dir / "verify_vertical.png"
        if verify.exists():
            self._show_preview(verify)
        self.open_btn.setEnabled(True)
        self.generate_btn.setEnabled(self.project.all_recorded())
        self.round_btn.setEnabled(self.project.game_complete(game))
        self.update_slot_cards()
        self._update_next_controls()
        self.start_hint.setText(
            "Tutte le clip del gioco sono pronte. Premi Gioco successivo."
            if self.project.game_complete(game) else
            "Clip pronta. Controllala, poi Clip successiva."
        )

    def retry_capture(self) -> None:
        if not self.session:
            return
        self.panel.set_status("Pronto per un nuovo take")
        self.panel.set_recording(False)
        if self.cover_recording:
            self.panel.set_next_label("Clip successiva")
            self.panel.set_has_take(False)
        else:
            self.panel.set_next_label(self._next_label())
            self.panel.set_has_take(bool(self.project.current_clip_entry.take_id))
        self.showMinimized()

    def toggle_lock(self) -> None:
        locked = not self.overlay.locked
        self.overlay.set_locked(locked)
        self.panel.set_locked(locked)

    def next_step(self) -> None:
        if not self.project:
            return
        game = self.project.current_game
        slot = self.project.current_clip
        if not self.project.clip_mp4(game, slot):
            QMessageBox.warning(
                self, "Nessuna clip",
                f"Registra prima {CLIP_LABELS[slot]} per {game.title}.",
            )
            return
        self.project.accept_clip(game, slot)
        self.close_capture()

        if self.project.game_complete(game):
            if self.project.next_game():
                self.load_game()
                self.showNormal()
                self.activateWindow()
                return
            self.load_game()
            self.generate_btn.setEnabled(self.project.all_recorded())
            QMessageBox.information(
                self, "Registrazioni complete",
                "Tutte le 24 clip originali sono pronte. Approva i 18 indizi ASCII, "
                "poi Genera Short.",
            )
            self.pages.setCurrentWidget(self.home)
            self.refresh_recent()
            for i in range(self.recent.count()):
                if self.recent.item(i).data(Qt.UserRole) == str(self.project.path):
                    self.recent.setCurrentRow(i)
                    break
            return

        if not self.project.next_clip():
            missing = next(
                i for i, clip in enumerate(game.clips) if not clip.take_id
            )
            self.project.set_clip_index(missing)
            QMessageBox.information(
                self, "Clip mancante",
                f"Manca {CLIP_LABELS[missing]} di {game.title}.",
            )
        self.load_game()
        self.showNormal()
        self.activateWindow()

    def previous_step(self) -> None:
        if not self.project:
            return
        self.close_capture()
        if self.project.previous_clip():
            self.load_game()
        elif self.project.previous_game():
            self.project.set_clip_index(CLIP_COUNT - 1)
            self.load_game()
        self.showNormal()
        self.activateWindow()

    def close_capture(self) -> None:
        try:
            self.watch_timer.stop()
            self.overlay.hide()
            self.panel.hide()
            self.panel.set_warning("")
        except Exception:
            pass
        if self.session:
            self.session.close()
            self.session = None
        self.prepared = None
        self.cover_recording = False

    def open_clip(self) -> None:
        if not self.project:
            return
        mp4 = (
            self.project.cover_mp4() if self.cover_recording
            else self.project.clip_mp4(self.project.current_game, self.project.current_clip)
        )
        if mp4:
            os.startfile(mp4)
        else:
            QMessageBox.information(self, "Clip", "Nessuna clip disponibile.")

    def preview_round(self) -> None:
        if not self.project:
            return
        game = self.project.current_game
        if not self.project.ascii_ready_for_game(game):
            QMessageBox.warning(
                self, "Anteprima round",
                f"Servono tre indizi ASCII approvati e il reveal di {game.title}.",
            )
            return
        if self.round_worker and self.round_worker.isRunning():
            QMessageBox.information(self, "Anteprima round", "Generazione già in corso.")
            return
        self.round_btn.setEnabled(False)
        self.start_hint.setText("Generazione del round in corso...")
        self.round_worker = RoundWorker(self.project.id, self.project.current_index)
        self.round_worker.done.connect(self.on_round_done)
        self.round_worker.failed.connect(self.on_round_failed)
        self.round_worker.start()

    def on_round_done(self, path: str) -> None:
        self.round_btn.setEnabled(True)
        self.start_hint.setText("Round generato.")
        QMessageBox.information(self, "Anteprima round", f"Round generato:\n{path}")
        try:
            os.startfile(path)
        except Exception:
            pass

    def on_round_failed(self, message: str) -> None:
        self.round_btn.setEnabled(True)
        self.start_hint.setText("Generazione del round non riuscita.")
        QMessageBox.critical(self, "Anteprima round", message)

    def build_three_rounds(self) -> None:
        if not self.project:
            return
        first = self.project.games[:3]
        if not all(self.project.ascii_ready_for_game(g) for g in first):
            QMessageBox.warning(
                self, "Montaggio 3 round",
                "Servono tre indizi ASCII approvati e il reveal per i primi tre giochi.",
            )
            return
        if self.short_preview_worker and self.short_preview_worker.isRunning():
            QMessageBox.information(self, "Montaggio 3 round", "Generazione già in corso.")
            return
        self.rounds3_btn.setEnabled(False)
        self.start_hint.setText("Montaggio dei primi tre round in corso...")
        self.short_preview_worker = ShortPreviewWorker(self.project.id, 3)
        self.short_preview_worker.done.connect(self.on_short_preview_done)
        self.short_preview_worker.failed.connect(self.on_short_preview_failed)
        self.short_preview_worker.start()

    def on_short_preview_done(self, path: str, frames: int) -> None:
        self.rounds3_btn.setEnabled(True)
        self.start_hint.setText(f"Montaggio 3 round generato ({frames} frame).")
        QMessageBox.information(
            self, "Montaggio 3 round", f"Video generato:\n{path}\n\nFrame: {frames}"
        )
        try:
            os.startfile(path)
        except Exception:
            pass

    def on_short_preview_failed(self, message: str) -> None:
        self.rounds3_btn.setEnabled(True)
        self.start_hint.setText("Montaggio 3 round non riuscito.")
        QMessageBox.critical(self, "Montaggio 3 round", message)

    def generate_short(self) -> None:
        if not self.project or not self.project.ascii_ready():
            QMessageBox.warning(
                self, "Genera Short",
                "Servono tre indizi ASCII approvati e il reveal originale per tutti i sei giochi.",
            )
            return
        if self.short_worker and self.short_worker.isRunning():
            QMessageBox.information(self, "Genera Short", "Generazione già in corso.")
            return
        self.generate_btn.setEnabled(False)
        self.home_generate.setEnabled(False)
        self.start_hint.setText("Generazione del video da 60 secondi in corso...")
        self.short_worker = ShortWorker(self.project.id)
        self.short_worker.done.connect(self.on_short_done)
        self.short_worker.failed.connect(self.on_short_failed)
        self.short_worker.start()

    def on_short_done(self, path: str) -> None:
        self.generate_btn.setEnabled(True)
        self.update_home_generate()
        self.start_hint.setText("Short generato.")
        QMessageBox.information(self, "Genera Short", f"Video generato:\n{path}")
        try:
            os.startfile(path)
        except Exception:
            pass

    def on_short_failed(self, message: str) -> None:
        self.generate_btn.setEnabled(True)
        self.update_home_generate()
        self.start_hint.setText("Generazione non riuscita.")
        QMessageBox.critical(self, "Genera Short", message)

    def closeEvent(self, event):
        self.close_capture()
        if self.warm_worker and self.warm_worker.isRunning():
            self.warm_worker.wait(5000)
        if self.ascii_page.worker and self.ascii_page.worker.isRunning():
            self.ascii_page.worker.cancel()
            self.ascii_page.worker.wait(12000)
        if self.short_preview_worker and self.short_preview_worker.isRunning():
            self.short_preview_worker.wait(12000)
        try:
            Obs().close_portable()
        except Exception:
            pass
        super().closeEvent(event)


def run() -> None:
    import ctypes
    import os
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    os.environ.setdefault("QT_SCALE_FACTOR", "1")
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Gaming Content Factory")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()


