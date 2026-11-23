from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from gcf.ascii import luma, media, preset, render, spatial, tone
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
    grid = (data["grid"]["cols"], data["grid"]["rows"])
    ren = Image.open(still_path or _still_path(candidate)).convert("RGB")
    cells, edge, lit, rgb, rgb_render = _cell_arrays(source, ren, grid)
    structure = _pearson(edge, lit)
    edge_threshold = float(np.percentile(edge, 70))
    dark = (cells < data["shadow"]) & (edge >= edge_threshold)
    shadow = float(np.mean(lit[dark] > 0.005)) if np.any(dark) else 0.0
    empty = float(np.mean(lit < 0.005))
    blocks = []
    for by in range(6):
        for bx in range(8):
            y0, y1 = by * grid[1] // 6, (by + 1) * grid[1] // 6
            x0, x1 = bx * grid[0] // 8, (bx + 1) * grid[0] // 8
            blocks.append(float(np.mean(lit[y0:y1, x0:x1] > 0.005)))
    occupied = sum(blocks)
    entropy = 0.0
    if occupied and len(blocks) > 1:
        for value in blocks:
            if value > 0:
                p = value / occupied
                entropy -= p * math.log(p)
        entropy /= math.log(len(blocks))
    if candidate.ascii_mode == "spatial" and candidate.spatial:
        index_path = Path(candidate.spatial["dir"]) / "idx" / f"i_{frame:04d}.png"
        if index_path.exists():
            idx = np.asarray(Image.open(index_path).convert("L"), dtype=np.float32) / 32.0
        else:
            idx = np.rint(lit * 8.0)
    else:
        idx = np.rint(lit * 8.0)
    high = float(np.mean(idx >= 7))
    saturation = max(0.0, 1.0 - max(0.0, high - 0.45))
    visible = lit > 0.08
    color_error = (float(np.mean(np.abs(rgb[visible] - rgb_render[visible])))
                   if np.any(visible) else 1.0)
    color = max(0.0, 1.0 - min(1.0, color_error * 2.5))
    density = entropy * (0.45 if (empty < 0.10 or empty > 0.85) else 1.0)
    mean = float(np.mean(np.asarray(ren.convert("L"), dtype=np.float32)) / 255.0)
    max_pixel = int(np.asarray(ren.convert("L")).max())
    return {"structure": round(structure, 4), "shadow": round(shadow, 4),
            "density": round(density, 4), "empty": round(empty, 4),
            "saturation": round(saturation, 4), "color": round(color, 4),
            "render_mean": round(mean * 255, 2), "render_max": max_pixel,
            "lit": lit}


def _score(metrics: dict, temporal: float) -> float:
    if metrics["render_max"] < 8 or metrics["render_mean"] < 0.75:
        return -1.0
    if metrics["empty"] > 0.95:
        return -1.0
    temporal_score = max(0.0, 1.0 - min(1.0, temporal * 5.0))
    return (0.35 * metrics["structure"] + 0.15 * metrics["shadow"]
            + 0.20 * metrics["density"] + 0.05 * metrics["saturation"]
            + 0.05 * metrics["color"] + 0.10 * temporal_score)


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


def _windows_for(candidate, source: str, fmt: str, start: float, duration: float,
                 evidence: Path, tag: str, cols: int, rows: int) -> dict:
    metrics = []
    invalid = []
    excess = []
    samples = []
    for w, rel in enumerate((0.15, 0.45, 0.75)):
        first = max(1, int(round(rel * duration * 30)) + 1)
        last = first + 2
        outdir = candidate.path / "temp" / f"selector_w{w}"
        frames = render.render_window(candidate, first, last, outdir)
        srcs = _source_window(source, fmt, start + (first - 1) / 30.0, 3,
                              evidence / f"{tag}_src_w{w}")
        n = min(len(frames), len(srcs))
        for f in frames[:n]:
            im = Image.open(f).convert("L")
            h = im.histogram()
            mean = sum(k * c for k, c in enumerate(h)) / (im.width * im.height)
            hi = max(i for i, c in enumerate(h) if c)
            if mean < 0.75 or hi < 8:
                invalid.append((w, f.name, round(mean, 2), hi))
        if n < 2:
            continue
        mid = n // 2
        src = Image.open(srcs[mid]).convert("RGB")
        ren = frames[mid]
        m = _candidate_metrics(candidate, candidate, candidate, src, first + mid,
                               still_path=ren)
        metrics.append(m)
        samples.append({"window": w, "source": str(srcs[mid]), "candidate": str(ren)})
        lits = [_lit_cells(f, cols, rows) for f in frames[:n]]
        src_cells = [luma.linear_cells(Image.open(s).convert("RGB"), cols, rows)
                     for s in srcs[:n]]
        idxs = [_index_cells(candidate, first + i, lits[i]) for i in range(n)]
        for i in range(1, n):
            sd = float(np.mean(np.abs(src_cells[i] - src_cells[i - 1])))
            cd = float(np.mean(np.abs(idxs[i] - idxs[i - 1])))
            excess.append(max(0.0, cd - sd * 8.0 * 1.5))
    avg = {}
    for key in ("structure", "shadow", "density", "empty", "saturation", "color",
                "render_mean", "render_max"):
        vals = [m[key] for m in metrics if key in m]
        avg[key] = round(float(np.mean(vals)), 4) if vals else 0.0
    temporal = float(np.mean(excess)) if excess else 1.0
    score = -1.0 if invalid or avg.get("render_max", 0) < 8 else _score(avg, min(0.2, temporal))
    return {"metrics": avg, "temporal_excess": round(temporal, 4),
            "invalid_frames": invalid, "score": round(score, 4),
            "frames": len(metrics), "samples": samples}


