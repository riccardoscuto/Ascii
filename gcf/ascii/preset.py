from __future__ import annotations

import json
from pathlib import Path

from gcf.config import ROOT

PRESET_NAME = "ASCII_Cinematic_Balanced_v2_96x54"
PRESET_JSON = ROOT / "ascii" / "presets" / f"{PRESET_NAME}.json"
PRESET_BLEND = ROOT / "ascii" / "presets" / f"{PRESET_NAME}.blend"

# The v2 grid plane: 16:9 horizontal, swapped for 9:16 vertical.
PLANE_X = 1.775625467300415
PLANE_Y = 0.9996469020843506


def load_preset() -> dict:
    return json.loads(PRESET_JSON.read_text(encoding="utf-8"))


def grid_for(format_: str, density: int) -> dict:
    density = max(32, min(160, int(density)))
    if format_ == "vertical":
        cols = density
        rows = round(density * 16 / 9)
        plane_x, plane_y = PLANE_Y, PLANE_X
        glyph = plane_x / cols * 0.9
        resolution = (1080, 1920)
    else:
        cols = round(density * 16 / 9)
        rows = density
        plane_x, plane_y = PLANE_X, PLANE_Y
        glyph = plane_y / rows * 0.9
        resolution = (1920, 1080)
    return {
        "cols": int(cols),
        "rows": int(rows),
        "plane_x": plane_x,
        "plane_y": plane_y,
        "glyph": round(glyph, 5),
        "resolution": resolution,
    }


def resolve(project) -> dict:
    preset = load_preset()
    params = {**preset["sockets"]}
    # preset sockets are {Socket_N: {name, value}}
    by_name = {row["name"]: row["value"] for row in params.values()}
    grid = grid_for(project.format, project.params.get("density", 54))
    user = project.params
    by_name["Grid X"] = grid["cols"]
    by_name["Grid Y"] = grid["rows"]
    by_name["Glyph Size"] = grid["glyph"]
    by_name["Gamma"] = float(user.get("gamma", by_name["Gamma"]))
    by_name["Shadow Threshold"] = float(user.get("shadow", by_name["Shadow Threshold"]))
    by_name["Contrast Low"] = float(user.get("contrast_low", by_name["Contrast Low"]))
    by_name["Contrast High"] = float(user.get("contrast_high", by_name["Contrast High"]))
    by_name["Local Contrast"] = float(user.get("local_contrast", by_name["Local Contrast"]))
    by_name["Color Mode"] = float(user.get("color_mode", by_name["Color Mode"]))
    by_name["Character Ramp"] = by_name.get("Character Ramp", " .,:;+HW@")
    by_name["White Point"] = float(by_name.get("White Point", 0.95))
    by_name["Palette Mix"] = 0.0
    return {
        "name": PRESET_NAME,
        "preset_blend": str(PRESET_BLEND),
        "format": project.format,
        "grid": grid,
        "resolution": grid["resolution"],
        "plane": [grid["plane_x"], grid["plane_y"]],
        "ramp": by_name["Character Ramp"],
        "gamma": by_name["Gamma"],
        "shadow": by_name["Shadow Threshold"],
        "white": by_name["White Point"],
        "contrast_low": by_name["Contrast Low"],
        "contrast_high": by_name["Contrast High"],
        "local_contrast": by_name["Local Contrast"],
        "color_mode": by_name["Color Mode"],
        "density": grid["cols"] if project.format == "vertical" else grid["rows"],
        "sockets": by_name,
    }


def expected(project, plan: dict | None = None) -> dict:
    data = resolve(project)
    return {
        "grid_x": data["grid"]["cols"],
        "grid_y": data["grid"]["rows"],
        "glyph_size": data["grid"]["glyph"],
        "resolution": list(data["resolution"]),
        "character_ramp": data["ramp"],
        "gamma": data["gamma"],
        "contrast_low": data["contrast_low"],
        "contrast_high": data["contrast_high"],
        "local_contrast": data["local_contrast"],
        "color_mode": data["color_mode"],
        "shadow": data["shadow"],
        "white": data["white"],
        "source_frame_scale": round((project.working_info.get("fps", 30.0) / 30.0), 6) if project.working_info else None,
        "source_frame_offset": round((1.0 - project.working_info.get("fps", 30.0) / 30.0), 6) if project.working_info else None,
        "frames": int(round(project.working_info.get("duration", 0.0) * 30.0)) if project.working_info else None,
    }
