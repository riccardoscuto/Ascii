from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from gcf.capture.takes import SLOT_LABELS, media_duration, probe, sha256
from gcf.config import ROOT, ffmpeg_bin, video_encode_args

FONT = ROOT / "assets" / "fonts" / "Montserrat-Variable.ttf"
MUSIC = ROOT / "assets" / "music" / "placeholder_120_60.wav"
BEATMAP = ROOT / "assets" / "music" / "placeholder_120_60.json"
PRESET = ROOT / "assets" / "presets" / "guess_default.json"

W, H, FPS = 1080, 1920, 30
OUTLINE = (0, 0, 0, 255)
DEFAULT_CLIP_DURATIONS = (2.0, 2.0, 2.0, 3.0)

DEFAULT_PRESET = {
    "name": "guess_default",
    "font": "assets/fonts/Montserrat-Variable.ttf",
    "number": {
        "font_size": 116, "x": 72, "y": 300, "anchor": "lt",
        "color": [255, 255, 255, 255], "outline": [0, 0, 0, 255], "stroke": 8,
    },
    "title": {
        "font_size": 120, "y": 1000, "max_width": 940,
        "color": [0, 183, 255, 255], "outline": [0, 0, 0, 255], "stroke": 7,
    },
    "cover": {
        "font_size": 104, "center_y": 880, "max_width": 800, "line_gap": 18,
        "color": [255, 255, 255, 255], "highlight_color": [0, 183, 255, 255],
        "outline": [0, 0, 0, 255], "stroke": 9,
        "highlight_phrases": ["THE GAME"], "fade_in": 0.35, "slide_px": 28,
    },
}


def load_preset(path: str | Path | None = None) -> dict:
    data = json.loads(json.dumps(DEFAULT_PRESET))
    preset_path = Path(path) if path else PRESET
    if not preset_path.is_absolute():
        preset_path = ROOT / preset_path
    if preset_path.exists():
        raw = json.loads(preset_path.read_text(encoding="utf-8"))
        for key, value in raw.items():
            if isinstance(value, dict) and isinstance(data.get(key), dict):
                data[key].update(value)
            else:
                data[key] = value
    return data


class InsufficientMaterial(RuntimeError):
    pass


class ClipTooShort(InsufficientMaterial):
    pass


@dataclass(frozen=True)
class RoundTiming:
    clip_durations: tuple[float, ...]
    number_at: float = 0.0

    @property
    def total(self) -> float:
        return round(sum(self.clip_durations), 3)

    @property
    def reveal_at(self) -> float:
        return round(sum(self.clip_durations[:3]), 3)


def ensure_music(duration: float = 60.0, bpm: int = 120) -> None:
    MUSIC.parent.mkdir(parents=True, exist_ok=True)
    if not MUSIC.exists():
        expr = (
            "0.22*sin(2*PI*1000*t)*exp(-50*mod(t,0.5))"
            "+0.16*sin(2*PI*110*t)*exp(-7*mod(t,2))"
            "+0.035*sin(2*PI*220*t)"
        )
        subprocess.run([
            ffmpeg_bin(), "-y", "-v", "error", "-f", "lavfi",
            "-i", f"aevalsrc='{expr}':s=48000:d={duration}",
            "-ac", "2", "-c:a", "pcm_s16le", str(MUSIC),
        ], check=True)
    if not BEATMAP.exists():
        beat = 60.0 / bpm
        beats = [round(i * beat, 4) for i in range(int(duration / beat) + 1)]
        downbeats = [round(i * beat * 4, 4) for i in range(int(duration / (beat * 4)) + 1)]
        BEATMAP.write_text(json.dumps({
            "bpm": bpm, "offset": 0.0, "duration": duration,
            "beats": beats, "downbeats": downbeats,
        }, indent=2), encoding="utf-8")


def beat_time(beat_index: int) -> float:
    if not BEATMAP.exists():
        ensure_music()
    data = json.loads(BEATMAP.read_text(encoding="utf-8"))
    return float(data["beats"][beat_index])


