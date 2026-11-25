from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from gcf.capture.takes import SLOT_KEYS, SLOT_LABELS, media_duration, probe, sha256
from gcf.config import ROOT, ffmpeg_bin, project_dir, video_encode_args
from gcf.guess.cover import build_cover
from gcf.guess.round import (
    BEATMAP,
    DEFAULT_CLIP_DURATIONS,
    FONT,
    FPS,
    H,
    MUSIC,
    W,
    InsufficientMaterial,
    RoundTiming,
    _rel,
    _text_layer,
    build_round_segments,
    ensure_music,
    load_beatmap,
    load_preset,
    make_round_timing,
)
from gcf.gui.project import Project

SHORT_DURATION = 60.0


def _background() -> Image.Image:
    img = Image.new("RGBA", (W, H), (12, 14, 20, 255))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 48):
        d.line([(x, 0), (x, H)], fill=(0, 183, 255, 18), width=1)
    for y in range(0, H, 48):
        d.line([(0, y), (W, y)], fill=(0, 183, 255, 18), width=1)
    d.rectangle([28, 28, W - 28, H - 28], outline=(0, 183, 255, 90), width=3)
    return img


def _make_title_card(
    text: str, sub: str, y: int, font_path: str | Path | None = None
) -> Image.Image:
    img = _background()
    img = Image.alpha_composite(
        img, _text_layer(text, y, 110, (255, 255, 255, 255), 900, font_path=font_path)
    )
    img = Image.alpha_composite(
        img, _text_layer(sub, y + 170, 46, (0, 183, 255, 255), 860, font_path=font_path)
    )
    return img


def _make_clip(png: Path, out: Path, duration: float) -> None:
    subprocess.run([
        ffmpeg_bin(), "-y", "-v", "error", "-loop", "1", "-i", str(png),
        "-t", f"{duration}", "-r", str(FPS), "-vf", "setsar=1",
        *video_encode_args(18), "-pix_fmt", "yuv420p", "-an", str(out),
    ], check=True)


def short_outro_duration(cover_duration: float, round_duration: float) -> float:
    outro = round(SHORT_DURATION - cover_duration - 6 * round_duration, 3)
    if outro < 1.0:
        raise InsufficientMaterial(
            f"Copertina ({cover_duration:.2f}s) e round ({round_duration:.2f}s × 6) "
            f"non lasciano spazio all'outro in un video da {SHORT_DURATION:.0f}s."
        )
    return outro


def _media_stamp(path: Path) -> list:
    return [str(path), path.stat().st_mtime_ns, path.stat().st_size]


def _round_fingerprint(
    project: Project,
    game_index: int,
    timing: RoundTiming,
    preset: dict,
    number_text: str,
    music: Path,
    beatmap: Path,
) -> dict:
    game = project.games[game_index]
    clips = []
    for slot, clip in enumerate(game.clips):
        path = project.ascii_mp4(game, slot) if slot < 3 else project.clip_mp4(game, slot)
        clips.append({
            "slot": slot,
            "take_id": clip.take_id,
            "crop": clip.crop,
            "kind": "ascii" if slot < 3 else "original",
            "ascii": {
                key: (clip.ascii or {}).get(key) for key in
                ("fingerprint", "cache_signature", "renderer", "variant", "mode",
                 "density", "color", "start", "duration", "status")
            },
            "file": _media_stamp(path) if path else None,
        })
    return {
        "clips": clips,
        "timing": [list(timing.clip_durations), timing.number_at, timing.reveal_at],
        "preset": preset,
        "number": number_text,
        "music": _media_stamp(music),
        "beatmap": _media_stamp(beatmap),
    }


def _clip_rows(project: Project, game_index: int) -> list[dict]:
    game = project.games[game_index]
    rows = []
    for slot, entry in enumerate(game.clips):
        if slot < 3:
            path = project.ascii_mp4(game, slot)
            if not path:
                raise InsufficientMaterial(
                    f"Manca la conversione ASCII di {SLOT_LABELS[slot]} per {game.title}."
                )
            kind = "ascii"
        else:
            path = project.clip_mp4(game, slot)
            if not path:
                raise InsufficientMaterial(
                    f"Manca {SLOT_LABELS[slot]} per {game.title}."
                )
            kind = "original"
        rows.append({
            "path": path,
            "slot": slot,
            "slot_key": SLOT_KEYS[slot],
            "take_id": entry.take_id,
            "crop": entry.crop,
            "kind": kind,
            "ascii": entry.ascii if kind == "ascii" else None,
        })
    return rows


