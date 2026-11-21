"""Per-shot adaptive tone mapping for the ASCII renderer.

Reads a JSON config, analyses an extracted frame sequence at 10 fps,
detects cuts and sustained luminance segments, computes p10/p95 per shot,
derives Shadow Threshold / White Point around the B reference, applies
manual overrides, and emits a keyframe plan for the Geometry Nodes modifier.

This tool does not render. It writes a JSON plan that apply_adaptive_tonemap.py
turns into modifier-input keyframes.
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image

COLS, ROWS = 80, 45


def pct(vals, p):
    s = sorted(vals)
    return s[min(len(s) - 1, int(p * len(s)))]


def analyze_frames(frames_dir, start_time, fps):
    frames = []
    prev = None
    for path in sorted(Path(frames_dir).glob("f_*.png")):
        idx = int(path.stem.split("_")[1])
        t = start_time + (idx - 1) / fps
        im = Image.open(path).convert("L")
        small = im.resize((160, 90), Image.Resampling.BOX)
        sp = small.load()
        vals = [sp[x, y] / 255.0 for y in range(90) for x in range(160)]
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
        frames.append({
            "t": t, "hd": hd, "dl": dl, "luma": sum(vals) / len(vals),
            "p10": pct(cvals, 0.10), "p25": pct(cvals, 0.25),
            "p50": pct(cvals, 0.50), "p95": pct(cvals, 0.95), "cells": cvals,
            "hist": hist,
        })
        prev = frames[-1]
    return frames


def detect_cuts(frames):
    cuts = []
    for i, fr in enumerate(frames[1:], 1):
        if fr["hd"] > 0.28 or (fr["hd"] > 0.16 and fr["dl"] > 0.09):
            cuts.append(i)
    # merge cuts closer than 0.4 s
    merged = []
    for c in cuts:
        if not merged or (frames[c]["t"] - frames[merged[-1]]["t"]) > 0.4:
            merged.append(c)
    return merged


def stable_at(frames, i, level, n=5, tol=0.05):
    return i + n <= len(frames) and all(abs(frames[j]["p50"] - level) < tol for j in range(i, i + n))


def segment(frames, cuts):
    bounds = [0] + cuts + [len(frames)]
    base = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a < 10 and base:
            base[-1][1] = b
        else:
            base.append([a, b])
    out = []
    for a, b in base:
        start = a
        while b - start > 12:
            level = pct([frames[j]["p50"] for j in range(start, min(start + 4, b))], 0.5)
            found = None
            for j in range(start + 10, b - 5):
                if abs(frames[j]["p50"] - level) > 0.09 and stable_at(frames, j, frames[j]["p50"]):
                    found = j
                    break
            if not found:
                break
            out.append([start, found])
            start = found
        out.append([start, b])
    # merge short segments
    merged = []
    for a, b in out:
        if merged and (b - a) < 12:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return merged


def stats_for(frames, a, b):
    cells = [v for fr in frames[a:b] for v in fr["cells"]]
    return {k: pct(cells, p) for k, p in (("p5", 0.05), ("p10", 0.10), ("p25", 0.25), ("p50", 0.50), ("p95", 0.95))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    frames = analyze_frames(cfg["frames_dir"], cfg["start"], cfg["analysis_fps"])
    cuts = detect_cuts(frames)
    segs = segment(frames, cuts)
    ref = cfg["reference"]
    ref_rows = [fr for fr in frames if ref["start"] <= fr["t"] < ref["end"]]
    ref_stats = stats_for(frames, frames.index(ref_rows[0]), frames.index(ref_rows[-1]) + 1)
    base_sh, base_wh = ref["shadow"], ref["white"]
    limit = cfg["limit"]
    flat = cfg["flat_bright"]

    segments = []
    for a, b in segs:
        st = stats_for(frames, a, b)
        auto_sh = max(base_sh - limit, min(base_sh + limit, base_sh + (st["p10"] - ref_stats["p10"])))
        auto_wh = max(base_wh - limit, min(base_wh, base_wh + (st["p95"] - ref_stats["p95"])))
        is_flat = st["p10"] > flat["p10_min"] and (st["p95"] - st["p10"]) < flat["range_max"]
        if is_flat:
            auto_sh = max(auto_sh, st["p25"] + flat["shadow_offset"])
            auto_wh = min(0.97, max(auto_wh, st["p95"] + flat["white_offset"]))
        segments.append({
            "start": frames[a]["t"], "end": frames[b - 1]["t"] + 1 / cfg["analysis_fps"],
            "p5": st["p5"], "p10": st["p10"], "p25": st["p25"], "p50": st["p50"], "p95": st["p95"],
            "shadow": auto_sh, "white": auto_wh,
            "flat_bright": is_flat, "source": "auto",
        })

    # split timeline at override and pin boundaries
    pin = cfg.get("pin", {"start": ref["start"], "end": ref["end"], "shadow": base_sh, "white": base_wh})
    overrides = cfg.get("overrides", [])
    points = set()
    for s in segments:
        points.add(round(s["start"], 3)); points.add(round(s["end"], 3))
    for o in [pin] + overrides:
        points.add(round(o["start"], 3)); points.add(round(o["end"], 3))
    points = sorted(points)

    intervals = []
    for a, b in zip(points, points[1:]):
        if b - a < 0.001:
            continue
        mid = (a + b) / 2
        parent = next(s for s in segments if s["start"] - 1e-6 <= mid < s["end"] + 1e-6)
        vals = {k: parent[k] for k in ("p5", "p10", "p25", "p50", "p95", "shadow", "white", "flat_bright")}
        vals["source"] = "auto"
        if pin["start"] - 1e-6 <= a and b <= pin["end"] + 1e-6:
            vals["shadow"] = pin["shadow"]; vals["white"] = pin["white"]; vals["source"] = "reference pin"
        else:
            for o in overrides:
                if o["start"] - 1e-6 <= a and b <= o["end"] + 1e-6:
                    vals["shadow"] = o["shadow"]; vals["white"] = o["white"]
                    vals["source"] = "override: " + o.get("reason", "")
                    break
        intervals.append({"start": a, "end": b, **vals})

    # keyframes: 2-frame cut ramps, 10-frame soft ramps
    rfps = cfg["render_fps"]
    def fr(t): return int(round(t * rfps))
    cut_times = [frames[c]["t"] for c in cuts]
    keys = [{"frame": fr(intervals[0]["start"]), "shadow": intervals[0]["shadow"],
             "white": intervals[0]["white"], "segment": 0}]
    for i in range(1, len(intervals)):
        prev, cur = intervals[i - 1], intervals[i]
        b = fr(cur["start"])
        is_cut = any(abs(cur["start"] - ct) < 0.15 for ct in cut_times)
        ramp = cfg["transitions"]["cut"] if is_cut else cfg["transitions"]["soft"]
        if b - 1 > keys[-1]["frame"]:
            keys.append({"frame": b - 1, "shadow": prev["shadow"], "white": prev["white"], "segment": i - 1})
        keys.append({"frame": b + ramp - 1, "shadow": cur["shadow"], "white": cur["white"], "segment": i})
    last = intervals[-1]
    endf = fr(last["end"]) - 1
    if endf > keys[-1]["frame"]:
        keys.append({"frame": endf, "shadow": last["shadow"], "white": last["white"], "segment": len(intervals) - 1})
    # dedupe last wins
    ded = {}
    for k in keys:
        ded[k["frame"]] = k
    keys = [ded[f] for f in sorted(ded)]

    scale = cfg["source_fps"] / cfg["render_fps"]
    plan = {
        "source": cfg["source"], "start": cfg["start"], "end": cfg["end"],
        "source_fps": cfg["source_fps"], "render_fps": cfg["render_fps"],
        "frame_scale": round(scale, 6), "frame_offset": round(1 - scale, 6),
        "reference": {"start": ref["start"], "end": ref["end"], "shadow": base_sh, "white": base_wh,
                      "p10": ref_stats["p10"], "p95": ref_stats["p95"]},
        "cuts": [round(t, 3) for t in cut_times],
        "intervals": intervals, "keyframes": keys,
        "overrides": overrides,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(plan, indent=2), encoding="utf-8")

    print("cuts:", [round(t, 2) for t in cut_times])
    print(f"reference p10 {ref_stats['p10']:.3f} p95 {ref_stats['p95']:.3f}")
    print("segment                         p10   p25   p95   shadow  white  source")
    for iv in intervals:
        print(f"{iv['start']:5.2f}-{iv['end']:5.2f}  {iv['p10']:.3f} {iv['p25']:.3f} {iv['p95']:.3f}   "
              f"{iv['shadow']:.3f}  {iv['white']:.3f}  {iv['source']}")
    print("keyframes:", [(k["frame"], round(k["shadow"], 3), round(k["white"], 3)) for k in keys])


if __name__ == "__main__":
    main()
