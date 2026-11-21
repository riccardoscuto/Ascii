import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
ins = mod.properties.inputs
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}
getattr(ins, ids["Grid X"]).value = 96
getattr(ins, ids["Grid Y"]).value = 54
getattr(ins, ids["Glyph Size"]).value = 0.0166
du, dv = 1.0 / (96 * 4), 1.0 / (54 * 4)
for name, vec in {"Cell Sample A Offset": (-du, -dv, 0.0), "Cell Sample B Offset": (du, -dv, 0.0),
                  "Cell Sample C Offset": (-du, dv, 0.0), "Cell Sample D Offset": (du, dv, 0.0)}.items():
    ng.nodes[name].inputs[1].default_value = vec
sc.frame_start = 1440
sc.frame_end = 2039
sc.frame_set(1800)
sc.render.filepath = r"G:\VDGP\ascii\render\ascii_96_"
bpy.ops.wm.save_as_mainfile(filepath=r"G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_v2_96x54.blend")
print("FIXED V2", getattr(ins, ids["Grid X"]).value, getattr(ins, ids["Grid Y"]).value, getattr(ins, ids["Glyph Size"]).value)