def build_game_round(
    project: Project,
    game_index: int,
    outdir: Path | None = None,
    timing: RoundTiming | None = None,
    number_text: str | None = None,
    durations: tuple[float, ...] | None = None,
    beatmap_path: Path | None = None,
    music_path: Path | None = None,
    preset: dict | None = None,
) -> dict:
    """Render one round from its four clips; no other game is touched."""
    ensure_music()
    beatmap_file = Path(beatmap_path).resolve() if beatmap_path else BEATMAP
    music_file = Path(music_path).resolve() if music_path else MUSIC
    preset = preset or load_preset(project.graphics_preset or None)
    timing = timing or make_round_timing(
        load_beatmap(beatmap_file), durations or DEFAULT_CLIP_DURATIONS
    )
    game = project.games[game_index]
    outdir = Path(outdir).resolve() if outdir else (project.path / "rounds" / f"round_{game_index + 1}")
    text = number_text or f"{game_index + 1}."
    fingerprint = _round_fingerprint(
        project, game_index, timing, preset, text, music_file, beatmap_file
    )
    manifest_path = outdir / "manifest.json"
    round_path = outdir / "round_01.mp4"
    if manifest_path.exists() and round_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("fingerprint") == fingerprint:
            return existing
    return build_round_segments(
        project=project.id,
        game=game.title,
        title=game.title,
        clips=_clip_rows(project, game_index),
        number_text=text,
        timing=timing,
        outdir=outdir,
        music=music_file,
        beatmap_path=beatmap_file,
        preset=preset,
        fingerprint=fingerprint,
    )


def short_metadata(project: Project) -> dict:
    challenge = project.challenge_title.strip().upper()
    return {
        "title": f"{challenge.title()} | 6 Games in 60 Seconds",
        "description": (
            f"{challenge.title()}. Six games, one minute. "
            "Comment your score.\n\n"
            "No spoilers: each game title appears only in its reveal."
        ),
        "hashtags": ["#gaming", "#videogames", "#guessthegame", "#shorts"],
        "games_count": len(project.games),
        "challenge_category": project.challenge_category,
        "approval": "pending",
    }


