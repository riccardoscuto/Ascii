from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from gcf.config import ROOT, ffmpeg_bin, ffprobe_bin, video_encode_args


SLOT_KEYS = ("clue_1", "clue_2", "clue_3", "reveal")
SLOT_LABELS = ("Indizio 1", "Indizio 2", "Indizio 3", "Risultato")


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return value.strip("_") or "game"


def crop_rect(width: int, height: int, offset: int = 0) -> dict:
    target = 9 / 16
    if width / height > target:
        cw = round(height * target)
        ch = height
        x = (width - cw) // 2 + offset
        y = 0
    else:
        cw = width
        ch = round(width / target)
        x = 0
        y = (height - ch) // 2 + offset
    cw = max(2, min(cw, width))
    ch = max(2, min(ch, height))
    x = max(0, min(x, width - cw))
    y = max(0, min(y, height - ch))
    return {"x": x, "y": y, "w": cw, "h": ch}


def make_vertical_preview(full_png: Path, out_png: Path, crop: dict, width: int = 1080, height: int = 1920) -> None:
    with Image.open(full_png) as im:
        im = im.convert("RGB")
        box = (crop["x"], crop["y"], crop["x"] + crop["w"], crop["y"] + crop["h"])
        im = im.crop(box).resize((width, height), Image.Resampling.LANCZOS)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        im.save(out_png)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(path: Path) -> dict:
    cmd = [
        ffprobe_bin(), "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        raise RuntimeError(f"Nessuno stream video in {path}")
    num, den = video.get("r_frame_rate", "0/1").split("/")
    fps = (float(num) / float(den)) if float(den) else 0.0
    duration = float(video.get("duration") or data.get("format", {}).get("duration") or 0.0)
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": round(fps, 3),
        "duration": round(duration, 3),
        "frames": int(video.get("nb_frames") or round(duration * fps)),
        "codec": video.get("codec_name"),
        "has_audio": any(s.get("codec_type") == "audio" for s in data.get("streams", [])),
    }


def media_duration(path: Path) -> float:
    cmd = [
        ffprobe_bin(), "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(proc.stdout.strip() or 0.0)


def make_vertical_mp4(mkv: Path, mp4: Path, crop: dict, width: int = 1080, height: int = 1920) -> None:
    """Create the working 9:16 take from the full-frame recording.

    The MKV stays as the full-frame archival original; the MP4 is the
    vertical, silent source used by the Guess renderer.
    """
    vf = (
        f"crop={crop['w']}:{crop['h']}:{crop['x']}:{crop['y']},"
        f"scale={width}:{height}:flags=lanczos"
    )
    cmd = [
        ffmpeg_bin(), "-y", "-v", "error", "-i", str(mkv),
        "-map", "0:v:0", "-vf", vf, "-an",
        *video_encode_args(18),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4),
    ]
    subprocess.run(cmd, check=True)


def frame_at(video: Path, out_png: Path, at: float = 1.0) -> None:
    cmd = [
        ffmpeg_bin(), "-y", "-v", "error", "-ss", f"{at:.3f}", "-i", str(video),
        "-frames:v", "1", str(out_png),
    ]
    subprocess.run(cmd, check=True)


def take_id(project_dir: Path, game: str) -> str:
    base = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = base
    index = 1
    root = project_dir / "takes" / slug(game)
    while (root / candidate).exists():
        candidate = f"{base}_{index:02d}"
        index += 1
    return candidate


def list_takes(project_dir: Path, game: str | None = None, slot: int | None = None) -> list[dict]:
    root = project_dir / "takes"
    if not root.exists():
        return []
    rows = []
    for meta_path in sorted(root.glob("*/*/take.json")):
        if game and meta_path.parent.parent.name != slug(game):
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if slot is not None and meta.get("slot") != slot:
            continue
        rows.append({
            "game": meta.get("game"),
            "take_id": meta.get("take_id"),
            "slot": meta.get("slot"),
            "selected": bool(meta.get("selected")),
            "capture": meta.get("capture"),
            "duration": meta.get("video", {}).get("duration"),
            "size": [meta.get("video", {}).get("width"), meta.get("video", {}).get("height")],
            "fps": meta.get("video", {}).get("fps"),
            "mp4": meta.get("paths", {}).get("mp4"),
        })
    return rows


def select_take(project_dir: Path, game: str, chosen: str) -> None:
    root = project_dir / "takes" / slug(game)
    found = False
    for meta_path in root.glob("*/take.json"):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["selected"] = meta.get("take_id") == chosen
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        found = found or meta["selected"]
    if not found:
        raise SystemExit(f"Take non trovato: {game}/{chosen}")



def write_take_metadata(
    project: str,
    game: str,
    take_dir: Path,
    capture: str,
    target: str | None,
    requested_size: tuple[int, int],
    crop: dict,
    mkv: Path,
    mp4: Path,
    preview_full: Path | None,
    preview_vertical: Path | None,
    verify_vertical: Path | None,
    monitor: str | None = None,
    slot: int | None = None,
    video_info: dict | None = None,
    source_video_info: dict | None = None,
) -> dict:
    info = video_info or probe(mp4)
    source_info = source_video_info or probe(mkv)
    if source_info.get("duration", 0) <= 0:
        source_info["duration"] = info["duration"]
        source_info["frames"] = info["frames"]
    slot_key = SLOT_KEYS[slot] if slot is not None and 0 <= slot < len(SLOT_KEYS) else None
    slot_label = SLOT_LABELS[slot] if slot is not None and 0 <= slot < len(SLOT_LABELS) else None
    meta = {
        "project": project,
        "game": game,
        "take_id": take_dir.name,
        "slot": slot,
        "slot_key": slot_key,
        "slot_label": slot_label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "capture": capture,
        "target": target,
        "monitor": monitor,
        "requested_size": list(requested_size),
        "crop": crop,
        "source_video": source_info,
        "video": info,
        "audio": False,
        "paths": {
            "take_dir": str(take_dir.relative_to(ROOT)),
            "mkv": str(mkv.relative_to(ROOT)),
            "mp4": str(mp4.relative_to(ROOT)),
            "preview_full": str(preview_full.relative_to(ROOT)) if preview_full else None,
            "preview_vertical": str(preview_vertical.relative_to(ROOT)) if preview_vertical else None,
            "verify_vertical": str(verify_vertical.relative_to(ROOT)) if verify_vertical else None,
        },
        "sha256": {
            "mkv": sha256(mkv),
            "mp4": sha256(mp4),
        },
    }
    (take_dir / "take.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
