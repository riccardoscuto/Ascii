from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRect

from gcf.capture.obs import CaptureSetup, Obs
from gcf.capture.takes import (
    frame_at,
    make_vertical_mp4,
    make_vertical_preview,
    probe,
    take_id,
    write_take_metadata,
)
from gcf.config import ffmpeg_bin
from gcf.gui.project import GameEntry, Project
from gcf.gui.windows import (
    find_window,
    monitor_rect_from_obs_item,
    primary_screen,
    title_from_obs_item,
)


@dataclass
class PreparedCapture:
    setup: CaptureSetup
    client_rect: QRect
    game_title: str
    target: str
    capture: str
    monitor_index: int | None = None
    monitor_name: str = ""
    monitor_rect: QRect | None = None
    backend: str = "obs"


class FfmpegMonitorRecorder:
    """Fallback for monitors OBS cannot distinguish (duplicate monitor_id)."""

    def __init__(self, rect: QRect, path: Path):
        self.rect = rect
        self.path = path
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg_bin(), "-y", "-v", "error",
            "-f", "gdigrab", "-framerate", "60",
            "-offset_x", str(self.rect.x()), "-offset_y", str(self.rect.y()),
            "-video_size", f"{self.rect.width()}x{self.rect.height()}",
            "-draw_mouse", "0", "-i", "desktop",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-an", str(self.path),
        ]
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def stop(self) -> Path:
        if self.proc:
            try:
                if self.proc.stdin:
                    self.proc.stdin.write(b"q")
                    self.proc.stdin.flush()
                    self.proc.stdin.close()
            except Exception:
                pass
            try:
                self.proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=5)
        if not self.path.exists():
            raise RuntimeError("Registrazione FFmpeg non trovata")
        return self.path


