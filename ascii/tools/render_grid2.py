import bpy, os, time

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
ins = mod.properties.inputs
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}
if obj.animation_data:
    obj.animation_data.action = None
getattr(ins, ids["Shadow Threshold"]).value = 0.58
getattr(ins, ids["White Point"]).value = 0.95
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = 8
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.resolution_percentage = 100
sc.frame_set(1800)
sc.render.image_settings.media_type = "IMAGE"
sc.render.image_settings.file_format = "PNG"
outdir = r"G:\VDGP\ascii\experiments\gridgeom2"
os.makedirs(outdir, exist_ok=True)


def shot(tag, cols, rows, size):
    getattr(ins, ids["Grid X"]).value = cols
    getattr(ins, ids["Grid Y"]).value = rows
    getattr(ins, ids["Glyph Size"]).value = size
    du, dv = 1.0 / (cols * 4), 1.0 / (rows * 4)
    for name, vec in {"Cell Sample A Offset": (-du, -dv, 0.0), "Cell Sample B Offset": (du, -dv, 0.0),
                      "Cell Sample C Offset": (-du, dv, 0.0), "Cell Sample D Offset": (du, dv, 0.0)}.items():
        ng.nodes[name].inputs[1].default_value = vec
    sc.render.filepath = rf"{outdir}\{tag}.png"
    bpy.ops.render.render(write_still=True)
    print("WROTE", tag)


for tag, c, r, s in (("80_020", 80, 45, 0.020), ("80_017", 80, 45, 0.017), ("80_015", 80, 45, 0.015),
                     ("96_0166", 96, 54, 0.0166), ("96_0155", 96, 54, 0.0155),
                     ("120_0133", 120, 68, 0.0133), ("120_0125", 120, 68, 0.0125)):
    shot(tag, c, r, s)
print("DONE GRID")
