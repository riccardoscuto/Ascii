from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from gcf.ascii import luma
from gcf.ascii.preset import PRESET_BLEND, blend_for

RENDERER_VERSION = "spatial-1"
DEFAULT_RAMP = " .,:;+HW@"
SPATIAL = {"radius": 4, "sigma_s": 2.5, "sigma_r": 0.08,
           "index_floor": 0.008, "index_span": 0.392, "index_gamma": 0.80}
D_CONSERVATIVE = {"radius": 2, "empty_below": 0.35, "reduce_below": 0.65,
                  "luma_lo": 1.8, "luma_hi": 2.8}
ASCII_MODES = ("legacy", "spatial", "auto")
SPATIAL_VARIANTS = ("d", "conservative", "global", "adaptive", "adaptive-conservative",
                    "range", "compress", "local", "guarded")
ADAPTIVE_VARIANTS = ("adaptive", "adaptive-conservative", "range", "compress", "local", "guarded")


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _json_sha1(value) -> str:
    return hashlib.sha1(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def encoded_levels(ramp: str = DEFAULT_RAMP) -> tuple[int, ...]:
    n = max(1, len(ramp) - 1)
    return tuple(sorted({int(round(min(1.0, i / n + 0.001) * 255)) for i in range(n + 1)}))


def encode_index(idx: np.ndarray, ramp: str = DEFAULT_RAMP) -> Image.Image:
    n = max(1, len(ramp) - 1)
    values = np.rint(np.minimum(1.0, idx / n + 0.001) * 255).astype(np.uint8)
    return Image.fromarray(values, mode="L")


def smoothstep(x, a, b):
    if b <= a:
        return (x >= a).astype(np.float32)
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return (t * t * (3.0 - 2.0 * t)).astype(np.float32)


def bilateral(L: np.ndarray, radius: int = 4, sigma_s: float = 2.5,
              sigma_r: float = 0.08) -> np.ndarray:
    """Edge-aware local mean on the cell grid."""
    h, w = L.shape
    pad = np.pad(L, radius, mode="edge")
    acc = np.zeros_like(L, dtype=np.float32)
    wsum = np.zeros_like(L, dtype=np.float32)
    ss = 2.0 * sigma_s * sigma_s
    sr = 2.0 * sigma_r * sigma_r
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            near = pad[radius + dy:radius + dy + h, radius + dx:radius + dx + w]
            ds = float(dx * dx + dy * dy)
            dr = (near - L) ** 2
            wt = np.exp(-ds / ss - dr / sr).astype(np.float32)
            acc += near * wt
            wsum += wt
    return (acc / np.maximum(wsum, 1e-8)).astype(np.float32)


def tone_at(plan: dict, frame: int, data: dict) -> dict:
    keys = plan.get("keyframes") or []
    shadow, white = data["shadow"], data["white"]
    if keys:
        if frame <= keys[0]["frame"]:
            shadow, white = keys[0]["shadow"], keys[0]["white"]
        elif frame >= keys[-1]["frame"]:
            shadow, white = keys[-1]["shadow"], keys[-1]["white"]
        else:
            for a, b in zip(keys, keys[1:]):
                if a["frame"] <= frame <= b["frame"]:
                    t = (frame - a["frame"]) / max(1, b["frame"] - a["frame"])
                    shadow = a["shadow"] + (b["shadow"] - a["shadow"]) * t
                    white = a["white"] + (b["white"] - a["white"]) * t
                    break
    return {"shadow": float(shadow), "white": float(white),
            "gamma": float(data["gamma"]), "contrast_low": float(data["contrast_low"]),
            "contrast_high": float(data["contrast_high"]),
            "local_contrast": float(data["local_contrast"])}


def global_index(cells: np.ndarray, centre: np.ndarray, tone: dict,
                 ramp: str = DEFAULT_RAMP) -> np.ndarray:
    local = cells + tone["local_contrast"] * (centre - cells)
    span = max(1e-6, tone["white"] - tone["shadow"])
    x = np.clip((local - tone["shadow"]) / span, 0.0, 1.0) ** tone["gamma"]
    span = max(1e-6, tone["contrast_high"] - tone["contrast_low"])
    c = np.clip((x - tone["contrast_low"]) / span, 0.0, 1.0)
    return np.rint(c * (len(ramp) - 1)).astype(np.uint8), (c * 255.0).astype(np.uint8)


def adjust_levels(idx: np.ndarray, tone: np.ndarray, data: dict,
                  ramp: str = DEFAULT_RAMP) -> tuple[np.ndarray, np.ndarray]:
    """Apply the exposed luminance controls; identity at the default values."""
    gamma = float(data.get("gamma", 0.82))
    shadow = float(data.get("shadow", 0.31))
    contrast = float(data.get("contrast_high", 0.85))
    if (abs(gamma - 0.82) < 1e-6 and abs(shadow - 0.31) < 1e-6
            and abs(contrast - 0.85) < 1e-6):
        return idx, tone
    gain = max(0.25, contrast / 0.85)
    lift = (shadow - 0.31) * 0.5
    exponent = gamma / 0.82
    levels = max(1, len(ramp) - 1)

    def curve(values):
        x = np.clip(values, 0.0, 1.0) ** exponent
        return np.clip((x - 0.5) * gain + 0.5 + lift, 0.0, 1.0)

    new_idx = np.rint(curve(idx.astype(np.float32) / levels) * levels).astype(np.uint8)
    new_tone = np.clip(curve(tone.astype(np.float32) / 255.0) * 255.0, 0, 255).astype(np.uint8)
    return new_idx, new_tone


def _variant_values(cells: np.ndarray, base: np.ndarray, target: float,
                    variant: str) -> np.ndarray:
    detail = cells - base
    gain = np.clip((target / np.maximum(base, 0.002)) ** 0.5, 0.45, 4.0)
    gate = smoothstep(np.abs(detail), 0.008, 0.045)
    gain = 1.0 + (gain - 1.0) * gate
    if variant == "local":
        local = luma.local_std(cells, 2)
        boost = np.clip(0.20 / np.maximum(local, 0.006), 0.65, 2.4)
        detail = detail * boost
    return np.clip(base * gain + detail, 0.0, 1.0)


def spatial_index(cells: np.ndarray, base: np.ndarray, target: float,
                  ramp: str = DEFAULT_RAMP, conservative: bool = False,
                  stats: dict | None = None, variant: str = ""):
    st = stats or {}
    v = _variant_values(cells, base, target, variant)
    if variant in ("range", "compress", "local"):
        lo = float(st.get("v_p02", SPATIAL["index_floor"]))
        hi = float(st.get("v_p98", SPATIAL["index_span"] + lo))
        c = np.clip((v - lo) / max(1e-6, hi - lo), 0.0, 1.0)
        if variant == "compress":
            # Soft highlight shoulder: keeps 0/1 fixed while compressing the
            # upper range instead of clipping every value above 0.40.
            c = c * 1.6 / (1.0 + 0.6 * c)
        else:
            c = c ** 0.92
        idx = np.rint(c * (len(ramp) - 1)).astype(np.uint8)
        tone = (v * 255.0).astype(np.uint8)
        return idx, tone
    c = np.clip((v - SPATIAL["index_floor"]) / SPATIAL["index_span"], 0.0, 1.0) ** SPATIAL["index_gamma"]
    idx = np.rint(c * (len(ramp) - 1)).astype(np.uint8)
    tone = (v * 255.0).astype(np.uint8)
    if not conservative:
        return idx, tone
    edge_p50 = float(st.get("edge_p50", 0.02))
    edge_p85 = float(st.get("edge_p85", 0.08))
    std_p50 = float(st.get("std_p50", 0.004))
    std_p85 = float(st.get("std_p85", 0.02))
    detail = cells - base
    edge_rel = np.abs(detail) / np.maximum(base, 0.002)
    local = luma.local_std(cells, D_CONSERVATIVE["radius"])
    keep = np.maximum.reduce([
        smoothstep(edge_rel, edge_p50, edge_p85),
        smoothstep(local, std_p50, std_p85),
        smoothstep(v, target * D_CONSERVATIVE["luma_lo"], target * D_CONSERVATIVE["luma_hi"]),
    ])
    out = idx.copy()
    out[keep < D_CONSERVATIVE["empty_below"]] = 0
    mid = (keep >= D_CONSERVATIVE["empty_below"]) & (keep < D_CONSERVATIVE["reduce_below"])
    out[mid] = np.maximum(0, idx[mid].astype(np.int16) - 1).astype(np.uint8)
    # The fixed D-Conservative rule protects every dense glyph.  The
    # experimental "guarded" variant protects them only where local contrast
    # actually justifies the density.
    dense = idx >= (len(ramp) - 2)
    if variant == "guarded":
        dense = dense & ((edge_rel >= edge_p85) | (local >= std_p85))
    out[dense] = idx[dense]
    return out, tone


def _flash_frames(means: list[float]) -> set[int]:
    flash = set()
    for i, mean in enumerate(means):
        if i == 0:
            continue
        window = [means[j] for j in range(max(0, i - 4), min(len(means), i + 5)) if j != i]
        after = [means[j] for j in range(i + 1, min(len(means), i + 4))]
        previous = means[i - 1]
        if (window and after and mean > previous + 0.12
                and abs(after[0] - previous) < 0.12
                and max(after) < float(np.median(window)) + 0.08):
            flash.add(i)
    return flash


def _shot_bounds(cuts: list[float], total: int) -> list[tuple[int, int]]:
    points = [1]
    for cut in sorted(float(c) for c in cuts):
        frame = max(1, min(total, int(round(cut * 30)) + 1))
        if frame > points[-1] + 1:
            points.append(frame)
    if points[-1] <= total:
        points.append(total + 1)
    bounds = [(a, b - 1) for a, b in zip(points, points[1:])]
    merged = []
    for start, end in bounds:
        if merged and end - start + 1 < 24:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    if len(merged) > 1 and merged[0][1] - merged[0][0] + 1 < 24:
        merged[1] = (merged[0][0], merged[1][1])
        merged.pop(0)
    return merged


def adaptive_stats(project, data: dict, plan: dict, kind: str,
                   conservative: bool, variant: str = '') -> dict:
    """Per-shot targets plus a slow, flash-safe intra-shot target curve."""
    frames = sorted((project.path / "analysis").glob("f_*.png"))
    if not frames:
        raise RuntimeError("Spatial adattivo: nessun frame di analisi.")
    step = max(1, len(frames) // 300)
    frames = frames[::step]
    total = int(plan["total_frames"])
    times = np.array([(i * step) / 10.0 for i in range(len(frames))], dtype=np.float32)
    medians, means = [], []
    edge_values, std_values = [], []
    cells_list, base_list = [], []
    for path in frames:
        im = Image.open(path).convert("RGB")
        cells, centre = luma.linear_luma_cell_samples(im, data["grid"]["cols"], data["grid"]["rows"])
        base = bilateral(cells)
        cells_list.append(cells)
        base_list.append(base)
        medians.append(float(np.median(cells)))
        means.append(float(np.mean(np.asarray(im.convert("L"), dtype=np.float32)) / 255.0))
        if kind == "conservative":
            edge_values.append((np.abs(cells - base) / np.maximum(base, 0.002)).ravel())
            std_values.append(luma.local_std(cells, D_CONSERVATIVE["radius"]).ravel())
    medians = np.asarray(medians, dtype=np.float32)
    flashes = _flash_frames(list(means))
    bounds = _shot_bounds(plan.get("cuts", []), total)
    curve = np.zeros(total, dtype=np.float32)
    shots = []
    for start, end in bounds:
        start_t, end_t = (start - 1) / 30.0, (end - 1) / 30.0 + 1 / 30.0
        idx = [i for i, t in enumerate(times) if start_t <= t < end_t]
        if not idx:
            idx = [int(np.clip(np.searchsorted(times, start_t), 0, len(times) - 1))]
        shot_means = np.asarray(means, dtype=np.float32)[idx] if idx else np.asarray(means, dtype=np.float32)
        shot_med = float(np.median(shot_means)) if len(shot_means) else 0.0
        j = 0
        while j < len(idx):
            if means[idx[j]] > shot_med + 0.20:
                k = j + 1
                while k < len(idx) and means[idx[k]] > shot_med + 0.20:
                    k += 1
                if 1 <= k - j <= 5 and (k - j) < len(idx):
                    flashes.update(idx[j:k])
                j = k
            else:
                j += 1
        clean = [i for i in idx if i not in flashes]
        use = clean or idx
        target = float(np.median(medians[use]))
        raw = medians[idx].astype(np.float32).copy()
        # A brief flash is an outlier, not a new exposure target.
        for j, i in enumerate(idx):
            if i in flashes:
                raw[j] = np.nan
        good = np.flatnonzero(~np.isnan(raw))
        if len(good) >= 2:
            raw = np.interp(np.arange(len(raw)), good, raw[good]).astype(np.float32)
        elif len(good) == 1:
            raw[:] = raw[good[0]]
        else:
            raw[:] = target
        raw = np.clip(raw, target * 0.65, target * 1.45)
        if len(raw) >= 3:
            raw = np.array([np.median(raw[max(0, j - 1):min(len(raw), j + 2)])
                            for j in range(len(raw))], dtype=np.float32)
        smoothed = np.zeros_like(raw)
        value = raw[0]
        max_step = max(1e-5, target * 0.04)
        for j, item in enumerate(raw):
            value += 0.30 * (float(item) - value)
            value = float(np.clip(value, value - max_step, value + max_step))
            smoothed[j] = value
        shot_times = times[idx]
        for frame in range(start, end + 1):
            t = (frame - 1) / 30.0
            curve[frame - 1] = float(np.interp(t, shot_times, smoothed,
                                               left=smoothed[0], right=smoothed[-1]))
        shot = {"start": start, "end": end, "target": round(target, 5),
                "flash_frames": sorted(int(round(times[i] * 30)) + 1 for i in idx if i in flashes)}
        if kind == "conservative":
            shot_edges = np.concatenate([edge_values[i] for i in use])
            shot_stds = np.concatenate([std_values[i] for i in use])
            shot.update({
                "edge_p50": float(np.percentile(shot_edges, 50)),
                "edge_p85": float(np.percentile(shot_edges, 85)),
                "std_p50": float(np.percentile(shot_stds, 50)),
                "std_p85": float(np.percentile(shot_stds, 85)),
            })
        if variant in ("range", "compress", "local") and idx:
            values = []
            for i in idx:
                frame = max(1, min(total, int(round(times[i] * 30)) + 1))
                values.append(_variant_values(cells_list[i], base_list[i],
                                              float(curve[frame - 1]), variant).ravel())
            merged = np.concatenate(values)
            shot.update({
                "v_p02": float(np.percentile(merged, 2)),
                "v_p50": float(np.percentile(merged, 50)),
                "v_p98": float(np.percentile(merged, 98)),
            })
        shots.append(shot)
    return {
        "adaptive": True,
        "target_curve": [round(float(v), 6) for v in curve],
        "shots": shots,
        "flashes": sorted(int(round(times[i] * 30)) + 1 for i in flashes),
        "analysis_frames": len(frames),
    }


def shot_stats_at(stats: dict, frame: int) -> dict:
    for shot in stats.get("shots", []):
        if shot["start"] <= frame <= shot["end"]:
            return shot
    return stats.get("shots", [{}])[0] if stats.get("shots") else {}


def analysis_stats(project, data: dict, plan: dict, variant: str = '') -> dict:
    """Target and local-structure percentiles from the 10 fps analysis frames."""
    frames = sorted((project.path / "analysis").glob("f_*.png"))
    if not frames:
        raise RuntimeError("Spatial analysis: nessun frame di analisi.")
    step = max(1, len(frames) // 300)
    frames = frames[::step]
    medians = []
    edges = []
    stds = []
    for path in frames:
        im = Image.open(path).convert("RGB")
        cells, centre = luma.linear_luma_cell_samples(im, data["grid"]["cols"], data["grid"]["rows"])
        base = bilateral(cells)
        medians.append(float(np.median(cells)))
        detail = np.abs(cells - base) / np.maximum(base, 0.002)
        edges.append(detail.ravel())
        stds.append(luma.local_std(cells, D_CONSERVATIVE["radius"]).ravel())
    edge = np.concatenate(edges)
    std = np.concatenate(stds)
    out = {
        "target": float(np.median(medians)),
        "p50": float(np.median(np.concatenate([np.array([m]) for m in medians]))),
        "edge_p50": float(np.percentile(edge, 50)),
        "edge_p85": float(np.percentile(edge, 85)),
        "std_p50": float(np.percentile(std, 50)),
        "std_p85": float(np.percentile(std, 85)),
        "analysis_frames": len(frames),
    }
    if variant in ("range", "compress", "local") and frames:
        target = out["target"]
        values = []
        for path in frames:
            im = Image.open(path).convert("RGB")
            cells, _ = luma.linear_luma_cell_samples(im, data["grid"]["cols"], data["grid"]["rows"])
            values.append(_variant_values(cells, bilateral(cells), target, variant).ravel())
        merged = np.concatenate(values)
        out.update({"v_p02": float(np.percentile(merged, 2)),
                    "v_p50": float(np.percentile(merged, 50)),
                    "v_p98": float(np.percentile(merged, 98))})
    return out


def _map_params(data: dict, plan: dict, kind: str, conservative: bool, stats: dict,
                variant: str = '') -> dict:
    out = {
        "renderer_version": RENDERER_VERSION,
        "grid": [data["grid"]["cols"], data["grid"]["rows"]],
        "ramp": data["ramp"],
        "kind": kind,
        "conservative": bool(conservative),
        "spatial": SPATIAL,
        "conservative_params": D_CONSERVATIVE,
        "target": stats.get("target", 0.0),
        "stats": stats,
        "tone": {k: data[k] for k in ("gamma", "shadow", "white", "contrast_low",
                                       "contrast_high", "local_contrast")},
        "plan_keyframes": plan.get("keyframes", []),
        "plan_cuts": plan.get("cuts", []),
    }
    if stats.get("adaptive"):
        out["adaptive"] = True
    if variant:
        out["variant"] = variant
    if data.get("renderer") != "v2" and data.get("renderer_version"):
        out["renderer_version"] = data["renderer_version"]
    return out


def map_key(project, data: dict, plan: dict, kind: str, conservative: bool,
            stats: dict, variant: str = '') -> str:
    payload = {
        "source": _sha1(Path(project.working_source)),
        "preset": _sha1(blend_for(project)),
        "params": _map_params(data, plan, kind, conservative, stats, variant),
    }
    return _json_sha1(payload)


def _manifest_valid(folder: Path, manifest: dict, end: int, data: dict,
                    kind: str, conservative: bool, adaptive: bool = False,
                    variant: str = '') -> bool:
    if not manifest or manifest.get("renderer_version") != RENDERER_VERSION:
        return False
    if manifest.get("kind") != kind or bool(manifest.get("conservative")) != bool(conservative):
        return False
    if bool(manifest.get("adaptive")) != bool(adaptive):
        return False
    if variant and manifest.get("variant") != variant:
        return False
    if manifest.get("grid") != [data["grid"]["cols"], data["grid"]["rows"]]:
        return False
    if manifest.get("ramp") != data["ramp"]:
        return False
    if int(manifest.get("frames", 0)) < end:
        return False
    return len(list((folder / "idx").glob("i_*.png"))) >= end


def _index_root(folder: Path, end: int) -> str:
    h = hashlib.sha1()
    for i in range(1, end + 1):
        h.update((folder / "idx" / f"i_{i:04d}.png").read_bytes())
    return h.hexdigest()


def map_content_hash(folder: Path, end: int, subdirs: tuple[str, ...] = ("idx", "tone")) -> str:
    """Hash the actual map bytes, not only their path or size."""
    h = hashlib.sha1()
    for i in range(1, end + 1):
        for sub in subdirs:
            pattern = "i_%04d.png" if sub == "idx" else "t_%04d.png"
            path = folder / sub / (pattern % i)
            if not path.exists():
                raise RuntimeError(f"Mappa mancante: {path}")
            h.update(path.read_bytes())
    return h.hexdigest()


def validate_index_maps(folder: Path, end: int, cols: int, rows: int,
                        ramp: str = DEFAULT_RAMP) -> dict:
    expected = set(encoded_levels(ramp))
    files = sorted((folder / "idx").glob("i_*.png"))
    if len(files) < end:
        raise RuntimeError(f"Indici mancanti: {len(files)}/{end}")
    levels = set()
    for path in files[:end]:
        im = Image.open(path).convert("L")
        if im.size != (cols, rows):
            raise RuntimeError(f"Griglia indice errata: {path.name} {im.size}")
        levels.update(im.getdata())
    extra = sorted(v for v in levels if v not in expected)
    if extra:
        raise RuntimeError(f"Indici fuori codifica 0–255: {extra[:12]}")
    return {"levels": sorted(levels), "frames": end, "index_root": _index_root(folder, end)}


def validate_renders(frames_dir: Path, maps_dir: Path, end: int, cols: int, rows: int,
                     sample_step: int = 1, normalize: bool = False,
                     black_mean: float = 0.75) -> dict:
    """Black-frame and index/render alignment guard."""
    issues = []
    checked = 0
    step = max(1, int(sample_step))
    for i in range(1, end + 1, step):
        frame = frames_dir / f"f_{i:04d}.png"
        index = maps_dir / "idx" / f"i_{i:04d}.png"
        if not frame.exists() or not index.exists():
            issues.append(f"frame/indice mancante: {i}")
            continue
        ren = Image.open(frame).convert("L")
        h = ren.histogram()
        mean = sum(k * c for k, c in enumerate(h)) / max(1, ren.width * ren.height)
        hi = max(i for i, c in enumerate(h) if c)
        idx = Image.open(index).convert("L")
        cells = idx.getdata()
        occupied = sum(1 for v in cells if v) / max(1, idx.width * idx.height)
        if occupied > 0.02 and hi < 8:
            issues.append(f"frame nero non giustificato: {i} max={hi}")
        if occupied > 0.02 and mean < black_mean:
            issues.append(f"render quasi nero: {i} mean={mean:.3f}")
        if occupied > 0.10 and mean >= (20.0 if normalize else 0.5):
            small = ren.resize((cols, rows), Image.Resampling.BOX)
            values = list(small.getdata())
            index_values = list(idx.getdata())
            if normalize:
                def _norm(vals):
                    ordered = sorted(vals)
                    lo = ordered[max(0, int(len(ordered) * 0.02))]
                    hi = ordered[min(len(ordered) - 1, int(len(ordered) * 0.98))]
                    return [max(0.0, min(255.0, (v - lo) * 255.0 / max(1.0, hi - lo)))
                            for v in vals]
                values = _norm(values)
                index_values = _norm(index_values)
            mv = sum(values) / len(values)
            mi = sum(index_values) / len(index_values)
            num = sum((a - mv) * (b - mi) for a, b in zip(values, index_values))
            den = (sum((a - mv) ** 2 for a in values)
                   * sum((b - mi) ** 2 for b in index_values)) ** 0.5
            if den and num / den < 0.25:
                issues.append(f"mappa/render disallineati: frame {i}")
        checked += 1
    if issues:
        raise RuntimeError("; ".join(issues[:12]))
    return {"checked": checked, "issues": []}


def ensure_maps(project, data: dict, plan: dict, end: int, kind: str = "spatial",
                conservative: bool = False, progress=None, cancel=None,
                start: int = 1, adaptive: bool = False, variant: str = '') -> dict:
    """Generate or reuse deterministic tone/index maps for render frames."""
    if kind not in ("global", "spatial", "conservative"):
        raise ValueError(f"Tipo mappa non valido: {kind}")
    if end < 1:
        raise ValueError("Intervallo mappe vuoto.")
    if kind == "global":
        stats = {"target": 0.0, "p50": 0.0, "edge_p50": 0.0, "edge_p85": 0.0,
                 "std_p50": 0.0, "std_p85": 0.0, "analysis_frames": 0}
    elif adaptive:
        stats = adaptive_stats(project, data, plan, kind, conservative, variant)
    else:
        stats = analysis_stats(project, data, plan, variant)
    key = map_key(project, data, plan, kind, conservative, stats, variant)
    root = project.path / "temp" / "spatial" / key
    idx_dir = root / "idx"
    tone_dir = root / "tone"
    idx_dir.mkdir(parents=True, exist_ok=True)
    tone_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    if _manifest_valid(root, manifest, end, data, kind, conservative, adaptive, variant):
        try:
            checked = validate_index_maps(root, end, data["grid"]["cols"], data["grid"]["rows"], data["ramp"])
            if checked["index_root"] != manifest.get("index_root"):
                raise RuntimeError("Contenuto mappe diverso dall'hash registrato.")
            project.spatial = {"key": key, "dir": str(root), "manifest": str(manifest_path),
                               "index_root": manifest["index_root"], "frames": end,
                               "kind": kind, "conservative": conservative,
                               "adaptive": adaptive, "target": stats.get("target", 0.0)}
            project.save()
            return manifest
        except Exception:
            # Corrupt/legacy 0-8 maps must never be reused.
            for old in list(idx_dir.glob("*.png")) + list(tone_dir.glob("*.png")):
                old.unlink(missing_ok=True)
            manifest = {}

    cols, rows = data["grid"]["cols"], data["grid"]["rows"]
    w, h = data["resolution"]
    source = str(project.working_source)
    cmd = ["ffmpeg", "-v", "error", "-i", source, "-vf", f"fps=30,scale={w}:{h}",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    from gcf.config import ffmpeg_bin
    cmd[0] = ffmpeg_bin()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_bytes = w * h * 3
    started = time.time()
    done = 0
    try:
        for frame in range(1, end + 1):
            buf = proc.stdout.read(frame_bytes)
            if len(buf) != frame_bytes:
                raise RuntimeError(f"Sorgente esaurita al frame {frame}.")
            if frame < start:
                continue
            out_idx = idx_dir / f"i_{frame:04d}.png"
            out_tone = tone_dir / f"t_{frame:04d}.png"
            if not (out_idx.exists() and out_tone.exists()):
                im = Image.frombytes("RGB", (w, h), buf)
                cells, centre = luma.linear_luma_cell_samples(im, cols, rows)
                if kind == "global":
                    idx, tone = global_index(cells, centre, tone_at(plan, frame, data), data["ramp"])
                else:
                    base = bilateral(cells)
                    target = stats["target_curve"][frame - 1] if adaptive else stats["target"]
                    frame_stats = shot_stats_at(stats, frame) if adaptive else stats
                    idx, tone = spatial_index(cells, base, target, data["ramp"],
                                              conservative=conservative, stats=frame_stats,
                                              variant=variant)
                    idx, tone = adjust_levels(idx, tone, data, data["ramp"])
                encode_index(idx, data["ramp"]).save(out_idx)
                Image.fromarray(tone, mode="L").save(out_tone)
            done += 1
            if progress and (done % 3 == 0 or frame == end):
                elapsed = time.time() - started
                total = max(1, end - start + 1)
                eta = elapsed * (total - done) / done if done else None
                progress(done, total, elapsed, eta, "Mappe spaziali")
            if cancel is not None and cancel.is_set():
                raise RuntimeError("Generazione mappe interrotta.")
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
    validate_index_maps(root, end, cols, rows, data["ramp"])
    index_root = _index_root(root, end)
    manifest = {
        **_map_params(data, plan, kind, conservative, stats, variant),
        "frames": end,
        "index_root": index_root,
        "source": str(project.working_source),
        "source_sha1": _sha1(Path(project.working_source)),
        "preset_sha1": _sha1(blend_for(project)),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "map_key": key,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    project.spatial = {"key": key, "dir": str(root), "manifest": str(manifest_path),
                       "index_root": index_root, "frames": end, "kind": kind,
                       "conservative": conservative, "adaptive": adaptive,
                       "target": stats.get("target", 0.0)}
    project.save()
    return manifest


def encode_png_movie(folder: Path, pattern: str, frames: int, out: Path) -> Path:
    """Encode a PNG sequence as a lossless FFV1 movie."""
    from gcf.config import ffmpeg_bin
    cmd = [ffmpeg_bin(), "-y", "-v", "error", "-framerate", "30",
           "-start_number", "1", "-i", str(Path(folder) / pattern),
           "-frames:v", str(frames), "-c:v", "ffv1", "-pix_fmt", "rgb24",
           "-color_range", "pc", str(out)]
    subprocess.run(cmd, check=True)
    return out


def encode_index_movie(project, frames: int, out: Path | None = None) -> Path:
    """Encode the index PNG sequence as a lossless FFV1 movie."""
    root = Path(project.spatial["dir"]) / "idx"
    out = out or Path(project.spatial["dir"]) / "index_movie.mkv"
    return encode_png_movie(root, "i_%04d.png", frames, out)


def validate_png_movie(folder: Path, pattern: str, movie: Path, frames: int,
                       rgb: bool = False) -> dict:
    """Compare decoded FFV1 frames with the source PNG sequence exactly."""
    import numpy as np
    from PIL import Image
    from gcf.config import ffmpeg_bin
    first = Image.open(Path(folder) / (pattern % 1)).convert("RGB" if rgb else "L")
    width, height = first.size
    channels = 3 if rgb else 1
    expected = width * height * channels
    proc = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(movie),
                           "-f", "rawvideo", "-pix_fmt", "rgb24" if rgb else "gray", "-"],
                          capture_output=True, check=True)
    data = proc.stdout
    if len(data) < expected * frames:
        raise RuntimeError(f"Movie troppo corto: {len(data)} byte")
    for frame in range(frames):
        buf = data[frame * expected:(frame + 1) * expected]
        got = np.frombuffer(buf, dtype=np.uint8).reshape(height, width, channels)
        want = np.asarray(Image.open(Path(folder) / (pattern % (frame + 1)))
                          .convert("RGB" if rgb else "L"), dtype=np.uint8)
        if not rgb:
            want = want[..., None]
        if not np.array_equal(got, want):
            diff = int(np.abs(got.astype(np.int16) - want.astype(np.int16)).max())
            raise RuntimeError(f"Movie diverso al frame {frame + 1}: max {diff}")
    return {"frames": frames, "exact": True, "size": [width, height], "rgb": rgb}


def validate_index_movie(project, movie: Path, frames: int) -> dict:
    """Decode the FFV1 index movie and compare every value to the PNG sequence."""
    import numpy as np
    from PIL import Image
    from gcf.config import ffmpeg_bin
    root = Path(project.spatial["dir"]) / "idx"
    cols, rows = Image.open(root / "i_0001.png").size
    expected = cols * rows * 3
    proc = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(movie),
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          capture_output=True, check=True)
    data = proc.stdout
    if len(data) < expected * frames:
        raise RuntimeError(f"Index movie troppo corto: {len(data)} byte")
    for frame in range(frames):
        buf = data[frame * expected:(frame + 1) * expected]
        got = np.frombuffer(buf, dtype=np.uint8).reshape(rows, cols, 3)[..., 0]
        want = np.asarray(Image.open(root / f"i_{frame + 1:04d}.png").convert("L"),
                          dtype=np.uint8)
        if not np.array_equal(got, want):
            diff = int(np.abs(got.astype(np.int16) - want.astype(np.int16)).max())
            raise RuntimeError(f"Index movie diverso al frame {frame + 1}: max {diff}")
    return {"frames": frames, "exact": True, "size": [cols, rows]}


def validate_manifest(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise RuntimeError("Manifest mappe assente.")
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("renderer_version") != RENDERER_VERSION:
        raise RuntimeError("Versione renderer mappe non coerente.")
    return data