class GuiCaptureSession:
    def __init__(
        self,
        project: Project,
        game: GameEntry,
        capture: str,
        target: str,
        monitor_index: int | None = None,
        monitor_rect: QRect | None = None,
        use_ffmpeg: bool = False,
        slot: int = 0,
        cover: bool = False,
    ):
        self.project = project
        self.game = game
        self.slot = slot
        self.cover = cover
        self.capture = capture
        self.target = target
        self.monitor_index = monitor_index
        self.monitor_rect_input = monitor_rect
        self.use_ffmpeg = use_ffmpeg
        self.obs = Obs()
        self.recorder: FfmpegMonitorRecorder | None = None
        self.prepared: PreparedCapture | None = None
        self.take_id: str | None = None
        self.take_dir: Path | None = None
        self.crop_global: QRect | None = None
        self.crop_source: dict | None = None
        self.mkv: Path | None = None
        self.mp4: Path | None = None

    def _clip(self):
        return self.project.cover_clip if self.cover else self.game.clips[self.slot]

    def _label(self) -> str:
        return "Copertina" if self.cover else self.game.title

    def prepare(self) -> PreparedCapture:
        if self.capture == "screen":
            monitor = self.monitor_rect_input
            if monitor is None:
                m = monitor_rect_from_obs_item(self.target, self.monitor_index or 0)
                if m:
                    monitor = QRect(m.left, m.top, m.width, m.height)
            if monitor is None:
                left, top, w, h = primary_screen()
                monitor = QRect(left, top, w, h)
            if self.use_ffmpeg:
                setup = CaptureSetup("", "", "screen", None, self.target,
                                     monitor.width(), monitor.height())
                prepared = PreparedCapture(
                    setup, monitor, self._label(), self.target, "screen",
                    self.monitor_index, self.target, monitor, "ffmpeg",
                )
            else:
                self.obs.ensure_running()
                setup = self.obs.setup_capture(
                    capture="screen", width=None, height=None, monitor=self.monitor_index,
                )
                prepared = PreparedCapture(
                    setup, monitor, self._label(), self.target, "screen",
                    self.monitor_index, setup.monitor or self.target, monitor, "obs",
                )
        else:
            self.obs.ensure_running()
            setup = self.obs.setup_capture(
                capture=self.capture, width=None, height=None, window=self.target,
            )
            title = title_from_obs_item(self.target)
            info = find_window(title, exclude=("OBS", "Gaming Content Factory", "OpenCode"))
            if info:
                left, top, w, h = info.client_rect
            else:
                left, top, w, h = primary_screen()
            prepared = PreparedCapture(
                setup, QRect(left, top, w, h), self._label(), self.target, self.capture,
                None, "", None, "obs",
            )
        self.prepared = prepared
        clip = self._clip()
        clip.capture = self.capture
        clip.monitor = prepared.monitor_index
        clip.monitor_name = prepared.monitor_name
        clip.monitor_ffmpeg = prepared.backend == "ffmpeg"
        clip.window = self.target if self.capture != "screen" else ""
        self.project.save()
        return prepared

    def begin_take(self, crop_global: QRect) -> Path:
        if not self.prepared:
            raise RuntimeError("prepare() non eseguito")
        self.crop_global = QRect(crop_global)
        folder = "_cover" if self.cover else self.game.title
        self.take_id = take_id(self.project.path, folder)
        self.take_dir = (
            self.project.cover_take_dir(self.take_id) if self.cover
            else self.project.take_dir(self.game, self.take_id)
        )
        self.take_dir.mkdir(parents=True, exist_ok=True)
        if self.prepared.backend == "ffmpeg":
            self.recorder = FfmpegMonitorRecorder(
                self.prepared.client_rect, self.take_dir / "ffmpeg_capture.mkv",
            )
            self.recorder.start()
        else:
            self.obs.start_record(self.take_dir)
        return self.take_dir

    def stop_take(self) -> dict:
        if not self.prepared or not self.take_dir or not self.crop_global:
            raise RuntimeError("registrazione non iniziata")
        if self.prepared.backend == "ffmpeg":
            self.mkv = self.recorder.stop() if self.recorder else None
        else:
            self.mkv = self.obs.stop_record(self.take_dir)
        if not self.mkv:
            raise RuntimeError("File di registrazione mancante")
        source_info = probe(self.mkv)
        crop = self.crop_from_overlay(self.crop_global, self.prepared.client_rect,
                                      self.prepared.setup.width, self.prepared.setup.height)
        self.crop_source = crop
        self.mp4 = self.take_dir / "take.mp4"
        make_vertical_mp4(self.mkv, self.mp4, crop)
        info = probe(self.mp4)

        preview_full = self.take_dir / "preview_full.png"
        frame_at(self.mkv, preview_full, at=min(1.0, max(0.0, source_info["duration"] / 2)))
        preview_vertical = self.take_dir / "preview_vertical.png"
        make_vertical_preview(preview_full, preview_vertical, crop)
        verify = self.take_dir / "verify_vertical.png"
        frame_at(self.mp4, verify, at=min(1.0, max(0.0, info["duration"] / 2)))

        meta = write_take_metadata(
            project=self.project.id,
            game="Copertina" if self.cover else self.game.title,
            take_dir=self.take_dir,
            capture=self.capture,
            target=self.prepared.target,
            monitor=self.prepared.monitor_name or None,
            requested_size=(self.prepared.setup.width, self.prepared.setup.height),
            crop=crop,
            mkv=self.mkv,
            mp4=self.mp4,
            preview_full=preview_full,
            preview_vertical=preview_vertical,
            verify_vertical=verify,
            slot=None if self.cover else self.slot,
            video_info=info,
            source_video_info=source_info,
        )
        if self.cover:
            self.project.set_cover_clip(self.take_id, crop)
        else:
            self.project.set_clip(self.game, self.slot, self.take_id, crop)
        return meta

    @staticmethod
    def frame_from_crop(crop: dict, client: QRect, source_w: int, source_h: int) -> QRect:
        return QRect(
            round(crop["x"] / max(1, source_w) * client.width()),
            round(crop["y"] / max(1, source_h) * client.height()),
            round(crop["w"] / max(1, source_w) * client.width()),
            round(crop["h"] / max(1, source_h) * client.height()),
        )

    @staticmethod
    def crop_from_overlay(overlay: QRect, client: QRect, source_w: int, source_h: int) -> dict:
        nx = (overlay.x() - client.x()) / max(1, client.width())
        ny = (overlay.y() - client.y()) / max(1, client.height())
        nw = overlay.width() / max(1, client.width())
        nh = overlay.height() / max(1, client.height())
        x = round(nx * source_w)
        y = round(ny * source_h)
        w = round(nw * source_w)
        h = round(nh * source_h)
        w = max(2, min(w, source_w))
        h = max(2, min(h, source_h))
        x = max(0, min(x, source_w - w))
        y = max(0, min(y, source_h - h))
        if w % 2:
            w -= 1
        if h % 2:
            h -= 1
        return {"x": x, "y": y, "w": w, "h": h}

    def close(self) -> None:
        try:
            self.obs.close()
        except Exception:
            pass