def evaluate_shot(source: str, fmt: str, start: float, duration: float,
                  evidence_dir: Path, tag: str, windows: int = 3,
                  compare_color: bool = True) -> dict:
    """Evaluate Legacy/Spatial/Conservative on representative consecutive windows."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    grid = preset.grid_for(fmt, 81)
    mid = _source_frame(source, start + duration / 2, evidence_dir / f"{tag}_char.png", fmt)
    cells = luma.linear_cells(mid, grid["cols"], grid["rows"]).ravel()
    p50m = float(np.median(cells))
    satm = float(np.mean(np.asarray(mid.convert("HSV").getchannel("S"), dtype=np.float32)) / 255.0)
    character = {"p50": round(p50m, 4), "sat": round(satm, 3),
                 "color_mode": 0.0 if satm > 0.18 and p50m > 0.015 else 1.0}
    character["auto_correction"] = bool(character["color_mode"] == 1.0 and p50m < 0.03)
    base_params = {"gamma": 0.82, "shadow": 0.31, "contrast_high": 0.85}
    candidates = {}
    for name, spec in CANDIDATES.items():
        params = {**base_params, "density": spec["density"],
                  "color_mode": character["color_mode"],
                  "auto_correction": character["auto_correction"]}
        cand = AsciiProject.create(source, fmt, start, duration, params,
                                   title=f"M71 {tag} {name}", ascii_mode=spec["mode"],
                                   spatial_variant=spec["variant"])
        result = _windows_for(cand, source, fmt, start, duration, evidence_dir,
                              f"{tag}_{name}", grid["cols"], grid["rows"])
        candidates[name] = {"project": str(cand.path), "mode": spec["mode"],
                            "variant": spec["variant"], "density": spec["density"],
                            "color_mode": character["color_mode"], **result}
    ordered = sorted(candidates.items(), key=lambda kv: kv[1]["score"], reverse=True)
    chosen = ordered[0][0]
    reason = "highest score"
    if candidates["legacy"]["score"] >= ordered[0][1]["score"] - 0.010:
        chosen = "legacy"
        reason = "baseline within margin"
    elif len(ordered) > 1 and ordered[0][1]["score"] - ordered[1][1]["score"] < 0.008:
        stable = min((ordered[0], ordered[1]), key=lambda kv: kv[1]["temporal_excess"])
        chosen = stable[0]
        reason = "close scores, lower temporal excess"
    unreadable = ordered[0][1]["score"] < 0.30 or all(v["score"] < 0 for v in candidates.values())
    if unreadable:
        chosen = "none"
        reason = "no acceptable candidate"
    color_alt = None
    if compare_color and chosen != "none":
        spec = CANDIDATES[chosen]
        alt_color = 1.0 - character["color_mode"]
        params = {**base_params, "density": spec["density"], "color_mode": alt_color,
                  "auto_correction": bool(alt_color == 1.0 and p50m < 0.03)}
        alt = AsciiProject.create(source, fmt, start, duration, params,
                                  title=f"M71 {tag} {chosen} altcolor",
                                  ascii_mode=spec["mode"], spatial_variant=spec["variant"])
        alt_result = _windows_for(alt, source, fmt, start, duration, evidence_dir,
                                  f"{tag}_{chosen}_alt", grid["cols"], grid["rows"])
        color_alt = {"project": str(alt.path), "color_mode": alt_color, **alt_result}
        if alt_result["score"] > candidates[chosen]["score"] + 0.010:
            keep_project = str(alt.path)
            candidates[chosen].update(alt_result)
            candidates[chosen]["project"] = keep_project
            candidates[chosen]["color_mode"] = alt_color
            reason += "; alternate color wins visual-render score"
    return {"tag": tag, "source": source, "format": fmt, "start": start,
            "end": start + duration, "duration": duration, "character": character,
            "candidates": candidates, "color_alt": color_alt,
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
    plan = tone.build_plan(shadow, shadow.working_info["fps"], data["shadow"], data["white"],
                           auto=bool(project.params.get("auto_correction", False)),
                           overrides=project.params.get("correction_overrides"),
                           analysis_grid=(144, 81), ramp=data["ramp"])
    shots = _shots(plan)
    base_params = {k: v for k, v in project.params.items()
                   if k in ("gamma", "shadow", "contrast_high", "local_contrast",
                            "contrast_low", "auto_correction")}
    rows = []
    for si, (start, end) in enumerate(shots):
        duration = end - start
        character = _shot_character(shadow, start, end)
        candidates = {}
        for name, spec in CANDIDATES.items():
            params = {**base_params, "density": spec["density"],
                      "color_mode": character["color_mode"],
                      "auto_correction": character["auto_correction"]}
            cand = AsciiProject.create(
                project.source, project.format, project.interval_start + start, duration,
                params, title=f"M7 {project.id} s{si} {name}",
                ascii_mode=spec["mode"], spatial_variant=spec["variant"])
            first_t = max(0.15, duration * 0.25)
            second_t = max(first_t + 0.1, duration * 0.65)
            stills = []
            metrics = []
            for k, at in enumerate((first_t, second_t)):
                try:
                    path = render.still(cand, at)
                    copy = evidence_dir / f"s{si}_{name}_{k}.png"
                    shutil.copy2(path, copy)
                    stills.append(str(copy))
                    frame = max(1, min(int(round(at * 30)) + 1,
                                       int(round(cand.working_info["duration"] * 30))))
                    src = _source_frame(project.source, project.interval_start + start + at,
                                        evidence_dir / f"src_s{si}_{k}.png", project.format)
                    metrics.append(_candidate_metrics(project, cand, project, src, frame))
                except Exception as exc:
                    stills.append("")
                    metrics.append({"error": str(exc), "lit": None})
            if metrics and "lit" in metrics[0]:
                temporal = float(np.mean(np.abs(metrics[0]["lit"] - metrics[1]["lit"]))) \
                    if len(metrics) > 1 and metrics[1].get("lit") is not None else 1.0
            else:
                temporal = 1.0
            avg = {}
            for key in ("structure", "shadow", "density", "empty", "saturation", "color",
                        "render_mean", "render_max"):
                vals = [m[key] for m in metrics if key in m]
                avg[key] = round(float(np.mean(vals)), 4) if vals else 0.0
            score = _score(avg, temporal) if avg.get("render_max", 0) >= 8 else -1.0
            candidates[name] = {
                "project": str(cand.path), "mode": spec["mode"], "variant": spec["variant"],
                "density": spec["density"], "stills": stills, "metrics": avg,
                "temporal": round(temporal, 4), "score": round(score, 4),
                "error": next((m.get("error") for m in metrics if m.get("error")), ""),
            }
            if progress:
                progress(si + 1, len(shots), name, score)
        ordered = sorted(candidates.items(), key=lambda kv: kv[1]["score"], reverse=True)
        chosen = ordered[0][0]
        reason = "highest score"
        if candidates["legacy"]["score"] >= ordered[0][1]["score"] - 0.010:
            chosen = "legacy"
            reason = "baseline within margin"
        elif len(ordered) > 1 and ordered[0][1]["score"] - ordered[1][1]["score"] < 0.008:
            stable = min((ordered[0], ordered[1]), key=lambda kv: kv[1]["temporal"])
            chosen = stable[0]
            reason = "close scores, lower temporal delta"
        rows.append({
            "shot": si, "start": round(start, 3), "end": round(end, 3),
            "duration": round(duration, 3), "character": character,
            "candidates": candidates, "selected": chosen, "reason": reason,
        })
    selection = {
        "version": 1,
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


def rescore(selection: dict, project, evidence_dir: Path) -> dict:
    """Recompute metrics/scores from the saved candidate stills."""
    for row in selection["shots"]:
        si = row["shot"]
        duration = row["duration"]
        first = max(0.15, duration * 0.25)
        ats = (first, max(first + 0.1, duration * 0.65))
        for name, candidate in row["candidates"].items():
            cand = AsciiProject.load(Path(candidate["project"]))
            metrics = []
            for k, at in enumerate(ats):
                still = candidate["stills"][k] if k < len(candidate["stills"]) else ""
                src_path = evidence_dir / f"src_s{si}_{k}.png"
                if not still or not src_path.exists():
                    metrics.append({"error": "still/source missing", "lit": None})
                    continue
                frame = max(1, min(int(round(at * 30)) + 1,
                                   int(round(cand.working_info["duration"] * 30))))
                metrics.append(_candidate_metrics(project, cand, project,
                                                  Image.open(src_path).convert("RGB"),
                                                  frame, still))
            if metrics and "lit" in metrics[0]:
                temporal = (float(np.mean(np.abs(metrics[0]["lit"] - metrics[1]["lit"])))
                            if len(metrics) > 1 and metrics[1].get("lit") is not None else 1.0)
            else:
                temporal = 1.0
            avg = {}
            for key in ("structure", "shadow", "density", "empty", "saturation",
                        "color", "render_mean", "render_max"):
                vals = [m[key] for m in metrics if key in m]
                avg[key] = round(float(np.mean(vals)), 4) if vals else 0.0
            candidate["metrics"] = avg
            candidate["temporal"] = round(temporal, 4)
            candidate["score"] = round(_score(avg, temporal) if avg.get("render_max", 0) >= 8 else -1.0, 4)
        ordered = sorted(row["candidates"].items(), key=lambda kv: kv[1]["score"], reverse=True)
        chosen = ordered[0][0]
        reason = "highest score"
        if row["candidates"]["legacy"]["score"] >= ordered[0][1]["score"] - 0.010:
            chosen = "legacy"
            reason = "baseline within margin"
        elif len(ordered) > 1 and ordered[0][1]["score"] - ordered[1][1]["score"] < 0.008:
            stable = min((ordered[0], ordered[1]), key=lambda kv: kv[1]["temporal"])
            chosen = stable[0]
            reason = "close scores, lower temporal delta"
        row["selected"] = chosen
        row["reason"] = reason
    path = Path(project.selection_plan)
    path.write_text(json.dumps(selection, indent=2), encoding="utf-8")
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
        if key not in row["candidates"]:
            raise ValueError(f"Candidato non valido per shot {row['shot']}: {key}")
        files.append(_render_shot(row, key, shot_dir))
        if progress:
            progress(row["shot"] + 1, len(selection["shots"]), key, row["candidates"][key]["score"])
    lst = out.parent / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in files), encoding="utf-8")
    audio = False
    for row in selection["shots"]:
        key = choices.get(row["shot"], row["selected"])
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
