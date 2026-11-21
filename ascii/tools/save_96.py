import bpy

sc = bpy.context.scene
ng = bpy.data.node_groups["Geometry Nodes.001"]
grid = ng.nodes["ASCII Grid"]
curves = ng.nodes["String to Curves"]
grid.inputs["Vertices X"].default_value = 96
grid.inputs["Vertices Y"].default_value = 54
curves.inputs["Size"].default_value = 0.0166
du, dv = 1.0 / (96 * 4), 1.0 / (54 * 4)
for name, vec in {"Cell Sample A Offset": (-du, -dv, 0.0), "Cell Sample B Offset": (du, -dv, 0.0),
                  "Cell Sample C Offset": (-du, dv, 0.0), "Cell Sample D Offset": (du, dv, 0.0)}.items():
    ng.nodes[name].inputs[1].default_value = vec
sc.frame_start = 1440
sc.frame_end = 2039
sc.frame_set(1800)
sc.render.filepath = r"G:\VDGP\ascii\render\ascii_96_"
bpy.ops.wm.save_as_mainfile(filepath=r"G:\VDGP\ascii\presets\ASCII_Cinematic_Balanced_96x54_TEST.blend")
print("SAVED 96")
