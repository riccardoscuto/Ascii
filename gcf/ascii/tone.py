from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

COLS, ROWS = 80, 45


def _pct(values, p):
    s = sorted(values)
    return s[min(len(s) - 1, int(p * len(s)))]


def _smoothstep(x, a, b):
    t = max(0.0, min(1.0, (x - a) / max(1e-6, b - a)))
    return t * t * (3 - 2 * t)


def _frames(folder: Path):
    rows = []
    prev = None
    for path in sorted(folder.glob("f_*.png")):
        idx = int(path.stem.split("_")[1])
        t = (idx - 1) / 10.0
        im = Image.open(path).convert("L")
        small = im.resize((160, 90), Image.Resampling.BOX)
        px = small.load()
        vals = [px[x, y] / 255.0 for y in range(90) for x in range(160)]
        hist = [0] * 32
        for v in vals:
            hist[min(31, int(v * 32))] += 1
        hist = [h / len(vals) for h in hist]
        cells = im.resize((COLS, ROWS), Image.Resampling.BOX)
        cp = cells.load()
        cvals = [cp[x, y] / 255.0 for y in range(ROWS) for x in range(COLS)]
        hd = dl = 0.0
        if prev:
            hd = sum(abs(a - b) for a, b in zip(hist, prev["hist"])) / 2
            dl = abs(sum(vals) / len(vals) - prev["luma"])
        rows.append({"t": t, "hd": hd, "dl": dl,
                     "luma": sum(vals) / len(vals),
                     "p10": _pct(cvals, 0.10), "p25": _pct(cvals, 0.25),
                     "p50": _pct(cvals, 0.50), "p95": _pct(cvals, 0.95),
                     "cells": cvals, "hist": hist})
        prev = rows[-1]
    return rows


def _cuts(rows):
    cuts = []
    for i, row in enumerate(rows[1:], 1):
        if row["hd"] > 0.28 or (row["hd"] > 0.16 and row["dl"] > 0.09):
            cuts.append(i)
    merged = []
    for c in cuts:
        if not merged or rows[c]["t"] - rows[merged[-1]]["t"] > 0.4:
            merged.append(c)
    return merged


def _baseline_plan(project, fps: float, base_shadow: float, base_white: float, write: bool = True) -> dict:
    folder = project.path / "analysis"
    rows = _frames(folder)
    if not rows:
        raise RuntimeError("Analisi tone mapping: nessun frame.")
    cuts = _cuts(rows)
    bounds = [0] + cuts + [len(rows)]
    segments = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a < 8 and segments:
            segments[-1][1] = b
        else:
            segments.append([a, b])
    all_cells = [v for r in rows for v in r["cells"]]
    ref10, ref95 = _pct(all_cells, 0.10), _pct(all_cells, 0.95)

    def value_for(a, b):
        cells = [v for r in rows[a:b] for v in r["cells"]]
        p10, p95 = _pct(cells, 0.10), _pct(cells, 0.95)
        cand_sh = max(0.12, min(0.55, p10 - 0.10))
        cand_wh = max(0.85, min(0.98, p95 + 0.10))
        sh = max(0.12, min(0.60, 0.6 * base_shadow + 0.4 * cand_sh))
        wh = max(0.85, min(0.98, 0.6 * base_white + 0.4 * cand_wh))
        if wh - sh < 0.25:
            wh = min(0.98, sh + 0.25)
        return round(sh, 4), round(wh, 4), round(p10, 4), round(p95, 4)

    intervals = []
    for a, b in segments:
        start = rows[a]["t"]
        end = rows[b - 1]["t"] + 0.1
        sh, wh, p10, p95 = value_for(a, b)
        intervals.append({"start": start, "end": end, "shadow": sh, "white": wh,
                          "p10": p10, "p95": p95, "cut": a in cuts})
    total = max(1, int(round(project.working_info["duration"] * 30)))
    keys = [{"frame": 1, "shadow": intervals[0]["shadow"], "white": intervals[0]["white"]}]
    for i, cur in enumerate(intervals[1:], 1):
        b = max(1, min(total, int(round(cur["start"] * 30)) + 1))
        prev = intervals[i - 1]
        ramp = 2 if cur["cut"] else 10
        if b - 1 > keys[-1]["frame"]:
            keys.append({"frame": b - 1, "shadow": prev["shadow"], "white": prev["white"]})
        keys.append({"frame": min(total, b + ramp - 1), "shadow": cur["shadow"], "white": cur["white"]})
    if keys[-1]["frame"] < total:
        keys.append({"frame": total, "shadow": intervals[-1]["shadow"], "white": intervals[-1]["white"]})
    ded = {k["frame"]: k for k in keys}
    keys = [ded[f] for f in sorted(ded)]

    scale = fps / 30.0
    plan = {
        "source_fps": round(fps, 6),
        "render_fps": 30,
        "frame_scale": round(scale, 6),
        "frame_offset": round(1.0 - scale, 6),
        "duration": project.working_info["duration"],
        "total_frames": total,
        "reference": {"p10": round(ref10, 4), "p95": round(ref95, 4),
                      "base_shadow": base_shadow, "base_white": base_white},
        "cuts": [round(rows[c]["t"], 3) for c in cuts],
        "intervals": intervals,
        "keyframes": keys,
        "note": "Generic adaptive plan: per-shot stats blended 60/40 with the preset base; no Nier overrides.",
    }
    if write:
        path = project.path / "temp" / "plan.json"
        path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        project.plan_path = str(path)
        project.save()
    return plan


def build_plan(project, fps: float, base_shadow: float, base_white: float,
               auto: bool = False, overrides=None) -> dict:
    if auto:
        from gcf.ascii.correction import build_auto_plan
        base = _baseline_plan(project, fps, base_shadow, base_white, write=False)
        return build_auto_plan(project, fps, base, overrides)
    return _baseline_plan(project, fps, base_shadow, base_white)
