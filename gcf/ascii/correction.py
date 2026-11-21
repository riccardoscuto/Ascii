from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

COLS, ROWS = 96, 54
RAMP = " .,:;+HW@"
INDEX_MAX = len(RAMP) - 1

# The look actually produced by the current adaptive plan (v2 baseline).
BASE = {"shadow": 0.234, "white": 0.91, "gamma": 0.82,
        "contrast_low": 0.18, "contrast_high": 0.85, "local_contrast": 0.24}
LIMITS = {
    "shadow": (0.005, 0.31),
    "white": (0.26, 0.97),
    "gamma": (0.78, 1.02),
    "contrast_low": (0.005, 0.18),
    "contrast_high": (0.70, 0.97),
    "local_contrast": (0.20, 0.40),
}
PARAMS = tuple(BASE)


def _clamp(value, low, high):
    return low if value < low else high if value > high else value


def _pct(sorted_values, p):
    return sorted_values[min(len(sorted_values) - 1, int(p * len(sorted_values)))] / 255.0


def _mapped_index(value, params):
    span = max(1e-6, params["white"] - params["shadow"])
    x = (value - params["shadow"]) / span
    if x <= 0:
        return 0
    if x >= 1:
        x = 1.0
    x = x ** params["gamma"]
    span = max(1e-6, params["contrast_high"] - params["contrast_low"])
    c = (x - params["contrast_low"]) / span
    if c <= 0:
        return 0
    if c >= 1:
        c = 1.0
    return int(round(c * INDEX_MAX))


def _simulate(cells, spread, params):
    visible = dense = saturated = edges = edge_visible = dark_detail = 0
    total = len(cells)
    values = []
    blocks = [[0, 0] for _ in range(48)]
    for i, (value, local) in enumerate(zip(cells, spread)):
        v = value / 255.0
        idx = _mapped_index(v, params)
        values.append(idx)
        if idx >= 1:
            visible += 1
        if idx >= 5:
            dense += 1
        if idx >= 6:
            saturated += 1
        if v < 0.345 and local / 255.0 > 0.04:
            dark_detail += 1
        if local / 255.0 >= 0.05:
            edges += 1
            if idx >= 1:
                edge_visible += 1
        bx = (i % COLS) // 12
        by = (i // COLS) // 9
        block = blocks[by * 8 + bx]
        block[1] += 1
        if idx >= 1:
            block[0] += 1
    mean = sum(values) / total
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / total)
    fractions = [c / n for c, n in blocks]
    occupied = sum(fractions)
    entropy = 0.0
    if occupied:
        for fraction in fractions:
            if fraction > 0:
                p = fraction / occupied
                entropy -= p * math.log(p)
        entropy /= math.log(len(fractions))
    return {
        "visible": visible / total,
        "dense": dense / total,
        "saturated": saturated / total,
        "dark_detail": dark_detail / total,
        "index_std": std,
        "edge_visible": (edge_visible / edges) if edges else 0.0,
        "edges": edges / total,
        "block_entropy": entropy,
        "empty_blocks": sum(1 for f in fractions if f < 0.05) / len(fractions),
        "dense_blocks": sum(1 for f in fractions if f > 0.70) / len(fractions),
    }


def _frame_stats(path: Path):
    im = Image.open(path).convert("RGB")
    gray = im.convert("L")
    cells_img = gray.resize((COLS, ROWS), Image.Resampling.BOX)
    cells = cells_img.tobytes()
    hi = gray.filter(ImageFilter.MaxFilter(3)).resize((COLS, ROWS), Image.Resampling.BOX).tobytes()
    lo = gray.filter(ImageFilter.MinFilter(3)).resize((COLS, ROWS), Image.Resampling.BOX).tobytes()
    spread = bytes(max(0, a - b) for a, b in zip(hi, lo))
    values = sorted(cells)
    hist = [0] * 32
    for value in cells:
        hist[min(31, value // 8)] += 1
    total = len(cells)
    hist = [h / total for h in hist]
    edge_hist = gray.filter(ImageFilter.FIND_EDGES).histogram()
    edge_density = sum(edge_hist[24:]) / (gray.width * gray.height)
    gray_hist = gray.histogram()
    dark = sum(gray_hist[:11]) / (gray.width * gray.height)
    clipped = sum(gray_hist[250:]) / (gray.width * gray.height)
    sat = ImageStat.Stat(im.convert("HSV").getchannel("S")).mean[0] / 255.0
    return {
        "cells": cells,
        "spread": spread,
        "hist": hist,
        "p5": _pct(values, 0.05),
        "p10": _pct(values, 0.10),
        "p25": _pct(values, 0.25),
        "p50": _pct(values, 0.50),
        "p95": _pct(values, 0.95),
        "mean": sum(cells) / (255.0 * total),
        "edge": edge_density,
        "sat": sat,
        "dark": dark,
        "clipped": clipped,
    }


def _need(sample, baseline):
    """How much this sample needs help, using tone, dark detail and density."""
    stats = _simulate(sample["cells"], sample["spread"], baseline)
    visible = stats["visible"]
    if sample["p95"] < 0.045 or sample["edge"] < 0.008:
        return 0.0, stats, "no_detail"
    if visible >= 0.28:
        visible_need = 0.0
    elif visible <= 0.08:
        visible_need = 1.0
    else:
        t = (0.28 - visible) / 0.20
        visible_need = t * t * (3 - 2 * t)
    dark_need = 0.0
    if stats["dark_detail"] >= 0.55:
        dark_need = min(1.0, (stats["dark_detail"] - 0.55) / 0.15)
    need = max(visible_need, dark_need)
    if need == 0:
        reason = "ok"
    elif dark_need > visible_need:
        reason = "medium_detail"
    elif visible <= 0.08:
        reason = "crushed"
    else:
        reason = "partial"
    return need, stats, reason


def _target(sample):
    p10, p50, p95 = sample["p10"], sample["p50"], sample["p95"]
    if p50 >= 0.18:
        # Medium/HDR scene: lift the dark half, compress highlights, keep black.
        shadow = _clamp(p10 * 0.85 + 0.07, 0.08, 0.18)
        white = _clamp(p95 * 1.2, 0.70, 0.95)
        gamma = 0.88
        low = 0.09
        high = 0.92
        local = 0.28
    else:
        # Truly dark scene: use the full range.
        shadow = _clamp(p10 * 0.85, 0.01, 0.20)
        white = _clamp(max(0.30, p95 * 1.15), shadow + 0.14, 0.95)
        gamma = _clamp(0.82 + (0.25 - p50) * 0.5, 0.82, 0.95)
        low = _clamp(0.03 if p50 < 0.12 else 0.06, 0.02, 0.12)
        high = 0.85
        local = _clamp(0.24 + (0.20 - p50) * 0.6, 0.24, 0.36)
    return {"shadow": shadow, "white": white, "gamma": gamma,
            "contrast_low": low, "contrast_high": high, "local_contrast": local}


def _mix(a, b, t):
    return {k: round(a[k] + (b[k] - a[k]) * t, 4) for k in PARAMS}


def _median(values):
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _smooth(values, alpha=0.45, window=3):
    median = [_median(values[max(0, i - window):i + window + 1]) for i in range(len(values))]
    out = []
    y = median[0] if median else 0.0
    for value in median:
        y += alpha * (value - y)
        out.append(y)
    return out


def _flashes(samples):
    flash = set()
    for i, sample in enumerate(samples):
        if i == 0:
            continue
        window = [samples[j]["mean"] for j in range(max(0, i - 4), min(len(samples), i + 5)) if j != i]
        after = [samples[j]["mean"] for j in range(i + 1, min(len(samples), i + 4))]
        previous = samples[i - 1]["mean"]
        if (window and after and sample["mean"] > previous + 0.12
                and abs(after[0] - previous) < 0.12
                and max(after) < _median(window) + 0.08):
            flash.add(i)
    return flash


def _cuts(samples, flash=None):
    flash = flash or set()
    cuts = []
    for i, sample in enumerate(samples[1:], 1):
        if i in flash or (i - 1) in flash:
            continue
        prev = samples[i - 1]
        hd = sum(abs(a - b) for a, b in zip(sample["hist"], prev["hist"])) / 2
        dl = abs(sample["mean"] - prev["mean"])
        if hd > 0.28 or (hd > 0.16 and dl > 0.09):
            cuts.append(i)
    merged = []
    for cut in cuts:
        if not merged or samples[cut]["t"] - samples[merged[-1]]["t"] > 0.4:
            merged.append(cut)
    return merged


def _episodes(samples, cuts):
    bounds = [0] + cuts + [len(samples)]
    return [(a, b) for a, b in zip(bounds, bounds[1:]) if b > a]


def _refine_cut_frames(project, times, total_frames):
    """Find the exact 30 fps frame where each cut lands, inside +-0.2 s."""
    from gcf.config import ffmpeg_bin

    source = getattr(project, "working_source", "")
    if not times or not source or not Path(source).exists():
        return [max(1, min(total_frames, int(round(float(t) * 30)) + 1)) for t in times]
    frames = []
    for t in times:
        start = max(0.0, float(t) - 0.2)
        cmd = [ffmpeg_bin(), "-v", "error", "-ss", f"{start:.4f}", "-i",
               project.working_source, "-t", "0.4", "-vf", "fps=30,scale=160:90",
               "-f", "rawvideo", "-pix_fmt", "gray", "-"]
        proc = subprocess.run(cmd, capture_output=True, check=False)
        size = 160 * 90
        data = proc.stdout
        rows = [data[i:i + size] for i in range(0, len(data) - size + 1, size)]
        best, best_score = 1, -1.0
        for i in range(1, len(rows)):
            a, b = rows[i - 1], rows[i]
            ha, hb = _hist16(a), _hist16(b)
            hd = sum(abs(x - y) for x, y in zip(ha, hb)) / 2
            dl = abs(sum(a) / size - sum(b) / size) / 255.0
            score = hd * 2 + dl * 3
            if score > best_score:
                best, best_score = i, score
        frame = int(round(start * 30)) + best + 1
        frames.append(max(1, min(total_frames, frame)))
    return frames


def _hist16(data):
    hist = [0] * 16
    for value in data:
        hist[min(15, value // 16)] += 1
    total = len(data)
    return [h / total for h in hist]


def build_auto_plan(project, fps: float, base_plan: dict, overrides=None) -> dict:
    frames = sorted((project.path / "analysis").glob("f_*.png"))
    if not frames:
        raise RuntimeError("Analisi correzione: nessun frame.")
    samples = []
    for index, path in enumerate(frames):
        data = _frame_stats(path)
        data["t"] = round(index / 10.0, 3)
        samples.append(data)

    # The baseline plan keyframes are the reference look for this source.
    base_keys = base_plan.get("keyframes", [])

    def baseline_at(t):
        frame = t * 30.0 + 1.0
        if not base_keys:
            return dict(BASE)
        if frame <= base_keys[0]["frame"]:
            return {**BASE, "shadow": base_keys[0]["shadow"], "white": base_keys[0]["white"]}
        if frame >= base_keys[-1]["frame"]:
            return {**BASE, "shadow": base_keys[-1]["shadow"], "white": base_keys[-1]["white"]}
        for a, b in zip(base_keys, base_keys[1:]):
            if a["frame"] <= frame <= b["frame"]:
                f = (frame - a["frame"]) / max(1, b["frame"] - a["frame"])
                return {**BASE,
                        "shadow": a["shadow"] + (b["shadow"] - a["shadow"]) * f,
                        "white": a["white"] + (b["white"] - a["white"]) * f}
        return dict(BASE)

    flash = _flashes(samples)
    cuts = _cuts(samples, flash)
    for t in base_plan.get("cuts", []):
        index = int(round(float(t) * 10))
        if 0 < index < len(samples) and index not in flash and (index - 1) not in flash:
            cuts.append(index)
    merged = []
    for cut in sorted(set(cuts)):
        if not merged or samples[cut]["t"] - samples[merged[-1]]["t"] > 0.4:
            merged.append(cut)
    cuts = merged
    total_frames = int(base_plan.get("total_frames") or round(project.working_info["duration"] * 30))
    switch_frames = _refine_cut_frames(project, [samples[c]["t"] for c in cuts], total_frames)
    episodes = _episodes(samples, cuts)
    episode_of = {}
    for e, (a, b) in enumerate(episodes):
        for i in range(a, b):
            episode_of[i] = e

    # Per-sample targets, smoothed inside each episode so a cut never drags.
    raw = []
    needs = []
    base_stats = []
    reasons = []
    for sample in samples:
        baseline = baseline_at(sample["t"])
        need, stats, reason = _need(sample, baseline)
        target = _target(sample)
        final = _mix(baseline, target, need)
        raw.append(final)
        needs.append(need)
        base_stats.append(stats)
        reasons.append(reason)

    smooth = [dict() for _ in samples]
    for a, b in episodes:
        series = {k: _smooth([raw[i][k] for i in range(a, b)]) for k in PARAMS}
        for offset, i in enumerate(range(a, b)):
            smooth[i] = {k: round(series[k][offset], 4) for k in PARAMS}

    # Apply manual overrides (list of {start, end, params}).
    active_overrides = []
    for row in overrides or []:
        start, end = float(row["start"]), float(row["end"])
        active_overrides.append(row)
        for i, sample in enumerate(samples):
            if start <= sample["t"] < end:
                for key, value in row.get("params", {}).items():
                    if key in PARAMS:
                        smooth[i][key] = _clamp(float(value), *LIMITS[key])

    # Keyframes every 0.3 s plus a one-frame switch at every cut.
    keys = {}

    def put(frame, values):
        frame = max(1, min(total_frames, int(frame)))
        keys[frame] = {k: round(float(values[k]), 4) for k in PARAMS}

    put(1, smooth[0])
    for e, (a, b) in enumerate(episodes):
        start_frame = switch_frames[e - 1] if e > 0 else 1
        if e > 0:
            prev = smooth[a - 1]
            put(start_frame - 1, prev)
            put(start_frame, smooth[a])
        i = a
        while i < b:
            frame = int(round(samples[i]["t"] * 30)) + 1
            if e > 0 and frame < start_frame:
                i += 3
                continue
            put(frame, smooth[i])
            i += 3
        put(int(round(samples[b - 1]["t"] * 30)) + 1, smooth[b - 1])
    put(total_frames, smooth[-1])

    keyframes = [{"frame": f, **keys[f]} for f in sorted(keys)]

    # Quality pass with the final smoothed values.
    cut_set = set(cuts)
    final_stats = []
    flagged = []
    flicker = 0.0
    for i, sample in enumerate(samples):
        stats = _simulate(sample["cells"], sample["spread"], smooth[i])
        base = base_stats[i]
        flags = []
        if i in flash:
            flags.append("flash")
            flagged.append(flags)
            final_stats.append({k: round(v, 4) for k, v in stats.items()})
            continue
        if reasons[i] == "no_detail":
            flags.append("intentional_dark")
        if stats["visible"] < 0.055 and reasons[i] in ("crushed", "partial"):
            flags.append("too_empty")
        if stats["visible"] > 0.94 and stats["visible"] > base["visible"] + 0.08:
            flags.append("too_dense")
        if stats["dense"] > 0.62 and stats["dense"] > base["dense"] + 0.08:
            flags.append("dense_glyphs")
        if base["index_std"] > 0.1 and stats["index_std"] < base["index_std"] * 0.55:
            flags.append("contrast_loss")
        if (stats["edges"] > 0.02 and stats["edge_visible"] < 0.30
                and stats["edge_visible"] < base["edge_visible"] - 0.08):
            flags.append("edges_lost")
        if (sample["edge"] > 0.12 and stats["dark_detail"] < 0.22
                and stats["visible"] > 0.25):
            flags.append("resolution_limited")
        if i and i not in cut_set:
            delta = max(abs(smooth[i][k] - smooth[i - 1][k]) for k in PARAMS)
            flicker = max(flicker, delta)
            if delta > 0.035:
                flags.append("flicker")
        if smooth[i]["shadow"] < 0.008 or smooth[i]["white"] < 0.27 or smooth[i]["gamma"] > 1.0:
            flags.append("aggressive")
        flagged.append(flags)
        final_stats.append({k: round(v, 4) for k, v in stats.items()})

    # Gradual brightness changes inside the same shot (no cut).
    changes = []
    for i in range(15, len(samples)):
        if any(c in cut_set for c in range(i - 15, i + 1)):
            continue
        ds = smooth[i]["shadow"] - smooth[i - 15]["shadow"]
        dw = smooth[i]["white"] - smooth[i - 15]["white"]
        if max(abs(ds), abs(dw)) > 0.025:
            changes.append({"start": samples[i - 15]["t"], "end": samples[i]["t"],
                            "delta_shadow": round(ds, 4), "delta_white": round(dw, 4)})
    merged_changes = []
    for row in changes:
        if merged_changes and row["start"] <= merged_changes[-1]["end"] + 0.5:
            merged_changes[-1]["end"] = row["end"]
            merged_changes[-1]["delta_shadow"] = row["delta_shadow"]
            merged_changes[-1]["delta_white"] = row["delta_white"]
        else:
            merged_changes.append(dict(row))
    for row in merged_changes:
        row["kind"] = "gradual"

    limitations = []
    for kind, action in (
        ("resolution_limited", "raise grid or capture a dedicated UI view; a 2x reframe was tested and is insufficient"),
        ("intentional_dark", "keep black; the source has no recoverable detail"),
    ):
        run_start = None
        for i, flags in enumerate(flagged + [[]]):
            hit = kind in flags
            if hit and run_start is None:
                run_start = i
            elif not hit and run_start is not None:
                if i - run_start >= 5:
                    limitations.append({"start": samples[run_start]["t"],
                                        "end": samples[i - 1]["t"],
                                        "kind": kind, "action": action})
                run_start = None

    # Problem intervals: at least 0.5 s with at least one real flag.
    problems = []
    run_start = None
    run_reasons = set()
    for i, flags in enumerate(flagged + [[]]):
        real = [f for f in flags if f not in ("intentional_dark", "flash", "resolution_limited")]
        if real and run_start is None:
            run_start = i
            run_reasons = set(real)
        elif real and run_start is not None:
            run_reasons.update(real)
        elif not real and run_start is not None:
            if i - run_start >= 5:
                problems.append({"start": samples[run_start]["t"], "end": samples[i - 1]["t"],
                                 "reasons": sorted(run_reasons)})
            run_start = None
            run_reasons = set()

    rows = []
    for i, sample in enumerate(samples):
        rows.append({
            **{k: sample[k] for k in ("t", "p5", "p10", "p25", "p50", "p95", "mean",
                                      "edge", "sat", "dark", "clipped")},
            "need": round(needs[i], 4),
            "visible_base": round(base_stats[i]["visible"], 4),
            "visible": final_stats[i]["visible"],
            "dense": final_stats[i]["dense"],
            "saturated": final_stats[i]["saturated"],
            "dark_detail": final_stats[i]["dark_detail"],
            "index_std": final_stats[i]["index_std"],
            "edge_visible": final_stats[i]["edge_visible"],
            "block_entropy": final_stats[i]["block_entropy"],
            "empty_blocks": final_stats[i]["empty_blocks"],
            "dense_blocks": final_stats[i]["dense_blocks"],
            "params": smooth[i],
            "flags": flagged[i],
        })

    segments = []
    for e, (a, b) in enumerate(episodes):
        rows_a = rows[a:b]
        segments.append({
            "start": rows[a]["t"], "end": rows[b - 1]["t"], "cut": e > 0,
            "shadow": round(sum(r["params"]["shadow"] for r in rows_a) / len(rows_a), 4),
            "white": round(sum(r["params"]["white"] for r in rows_a) / len(rows_a), 4),
            "gamma": round(sum(r["params"]["gamma"] for r in rows_a) / len(rows_a), 4),
            "contrast_low": round(sum(r["params"]["contrast_low"] for r in rows_a) / len(rows_a), 4),
            "local_contrast": round(sum(r["params"]["local_contrast"] for r in rows_a) / len(rows_a), 4),
            "visible": round(sum(r["visible"] for r in rows_a) / len(rows_a), 4),
            "flags": sorted({f for r in rows_a for f in r["flags"] if f != "intentional_dark"}),
        })

    plan = {
        "version": 2,
        "mode": "auto",
        "source": project.source,
        "duration": project.working_info["duration"],
        "total_frames": total_frames,
        "render_fps": 30,
        "frame_scale": round(fps / 30.0, 6),
        "frame_offset": round(1.0 - fps / 30.0, 6),
        "base": {"shadow": base_plan["keyframes"][0]["shadow"],
                 "white": base_plan["keyframes"][0]["white"],
                 **{k: BASE[k] for k in ("gamma", "contrast_low", "contrast_high", "local_contrast")}},
        "samples": rows,
        "segments": segments,
        "changes": merged_changes,
        "cuts": [round(samples[c]["t"], 3) for c in cuts],
        "keyframes": keyframes,
        "quality": {
            "samples": len(rows),
            "mean_visible_base": round(sum(r["visible_base"] for r in rows) / len(rows), 4),
            "mean_visible": round(sum(r["visible"] for r in rows) / len(rows), 4),
            "mean_dense": round(sum(r["dense"] for r in rows) / len(rows), 4),
            "mean_dark_detail": round(sum(r["dark_detail"] for r in rows) / len(rows), 4),
            "mean_saturated": round(sum(r["saturated"] for r in rows) / len(rows), 4),
            "mean_index_std": round(sum(r["index_std"] for r in rows) / len(rows), 4),
            "max_flicker": round(flicker, 4),
            "flagged_samples": sum(1 for f in flagged if f),
            "resolution_limited_samples": sum(1 for f in flagged if "resolution_limited" in f),
            "flash_samples": len(flash),
            "problems": len(problems),
            "limitations": len(limitations),
        },
        "problems": problems,
        "limitations": limitations,
        "overrides": active_overrides,
        "note": "Auto ASCII Correction: per-frame adaptive shadow/white/gamma/contrast, "
                "smoothed inside each shot, hard switch only at detected cuts.",
    }
    path = project.path / "temp" / "plan.json"
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    project.plan_path = str(path)
    project.save()
    return plan