def load_beatmap(path: Path | None = None) -> dict:
    path = path or BEATMAP
    if not path.exists():
        ensure_music()
    return json.loads(path.read_text(encoding="utf-8"))


def make_round_timing(
    beatmap: dict | None = None,
    durations: tuple[float, ...] = DEFAULT_CLIP_DURATIONS,
) -> RoundTiming:
    """Snap each clip duration to the music grid, never below one beat."""
    beatmap = beatmap or load_beatmap()
    beat = 60.0 / float(beatmap["bpm"])
    snapped = tuple(round(max(1, round(d / beat)) * beat, 4) for d in durations)
    return RoundTiming(snapped)


def _font(size: int, path: str | Path | None = None) -> ImageFont.FreeTypeFont:
    font_path = Path(path) if path else FONT
    if not font_path.is_absolute():
        font_path = ROOT / font_path
    if not font_path.exists():
        font_path = FONT
    font = ImageFont.truetype(str(font_path), size)
    try:
        font.set_variation_by_axes([800])
    except Exception:
        pass
    return font


def _fit_font(
    text: str, size: int, max_width: int, path: str | Path | None = None
) -> ImageFont.FreeTypeFont:
    while size > 40:
        font = _font(size, path)
        box = font.getbbox(text)
        if box[2] - box[0] <= max_width:
            return font
        size -= 4
    return _font(size, path)