def build_short(
    project_id: str,
    beatmap_path: Path | None = None,
    durations: tuple[float, ...] | None = None,
    music_path: Path | None = None,
) -> dict:
    project = Project.load(project_dir(project_id))
    if len(project.games) != 6:
        raise InsufficientMaterial("Il progetto non contiene sei giochi.")

    missing = []
    for game in project.games:
        for slot in range(3):
            state = project.ascii_state(game, slot)
            if state != "approved":
                missing.append(f"{game.title} — {SLOT_LABELS[slot]} ({state})")
        if not project.clip_mp4(game, 3):
            missing.append(f"{game.title} — {SLOT_LABELS[3]}")
    if missing:
        raise InsufficientMaterial(
            "Mancano clip ASCII approvate o reveal originali:\n"
            + "\n".join(f"• {row}" for row in missing)
        )

    ensure_music(60.0)
    music = Path(music_path).resolve() if music_path else MUSIC
    beatmap_file = Path(beatmap_path).resolve() if beatmap_path else BEATMAP
    if media_duration(music) < SHORT_DURATION:
        raise InsufficientMaterial(
            f"La musica dura meno di {SHORT_DURATION:.0f}s: {music}."
        )
    beatmap = load_beatmap(beatmap_file)
    timing = make_round_timing(beatmap, durations or DEFAULT_CLIP_DURATIONS)
    cover_duration = max(1.0, min(float(project.cover_duration), 10.0))
    outro_duration = short_outro_duration(cover_duration, timing.total)

    outdir = project.path / "output"
    work = project.path / "work" / "short"
    outdir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    round_manifests = [
        build_game_round(
            project, i, outdir=work / f"round_{i + 1}", timing=timing,
            beatmap_path=beatmap_file, music_path=music,
        )
        for i in range(6)
    ]

    cover_manifest = build_cover(
        project, outdir=work / "cover", duration=cover_duration, music_path=music,
    )
    cover = work / "cover" / "cover.mp4"

    preset = load_preset(project.graphics_preset or None)
    font_path = preset.get("font")
    font_file = Path(font_path) if font_path else FONT
    if not font_file.is_absolute():
        font_file = ROOT / font_file
    outro_png = work / "outro.png"
    _make_title_card(
        "HOW MANY DID YOU GET?", "Comment your score", 790, font_path=font_path
    ).convert("RGB").save(outro_png)
    outro = work / "outro.mp4"
    _make_clip(outro_png, outro, outro_duration)

    rounds = [work / f"round_{i + 1}" / "round_01.mp4" for i in range(6)]
    inputs = [cover] + rounds + [outro]
    input_labels = "".join(f"[{i}:v]setsar=1[v{i}];" for i in range(8))
    labels = "".join(f"[v{i}]" for i in range(8))
    filter_complex = f"{input_labels}{labels}concat=n=8:v=1:a=0[v]"
    output = outdir / "short.mp4"
    cmd = [ffmpeg_bin(), "-y", "-v", "error"]
    for path in inputs:
        cmd += ["-i", str(path)]
    cmd += ["-i", str(music)]
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "8:a",
        "-t", f"{SHORT_DURATION}", "-r", str(FPS),
        *video_encode_args(18), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(output),
    ]
    subprocess.run(cmd, check=True)

    info = probe(output)
    if abs(info["duration"] - SHORT_DURATION) > 0.1 or info["frames"] != int(SHORT_DURATION * FPS):
        raise RuntimeError(f"Output inatteso: {info}")

    metadata = short_metadata(project)
    (outdir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    manifest = {
        "project": project_id,
        "resolution": [W, H],
        "fps": FPS,
        "duration": SHORT_DURATION,
        "frames": int(round(SHORT_DURATION * FPS)),
        "output": _rel(output),
        "sha256": {"output": sha256(output), "music": sha256(music)},
        "cover": {
            "title": cover_manifest["title"],
            "duration": cover_duration,
            "output": cover_manifest["output"],
            "preview": cover_manifest["preview"],
            "still": cover_manifest["still"],
        },
        "intro": cover_duration,
        "outro": outro_duration,
        "round_duration": timing.total,
        "timing": {
            "clip_durations": list(timing.clip_durations),
            "reveal_at": timing.reveal_at,
            "number_at": timing.number_at,
        },
        "rounds": [
            {
                "game": game.title,
                "round": i + 1,
                "clips": round_manifests[i]["clips"],
            }
            for i, game in enumerate(project.games)
        ],
        "events": {
            "rounds_at": [cover_duration + i * timing.total for i in range(6)],
            "reveals_at": [
                cover_duration + i * timing.total + timing.reveal_at for i in range(6)
            ],
        },
        "music": _rel(music),
        "beatmap": _rel(beatmap_file),
        "font": _rel(font_file),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def build_short_preview(
    project_id: str,
    games: int = 3,
    beatmap_path: Path | None = None,
    durations: tuple[float, ...] | None = None,
    music_path: Path | None = None,
) -> dict:
    """Build an exact-frame montage of the first N approved rounds."""
    project = Project.load(project_dir(project_id))
    games = max(1, min(int(games), len(project.games)))
    ensure_music(60.0)
    music = Path(music_path).resolve() if music_path else MUSIC
    beatmap_file = Path(beatmap_path).resolve() if beatmap_path else BEATMAP
    timing = make_round_timing(load_beatmap(beatmap_file), durations or DEFAULT_CLIP_DURATIONS)
    duration = round(timing.total * games, 3)
    if media_duration(music) < duration:
        raise InsufficientMaterial(f"Musica troppo corta: {media_duration(music):.1f}s per {duration:.1f}s.")
    missing = [g.title for g in project.games[:games] if not project.ascii_ready_for_game(g)]
    if missing:
        raise InsufficientMaterial(
            "Servono tre indizi ASCII approvati e il reveal per: " + ", ".join(missing)
        )
    work = project.path / "work" / "preview_rounds"
    work.mkdir(parents=True, exist_ok=True)
    manifests = [
        build_game_round(
            project, i, outdir=work / f"round_{i + 1}", timing=timing,
            beatmap_path=beatmap_file, music_path=music,
        )
        for i in range(games)
    ]
    rounds = [work / f"round_{i + 1}" / "round_01.mp4" for i in range(games)]
    filters = "".join(f"[{i}:v]setsar=1[v{i}];" for i in range(games))
    filters += "".join(f"[v{i}]" for i in range(games))
    filters += f"concat=n={games}:v=1:a=0[v]"
    outdir = project.path / "output"
    outdir.mkdir(parents=True, exist_ok=True)
    output = outdir / "short_preview.mp4"
    cmd = [ffmpeg_bin(), "-y", "-v", "error"]
    for path in rounds:
        cmd += ["-i", str(path)]
    cmd += ["-i", str(music)]
    cmd += [
        "-filter_complex", filters, "-map", "[v]", "-map", f"{games}:a",
        "-t", f"{duration}", "-r", str(FPS), *video_encode_args(18),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(output),
    ]
    subprocess.run(cmd, check=True)
    info = probe(output)
    expected_frames = int(round(duration * FPS))
    if info["frames"] != expected_frames or abs(info["duration"] - duration) > 0.1:
        raise RuntimeError(f"Montaggio preview inatteso: {info}, attesi {expected_frames} frame.")
    manifest = {
        "project": project_id,
        "games": games,
        "duration": duration,
        "frames": expected_frames,
        "resolution": [W, H],
        "fps": FPS,
        "output": _rel(output),
        "sha256": {"output": sha256(output), "music": sha256(music)},
        "rounds": [
            {"game": project.games[i].title, "round": i + 1,
             "output": _rel(rounds[i]), "clips": manifests[i]["clips"]}
            for i in range(games)
        ],
        "timing": {
            "clip_durations": list(timing.clip_durations),
            "reveal_at": timing.reveal_at,
            "number_at": timing.number_at,
        },
        "music": _rel(music),
        "beatmap": _rel(beatmap_file),
    }
    (outdir / "short_preview_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest
