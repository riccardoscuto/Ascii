from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from gcf.ascii import luma, media, perceptual, preset, render, spatial, tone
from gcf.ascii.project import AsciiProject
from gcf.config import ffmpeg_bin

CANDIDATES = {
    "legacy": {"mode": "legacy", "variant": "d", "density": 54},
    "spatial": {"mode": "spatial", "variant": "adaptive", "density": 81},
    "conservative": {"mode": "spatial", "variant": "adaptive-conservative", "density": 81},
}


def _shots(plan: dict) -> list[tuple[float, float]]:
    total = int(plan["total_frames"]) / 30.0
    cuts = sorted(float(c) for c in plan.get("cuts", []))
    points = [0.0]
    for cut in cuts:
        if cut - points[-1] >= 0.8:
            points.append(cut)
    points.append(total)
    shots = list(zip(points, points[1:]))
    merged = []
    for start, end in shots:
        if merged and end - start < 0.8:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _shot_character(project, start: float, end: float) -> dict:
    frames = sorted((project.path / "analysis").glob("f_*.png"))
    selected = []
    for path in frames:
        t = (int(path.stem.split("_")[1]) - 1) / 10.0
        if start <= t < end:
            selected.append(path)
    if not selected:
        selected = frames[:1]
    grid = preset.grid_for(project.format, 81)
    p50 = []
    sat = []
    means = []
    for path in selected:
        im = Image.open(path).convert("RGB")
        cells = luma.linear_cells(im, grid["cols"], grid["rows"]).ravel()
        p50.append(float(np.median(cells)))
        sat.append(float(np.mean(np.asarray(im.convert("HSV").getchannel("S"), dtype=np.float32)) / 255.0))
        means.append(float(np.mean(np.asarray(im.convert("L"), dtype=np.float32)) / 255.0))
    p50m = float(np.median(p50))
    satm = float(np.median(sat))
    meanm = float(np.median(means))
    color = 0.0 if satm > 0.18 and p50m > 0.015 else 1.0
    auto = bool(color == 1.0 and p50m < 0.03)
    return {"p50": round(p50m, 4), "sat": round(satm, 3), "mean": round(meanm, 3),
            "color_mode": color, "auto_correction": auto, "analysis_frames": len(selected)}


def _still_path(project) -> Path:
    files = sorted((project.path / "preview").glob("still_*.png"))
    if not files:
        raise RuntimeError("Still del candidato assente.")
    return files[-1]


def _resolution(fmt: str) -> tuple[int, int]:
    return tuple(preset.grid_for(fmt, 81)["resolution"])


def _source_frame(source: str, t: float, out: Path, fmt: str = "horizontal") -> Image.Image:
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        w, h = _resolution(fmt)
        subprocess.run([ffmpeg_bin(), "-y", "-v", "error", "-ss", f"{t:.4f}",
                        "-i", source, "-frames:v", "1",
                        "-vf", f"scale={w}:{h},setsar=1", str(out)], check=True)
    return Image.open(out).convert("RGB")


def _cell_arrays(source: Image.Image, render_im: Image.Image, grid: tuple[int, int]):
    cols, rows = grid
    lum = luma.linear_luma_array(source)
    cells = luma.linear_cells(source, cols, rows)
    edge = luma.local_range(lum, 1)
    edge_img = Image.fromarray(edge, mode="F").resize((cols, rows), Image.Resampling.BOX)
    edge_cells = np.asarray(edge_img, dtype=np.float32)
    mask = render_im.convert("L").point(lambda v: 255 if v >= 16 else 0)
    lit = np.asarray(mask.resize((cols, rows), Image.Resampling.BOX), dtype=np.float32) / 255.0
    rgb = np.asarray(source.resize((cols, rows), Image.Resampling.BOX), dtype=np.float32) / 255.0
    rgb_render = np.asarray(render_im.resize((cols, rows), Image.Resampling.BOX), dtype=np.float32) / 255.0
    return cells, edge_cells, lit, rgb, rgb_render


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = a.ravel().astype(np.float32)
    b = b.ravel().astype(np.float32)
    if float(a.std()) < 1e-8 or float(b.std()) < 1e-8:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _candidate_metrics(project, candidate, client_project, source: Image.Image,
                       frame: int, still_path: str | Path | None = None) -> dict:
    data = preset.resolve(candidate)
    ren = Image.open(still_path or _still_path(candidate)).convert("RGB")
    m = perceptual.metrics(source, ren, candidate.format, data["shadow"])
    lum = ren.convert("L")
    hist = lum.histogram()
    mean = sum(k * c for k, c in enumerate(hist)) / (lum.width * lum.height)
    max_pixel = max(i for i, c in enumerate(hist) if c)
    m.update({"render_mean": round(mean, 2), "render_max": max_pixel})
    return m


def _score(metrics: dict, temporal: dict) -> float:
    if metrics.get("render_max", 0) < 8 or metrics.get("render_mean", 0) < 0.75:
        return -1.0
    flicker = float(temporal.get("flicker", 1.0))
    motion = float(temporal.get("motion_corr", 0.0))
    temporal_score = 0.6 * max(0.0, 1.0 - min(1.0, flicker * 8.0)) + 0.4 * max(0.0, motion)
    return (0.30 * metrics["structure"] + 0.10 * metrics["edge_ssim"]
            + 0.15 * metrics["shadow"] + 0.10 * metrics["highlight"]
            + 0.15 * metrics["uniform"] + 0.05 * metrics["color"]
            + 0.10 * metrics["ui"] + 0.05 * temporal_score)


def _source_window(source: str, fmt: str, t: float, count: int, prefix: Path) -> list[Path]:
    w, h = _resolution(fmt)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg_bin(), "-y", "-v", "error", "-ss", f"{t:.4f}",
                    "-i", source, "-frames:v", str(count),
                    "-vf", f"fps=30,scale={w}:{h},setsar=1",
                    str(prefix) + "_%02d.png"], check=True)
    return sorted(prefix.parent.glob(prefix.name + "_*.png"))[:count]


def _lit_cells(path: Path, cols: int, rows: int) -> np.ndarray:
    im = Image.open(path).convert("L").point(lambda v: 255 if v >= 16 else 0)
    return np.asarray(im.resize((cols, rows), Image.Resampling.BOX), dtype=np.float32) / 255.0


def _index_cells(candidate, frame: int, lit: np.ndarray) -> np.ndarray:
    if candidate.ascii_mode == "spatial" and candidate.spatial:
        p = Path(candidate.spatial["dir"]) / "idx" / f"i_{frame:04d}.png"
        if p.exists():
            return np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 32.0
    return np.rint(lit * 8.0)


def _source_stats(frames: list[Path]) -> dict:
    if not frames:
        return {"p50": 0.0, "p95": 0.0, "mean": 0.0, "sat": 0.0,
                "black": True, "frames": 0}
    p50, p95, means, sats = [], [], [], []
    for path in frames:
        im = Image.open(path).convert("RGB")
        lum = luma.linear_luma_array(im)
        p50.append(float(np.percentile(lum, 50)))
        p95.append(float(np.percentile(lum, 95)))
        means.append(float(np.mean(lum)))
        sats.append(float(np.mean(np.asarray(im.convert("HSV").getchannel("S"),
                                           dtype=np.float32)) / 255.0))
    black = bool(max(p95) < 0.02 and max(means) < 0.005)
    return {"p50": round(float(np.median(p50)), 4),
            "p95": round(float(np.median(p95)), 4),
            "mean": round(float(np.median(means)), 4),
            "sat": round(float(np.median(sats)), 3),
            "black": black, "frames": len(frames)}


def _windows_for(candidate, fmt: str, source_windows: list[list[Path]],
                 evidence: Path, tag: str, cols: int, rows: int) -> dict:
    metrics = []
    invalid = []
    window_errors = []
    temporal = {"flicker": 0.0, "motion_corr": 0.0, "static_motion": 0.0}
    samples = []
    for w, srcs in enumerate(source_windows):
        rel = (0.15, 0.45, 0.75)[w]
        first = max(1, int(round(rel * candidate.interval_duration * 30)) + 1)
        last = first + 2
        outdir = candidate.path / "temp" / f"selector_w{w}"
        frames = None
        error = ""
        for attempt in range(2):
            try:
                frames = render.render_window(candidate, first, last, outdir)
                if len(frames) == 3:
                    break
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        if frames is None or len(frames) < 2:
            window_errors.append({"window": w, "reason": "render", "error": error})
            continue
        if len(frames) != 3 or len(srcs) != 3:
            window_errors.append({"window": w, "frames": len(frames),
                                  "source_frames": len(srcs)})
        n = min(len(frames), len(srcs))
        if n < 2:
            window_errors.append({"window": w, "reason": "incomplete"})
            continue
        for frame_index, f in enumerate(frames[:n]):
            im = Image.open(f).convert("L")
            h = im.histogram()
            mean = sum(k * c for k, c in enumerate(h)) / (im.width * im.height)
            hi = max(i for i, c in enumerate(h) if c)
            source_im = Image.open(srcs[frame_index]).convert("L")
            source_hist = source_im.histogram()
            source_mean = (sum(k * c for k, c in enumerate(source_hist))
                           / (source_im.width * source_im.height))
            if (mean < 0.75 or hi < 8) and source_mean > 2.0:
                invalid.append((w, f.name, round(mean, 2), hi))
        mid = n // 2
        src = Image.open(srcs[mid]).convert("RGB")
        ren = frames[mid]
        m = _candidate_metrics(candidate, candidate, candidate, src, first + mid,
                               still_path=ren)
        metrics.append(m)
        samples.append({"window": w, "source": str(srcs[mid]), "candidate": str(ren)})
        if n >= 2:
            pair = perceptual.temporal_flicker(
                [Image.open(s).convert("RGB") for s in srcs[:n]],
                [Image.open(f).convert("RGB") for f in frames[:n]], fmt)
            temporal["flicker"] = max(temporal["flicker"], pair["flicker"])
            temporal["motion_corr"] = max(temporal["motion_corr"], pair["motion_corr"])
            temporal["static_motion"] = max(temporal["static_motion"], pair["static_motion"])
    avg = {}
    for key in ("structure", "ssim", "ssim_cov", "ssim_glyph", "edge_ssim",
                "shadow", "highlight", "uniform", "color", "ui", "coverage",
                "coverage_std", "edge_corr", "contrast", "glyph_luma",
                "render_mean", "render_max"):
        vals = [m[key] for m in metrics if key in m]
        avg[key] = round(float(np.mean(vals)), 4) if vals else 0.0
    valid = len(metrics) >= 2 and not window_errors and not invalid
    score = _score(avg, temporal) if valid else -1.0
    return {"metrics": avg, "temporal": temporal,
            "invalid_frames": invalid, "window_errors": window_errors,
            "score": round(score, 4), "frames": len(metrics), "samples": samples}


