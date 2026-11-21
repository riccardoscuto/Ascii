"""Apply an adaptive tone-mapping plan to the ASCII preset.

Usage:
  blender -b --factory-startup stage.blend --python apply_adaptive_tonemap.py -- \
      plan.json out.blend

Creates keyframes on the Geometry Nodes modifier inputs Shadow Threshold and
White Point, sets the source frame scale/offset, and verifies evaluation.
"""
import json
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
plan_path, out_path = argv[0], argv[1]
plan = json.loads(open(plan_path, encoding="utf-8").read())

scene = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = obj.modifiers["GeometryNodes"]
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}
ins = mod.properties.inputs


def setv(name, value):
    getattr(ins, ids[name]).value = value


# start clean: remove the test action
if obj.animation_data:
    obj.animation_data_clear()

setv("Source Frame Scale", plan["frame_scale"])
if "Source Frame Offset" in ids:
    setv("Source Frame Offset", plan["frame_offset"])
    offset_source = "modifier socket"
else:
    add = ng.nodes.get("Source Frame Add")
    if add is None:
        raise RuntimeError("Source Frame Add node missing")
    for link in list(add.inputs[1].links):
        ng.links.remove(link)
    add.inputs[1].default_value = plan["frame_offset"]
    offset_source = "constant node fallback"

# keyframe interpolation
try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
except Exception:
    pass

s4 = getattr(ins, ids["Shadow Threshold"])
s5 = getattr(ins, ids["White Point"])
for k in plan["keyframes"]:
    s4.value = k["shadow"]
    s5.value = k["white"]
    s4.keyframe_insert(data_path="value", frame=k["frame"])
    s5.keyframe_insert(data_path="value", frame=k["frame"])

ad = obj.animation_data
action = ad.action
slot = ad.action_slot
layer = action.layers[0]
strip = layer.strips[0]
channelbag = strip.channelbag(slot)
for fc in channelbag.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"

# scene range for the 20 s test
rfps = plan["render_fps"]
start_f = int(round(plan["start"] * rfps))
end_f = int(round(plan["end"] * rfps)) - 1
scene.frame_start = start_f
scene.frame_end = end_f
scene.frame_set(start_f)
scene.render.filepath = r"G:\VDGP\ascii\render\ascii_adaptive_"

# verify keyframe evaluation against the plan (linear interpolation)
def expected_at(frame):
    keys = plan["keyframes"]
    if frame <= keys[0]["frame"]:
        return keys[0]["shadow"], keys[0]["white"]
    if frame >= keys[-1]["frame"]:
        return keys[-1]["shadow"], keys[-1]["white"]
    for a, b in zip(keys, keys[1:]):
        if a["frame"] <= frame <= b["frame"]:
            f = (frame - a["frame"]) / max(1, b["frame"] - a["frame"])
            return a["shadow"] + (b["shadow"] - a["shadow"]) * f, a["white"] + (b["white"] - a["white"]) * f
    return keys[-1]["shadow"], keys[-1]["white"]


checks = []
check_frames = sorted({k["frame"] for k in plan["keyframes"]} | {1560, 1755, 1800, 1830, 1965, 2010, 2025})
for f in check_frames:
    scene.frame_set(f)
    got_sh = ins.Socket_4.value
    got_wh = ins.Socket_5.value
    exp_sh, exp_wh = expected_at(f)
    checks.append({"frame": f, "shadow": round(got_sh, 4), "white": round(got_wh, 4),
                   "expected_shadow": round(exp_sh, 4), "expected_white": round(exp_wh, 4)})
    if abs(got_sh - exp_sh) > 0.002 or abs(got_wh - exp_wh) > 0.002:
        raise RuntimeError(f"keyframe mismatch at {f}: {got_sh}/{got_wh} expected {exp_sh}/{exp_wh}")

# fps/frame mapping self-check: no cumulative drift
fps_checks = []
for src_fps in (30.0, 59.94, 60.0):
    scale = src_fps / rfps
    offset = 1.0 - scale
    for f in (1, 1440, 9000):
        src = f * scale + offset
        expected = 1.0 + (f - 1) * src_fps / rfps
        if abs(src - expected) > 1e-6:
            raise RuntimeError(f"frame mapping drift: {src_fps} {f} {src} {expected}")
    fps_checks.append({"source_fps": src_fps, "scale": round(scale, 6), "offset": round(offset, 6)})

fcurves = [(fc.data_path, fc.array_index, len(fc.keyframe_points)) for fc in channelbag.fcurves]
bpy.ops.wm.save_as_mainfile(filepath=out_path)

print(json.dumps({
    "saved": out_path,
    "offset_source": offset_source,
    "fcurves": fcurves,
    "evaluation": checks,
    "fps_checks": fps_checks,
    "range": [start_f, end_f],
}, indent=2))
