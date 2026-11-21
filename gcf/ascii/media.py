from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from gcf.config import ffmpeg_bin, ffprobe_bin


def _fraction(value: str) -> float:
    try:
        if "/" in value:
            a, b = value.split("/", 1)
            return float(a) / float(b) if float(b) else 0.0
        return float(value)
    except Exception:
        return 0.0


def probe(path: str | Path) -> dict:
    path = Path(path)
    cmd = [ffprobe_bin(), "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe fallito per {path.name}: {proc.stderr.strip()}")
    data = json.loads(proc.stdout or "{}")
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not video:
        raise RuntimeError(f"Nessun flusso video in {path.name}.")
    fps = _fraction(video.get("r_frame_rate") or video.get("avg_frame_rate") or "0/1")
    if fps <= 0:
        fps = _fraction(video.get("avg_frame_rate") or "30/1") or 30.0
    duration = float(data.get("format", {}).get("duration") or video.get("duration") or 0.0)
    return {
        "path": str(path),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": round(fps, 6),
        "duration": round(duration, 6),
        "has_audio": bool(audio),
        "audio_channels": int(audio.get("channels") or 0) if audio else 0,
        "video_codec": video.get("codec_name"),
    }


def _target(format_: str) -> tuple[int, int]:
    return (1080, 1920) if format_ == "vertical" else (1920, 1080)


def _crop_rect(width: int, height: int, format_: str) -> tuple[int, int, int, int]:
    target = 9 / 16 if format_ == "vertical" else 16 / 9
    source = width / height if height else 1.0
    if abs(source - target) < 0.01:
        return width, height, 0, 0
    if source > target:
        cw = max(2, int(round(height * target / 2)) * 2)
        cw = min(width, cw)
        ch = height
        x = (width - cw) // 2
        y = 0
    else:
        cw = width
        ch = max(2, int(round(width / target / 2)) * 2)
        ch = min(height, ch)
        x = 0
        y = (height - ch) // 2
    return cw, ch, x, y


def _fps_arg(fps: float) -> str:
    # Preserve the common fractional rates exactly.
    common = {
        23.976: "24000/1001", 29.97: "30000/1001", 59.94: "60000/1001",
    }
    for value, text in common.items():
        if abs(fps - value) < 0.01:
            return text
    return f"{fps:.6f}"


def prepare_working(project) -> dict:
    source = Path(project.source)
    if not source.exists():
        raise FileNotFoundError(f"Sorgente non trovata: {source}")
    info = probe(source)
    project.source_info = info
    full = info["duration"]
    start = max(0.0, float(project.interval_start or 0.0))
    if start >= full:
        raise ValueError("L'inizio intervallo è oltre la durata del video.")
    duration = project.interval_duration
    if duration is None or duration <= 0:
        duration = full - start
    duration = min(float(duration), full - start)
    if duration < 0.5:
        raise ValueError("Intervallo troppo corto (minimo 0,5 s).")
    tw, th = _target(project.format)
    cw, ch, cx, cy = _crop_rect(info["width"], info["height"], project.format)
    project.ensure_dirs()
    working = project.path / "source" / "working.mp4"
    audio_args = (["-map", "0:v:0", "-map", "0:a:0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
                  if info["has_audio"] else ["-an"])
    vf = f"crop={cw}:{ch}:{cx}:{cy},scale={tw}:{th}:flags=lanczos"
    preprocess = project.params.get("preprocess")
    if preprocess == "cas":
        strength = max(0.1, min(1.0, float(project.params.get("preprocess_strength", 0.5))))
        vf += f",cas=strength={strength:.2f}:planes=1"
    elif preprocess == "unsharp":
        vf += ",unsharp=5:5:0.6:5:5:0.0"
    vf += ",setsar=1"
    cmd = [
        ffmpeg_bin(), "-y", "-v", "error",
        "-ss", f"{start:.6f}", "-i", str(source), "-t", f"{duration:.6f}",
        "-vf", vf, "-r", _fps_arg(info["fps"]),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "14",
        "-pix_fmt", "yuv420p", *audio_args,
        "-movflags", "+faststart", str(working),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Preparazione sorgente fallita: {proc.stderr.strip()[-1200:]}")
    winfo = probe(working)
    project.working_info = winfo
    project.working_source = str(working)
    project.interval_start = start
    project.interval_duration = duration
    project.save()
    return winfo


def extract_analysis(project) -> Path:
    working = Path(project.working_source)
    out = project.path / "analysis"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_bin(), "-y", "-v", "error", "-i", str(working),
           "-vf", "fps=10,scale=320:180", str(out / "f_%04d.png")]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Analisi frame fallita: {proc.stderr.strip()[-800:]}")
    return out


def _audio_args(project) -> list[str]:
    if project.working_info.get("has_audio"):
        return ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    return ["-map", "0:v:0", "-an"]


def encode_frames(project, frames_dir: Path, out: Path, kind: str = "youtube",
                  preview_seconds: float | None = None) -> Path:
    files = sorted(frames_dir.glob("f_*.png"))
    if not files:
        raise RuntimeError("Nessun frame renderizzato.")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin(), "-y", "-v", "error",
        "-framerate", "30", "-start_number", "1", "-i", str(frames_dir / "f_%04d.png"),
        "-i", project.working_source, *_audio_args(project),
        "-t", f"{len(files) / 30.0:.6f}",
    ]
    if project.working_info.get("has_audio"):
        cmd += ["-af", "apad"]
    if kind == "master":
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "12", "-pix_fmt", "yuv420p"]
    elif kind == "preview":
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    else:
        mbps = max(4, int(project.params.get("youtube_mbps", 8)))
        cmd += ["-c:v", "libx264", "-preset", "slow", "-profile:v", "high", "-level", "4.1",
                "-pix_fmt", "yuv420p", "-b:v", f"{mbps}M",
                "-maxrate", f"{int(mbps * 1.25)}M", "-bufsize", f"{mbps * 2}M"]
    cmd += ["-movflags", "+faststart", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg fallito: {proc.stderr.strip()[-1200:]}")
    return out