def evaluate_shot(source: str, fmt: str, start: float, duration: float,
                  evidence_dir: Path, tag: str, windows: int = 3,
                  compare_color: bool = True, base_params: dict | None = None,
                  already_working: bool = False) -> dict:
    """Evaluate Legacy/Spatial/Conservative on representative windows.

    Source statistics come from the same frames used for every candidate, so
    black scenes, failed conversions and technical render errors are distinct.
    """
    evidence_dir.mkdir(parents=True, exist_ok=True)
    original_source = source
    original_start = start
    base_params = {**(base_params or {}), "gamma": (base_params or {}).get("gamma", 0.82),
                   "shadow": (base_params or {}).get("shadow", 0.31),
                   "contrast_high": (base_params or {}).get("contrast_high", 0.85)}
    if not already_working:
        probe = AsciiProject.create(source, fmt, start, duration, base_params,
                                    title=f"M72 probe {tag}", ascii_mode="legacy")
        media.prepare_working(probe)
        source = probe.working_source
        start = 0.0
    rels = (0.15, 0.45, 0.75)
    source_windows = []
    for w, rel in enumerate(rels):
        source_windows.append(_source_window(source, fmt, start + rel * duration, 3,
                                              evidence_dir / f"{tag}_src_w{w}"))
    stats = _source_stats([p for window in source_windows for p in window])
    grid = perceptual.detail_grid(fmt)
    p50s, sats = [], []
    for window in source_windows:
        for path in window:
            im = Image.open(path).convert("RGB")
            cells = luma.linear_cells(im, grid[0], grid[1]).ravel()
            p50s.append(float(np.median(cells)))
            sats.append(float(np.mean(np.asarray(im.convert("HSV").getchannel("S"),
                                                 dtype=np.float32)) / 255.0))
    p50m = float(np.median(p50s)) if p50s else 0.0
    satm = float(np.median(sats)) if sats else 0.0
    color_mode = 0.0 if satm > 0.18 and p50m > 0.015 else 1.0
    auto = bool(not stats["black"] and stats["p50"] < 0.09
                and stats["p95"] > 0.12 and stats["p95"] - stats["p50"] > 0.05)
    conversion_failed = False
    if not already_working:
        try:
            original = _source_frame(original_source, original_start + duration / 2,
                                     evidence_dir / f"{tag}_original_check.png", fmt)
            original_p95 = float(np.percentile(luma.linear_luma_array(original), 95))
            conversion_failed = bool(original_p95 > 0.05 and stats["p95"] < 0.02)
        except Exception:
            conversion_failed = False
    character = {"p50": round(p50m, 4), "sat": round(satm, 3),
                 "p95": stats["p95"], "mean": stats["mean"],
                 "color_mode": color_mode, "auto_correction": auto,
                 "scene_black": stats["black"],
                 "conversion_failed": conversion_failed,
                 "analysis_frames": stats["frames"]}
    candidates = {}
    for name, spec in CANDIDATES.items():
        variants = {}
        for color in (character["color_mode"], 1.0 - character["color_mode"]):
            params = {**base_params, "density": spec["density"],
                      "color_mode": color, "auto_correction": auto}
            try:
                cand = AsciiProject.create(source, fmt, start, duration, params,
                                           title=f"M72 {tag} {name} c{int(color)}",
                                           ascii_mode=spec["mode"],
                                           spatial_variant=spec["variant"])
                cgrid = perceptual.common_grid(fmt)
                result = _windows_for(cand, fmt, source_windows, evidence_dir,
                                      f"{tag}_{name}_c{int(color)}", cgrid[0], cgrid[1])
                variants[color] = {"project": str(cand.path), "mode": spec["mode"],
                                   "variant": spec["variant"], "density": spec["density"],
                                   "color_mode": color, **result}
            except Exception as exc:
                variants[color] = {"project": "", "mode": spec["mode"],
                                   "variant": spec["variant"], "density": spec["density"],
                                   "color_mode": color, "metrics": {}, "score": -1.0,
                                   "temporal": {"flicker": 1.0, "motion_corr": 0.0},
                                   "invalid_frames": [], "window_errors": [
                                       {"reason": "candidate", "error": f"{type(exc).__name__}: {exc}"}],
                                   "frames": 0, "samples": []}
        valid = {c: v for c, v in variants.items() if v["score"] >= 0}
        if valid:
            best_color = max(valid, key=lambda c: valid[c]["score"])
        else:
            best_color = min(variants, key=lambda c: len(variants[c].get("window_errors", [])))
        candidates[name] = variants[best_color]
        candidates[name]["color_variants"] = {str(int(c)): variants[c]["score"] for c in variants}
    ordered = sorted(candidates.items(), key=lambda kv: kv[1]["score"], reverse=True)
    chosen = ordered[0][0]
    reason = "highest score"
    if candidates["legacy"]["score"] >= ordered[0][1]["score"] - 0.010 and ordered[0][1]["score"] >= 0:
        chosen = "legacy"
        reason = "baseline within margin"
    elif (len(ordered) > 1 and ordered[0][1]["score"] >= 0
          and 0 <= ordered[0][1]["score"] - ordered[1][1]["score"] < 0.008):
        stable = min((ordered[0], ordered[1]),
                     key=lambda kv: kv[1]["temporal"]["flicker"])
        chosen = stable[0]
        reason = "close scores, lower static-cell flicker"
    technical = all(v["score"] < 0 for v in candidates.values())
    if stats["black"]:
        chosen, reason = "none", "intentional black scene"
    elif conversion_failed:
        chosen, reason = "none", "source conversion failed"
    elif technical:
        chosen, reason = "none", "technical render failure"
    elif ordered[0][1]["score"] < 0.30:
        chosen, reason = "none", "no acceptable candidate"
    unreadable = chosen == "none"
    return {"tag": tag, "source": original_source, "working_source": source,
            "format": fmt, "start": start, "end": start + duration,
            "duration": duration, "character": character,
            "source_stats": stats, "candidates": candidates,
            "selected": chosen, "reason": reason, "unreadable": unreadable}


