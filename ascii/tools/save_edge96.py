import bpy

ng = bpy.data.node_groups["Geometry Nodes.001"]
obj = bpy.data.objects["video"]
mod = next(m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng)
ins = mod.properties.inputs
ids = {i.name: i.identifier for i in ng.interface.items_tree
       if getattr(i, "in_out", None) == "INPUT" and i.item_type == "SOCKET"}
getattr(ins, ids["Grid X"]).value = 96
getattr(ins, ids["Grid Y"]).value = 54
getattr(ins, ids["Glyph Size"]).value = 0.0166
getattr(ins, ids["Edge Strength"]).value = 0.8
du, dv = 1.0 / (96 * 4), 1.0 / (54 * 4)
for name, vec in {"Cell Sample A Offset": (-du, -dv, 0.0), "Cell Sample B Offset": (du, -dv, 0.0),
                  "Cell Sample C Offset": (-du, dv, 0.0), "Cell Sample D Offset": (du, dv, 0.0)}.items():
    ng.nodes[name].inputs[1].default_value = vec
bpy.ops.wm.save_as_mainfile(filepath=r"G:\VDGP\ascii\experiments\edge_map_work_96.blend")
print("SAVED EDGE 96")