def _text_layer(
    text: str,
    y: int,
    size: int,
    fill: tuple,
    width: int = 940,
    stroke: int | None = None,
    outline: tuple = OUTLINE,
    font_path: str | Path | None = None,
) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _fit_font(text, size, width, font_path)
    stroke_width = max(3, size // 18) if stroke is None else int(stroke)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.text((W // 2, y + 10), text, font=font, anchor="mm",
            fill=(0, 0, 0, 190), stroke_width=max(2, size // 22), stroke_fill=(0, 0, 0, 190))
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)
    draw.text((W // 2, y), text, font=font, anchor="mm",
              fill=fill, stroke_width=stroke_width, stroke_fill=outline)
    return img


def _number_layer(text: str, cfg: dict, font_path: str | Path | None = None) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _font(int(cfg["font_size"]), font_path)
    draw.text(
        (int(cfg["x"]), int(cfg["y"])), text, font=font,
        anchor=cfg.get("anchor", "lt"),
        fill=tuple(cfg["color"]),
        stroke_width=int(cfg["stroke"]),
        stroke_fill=tuple(cfg["outline"]),
    )
    return img


def make_overlays(
    outdir: Path,
    number_text: str,
    title_text: str,
    preset: dict | None = None,
) -> tuple[Path, Path]:
    preset = preset or load_preset()
    number_cfg = preset["number"]
    title_cfg = preset["title"]
    font_path = preset.get("font")
    outdir.mkdir(parents=True, exist_ok=True)
    number = _number_layer(number_text, number_cfg, font_path)
    title = _text_layer(
        title_text.upper(), int(title_cfg["y"]), int(title_cfg["font_size"]),
        tuple(title_cfg["color"]), int(title_cfg["max_width"]),
        stroke=int(title_cfg["stroke"]), outline=tuple(title_cfg["outline"]),
        font_path=font_path,
    )
    number_path = outdir / "number.png"
    title_path = outdir / "title.png"
    number.save(number_path)
    title.save(title_path)
    return number_path, title_path


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def segment_window(duration: float, segment: float, reveal: bool) -> tuple[float, float]:
    """Pick the source portion automatically; only trim, never speed-ramp."""
    if duration + 1e-6 < segment:
        raise ClipTooShort(
            f"Clip troppo corta: {duration:.2f}s, servono almeno {segment:.2f}s."
        )
    start = duration - segment if reveal else (duration - segment) / 2
    start = max(0.0, round(start, 3))
    return start, round(start + segment, 3)


def build_round_segments(
    project: str,
    game: str,
    title: str,
    clips: list[dict],
    number_text: str,
    timing: RoundTiming,
    outdir: Path,
    music: Path = MUSIC,
    beatmap_path: Path = BEATMAP,
    preset: dict | None = None,
    fingerprint: dict | None = None,
) -> dict:
    """Build one 9s round from four distinct vertical clips.

    Each item in clips needs: path, slot, take_id, crop.
    Clue clips use their middle portion; the reveal clip uses its tail.
    """
    if len(clips) != 4:
        raise InsufficientMaterial(f"Servono quattro clip per {game}, trovate {len(clips)}.")
    music_duration = media_duration(music)
    if music_duration < timing.total:
        raise InsufficientMaterial(
            f"Musica troppo corta: {music_duration:.1f}s per un round da {timing.total:.1f}s."
        )

    preset = preset or load_preset()
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    number_path, title_path = make_overlays(outdir, number_text, title, preset)

    rows = []
    inputs = []
    for i, (clip, segment) in enumerate(zip(clips, timing.clip_durations)):
        path = Path(clip["path"]).resolve()
        info = probe(path)
        if (info["width"], info["height"]) != (W, H):
            raise InsufficientMaterial(
                f"{SLOT_LABELS[i]} di {game}: serve una clip {W}x{H}, "
                f"trovata {info['width']}x{info['height']}."
            )
        try:
            start, end = segment_window(info["duration"], segment, reveal=(i == 3))
        except ClipTooShort as exc:
            raise ClipTooShort(f"{SLOT_LABELS[i]} di {game}: {exc}") from None
        inputs.append(str(path))
        rows.append({
            "slot": i,
            "slot_key": clip.get("slot_key"),
            "slot_label": SLOT_LABELS[i],
            "take_id": clip.get("take_id"),
            "crop": clip.get("crop"),
            "clip": _rel(path),
            "source_duration": info["duration"],
            "trim_start": start,
            "trim_end": end,
            "duration": segment,
        })

    out = outdir / "round_01.mp4"
    filters = []
    for i, row in enumerate(rows):
        filters.append(
            f"[{i}:v]trim=start={row['trim_start']}:end={row['trim_end']},"
            f"setpts=PTS-STARTPTS,fps={FPS},setsar=1,scale={W}:{H}[v{i}]"
        )
    labels = "".join(f"[v{i}]" for i in range(4))
    number_until = round(timing.reveal_at - 0.05, 3)
    filters.append(f"{labels}concat=n=4:v=1:a=0[bg]")
    filters.append(
        f"[4:v]format=rgba,fade=in:st={timing.number_at}:d=0.18:alpha=1[num];"
        f"[5:v]format=rgba,fade=in:st={timing.reveal_at}:d=0.22:alpha=1[title];"
        f"[bg][num]overlay=0:0:enable='between(t,{timing.number_at},{number_until})'[v1];"
        f"[v1][title]overlay=0:0:enable='between(t,{timing.reveal_at},{timing.total})'[v];"
        f"[v]setsar=1[vout]"
    )
    cmd = [
        ffmpeg_bin(), "-y", "-v", "error",
        *sum((["-i", path] for path in inputs), []),
        "-loop", "1", "-i", str(number_path),
        "-loop", "1", "-i", str(title_path),
        "-i", str(music),
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", "6:a",
        "-t", f"{timing.total}", "-r", str(FPS),
        *video_encode_args(18), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(out),
    ]
    subprocess.run(cmd, check=True)

    manifest = {
        "project": project,
        "game": game,
        "title": title,
        "number": number_text,
        "duration": timing.total,
        "fps": FPS,
        "resolution": [W, H],
        "clips": rows,
        "timing": {
            "clip_durations": list(timing.clip_durations),
            "number_at": timing.number_at,
            "reveal_at": timing.reveal_at,
        },
        "preset": preset.get("name", "guess_default"),
        "graphics": preset,
        "fingerprint": fingerprint,
        "beatmap": _rel(beatmap_path),
        "music": _rel(music),
        "font": str(FONT.relative_to(ROOT)),
        "events": {
            "number_at": timing.number_at,
            "number_until": number_until,
            "reveal_at": timing.reveal_at,
            "number": number_text,
        },
        "output": str(out.relative_to(ROOT)),
        "sha256": {"music": sha256(music), "font": sha256(FONT), "mp4": sha256(out)},
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