def select(project, evidence_dir: Path, progress=None) -> dict:
    """Build an offline per-shot selection plan without mutating the source project."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    shadow = AsciiProject.create(project.source, project.format, project.interval_start,
                                project.interval_duration, project.params,
                                title=f"{project.title} auto", ascii_mode="auto")
    media.prepare_working(shadow)
    media.extract_analysis(shadow)
    shadow.params["density"] = 81
    shadow.save()
    data = preset.resolve(shadow)
    grid = preset.grid_for(shadow.format, 81)
    plan = tone.build_plan(shadow, shadow.working_info["fps"], data["shadow"], data["white"],
                           auto=bool(project.params.get("auto_correction", False)),
                           overrides=project.params.get("correction_overrides"),
                           analysis_grid=(grid["cols"], grid["rows"]), ramp=data["ramp"])
    shots = _shots(plan)
    base_params = {k: v for k, v in project.params.items()
                   if k in ("gamma", "shadow", "contrast_high", "local_contrast",
                            "contrast_low", "auto_correction")}
    rows = []
    for si, (start, end) in enumerate(shots):
        row = evaluate_shot(shadow.working_source, shadow.format, start, end - start,
                            evidence_dir, f"{shadow.id}_s{si}", compare_color=True,
                            base_params=base_params, already_working=True)
        row.update({"shot": si, "start": round(start, 3), "end": round(end, 3),
                    "duration": round(end - start, 3)})
        rows.append(row)
        if progress:
            score = row["candidates"].get(row["selected"], {}).get("score", -1)
            progress(si + 1, len(shots), 0, 0, f"Shot {si + 1} · {row['selected']} · {score}")
    selection = {
        "version": 3,
        "engine": "unified-m8-metrics",
        "mode": "auto",
        "source": project.source,
        "source_sha1": spatial._sha1(Path(shadow.working_source)),
        "preset_sha1": spatial._sha1(spatial.PRESET_BLEND),
        "plan": str(shadow.plan_path),
        "selector_project": str(shadow.path),
        "shots": rows,
        "renderer_version": spatial.RENDERER_VERSION,
    }
    plan_path = shadow.path / "temp" / "selection_plan.json"
    plan_path.write_text(json.dumps(selection, indent=2), encoding="utf-8")
    shadow.selection_plan = str(plan_path)
    shadow.ascii_mode = "auto"
    shadow.save()
    selection["selection_plan"] = str(plan_path)
    return selection


def _render_shot(row: dict, key: str, out_dir: Path) -> Path:
    cand = AsciiProject.load(Path(row["candidates"][key]["project"]))
    outputs = render.render(cand)
    out = out_dir / f"s{row['shot']:02d}_{key}.mp4"
    shutil.copy2(outputs["master"], out)
    return out


def render_plan(selection: dict, project, choices: dict[int, str], out: Path,
                progress=None) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    shot_dir = out.parent / "shots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for row in selection["shots"]:
        key = choices.get(row["shot"], row["selected"])
        if key == "none":
            raise RuntimeError(f"Shot {row['shot']} non recuperabile: nessun candidato valido.")
        if key not in row["candidates"]:
            raise ValueError(f"Candidato non valido per shot {row['shot']}: {key}")
        files.append(_render_shot(row, key, shot_dir))
        if progress:
            progress(row["shot"] + 1, len(selection["shots"]), 0, 0,
                     f"Shot {row['shot'] + 1} · {key}")
    lst = out.parent / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in files), encoding="utf-8")
    audio = False
    for row in selection["shots"]:
        key = choices.get(row["shot"], row["selected"])
        if key == "none":
            continue
        info = json.loads((Path(row["candidates"][key]["project"]) / "project.json").read_text())
        if (info.get("working_info") or {}).get("has_audio"):
            audio = True
            break
    cmd = [ffmpeg_bin(), "-y", "-v", "error", "-f", "concat", "-safe", "0",
           "-i", str(lst), "-map", "0:v:0"]
    if audio:
        cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    return out
