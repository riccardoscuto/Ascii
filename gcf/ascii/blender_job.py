from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import bpy


def expected_at(keys, frame, field):
    if not keys or field not in keys[0]:
        return None
    if frame <= keys[0]["frame"]:
        return keys[0][field]
    if frame >= keys[-1]["frame"]:
        return keys[-1][field]
    for a, b in zip(keys, keys[1:]):
        if a["frame"] <= frame <= b["frame"]:
            t = (frame - a["frame"]) / max(1, b["frame"] - a["frame"])
            return a[field] + (b[field] - a[field]) * t
    return keys[-1][field]


def main():
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    scene = bpy.context.scene
    ng = bpy.data.node_groups["Geometry Nodes.001"]
    obj = bpy.data.objects["video"]
    mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
    ins = mod.properties.inputs
    ids = {i.name: i.identifier for i in ng.interface.items_tree
           if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}

    # Source video replaces every image texture in the preset.
    source = Path(job["source"])
    if not source.exists():
        raise FileNotFoundError(str(source))
    image = bpy.data.images.load(str(source), check_existing=False)
    try:
        image.source = "MOVIE"
    except Exception:
        pass
    for node in ng.nodes:
        if node.bl_idname == "GeometryNodeImageTexture":
            node.inputs[0].default_value = image

    # Clear the Nier keyframes/plan before applying the new one.
    if obj.animation_data:
        obj.animation_data_clear()

    params = job["params"]
    for name, value in params.items():
        if name in ids:
            getattr(ins, ids[name]).value = value
    getattr(ins, ids["Source Frame Scale"]).value = job["source_frame_scale"]
    getattr(ins, ids["Source Frame Offset"]).value = job["source_frame_offset"]

    grid = ng.nodes["ASCII Grid"]
    grid.inputs["Size X"].default_value = job["plane"][0]
    grid.inputs["Size Y"].default_value = job["plane"][1]
    grid.inputs["Vertices X"].default_value = params["Grid X"]
    grid.inputs["Vertices Y"].default_value = params["Grid Y"]
    uv_scale = ng.nodes.get("UV Scale")
    uv_offset = ng.nodes.get("UV Offset")
    if uv_scale is not None:
        uv_scale.inputs[1].default_value = (1.0 / job["plane"][0], 1.0 / job["plane"][1], 0.0)
    if uv_offset is not None:
        uv_offset.inputs[1].default_value = (0.5, 0.5, 0.0)
    du, dv = 1.0 / (params["Grid X"] * 4), 1.0 / (params["Grid Y"] * 4)
    for name, vec in {"Cell Sample A Offset": (-du, -dv, 0.0), "Cell Sample B Offset": (du, -dv, 0.0),
                      "Cell Sample C Offset": (-du, dv, 0.0), "Cell Sample D Offset": (du, dv, 0.0)}.items():
        ng.nodes[name].inputs[1].default_value = vec

    ascii_mode = job.get("ascii_mode", "legacy")
    spatial_info = job.get("spatial") or {}
    index_first = None
    index_count = 0
    if ascii_mode == "spatial":
        index_dir = Path(spatial_info["index_dir"])
        index_files = sorted(index_dir.glob("i_*.png"))
        required = int(job.get("index_required", job["total_frames"]))
        if len(index_files) < required:
            raise RuntimeError(f"Index sequence incomplete: {len(index_files)}/{required}")
        index_first = index_files[0]
        index_img = bpy.data.images.load(str(index_first), check_existing=False)
        index_img.source = "SEQUENCE"
        try:
            index_img.frame_duration = len(index_files)
        except Exception:
            pass
        index_img.colorspace_settings.name = "Non-Color"
        index_count = len(index_files)
        index_node = ng.nodes.new("GeometryNodeImageTexture")
        index_node.name = "Index Map"
        index_node.inputs[0].default_value = index_img
        index_node.interpolation = "Closest"
        index_node.extension = "CLIP"
        ng.links.new(ng.nodes["UV Offset"].outputs["Vector"], index_node.inputs[1])
        index_node.inputs[2].default_value = 1
        if job.get("link_index_time", True):
            ng.links.new(ng.nodes["Scene Time"].outputs["Frame"], index_node.inputs[2])
        dot_index = ng.nodes.new("ShaderNodeVectorMath")
        dot_index.name = "Index Red"
        dot_index.operation = "DOT_PRODUCT"
        dot_index.inputs[1].default_value = (1.0, 0.0, 0.0)
        ng.links.new(index_node.outputs["Color"], dot_index.inputs[0])
        mr = ng.nodes["Map Range.001"]
        for link in list(mr.inputs[0].links):
            ng.links.remove(link)
        ng.links.new(dot_index.outputs["Value"], mr.inputs[0])

    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 8
    scene.render.resolution_x = job["resolution"][0]
    scene.render.resolution_y = job["resolution"][1]
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.use_file_extension = True
    scene.render.use_overwrite = True

    keys = job["plan"].get("keyframes", [])
    if not keys:
        raise RuntimeError("Piano adattivo senza keyframe.")
    field_sockets = {
        "shadow": ("Shadow Threshold", getattr(ins, ids["Shadow Threshold"])),
        "white": ("White Point", getattr(ins, ids["White Point"])),
        "gamma": ("Gamma", getattr(ins, ids["Gamma"])),
        "contrast_low": ("Contrast Low", getattr(ins, ids["Contrast Low"])),
        "contrast_high": ("Contrast High", getattr(ins, ids["Contrast High"])),
        "local_contrast": ("Local Contrast", getattr(ins, ids["Local Contrast"])),
    }
    keyed = [field for field in field_sockets if field in keys[0]]
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    except Exception:
        pass
    for key in keys:
        for field in keyed:
            socket = field_sockets[field][1]
            socket.value = float(key[field])
            socket.keyframe_insert(data_path="value", frame=int(key["frame"]))
    ad = obj.animation_data
    if ad and ad.action:
        act = ad.action
        bag = act.layers[0].strips[0].channelbag(ad.action_slot)
        for fc in bag.fcurves:
            for point in fc.keyframe_points:
                point.interpolation = "LINEAR"

    total = int(job["total_frames"])
    scene.frame_start = 1
    scene.frame_end = total
    checks = {}
    for f in (1, max(1, total // 2), total):
        scene.frame_set(f)
        row = {field: round(field_sockets[field][1].value, 4) for field in keyed}
        row["expected"] = {field: round(expected_at(keys, f, field), 4) for field in keyed}
        checks[str(f)] = row
    for f, row in checks.items():
        for field in keyed:
            if abs(row[field] - row["expected"][field]) > 0.002:
                raise RuntimeError(f"Keyframe mismatch at {f} {field}: {row}")

    actual = {
        "grid_x": getattr(ins, ids["Grid X"]).value,
        "grid_y": getattr(ins, ids["Grid Y"]).value,
        "glyph_size": round(getattr(ins, ids["Glyph Size"]).value, 5),
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "character_ramp": getattr(ins, ids["Character Ramp"]).value,
        "gamma": round(getattr(ins, ids["Gamma"]).value, 4),
        "shadow": round(getattr(ins, ids["Shadow Threshold"]).value, 4),
        "white": round(getattr(ins, ids["White Point"]).value, 4),
        "contrast_low": round(getattr(ins, ids["Contrast Low"]).value, 4),
        "contrast_high": round(getattr(ins, ids["Contrast High"]).value, 4),
        "local_contrast": round(getattr(ins, ids["Local Contrast"]).value, 4),
        "color_mode": round(getattr(ins, ids["Color Mode"]).value, 4),
        "source_frame_scale": round(getattr(ins, ids["Source Frame Scale"]).value, 6),
        "source_frame_offset": round(getattr(ins, ids["Source Frame Offset"]).value, 6),
        "source": str(source),
        "image_datablock": image.name,
        "frame_range": ([int(job.get("start_frame", 1)), int(job.get("end_frame", total))]
                        if job["mode"] == "segment" else [1, total]),
        "keyframes": keys,
        "checks": checks,
        "scene_fps": scene.render.fps,
        "mode": job["mode"],
        "ascii_mode": ascii_mode,
        "spatial_variant": job.get("spatial_variant", ""),
        "renderer_version": job.get("renderer_version", ""),
        "map_key": spatial_info.get("map_key", ""),
        "index": str(index_first) if index_first else "",
        "index_first": index_first.name if index_first else "",
        "index_count": index_count,
        "index_colorspace": "Non-Color" if index_first else "",
        "index_required": int(job.get("index_required", total)),
    }
    verification = Path(job["verification"])
    verification.parent.mkdir(parents=True, exist_ok=True)
    verification.write_text(json.dumps(actual, indent=2), encoding="utf-8")
    expected = job["expected"]
    mismatches = []
    numeric = {"grid_x", "grid_y", "glyph_size", "gamma", "contrast_high", "color_mode",
               "source_frame_scale", "source_frame_offset"}
    for key in ("grid_x", "grid_y", "glyph_size", "resolution", "character_ramp",
                "gamma", "contrast_low", "contrast_high", "local_contrast", "color_mode", "source_frame_scale", "source_frame_offset"):
        if key in keyed:
            continue
        if key not in expected:
            continue
        if key == "resolution":
            if list(actual[key]) != list(expected[key]):
                mismatches.append(f"{key}: {actual[key]} != {expected[key]}")
        elif key in numeric:
            try:
                if abs(float(actual[key]) - float(expected[key])) > 0.0002:
                    mismatches.append(f"{key}: {actual[key]} != {expected[key]}")
            except Exception:
                mismatches.append(f"{key}: {actual[key]} != {expected[key]}")
        elif actual[key] != expected[key]:
            mismatches.append(f"{key}: {actual[key]} != {expected[key]}")
    if mismatches:
        raise RuntimeError("Verifica preset fallita: " + "; ".join(mismatches))

    if job["mode"] == "still":
        scene.frame_set(int(job["still_frame"]))
        scene.render.filepath = str(job["still_path"])
        bpy.ops.render.render(write_still=True)
    else:
        if job["mode"] == "preview":
            start, end = 1, int(job["preview_frames"])
        elif job["mode"] == "segment":
            start = int(job.get("start_frame", 1))
            end = int(job.get("end_frame", total))
        else:
            start = int(job.get("start_frame", 1))
            end = total
        scene.frame_start = start
        scene.frame_end = end
        out = Path(job["frames_dir"])
        out.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(out / "f_")
        bpy.ops.render.render(animation=True)
    print("ASCII_JOB_OK", job["mode"], verification)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
